# -*- coding: utf-8 -*-
"""PNG → SRT_XXX.jpg 변환 GUI."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
import threading
import tkinter as tk
import traceback
from pathlib import Path
from tkinter import filedialog, font as tkfont, messagebox, ttk

from png2jpg import __version__
from png2jpg.converter import (
    ConvertResult,
    ConvertSkip,
    convert_images,
    DEFAULT_JPEG_QUALITY,
    iter_source_images,
)
from png2jpg.paths import default_input_dir, default_output_dir, default_srt_path
from png2jpg.settings import load_gui_settings, save_gui_settings


def _default_font() -> tuple[str, int]:
    try:
        f = tkfont.nametofont("TkDefaultFont")
        return (f.actual("family"), max(10, int(f.actual("size"))))
    except tk.TclError:
        return ("맑은 고딕", 10)


def _resolve_initial_dir(
    cli: Path | None,
    saved: str | None,
    fallback: Path,
) -> Path:
    if cli is not None:
        p = cli.expanduser().resolve()
        if p.is_dir():
            return p
    if saved:
        p = Path(saved).expanduser().resolve()
        if p.is_dir():
            return p
    return fallback.resolve()


def _count_targets(folder: Path, *, recursive: bool, include_jpg: bool) -> tuple[int, list[Path]]:
    try:
        files = iter_source_images(folder, recursive=recursive, include_jpg=include_jpg)
    except OSError:
        return 0, []
    return len(files), files


def main(
    *,
    initial_input: Path | None = None,
    initial_output: Path | None = None,
) -> None:
    if initial_input is None and initial_output is None and len(sys.argv) > 1:
        p = argparse.ArgumentParser(add_help=False)
        p.add_argument("-i", "--input", type=Path, default=None)
        p.add_argument("-o", "--output", type=Path, default=None)
        ns, _ = p.parse_known_args()
        initial_input = ns.input
        initial_output = ns.output

    cfg = load_gui_settings()
    in_default = _resolve_initial_dir(
        initial_input,
        cfg.get("input_dir"),
        default_input_dir(),
    )
    out_default = _resolve_initial_dir(
        initial_output,
        cfg.get("output_dir"),
        default_output_dir(),
    )
    srt_default = ""
    if cfg.get("srt_path") and Path(cfg["srt_path"]).is_file():
        srt_default = cfg["srt_path"]
    else:
        ds = default_srt_path()
        if ds is not None:
            srt_default = str(ds)

    root = tk.Tk()
    root.title(f"4_1pngToJpg {__version__}")
    root.minsize(680, 520)
    root.geometry("800x560")

    fam, sz = _default_font()
    root.option_add("*Font", (fam, sz))

    in_var = tk.StringVar(value=str(in_default))
    out_var = tk.StringVar(value=str(out_default))
    srt_var = tk.StringVar(value=srt_default)
    recursive_var = tk.BooleanVar(value=True)
    include_jpg_var = tk.BooleanVar(value=False)
    quality_var = tk.IntVar(value=DEFAULT_JPEG_QUALITY)
    target_count_var = tk.StringVar(value="")
    status_var = tk.StringVar(value="변환 대상 폴더를 지정한 뒤 변환을 실행하세요.")

    frm = ttk.Frame(root, padding=10)
    frm.pack(fill=tk.BOTH, expand=True)

    browse_widgets: list[tk.Widget] = []

    def row_dir(
        label: str,
        var: tk.StringVar,
        row: int,
        *,
        on_pick: Callable[[], None] | None = None,
    ) -> None:
        ttk.Label(frm, text=label).grid(row=row, column=0, sticky="w", pady=(0, 4))
        rf = ttk.Frame(frm)
        rf.grid(row=row + 1, column=0, sticky="ew", pady=(0, 10))
        rf.grid_columnconfigure(0, weight=1)
        ent = ttk.Entry(rf, textvariable=var)
        ent.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        def pick() -> None:
            initial = var.get().strip()
            init_dir = initial if initial and Path(initial).is_dir() else str(default_input_dir())
            p = filedialog.askdirectory(title=label, initialdir=init_dir)
            if p:
                var.set(p)
                if on_pick:
                    on_pick()

        btn = ttk.Button(rf, text="폴더 선택…", command=pick)
        btn.grid(row=0, column=1)
        browse_widgets.extend([ent, btn])

    def refresh_target_count() -> None:
        inp = Path(in_var.get().strip())
        if not inp.is_dir():
            target_count_var.set("(폴더 없음)")
            return
        n, _ = _count_targets(
            inp,
            recursive=bool(recursive_var.get()),
            include_jpg=bool(include_jpg_var.get()),
        )
        sub = "하위 포함" if recursive_var.get() else "현재 폴더만"
        target_count_var.set(f"PNG/JPG {n}개 ({sub})")

    def on_input_changed() -> None:
        refresh_target_count()

    row_dir("변환 대상 폴더 (PNG·JPG)", in_var, 0, on_pick=on_input_changed)
    row_dir("저장 폴더 (SRT_XXX.jpg)", out_var, 2)

    ttk.Label(frm, text="SRT 자막 파일 (timestamp 파일명 → SRT 번호 매칭)").grid(
        row=4, column=0, sticky="w", pady=(0, 4)
    )
    row_srt = ttk.Frame(frm)
    row_srt.grid(row=5, column=0, sticky="ew", pady=(0, 10))
    row_srt.grid_columnconfigure(0, weight=1)
    ent_srt = ttk.Entry(row_srt, textvariable=srt_var)
    ent_srt.grid(row=0, column=0, sticky="ew", padx=(0, 6))

    def pick_srt() -> None:
        initial = srt_var.get().strip()
        init_dir = str(Path(initial).parent) if initial and Path(initial).parent.is_dir() else str(
            default_input_dir()
        )
        p = filedialog.askopenfilename(
            title="SRT 자막 파일",
            initialdir=init_dir,
            filetypes=[("SRT", "*.srt"), ("모든 파일", "*.*")],
        )
        if p:
            srt_var.set(p)

    btn_srt = ttk.Button(row_srt, text="SRT 선택…", command=pick_srt)
    btn_srt.grid(row=0, column=1)
    browse_widgets.extend([ent_srt, btn_srt])

    frm.grid_columnconfigure(0, weight=1)

    row_target = ttk.Frame(frm)
    row_target.grid(row=6, column=0, sticky="ew", pady=(0, 8))
    ttk.Label(row_target, text="대상 파일:").pack(side=tk.LEFT)
    ttk.Label(row_target, textvariable=target_count_var).pack(side=tk.LEFT, padx=(6, 12))
    btn_scan = ttk.Button(row_target, text="대상 다시 확인", command=refresh_target_count)
    btn_scan.pack(side=tk.LEFT)
    browse_widgets.append(btn_scan)

    opts = ttk.Frame(frm)
    opts.grid(row=7, column=0, sticky="ew", pady=(0, 8))

    def on_opt_change() -> None:
        refresh_target_count()

    ttk.Checkbutton(
        opts, text="하위 폴더 포함", variable=recursive_var, command=on_opt_change
    ).pack(side=tk.LEFT)
    ttk.Checkbutton(
        opts,
        text="JPG 도 SRT 형식으로 재저장",
        variable=include_jpg_var,
        command=on_opt_change,
    ).pack(side=tk.LEFT, padx=(12, 0))
    ttk.Label(opts, text="JPEG 품질").pack(side=tk.LEFT, padx=(16, 4))
    ttk.Scale(opts, from_=60, to=95, orient=tk.HORIZONTAL, variable=quality_var, length=140).pack(
        side=tk.LEFT
    )
    ttk.Label(opts, textvariable=quality_var, width=3).pack(side=tk.LEFT, padx=(4, 0))

    prog = ttk.Progressbar(frm, mode="determinate", maximum=100)
    prog.grid(row=8, column=0, sticky="ew", pady=(4, 4))
    ttk.Label(frm, textvariable=status_var).grid(row=9, column=0, sticky="w")

    log = tk.Text(frm, height=10, wrap=tk.WORD, state=tk.DISABLED)
    log.grid(row=10, column=0, sticky="nsew", pady=(8, 0))
    frm.grid_rowconfigure(10, weight=1)

    def log_line(msg: str) -> None:
        log.configure(state=tk.NORMAL)
        log.insert(tk.END, msg + "\n")
        log.see(tk.END)
        log.configure(state=tk.DISABLED)

    btn_run: ttk.Button

    def set_busy(on: bool) -> None:
        state = tk.DISABLED if on else tk.NORMAL
        btn_run.configure(state=state)
        for w in browse_widgets:
            try:
                w.configure(state=state)
            except tk.TclError:
                pass

    def persist_dirs() -> None:
        try:
            save_gui_settings(
                input_dir=in_var.get().strip(),
                output_dir=out_var.get().strip(),
                srt_path=srt_var.get().strip(),
            )
        except OSError:
            pass

    def _resolve_srt_path() -> Path | None:
        raw = srt_var.get().strip()
        if not raw:
            return None
        p = Path(raw).resolve()
        return p if p.is_file() else None

    def run_convert() -> None:
        inp = Path(in_var.get().strip())
        out = Path(out_var.get().strip())
        if not inp.is_dir():
            messagebox.showerror("변환 대상", f"폴더가 없습니다:\n{inp}")
            return
        if not out_var.get().strip():
            messagebox.showwarning("저장 폴더", "저장 폴더를 지정하세요.")
            return
        out.mkdir(parents=True, exist_ok=True)
        q = max(60, min(95, int(quality_var.get())))
        persist_dirs()

        n_pre, _ = _count_targets(
            inp,
            recursive=bool(recursive_var.get()),
            include_jpg=bool(include_jpg_var.get()),
        )
        if n_pre == 0:
            messagebox.showwarning(
                "변환 대상",
                f"변환할 PNG/JPG 가 없습니다.\n\n대상: {inp.resolve()}",
            )
            return
        srt_p = _resolve_srt_path()
        if srt_var.get().strip() and srt_p is None:
            messagebox.showerror("SRT", f"SRT 파일을 찾을 수 없습니다:\n{srt_var.get()}")
            return

        def work() -> None:
            err: Exception | None = None
            results: list[ConvertResult] = []
            skipped: list[ConvertSkip] = []

            def on_prog(i: int, total: int, item: ConvertResult | ConvertSkip) -> None:
                pct = 0 if total <= 0 else int(100 * i / total)

                def ui() -> None:
                    prog.configure(value=pct)
                    if isinstance(item, ConvertResult):
                        saved = item.saved_bytes
                        status_var.set(
                            f"변환 중… {pct}% ({i}/{total}) — {item.output.name} "
                            f"({item.size_px[0]}×{item.size_px[1]}, -{saved // 1024}KB)"
                        )
                        note = f" · {item.match_note}" if item.match_note else ""
                        log_line(
                            f"[{item.output.name}] ← {item.source.name}{note} "
                            f"({item.bytes_before // 1024}KB → {item.bytes_after // 1024}KB)"
                        )
                    else:
                        log_line(f"건너뜀: {item.source.name} — {item.reason}")

                root.after(0, ui)

            try:
                results, skipped = convert_images(
                    inp,
                    out,
                    srt_path=srt_p,
                    recursive=bool(recursive_var.get()),
                    include_jpg=bool(include_jpg_var.get()),
                    quality=q,
                    on_progress=on_prog,
                )
            except Exception as e:
                err = e
                traceback.print_exc()

            def done() -> None:
                set_busy(False)
                prog.configure(value=100 if not err else 0)
                refresh_target_count()
                if err:
                    messagebox.showerror("오류", str(err))
                    status_var.set("오류")
                    return
                total_saved = sum(r.saved_bytes for r in results)
                status_var.set(
                    f"완료: {len(results)}개 저장, 건너뜀 {len(skipped)}개 "
                    f"(절약 {total_saved // 1024}KB) → {out.resolve()}"
                )
                messagebox.showinfo(
                    "완료",
                    f"{len(results)}개 → {out.resolve()}\n"
                    f"건너뜀: {len(skipped)}개\n"
                    f"용량 절약: 약 {total_saved // 1024} KB",
                )

            root.after(0, done)

        set_busy(True)
        prog.configure(value=0)
        log.configure(state=tk.NORMAL)
        log.delete("1.0", tk.END)
        log.configure(state=tk.DISABLED)
        status_var.set(f"변환 시작… 대상 {n_pre}개 파일")
        threading.Thread(target=work, daemon=True).start()

    row_btns = ttk.Frame(frm)
    row_btns.grid(row=11, column=0, sticky="ew", pady=(8, 0))
    btn_run = ttk.Button(row_btns, text="PNG → SRT_XXX.jpg 변환", command=run_convert)
    btn_run.pack(side=tk.LEFT)

    def on_close() -> None:
        persist_dirs()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    refresh_target_count()
    root.mainloop()
