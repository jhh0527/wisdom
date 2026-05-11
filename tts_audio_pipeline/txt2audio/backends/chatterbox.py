"""Resemble AI Chatterbox — 로컬(chatterbox-tts) 또는 사용자 HTTP 서버."""

from __future__ import annotations

import asyncio
import base64
import json
import os
import uuid

# 기업망 SSL 프록시: HF·GitHub·기타 HTTPS 다운로드 실패 방지 (미설정 시 TLS 검증 완화).
# 엄격 검증이 필요하면 실행 전: set CHATTERBOX_HF_INSECURE_SSL=0
if "CHATTERBOX_HF_INSECURE_SSL" not in os.environ:
    os.environ["CHATTERBOX_HF_INSECURE_SSL"] = "1"
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from txt2audio.audio_merge import try_concat_with_ffmpeg
from txt2audio.backends.base import SynthesisBackend
from txt2audio.chunking import split_for_tts


def _insecure_ssl_enabled() -> bool:
    flag = os.environ.get("CHATTERBOX_HF_INSECURE_SSL", "1").strip().lower()
    if flag in ("0", "false", "no", "off"):
        return False
    return flag in ("1", "true", "yes", "")


def _apply_python_ssl_unverified_defaults() -> None:
    """requests/urllib3/httplib(githubusercontent 등)가 공용 SSL 컨텍스트를 쓸 때 검증 완화."""
    if not _insecure_ssl_enabled():
        return
    import ssl

    ssl._create_default_https_context = ssl._create_unverified_context  # type: ignore[attr-defined]
    try:
        import urllib3

        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    except ImportError:
        pass


def _apply_hf_insecure_ssl_if_requested() -> None:
    """CHATTERBOX_HF_INSECURE_SSL 켜짐일 때 HF Hub용 httpx에 verify=False 적용."""
    if not _insecure_ssl_enabled():
        return
    import httpx
    from huggingface_hub.utils._http import (
        async_hf_request_event_hook,
        async_hf_response_event_hook,
        hf_request_event_hook,
        set_async_client_factory,
        set_client_factory,
    )

    def _sync_factory() -> httpx.Client:
        return httpx.Client(
            event_hooks={"request": [hf_request_event_hook]},
            follow_redirects=True,
            timeout=None,
            verify=False,
        )

    def _async_factory() -> httpx.AsyncClient:
        return httpx.AsyncClient(
            event_hooks={
                "request": [async_hf_request_event_hook],
                "response": [async_hf_response_event_hook],
            },
            follow_redirects=True,
            timeout=None,
            verify=False,
        )

    set_client_factory(_sync_factory)
    set_async_client_factory(_async_factory)


_apply_python_ssl_unverified_defaults()
_apply_hf_insecure_ssl_if_requested()

ChatterboxVariant = Literal["english", "multilingual", "turbo"]

_LOCAL_MODEL_CACHE: dict[tuple[Any, ...], Any] = {}


def chatterbox_local_prereq_message() -> str | None:
    """로컬 Chatterbox를 쓸 수 있으면 None, 아니면 사용자에게 보여줄 안내 문장."""
    import sys

    if getattr(sys, "frozen", False):
        return (
            "이 exe에는 PyTorch·Chatterbox 모델이 포함되어 있지 않습니다(용량·라이선스).\n\n"
            "· 백엔드를 「Chatterbox (HTTP)」로 바꾸거나\n"
            "· 소스에서: tts_audio_pipeline 폴더로 이동 후\n"
            "    pip install -r requirements-chatterbox.txt\n"
            "    python -m txt2audio --gui\n\n"
            "GPU 사용 시 torch는 https://pytorch.org 에서 환경에 맞게 설치하세요."
        )
    try:
        import torch  # noqa: F401
    except ImportError:
        return (
            "모듈 torch(PyTorch)가 없습니다.\n\n"
            "PowerShell 예:\n"
            "  cd …\\tts_audio_pipeline\n"
            "  pip install -r requirements-chatterbox.txt\n\n"
            "GPU를 쓰면 https://pytorch.org 에서 CUDA 버전에 맞는 설치 명령을 추가로 실행하세요."
        )
    try:
        import chatterbox  # noqa: F401
    except ImportError:
        return (
            "chatterbox-tts 패키지가 없습니다.\n\n"
            "  pip install -r requirements-chatterbox.txt"
        )
    return None


