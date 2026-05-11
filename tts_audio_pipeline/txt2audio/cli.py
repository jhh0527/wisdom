"""명령줄 진입점."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

from txt2audio import __version__
from txt2audio.backends.chatterbox import (
    ChatterboxHttpBackend,
    ChatterboxLocalBackend,
    chatterbox_local_prereq_message,
)
from txt2audio.backends.edge import EdgeTtsBackend, list_voices as list_edge_voices
from txt2audio.backends.elevenlabs import ElevenLabsBackend


def _frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def _win_utf8_stdio() -> None:
    if sys.platform != "win32":
        return
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError, ValueError):
            pass


def _pause_console() -> None:
    """더블클릭 실행 시 창이 바로 닫히지 않도록 대기."""
    if not _frozen():
        return
    try:
        input("\nEnter 키를 누르면 종료합니다...")
    except (EOFError, KeyboardInterrupt):
        pass


def _print_double_click_help() -> None:
    print(
        "txt2audio — 텍스트를 음성(MP3)으로 변환합니다.\n\n"
        "이 프로그램은 명령줄 도구입니다. 더블클릭만으로는 변환이 되지 않습니다.\n"
        "아래처럼 **입력 텍스트 파일**과 **출력 음성 파일 경로**를 함께 지정해야 합니다.\n\n"
        "예시(명령 프롬프트 또는 PowerShell에서 exe가 있는 폴더로 이동 후):\n"
        r'  txt2audio.exe -i "C:\경로\대본.txt" -o "C:\경로\결과.mp3"' "\n\n"
        "edge 음성 목록만 보기:\n"
        "  txt2audio.exe --list-voices --lang ko\n\n"
        "Chatterbox(로컬/HTTP) 예:\n"
        r'  txt2audio.exe --backend chatterbox -i "대본.txt" -o "out.wav"' "\n"
        r'  txt2audio.exe --backend chatterbox --chatterbox-mode http --chatterbox-url http://127.0.0.1:8000 -i in.txt -o out.mp3' "\n\n"
        "파일을 고르는 창이 필요하면 같은 폴더의 txt2audio_gui.exe 를 실행하세요.\n"
        "  (또는: txt2audio.exe --gui)\n\n"
        "자세한 옵션: txt2audio.exe --help\n",
        flush=True,
    )


def _read_input(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="txt2audio",
        description="UTF-8 텍스트 파일을 음성 파일로 변환합니다.",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    p.add_argument(
        "--gui",
        action="store_true",
        help="파일 선택 창이 있는 그래픽 화면을 엽니다.",
    )
    p.add_argument(
        "--list-voices",
        action="store_true",
        help="edge-tts 사용 가능 음성 목록을 출력하고 종료합니다.",
    )
    p.add_argument(
        "--lang",
        default="",
        help="--list-voices 시 로케일 접두어로 필터(예: ko, en)",
    )
    p.add_argument("-i", "--input", type=Path, help="입력 UTF-8 텍스트 파일")
    p.add_argument("-o", "--output", type=Path, help="출력 오디오 경로(예: out.mp3)")
    p.add_argument(
        "--backend",
        choices=("edge", "elevenlabs", "chatterbox"),
        default="edge",
        help="TTS 백엔드 (기본: edge)",
    )
    p.add_argument(
        "--voice",
        default="ko-KR-SunHiNeural",
        help="edge-tts ShortName (기본: 한국어 Sun-Hi)",
    )
    p.add_argument(
        "--voice-id",
        default="",
        help="ElevenLabs voice_id (미지정 시 환경 변수 ELEVENLABS_VOICE_ID)",
    )
    p.add_argument(
        "--model",
        default="eleven_multilingual_v2",
        help="ElevenLabs model_id",
    )
    p.add_argument("--rate", default="+0%", help="edge-tts 속도(예: +10%%, -5%%)")
    p.add_argument("--pitch", default="+0Hz", help="edge-tts 피치")
    p.add_argument("--volume", default="+0%", help="edge-tts 볼륨")
    p.add_argument(
        "--max-chunk",
        type=int,
        default=0,
        help="청크당 최대 글자 수(0이면 백엔드 기본값)",
    )
    p.add_argument(
        "--voice-prompt",
        type=Path,
        default=None,
        help="Chatterbox 음성 복제용 참조 오디오(WAV 등). --backend chatterbox 에서 사용",
    )
    p.add_argument(
        "--chatterbox-mode",
        choices=("local", "http"),
        default="local",
        help="Chatterbox: 로컬(chatterbox-tts) 또는 HTTP 서버 (기본: local)",
    )
    p.add_argument(
        "--chatterbox-variant",
        choices=("english", "multilingual", "turbo"),
        default="multilingual",
        help="Chatterbox 로컬 모델 (기본: multilingual, 한국어 등 다국어)",
    )
    p.add_argument(
        "--chatterbox-device",
        default="auto",
        help="Chatterbox 로컬 디바이스: auto, cuda, cpu, mps",
    )
    p.add_argument(
        "--chatterbox-language-id",
        default="ko",
        help="Chatterbox 다국어 모델용 BCP-47 언어 코드(예: ko, en, ja)",
    )
    p.add_argument(
        "--chatterbox-mtl-v3",
        action="store_true",
        help="다국어 모델을 v3 체크포인트로 로드",
    )
    p.add_argument(
        "--chatterbox-url",
        default="http://127.0.0.1:8000",
        help="Chatterbox HTTP 서버 베이스 URL (--chatterbox-mode http)",
    )
    p.add_argument(
        "--chatterbox-path",
        default="/tts",
        help="Chatterbox HTTP API 경로 (베이스 URL에 이어 붙임)",
    )
    p.add_argument(
        "--chatterbox-http-key",
        default="",
        help="HTTP Bearer 토큰(미지정 시 환경 변수 CHATTERBOX_HTTP_API_KEY)",
    )
    p.add_argument(
        "--chatterbox-http-json",
        action="store_true",
        help="HTTP 요청을 application/json 으로 보냄(audio_prompt_base64)",
    )
    p.add_argument(
        "--chatterbox-timeout",
        type=int,
        default=300,
        help="Chatterbox HTTP 요청 타임아웃(초)",
    )
    return p


async def _cmd_list_voices(lang: str) -> int:
    rows = await list_edge_voices(language_prefix=lang or None)
    for r in rows:
        print(f"{r['ShortName']}\t{r['Locale']}\t{r['FriendlyName']}")
    return 0


async def _cmd_synthesize(args: argparse.Namespace) -> int:
    if args.input is None or args.output is None:
        print("-i/--input 과 -o/--output 이 필요합니다.", file=sys.stderr)
        return 2
    if not args.input.is_file():
        print(f"입력 파일을 찾을 수 없습니다: {args.input}", file=sys.stderr)
        return 1

    text = _read_input(args.input)
    max_chunk = args.max_chunk or None

    if args.backend == "edge":
        mc = max_chunk if max_chunk else 2800
        backend = EdgeTtsBackend(
            args.voice,
            rate=args.rate,
            pitch=args.pitch,
            volume=args.volume,
            max_chars_per_request=mc,
        )
    elif args.backend == "chatterbox":
        vp = args.voice_prompt
        if vp is not None and str(vp).strip() and not vp.is_file():
            print(f"참조 음성 파일을 찾을 수 없습니다: {vp}", file=sys.stderr)
            return 1
        prompt_path = vp if (vp is not None and str(vp).strip() and vp.is_file()) else None
        mc = max_chunk if max_chunk else 1200
        if args.chatterbox_mode == "local":
            pre = chatterbox_local_prereq_message()
            if pre:
                print(pre, file=sys.stderr)
                return 1
        if args.chatterbox_mode == "http":
            backend = ChatterboxHttpBackend(
                args.chatterbox_url,
                path=args.chatterbox_path,
                language_id=args.chatterbox_language_id,
                model_variant=args.chatterbox_variant,
                audio_prompt_path=prompt_path,
                api_key=args.chatterbox_http_key,
                prefer_json=args.chatterbox_http_json,
                max_chars_per_request=mc,
                timeout=args.chatterbox_timeout,
            )
        else:
            backend = ChatterboxLocalBackend(
                variant=args.chatterbox_variant,
                device=args.chatterbox_device,
                language_id=args.chatterbox_language_id,
                audio_prompt_path=prompt_path,
                max_chars_per_request=mc,
                mtl_t3="v3" if args.chatterbox_mtl_v3 else "",
            )
    else:
        vid = (args.voice_id or os.environ.get("ELEVENLABS_VOICE_ID", "")).strip()
        if not vid:
            print(
                "ElevenLabs voice_id가 필요합니다: --voice-id 또는 ELEVENLABS_VOICE_ID",
                file=sys.stderr,
            )
            return 1
        mc = max_chunk if max_chunk else 4500
        backend = ElevenLabsBackend(vid, model_id=args.model, max_chars_per_request=mc)

    await backend.synthesize_file(text, args.output)
    print(f"저장 완료: {args.output.resolve()}")
    return 0


def main(argv: list[str] | None = None) -> int:
    _win_utf8_stdio()

    eff: list[str] = list(argv) if argv is not None else sys.argv[1:]
    if _frozen() and len(eff) == 0:
        _print_double_click_help()
        _pause_console()
        return 0

    parser = _build_parser()
    args = parser.parse_args(eff)

    if args.gui:
        from txt2audio.gui_app import main as gui_main

        gui_main()
        return 0

    if args.list_voices:
        code = asyncio.run(_cmd_list_voices(args.lang))
    else:
        code = asyncio.run(_cmd_synthesize(args))

    if _frozen() and code not in (0, None):
        _pause_console()
    return int(code) if code is not None else 0
