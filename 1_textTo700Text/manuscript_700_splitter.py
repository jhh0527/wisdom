#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""대본을 줄바꿈 없이 공백 포함 정확히 700자 단위로 나눠 여러 UTF-8 .txt로 저장합니다."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

CHUNK_SIZE = 700
PROJECT_DIRNAME = "1_textTo700Text"
OUTPUT_DIRNAME = "output"


def flatten_for_chunking(text: str) -> str:
    """줄바꿈·캐리지리턴을 제거한 뒤 공백 포함 연속 문자열로 만듭니다."""
    return text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "")


def resolve_output_dir() -> Path:
    """`1_textTo700Text/output/` 절대 경로를 반환합니다."""
    if getattr(sys, "frozen", False):
        start = Path(sys.executable).resolve().parent
    else:
        start = Path(__file__).resolve().parent
    for p in [start, *start.parents]:
        if p.name == PROJECT_DIRNAME:
            return p / OUTPUT_DIRNAME
    return start / OUTPUT_DIRNAME


def _text_widget_content(widget) -> str:
    """Tk Text 위젯 본문(끝의 자동 개행 제외)."""
    return widget.get("1.0", "end-1c")


def split_into_chunks(text: str, size: int = CHUNK_SIZE) -> list[str]:
    """줄바꿈을 무시한 연속 문자열을 공백 포함 정확히 size자씩 잘라 반환합니다."""
    if size <= 0:
        raise ValueError("size는 1 이상이어야 합니다.")
    if not text:
        return []
    flat = flatten_for_chunking(text)
    if not flat:
        return []
    return [flat[i : i + size] for i in range(0, len(flat), size)]


def write_chunk_files(chunks: list[str], out_dir: Path, stem: str) -> list[Path]:
    """chunks를 out_dir에 stem_NNN.txt 형식으로 저장하고 경로 목록을 반환합니다."""
    out_dir.mkdir(parents=True, exist_ok=True)
    width = max(3, len(str(len(chunks))))
    paths: list[Path] = []
    for idx, body in enumerate(chunks, start=1):
        name = f"{stem}_{idx:0{width}d}.txt"
        path = out_dir / name
        path.write_text(body, encoding="utf-8", newline="\n")
        paths.append(path)
    return paths