def _resolve_device(explicit: str) -> str:
    e = explicit.strip().lower()
    if e in ("cuda", "cpu", "mps"):
        return e
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError("로컬 Chatterbox에는 torch가 필요합니다. pip install -r requirements-chatterbox.txt") from exc
    if torch.cuda.is_available():
        return "cuda"
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def _load_local_model(
    variant: ChatterboxVariant,
    device: str,
    *,
    mtl_t3: str = "",
) -> Any:
    key = (variant, device, mtl_t3 or "")
    if key in _LOCAL_MODEL_CACHE:
        return _LOCAL_MODEL_CACHE[key]
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError(
            "chatterbox-tts 패키지와 PyTorch가 필요합니다.\n"
            "  pip install -r requirements-chatterbox.txt"
        ) from exc
    if variant == "turbo":
        from chatterbox.tts_turbo import ChatterboxTurboTTS

        model = ChatterboxTurboTTS.from_pretrained(device=device)
    elif variant == "multilingual":
        from chatterbox.mtl_tts import ChatterboxMultilingualTTS

        kwargs: dict[str, Any] = {"device": device}
        if mtl_t3.strip().lower() in ("v3", "3"):
            kwargs["t3_model"] = "v3"
        model = ChatterboxMultilingualTTS.from_pretrained(**kwargs)
    else:
        from chatterbox.tts import ChatterboxTTS

        model = ChatterboxTTS.from_pretrained(device=device)
    _LOCAL_MODEL_CACHE[key] = model
    return model


def _save_tensor_wav(wav: Any, sr: int, path: Path) -> None:
    import torch
    import torchaudio as ta

    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(wav, torch.Tensor):
        t = wav
    else:
        t = torch.as_tensor(wav)
    if t.dim() == 1:
        t = t.unsqueeze(0)
    ta.save(str(path), t.cpu(), sr)


def _concat_wavs_torch(wavs: list[Any], sr: int) -> Any:
    import torch

    tensors: list[Any] = []
    for w in wavs:
        t = w if isinstance(w, torch.Tensor) else torch.as_tensor(w)
        if t.dim() == 1:
            t = t.unsqueeze(0)
        tensors.append(t)
    return torch.cat(tensors, dim=-1)


