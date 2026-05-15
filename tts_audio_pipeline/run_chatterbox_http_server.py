#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""로컬 Chatterbox를 HTTP로 노출합니다.

GUI의 「Chatterbox (HTTP)」 기본값과 맞춤: POST http://127.0.0.1:8000/tts

- multipart: text, model (english|multilingual|turbo), language_id (선택), audio_prompt (파일, 선택)
- JSON: {"text", "model", "language_id"?, "audio_prompt_base64"?}
- 응답: WAV 바이너리 (audio/wav)

환경 변수 CHATTERBOX_HTTP_API_KEY 가 있으면 Authorization: Bearer … 가 일치해야 합니다.

실행 예 (프로젝트 루트에서, Chatterbox venv):
  .\\.venv_chatterbox\\Scripts\\python.exe run_chatterbox_http_server.py

환경 변수 CHATTERBOX_HF_INSECURE_SSL 이 없으면 기본값 1 로 둡니다(기업망 SSL 프록시 대응).
끄려면: set CHATTERBOX_HF_INSECURE_SSL=0
"""

from __future__ import annotations

import os

# txt2audio.backends.chatterbox 로드 전에 설정해야 HF Hub 클라이언트에 반영됩니다.
if "CHATTERBOX_HF_INSECURE_SSL" not in os.environ:
    os.environ["CHATTERBOX_HF_INSECURE_SSL"] = "1"
if os.name == "nt" and "HF_HUB_DISABLE_SYMLINKS" not in os.environ:
    os.environ["HF_HUB_DISABLE_SYMLINKS"] = "1"

import argparse
import base64
import tempfile
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response
import uvicorn

from txt2audio.backends.chatterbox import ChatterboxLocalBackend, chatterbox_local_prereq_message

app = FastAPI(title="txt2audio Chatterbox bridge", version="0.1.0")


def _parse_model(raw: str) -> str:
    v = (raw or "multilingual").strip().lower()
    if v not in ("english", "multilingual", "turbo"):
        raise HTTPException(status_code=400, detail=f"unsupported model: {raw}")
    return v


def _auth_or_401(request: Request, expected: str) -> None:
    if not expected:
        return
    auth = request.headers.get("authorization", "")
    if auth.strip() != f"Bearer {expected}":
        raise HTTPException(status_code=401, detail="Authorization Bearer 토큰이 필요합니다.")


@app.post("/tts")
async def tts(request: Request) -> Response:
    pre = chatterbox_local_prereq_message()
    if pre:
        raise HTTPException(status_code=503, detail=pre)

    expected_key = (os.environ.get("CHATTERBOX_HTTP_API_KEY") or "").strip()
    _auth_or_401(request, expected_key)

    ctype = (request.headers.get("content-type") or "").split(";")[0].strip().lower()
    audio_path: Path | None = None
    tmp_paths: list[Path] = []

    try:
        if ctype == "application/json":
            body: dict[str, Any] = await request.json()
            text = str(body.get("text") or "").strip()
            model = _parse_model(str(body.get("model") or "multilingual"))
            language_id = str(body.get("language_id") or "ko").strip() or "ko"
            b64 = body.get("audio_prompt_base64")
            if isinstance(b64, str) and b64.strip():
                raw = base64.standard_b64decode(b64)
                fd, name = tempfile.mkstemp(suffix=".wav", prefix="prompt_")
                try:
                    os.write(fd, raw)
                finally:
                    os.close(fd)
                p = Path(name)
                audio_path = p
                tmp_paths.append(p)
        else:
            form = await request.form()
            text = str(form.get("text") or "").strip()
            model = _parse_model(str(form.get("model") or "multilingual"))
            language_id = str(form.get("language_id") or "ko").strip() or "ko"
            upl = form.get("audio_prompt")
            if upl is not None and hasattr(upl, "read"):
                raw = await upl.read()
                if raw:
                    fd, name = tempfile.mkstemp(suffix=".wav", prefix="prompt_")
                    try:
                        os.write(fd, raw)
                    finally:
                        os.close(fd)
                    p = Path(name)
                    audio_path = p
                    tmp_paths.append(p)

        if not text:
            raise HTTPException(status_code=400, detail="text 비어 있음")

        if model == "turbo" and (audio_path is None or not audio_path.is_file()):
            raise HTTPException(status_code=400, detail="turbo 모델은 참조 음성(audio_prompt)이 필요합니다.")

        backend = ChatterboxLocalBackend(
            variant=model,  # type: ignore[arg-type]
            device=os.environ.get("CHATTERBOX_DEVICE", "auto"),
            language_id=language_id,
            audio_prompt_path=audio_path,
        )

        fd_out, out_name = tempfile.mkstemp(suffix=".wav", prefix="tts_out_")
        os.close(fd_out)
        out_tmp = Path(out_name)
        tmp_paths.append(out_tmp)

        try:
            await backend.synthesize_file(text, out_tmp)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e)[:8000]) from e
        data = out_tmp.read_bytes()
        return Response(content=data, media_type="audio/wav")
    finally:
        for p in tmp_paths:
            if p.exists():
                try:
                    p.unlink()
                except OSError:
                    pass


def main() -> None:
    ap = argparse.ArgumentParser(description="Chatterbox 로컬 → HTTP 브리지")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--path", default="/tts", help="단일 POST 엔드포인트 경로")
    args = ap.parse_args()

    # 커스텀 경로: 새 앱에 라우트만 복제하기 번거로우므로 루트는 / 로 두고 path가 /tts 가 아니면 안내
    if args.path.rstrip("/") != "/tts":
        print("경고: 현재 구현은 POST /tts 만 지원합니다. --path 는 무시됩니다.", flush=True)

    print(
        "HF SSL: CHATTERBOX_HF_INSECURE_SSL="
        f"{os.environ.get('CHATTERBOX_HF_INSECURE_SSL', '')!r} "
        "(1/true/yes → TLS 검증 끔, 끄려면 실행 전 set CHATTERBOX_HF_INSECURE_SSL=0)",
        flush=True,
    )

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