def run_gui() -> int:
    import tkinter as tk
    from tkinter import filedialog, messagebox, font as tkfont
    from tkinter import ttk

    root = tk.Tk()
    root.title(f"대본 {CHUNK_SIZE}자 분할 저장 (줄바꿈 없이 공백 포함)")
    root.minsize(560, 420)
    root.geometry("760x520")

    try:
        default_font = tkfont.nametofont("TkTextFont")
        text_font = (default_font.actual("family"), max(10, default_font.actual("size")))
    except tk.TclError:
        text_font = ("맑은 고딕", 11)

    output_dir = resolve_output_dir()
    output_dir.mkdir(parents=True, exist_ok=True)
    stem_var = tk.StringVar(value="script_part")

    frm = tk.Frame(root, padx=10, pady=8)
    frm.grid(row=0, column=0, sticky="nsew")
    root.grid_rowconfigure(0, weight=1)
    root.grid_columnconfigure(0, weight=1)
    frm.grid_rowconfigure(1, weight=1)
    frm.grid_columnconfigure(0, weight=1)

    ttk.Label(frm, text="대본 (붙여넣기 또는 아래에서 파일 불러오기)").grid(row=0, column=0, sticky="w")
    text = tk.Text(frm, wrap=tk.WORD, undo=True, font=text_font, padx=6, pady=6)
    scroll_y = tk.Scrollbar(frm, command=text.yview)
    text.configure(yscrollcommand=scroll_y.set)
    text.grid(row=1, column=0, sticky="nsew", pady=(4, 8))
    scroll_y.grid(row=1, column=1, sticky="ns", pady=(4, 8))

    row_opts = ttk.Frame(frm)
    row_opts.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 6))
    row_opts.grid_columnconfigure(1, weight=1)

    ttk.Label(row_opts, text="저장 폴더(고정)").grid(row=0, column=0, sticky="nw", padx=(0, 6))
    ttk.Label(
        row_opts,
        text=str(output_dir.resolve()),
        wraplength=520,
        justify=tk.LEFT,
    ).grid(row=0, column=1, columnspan=2, sticky="ew")

    ttk.Label(row_opts, text="파일 이름 접두사").grid(row=1, column=0, sticky="w", padx=(0, 6), pady=(6, 0))
    ttk.Entry(row_opts, textvariable=stem_var).grid(row=1, column=1, columnspan=2, sticky="ew", pady=(6, 0))

    row_btns = ttk.Frame(frm)
    row_btns.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(4, 6))

    status = tk.Label(frm, anchor=tk.W, justify=tk.LEFT, relief=tk.SUNKEN, padx=6, pady=4)

    def load_file() -> None:
        path = filedialog.askopenfilename(
            title="대본 열기",
            filetypes=[("텍스트", "*.txt"), ("마크다운", "*.md"), ("모든 파일", "*.*")],
        )
        if not path:
            return
        p = Path(path)
        try:
            data = p.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            messagebox.showerror("열기 오류", str(e))
            return
        text.delete("1.0", tk.END)
        text.insert("1.0", data)
        if not stem_var.get().strip():
            stem_var.set(p.stem)

    def do_split_save() -> None:
        body = _text_widget_content(text)
        if not body.strip():
            messagebox.showwarning("내용 없음", "저장할 대본이 비어 있습니다.")
            return
        stem = stem_var.get().strip() or "script_part"
        bad = set('<>:"/\\|?*')
        if any(c in stem for c in bad):
            messagebox.showerror(
                "이름 오류",
                f'파일 이름에 사용할 수 없는 문자가 있습니다: {", ".join(sorted(bad & set(stem)))}',
            )
            return
        odir = resolve_output_dir()
        odir.mkdir(parents=True, exist_ok=True)
        try:
            chunks = split_into_chunks(body, CHUNK_SIZE)
            paths = write_chunk_files(chunks, odir, stem)
        except OSError as e:
            messagebox.showerror("저장 오류", str(e))
            return
        status.config(text=f"{len(paths)}개 파일 저장: {paths[0].parent}")
        messagebox.showinfo("완료", f"{len(paths)}개 파일을 저장했습니다.\n{odir.resolve()}")

    ttk.Button(row_btns, text="텍스트 파일 불러오기…", command=load_file).pack(side=tk.LEFT, padx=(0, 8))
    ttk.Button(row_btns, text=f"{CHUNK_SIZE}자 단위로 분할 저장", command=do_split_save).pack(side=tk.LEFT)

    status.grid(row=4, column=0, columnspan=2, sticky="ew")
    frm.grid_rowconfigure(4, weight=0)

    status.config(
        text=(
            f"대기 중 — 줄바꿈을 제외한 본문을 공백 포함 정확히 {CHUNK_SIZE}자씩 끊어 "
            f"{output_dir} 에 저장합니다."
        ),
    )
    root.mainloop()
    return 0


def run_cli(in_path: Path, out_dir: Path, stem: str) -> int:
    try:
        body = in_path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        print(f"읽기 오류: {e}", file=sys.stderr)
        return 1
    if not body.strip():
        print("내용이 비어 있습니다.", file=sys.stderr)
        return 1
    chunks = split_into_chunks(body, CHUNK_SIZE)
    try:
        paths = write_chunk_files(chunks, out_dir, stem)
    except OSError as e:
        print(f"저장 오류: {e}", file=sys.stderr)
        return 1
    for p in paths:
        print(p)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            f"대본의 줄바꿈을 제외한 본문을 공백 포함 정확히 {CHUNK_SIZE}자씩 잘라 "
            "여러 UTF-8 .txt로 저장합니다. 인자 없이 실행하면 편집 창이 열립니다."
        ),
    )
    parser.add_argument("input", nargs="?", type=Path, help="입력 텍스트 파일 (지정 시 콘솔만 사용)")
    parser.add_argument(
        "-o",
        "--out-dir",
        type=Path,
        default=None,
        help=f"출력 폴더 (기본: {PROJECT_DIRNAME}/{OUTPUT_DIRNAME})",
    )
    parser.add_argument(
        "-n",
        "--name",
        default="script_part",
        help="저장 파일 접두사 (기본: script_part)",
    )
    parser.add_argument(
        "-g",
        "--gui",
        action="store_true",
        help="입력 파일이 있어도 GUI를 엽니다",
    )
    args = parser.parse_args()
    out = args.out_dir if args.out_dir is not None else resolve_output_dir()
    out.mkdir(parents=True, exist_ok=True)

    if args.gui or args.input is None:
        return run_gui()
    return run_cli(args.input, out, args.name)


if __name__ == "__main__":
    raise SystemExit(main())
