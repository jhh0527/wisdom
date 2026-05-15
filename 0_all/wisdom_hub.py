#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""wisdom 루트 하위 프로그램을 탭에서 실행합니다 (program.md / all/dist)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    if getattr(sys, "frozen", False):
        # all/dist/WisdomHub.exe → wisdom 루트
        return Path(sys.executable).resolve().parent.parent.parent
    return Path(__file__).resolve().parent.parent


# (탭 제목, exe 경로 repo 기준)
_APPS: tuple[tuple[str, str], ...] = (
    ("대본 700자 분할", "1_textTo700Text/dist/manuscript_700_splitter.exe"),
    ("3_ttsToVoice", "3_ttsToVoice/dist/3_ttsToVoice_gui.exe"),
    ("4_srtToImage (GUI)", "4_srtToImage/dist/4_srtToImage_gui.exe"),
    ("5_video (GUI)", "5_video/dist/5_video_gui.exe"),
    ("2_textToTts (GUI)", "2_textToTts/dist/2_textToTts_gui.exe"),
    ("txt2audio (GUI)", "tts_audio_pipeline/dist/txt2audio_gui.exe"),
    ("Video Studio", "video_studio/dist/VideoStudio.exe"),
    ("글자수 체크", "dist/char_count.exe"),
)


def main() -> int:
    import tkinter as tk
    from tkinter import messagebox, font as tkfont
    from tkinter import ttk

    root = tk.Tk()
    root.title("Wisdom Hub")
    root.minsize(420, 240)
    root.geometry("480x280")

    try:
        default_font = tkfont.nametofont("TkDefaultFont")
        fam = default_font.actual("family")
        sz = max(10, default_font.actual("size"))
    except tk.TclError:
        fam, sz = "맑은 고딕", 10
    root.option_add("*Font", (fam, sz))

    base = _repo_root()

    nb = ttk.Notebook(root, padding=6)
    nb.pack(fill=tk.BOTH, expand=True)

    def make_launcher(title: str, rel: str) -> None:
        tab = ttk.Frame(nb, padding=12)
        nb.add(tab, text=title)
        target = (base / rel).resolve()

        info = ttk.Label(
            tab,
            text=f"경로:\n{target}",
            wraplength=420,
            justify=tk.LEFT,
        )
        info.pack(anchor=tk.W, pady=(0, 10))

        def run_app() -> None:
            if not target.is_file():
                messagebox.showerror(
                    "실행 파일 없음",
                    f"다음 파일이 없습니다. 해당 폴더에서 build\\build_exe.bat 으로 빌드하세요.\n\n{target}",
                )
                return
            try:
                subprocess.Popen([str(target)], cwd=str(target.parent))
            except OSError as e:
                messagebox.showerror("실행 오류", str(e))

        ttk.Button(tab, text="프로그램 실행", command=run_app).pack(anchor=tk.W)

    for title, rel in _APPS:
        make_launcher(title, rel)

    out_hint = ttk.Label(
        root,
        text=f"통합 산출물 폴더: {base / 'all' / 'output'}",
        padding=(10, 0, 10, 8),
    )
    out_hint.pack(fill=tk.X, side=tk.BOTTOM)

    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