def _synthesize_local_sync(
    text: str,
    output_path: Path,
    *,
    variant: ChatterboxVariant,
    device_spec: str,
    language_id: str,
    audio_prompt_path: Path | None,
    max_chars: int,
    mtl_t3: str,
    on_progress: Callable[[int, int], None] | None,
) -> None:
    import torch

    device = _resolve_device(device_spec)
    model = _load_local_model(variant, device, mtl_t3=mtl_t3)
    sr = int(getattr(model, "sr", 24000))

    if variant == "turbo" and (audio_prompt_path is None or not audio_prompt_path.is_file()):
        raise RuntimeError(
            "Chatterbox-Turbo는 참조 음성이 필요합니다. --voice-prompt 로 WAV 등 경로를 지정하세요."
        )

    pieces = split_for_tts(text, max_chars)
    if not pieces:
        raise ValueError("합성할 텍스트가 비어 있습니다.")

    ap = str(audio_prompt_path.resolve()) if audio_prompt_path and audio_prompt_path.is_file() else None

    n = len(pieces)
    total = n + 1
    if on_progress:
        on_progress(0, total)

    wavs: list[Any] = []
    for i, chunk in enumerate(pieces):
        if variant == "multilingual":
            lid = (language_id or "ko").strip() or "ko"
            if ap:
                w = model.generate(chunk, language_id=lid, audio_prompt_path=ap)
            else:
                w = model.generate(chunk, language_id=lid)
        else:
            if ap:
                w = model.generate(chunk, audio_prompt_path=ap)
            else:
                w = model.generate(chunk)
        wavs.append(w)
        if on_progress:
            on_progress(i + 1, total)

    merged = _concat_wavs_torch(wavs, sr) if len(wavs) > 1 else wavs[0]
    if isinstance(merged, torch.Tensor) and merged.dim() == 1:
        merged = merged.unsqueeze(0)

    import shutil
    import subprocess

    tmp_wav = output_path.with_suffix(".tmp.wav")
    try:
        _save_tensor_wav(merged, sr, tmp_wav)
        if on_progress:
            on_progress(total, total)

        if output_path.suffix.lower() == ".mp3":
            if shutil.which("ffmpeg"):
                output_path.parent.mkdir(parents=True, exist_ok=True)
                if output_path.exists():
                    output_path.unlink()
                r = subprocess.run(
                    [
                        "ffmpeg",
                        "-y",
                        "-i",
                        str(tmp_wav),
                        "-codec:a",
                        "libmp3lame",
                        "-qscale:a",
                        "2",
                        str(output_path),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=600,
                )
                if r.returncode != 0 or not output_path.is_file():
                    raise RuntimeError(
                        "MP3로 인코딩하지 못했습니다(ffmpeg). WAV로 저장하려면 출력 확장자를 .wav 로 지정하세요.\n"
                        + (r.stderr or r.stdout or "")
                    )
                try:
                    tmp_wav.unlink()
                except OSError:
                    pass
            else:
                dest_wav = output_path.with_suffix(".wav")
                if dest_wav.exists():
                    dest_wav.unlink()
                tmp_wav.replace(dest_wav)
                raise RuntimeError(
                    f"MP3 저장에는 ffmpeg가 필요합니다. WAV로 저장했습니다: {dest_wav}\n"
                    "또는 ffmpeg 설치 후 다시 MP3로 지정하세요."
                )
        else:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            if output_path.exists():
                output_path.unlink()
            tmp_wav.replace(output_path)
    finally:
        if tmp_wav.exists():
            try:
                tmp_wav.unlink()
            except OSError:
                pass


class ChatterboxLocalBackend(SynthesisBackend):
    """chatterbox-tts 로컬 추론(블로킹 작업은 스레드에서 실행)."""

    def __init__(
        self,
        *,
        variant: ChatterboxVariant = "multilingual",
        device: str = "auto",
        language_id: str = "ko",
        audio_prompt_path: Path | None = None,
        max_chars_per_request: int = 1200,
        mtl_t3: str = "",
    ) -> None:
        self.variant = variant
        self.device = device
        self.language_id = language_id
        self.audio_prompt_path = audio_prompt_path
        self.max_chars = max_chars_per_request
        self.mtl_t3 = mtl_t3

    async def synthesize_file(
        self,
        text: str,
        output_path: Path,
        *,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> None:
        ap = self.audio_prompt_path
        await asyncio.to_thread(
            _synthesize_local_sync,
            text,
            output_path,
            variant=self.variant,
            device_spec=self.device,
            language_id=self.language_id,
            audio_prompt_path=ap,
            max_chars=self.max_chars,
            mtl_t3=self.mtl_t3,
            on_progress=on_progress,
        )


def _build_multipart(
    fields: dict[str, str],
    files: dict[str, Path],
) -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex.encode("ascii")
    crlf = b"\r\n"
    parts: list[bytes] = []
    for name, value in fields.items():
        parts.append(b"--" + boundary + crlf)
        disp = f'Content-Disposition: form-data; name="{name}"'.encode()
        parts.append(disp + crlf + crlf + value.encode("utf-8") + crlf)
    for name, path in files.items():
        raw = path.read_bytes()
        mime = "application/octet-stream"
        suf = path.suffix.lower()
        if suf == ".wav":
            mime = "audio/wav"
        elif suf == ".mp3":
            mime = "audio/mpeg"
        parts.append(b"--" + boundary + crlf)
        disp = (
            f'Content-Disposition: form-data; name="{name}"; filename="{path.name}"'.encode("utf-8", errors="replace")
        )
        parts.append(disp + crlf)
        parts.append(f"Content-Type: {mime}".encode() + crlf + crlf + raw + crlf)
    parts.append(b"--" + boundary + b"--" + crlf)
    body = b"".join(parts)
    ct = f"multipart/form-data; boundary={boundary.decode('ascii')}"
    return body, ct


def _post_http_sync(
    base_url: str,
    path: str,
    *,
    text: str,
    language_id: str,
    model_variant: str,
    audio_prompt_path: Path | None,
    api_key: str,
    prefer_json: bool,
    timeout: int,
) -> bytes:
    base = base_url.rstrip("/") + "/"
    url = urljoin(base, path.lstrip("/"))

    headers: dict[str, str] = {}
    key = (api_key or os.environ.get("CHATTERBOX_HTTP_API_KEY", "")).strip()
    if key:
        headers["Authorization"] = f"Bearer {key}"

    if prefer_json:
        payload: dict[str, Any] = {"text": text, "model": model_variant}
        if language_id:
            payload["language_id"] = language_id
        if audio_prompt_path and audio_prompt_path.is_file():
            payload["audio_prompt_base64"] = base64.standard_b64encode(audio_prompt_path.read_bytes()).decode(
                "ascii"
            )
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
        req = Request(url, data=data, method="POST", headers=headers)
    else:
        fields = {"text": text, "model": model_variant}
        if language_id:
            fields["language_id"] = language_id
        files: dict[str, Path] = {}
        if audio_prompt_path and audio_prompt_path.is_file():
            files["audio_prompt"] = audio_prompt_path
        body, ct = _build_multipart(fields, files)
        headers["Content-Type"] = ct
        req = Request(url, data=body, method="POST", headers=headers)

    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            hdr = resp.headers.get("Content-Type", "") if resp.headers else ""
            ctype = hdr.split(";")[0].strip().lower()
    except HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Chatterbox HTTP 오류 {e.code}: {err}") from e
    except URLError as e:
        raise RuntimeError(f"Chatterbox HTTP 연결 실패: {e}") from e

    if "json" in ctype:
        try:
            obj = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return raw
        b64 = obj.get("audio_base64") or obj.get("audio") or obj.get("data")
        if isinstance(b64, str):
            return base64.standard_b64decode(b64)
        raise RuntimeError("JSON 응답에 audio_base64(또는 audio) 필드가 없습니다.")

    return raw


def _synthesize_http_sync(
    text: str,
    output_path: Path,
    *,
    base_url: str,
    http_path: str,
    language_id: str,
    model_variant: str,
    audio_prompt_path: Path | None,
    api_key: str,
    prefer_json: bool,
    max_chars: int,
    timeout: int,
    on_progress: Callable[[int, int], None] | None,
) -> None:
    pieces = split_for_tts(text, max_chars)
    if not pieces:
        raise ValueError("합성할 텍스트가 비어 있습니다.")

    n = len(pieces)
    total_steps = n + (1 if n > 1 else 0)
    if on_progress:
        on_progress(0, total_steps)

    if n == 1:
        if on_progress:
            on_progress(0, total_steps)
        data = _post_http_sync(
            base_url,
            http_path,
            text=pieces[0],
            language_id=language_id,
            model_variant=model_variant,
            audio_prompt_path=audio_prompt_path,
            api_key=api_key,
            prefer_json=prefer_json,
            timeout=timeout,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if output_path.exists():
            output_path.unlink()
        output_path.write_bytes(data)
        if on_progress:
            on_progress(total_steps, total_steps)
        return

    tmp_paths: list[Path] = []
    try:
        for i, chunk in enumerate(pieces):
            data = _post_http_sync(
                base_url,
                http_path,
                text=chunk,
                language_id=language_id,
                model_variant=model_variant,
                audio_prompt_path=audio_prompt_path,
                api_key=api_key,
                prefer_json=prefer_json,
                timeout=timeout,
            )
            ext = ".mp3" if data[:3] == b"ID3" or data[:2] == b"\xff\xfb" else ".wav"
            tmp = output_path.with_suffix(f".part{i:04d}{ext}")
            tmp.write_bytes(data)
            tmp_paths.append(tmp)
            if on_progress:
                on_progress(i + 1, total_steps)

        if asyncio.run(try_concat_with_ffmpeg(tmp_paths, output_path)):
            if on_progress:
                on_progress(total_steps, total_steps)
            return
        if output_path.suffix.lower() == ".mp3":
            from txt2audio.audio_merge import concat_mp3_binary

            concat_mp3_binary(tmp_paths, output_path)
            if on_progress:
                on_progress(total_steps, total_steps)
            return
        raise RuntimeError(
            "여러 구간 HTTP 합성: 서버가 WAV를 반환하면 ffmpeg로 이어붙이거나, 출력을 .mp3로 지정하세요."
        )
    finally:
        for p in tmp_paths:
            if p.exists():
                try:
                    p.unlink()
                except OSError:
                    pass


class ChatterboxHttpBackend(SynthesisBackend):
    """사용자가 띄운 Chatterbox 호환 HTTP 서버.

    기본 계약(``--chatterbox-http-json`` 미사용 시): ``multipart/form-data``

    - ``text`` (필수), ``model`` (english|multilingual|turbo), ``language_id`` (선택)
    - ``audio_prompt`` 파일 필드(선택, 음성 복제)

    응답: ``audio/wav`` 또는 ``audio/mpeg`` 바이너리, 또는 JSON ``{\"audio_base64\": \"...\"}``.

    ``--chatterbox-http-json`` 사용 시: ``application/json`` 으로 동일 필드 + ``audio_prompt_base64`` 선택.
    """

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8000",
        *,
        path: str = "/tts",
        language_id: str = "ko",
        model_variant: str = "multilingual",
        audio_prompt_path: Path | None = None,
        api_key: str = "",
        prefer_json: bool = False,
        max_chars_per_request: int = 1200,
        timeout: int = 300,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.path = path
        self.language_id = language_id
        self.model_variant = model_variant
        self.audio_prompt_path = audio_prompt_path
        self.api_key = api_key
        self.prefer_json = prefer_json
        self.max_chars = max_chars_per_request
        self.timeout = timeout

    async def synthesize_file(
        self,
        text: str,
        output_path: Path,
        *,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> None:
        await asyncio.to_thread(
            _synthesize_http_sync,
            text,
            output_path,
            base_url=self.base_url,
            http_path=self.path,
            language_id=self.language_id,
            model_variant=self.model_variant,
            audio_prompt_path=self.audio_prompt_path,
            api_key=self.api_key,
            prefer_json=self.prefer_json,
            max_chars=self.max_chars,
            timeout=self.timeout,
            on_progress=on_progress,
        )
