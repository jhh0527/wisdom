#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""텍스트 파일·표준 입력·메모장 형태 편집기로 글자수를 집계합니다."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def count_stats(text: str) -> dict[str, int]:
    """공백 포함/제외, 줄 수, 단어 수 등을 계산합니다."""
    lines = text.splitlines()
    words = text.split()
    return {
        "chars_with_spaces": len(text),
        "chars_no_spaces": sum(1 for c in text if not c.isspace()),
        "lines": len(lines),
        "words": len(words),
    }


def read_text(path: Path | None) -> str:
    if path is None:
        return sys.stdin.read()
    return path.read_text(encoding="utf-8", errors="replace")


def _text_widget_content(widget) -> str:
    """Tk Text 위젯 본문(끝의 자동 개행 제외)."""
    return widget.get("1.0", "end-1c")


def run_editor_gui() -> int:
    import tkinter as tk
    from tkinter import filedialog, messagebox, font as tkfont

    current_path: list[Path | None] = [None]

    root = tk.Tk()
    root.title("글자수 체크")
    root.minsize(520, 360)
    root.geometry("720x480")

    try:
        default_font = tkfont.nametofont("TkTextFont")
        text_font = (default_font.actual("family"), max(10, default_font.actual("size")))
    except tk.TclError:
        text_font = ("맑은 고딕", 11)

    menubar = tk.Menu(root)
    file_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="파일", menu=file_menu)

    text = tk.Text(root, wrap=tk.WORD, undo=True, font=text_font, padx=6, pady=6)
    scroll_y = tk.Scrollbar(root, command=text.yview)
    text.configure(yscrollcommand=scroll_y.set)

    status = tk.Label(root, anchor=tk.W, justify=tk.LEFT, relief=tk.SUNKEN, padx=6, pady=4)

    def refresh_title() -> None:
        name = current_path[0].name if current_path[0] else "제목 없음"
        root.title(f"{name} — 글자수 체크")

    def update_stats(_event=None) -> None:
        body = _text_widget_content(text)
        s = count_stats(body)
        status.config(
            text=(
                f"글자(공백 포함): {s['chars_with_spaces']}  |  "
                f"글자(공백 제외): {s['chars_no_spaces']}  |  "
                f"줄: {s['lines']}  |  "
                f"단어: {s['words']}"
            )
        )

    def new_file() -> None:
        if messagebox.askokcancel("새 파일", "내용을 지우고 새로 시작할까요?"):
            text.delete("1.0", tk.END)
            current_path[0] = None
            refresh_title()
            update_stats()

    def open_file() -> None:
        path = filedialog.askopenfilename(
            title="열기",
            filetypes=[("텍스트 파일", "*.txt"), ("모든 파일", "*.*")],
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
        current_path[0] = p
        refresh_title()
        update_stats()

    def save_file() -> None:
        if current_path[0] is None:
            save_as()
            return
        try:
            current_path[0].write_text(_text_widget_content(text), encoding="utf-8", newline="\n")
        except OSError as e:
            messagebox.showerror("저장 오류", str(e))
            return
        messagebox.showinfo("저장", "저장했습니다.")

    def save_as() -> None:
        path = filedialog.asksaveasfilename(
            title="다른 이름으로 저장",
            defaultextension=".txt",
            filetypes=[("텍스트 파일", "*.txt"), ("모든 파일", "*.*")],
        )
        if not path:
            return
        p = Path(path)
        try:
            p.write_text(_text_widget_content(text), encoding="utf-8", newline="\n")
        except OSError as e:
            messagebox.showerror("저장 오류", str(e))
            return
        current_path[0] = p
        refresh_title()
        messagebox.showinfo("저장", "저장했습니다.")

    file_menu.add_command(label="새 파일", command=new_file, accelerator="Ctrl+N")
    file_menu.add_command(label="열기…", command=open_file, accelerator="Ctrl+O")
    file_menu.add_command(label="저장", command=save_file, accelerator="Ctrl+S")
    file_menu.add_command(label="다른 이름으로 저장…", command=save_as)
    file_menu.add_separator()
    file_menu.add_command(label="종료", command=root.destroy, accelerator="Alt+F4")

    root.config(menu=menubar)

    text.grid(row=0, column=0, sticky="nsew")
    scroll_y.grid(row=0, column=1, sticky="ns")
    status.grid(row=1, column=0, columnspan=2, sticky="ew")
    root.grid_rowconfigure(0, weight=1)
    root.grid_columnconfigure(0, weight=1)

    for seq in ("<KeyRelease>", "<<Paste>>", "<<Cut>>"):
        text.bind(seq, update_stats)

    def on_modified(_event=None) -> None:
        if text.edit_modified():
            text.edit_modified(False)
            update_stats()

    text.bind("<<Modified>>", on_modified)

    root.bind_all("<Control-n>", lambda e: new_file())
    root.bind_all("<Control-o>", lambda e: open_file())
    root.bind_all("<Control-s>", lambda e: save_file())

    refresh_title()
    update_stats()
    root.mainloop()
    return 0


def run_cli(path: Path | None) -> int:
    try:
        text = read_text(path)
    except OSError as e:
        print(f"읽기 오류: {e}", file=sys.stderr)
        return 1

    s = count_stats(text)
    label = str(path) if path else "(표준 입력)"
    print(f"출처: {label}")
    print(f"글자 수(공백 포함): {s['chars_with_spaces']}")
    print(f"글자 수(공백 제외): {s['chars_no_spaces']}")
    print(f"줄 수: {s['lines']}")
    print(f"단어 수(공백 기준): {s['words']}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="텍스트의 글자수·줄 수·단어 수를 집계합니다. "
        "파일을 지정하지 않으면 메모장 형태 창이 열립니다(표준 입력이 파이프되면 콘솔 집계).",
    )
    parser.add_argument(
        "file",
        nargs="?",
        type=Path,
        help="분석할 UTF-8 텍스트 파일(지정 시 콘솔에만 출력)",
    )
    parser.add_argument(
        "-e",
        "--editor",
        action="store_true",
        help="항상 메모장 형태 창을 엽니다",
    )
    args = parser.parse_args()

    if args.editor:
        return run_editor_gui()

    if args.file is not None:
        return run_cli(args.file)

    if not sys.stdin.isatty():
        return run_cli(None)

    if getattr(sys, "frozen", False):
        return run_editor_gui()

    return run_editor_gui()


if __name__ == "__main__":
    raise SystemExit(main())
