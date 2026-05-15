"""이미지 프롬프트 → 그림 변환 GUI (Tkinter)."""

from __future__ import annotations

import threading
import tkinter as tk
import traceback
from pathlib import Path
from tkinter import filedialog, font as tkfont, messagebox, ttk

from prompt2image import __version__
from prompt2image.backends.openai_image import OpenAIImageBackend
from prompt2image.backends.pollinations import PollinationsBackend
from prompt2image.generator import generate_scenes
from prompt2image.prompt_parser import Scene, parse_markdown_file


def _default_font() -> tuple[str, int]:
    try:
        f = tkfont.nametofont("TkDefaultFont")
        return (f.actual("family"), max(10, int(f.actual("size"))))
    except tk.TclError:
        return ("맑은 고딕", 10)


def main() -> None:
    root = tk.Tk()
    root.title(f"4_srtToImage GUI {__version__}")
    root.minsize(720, 520)
    root.geometry("840x600")

    fam, sz = _default_font()
    root.option_add("*Font", (fam, sz))

    state: dict[str, object] = {
        "scenes": [],
        "stop": False,
    }
    md_path = tk.StringVar()
    out_dir = tk.StringVar()
    backend_var = tk.StringVar(value="pollinations")
    model_var = tk.StringVar(value="flux")
    size_var = tk.StringVar(value="1024x1024")
    status_var = tk.StringVar(value="대기 중 — 마크다운 파일을 선택하세요.")

    frm = ttk.Frame(root, padding=10)
    frm.grid(row=0, column=0, sticky="nsew")
    root.grid_rowconfigure(0, weight=1)
    root.grid_columnconfigure(0, weight=1)

    # 입력 마크다운 행
    ttk.Label(frm, text="이미지 프롬프트 마크다운(.md)").grid(row=0, column=0, sticky="w")
    row1 = ttk.Frame(frm)
    row1.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(0, 8))
    row1.grid_columnconfigure(0, weight=1)
    ent_md = ttk.Entry(row1, textvariable=md_path)
    ent_md.grid(row=0, column=0, sticky="ew", padx=(0, 6))

    # 저장 폴더 행
    ttk.Label(frm, text="저장 폴더").grid(row=2, column=0, sticky="w")
    row2 = ttk.Frame(frm)
    row2.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(0, 8))
    row2.grid_columnconfigure(0, weight=1)
    ent_out = ttk.Entry(row2, textvariable=out_dir)
    ent_out.grid(row=0, column=0, sticky="ew", padx=(0, 6))

    # 백엔드 / 모델 / 사이즈
    row3 = ttk.Frame(frm)
    row3.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(0, 8))
    ttk.Label(row3, text="백엔드").grid(row=0, column=0, padx=(0, 4))
    cb_backend = ttk.Combobox(
        row3,
        textvariable=backend_var,
        values=("pollinations", "openai"),
        state="readonly",
        width=14,
    )
    cb_backend.grid(row=0, column=1, padx=(0, 12))
    ttk.Label(row3, text="모델").grid(row=0, column=2, padx=(0, 4))
    ent_model = ttk.Entry(row3, textvariable=model_var, width=18)
    ent_model.grid(row=0, column=3, padx=(0, 12))
    ttk.Label(row3, text="크기").grid(row=0, column=4, padx=(0, 4))
    ent_size = ttk.Entry(row3, textvariable=size_var, width=12)
    ent_size.grid(row=0, column=5)

    def on_backend_change(_e=None) -> None:
        if backend_var.get() == "openai":
            model_var.set("gpt-image-1")
        else:
            model_var.set("flux")

    cb_backend.bind("<<ComboboxSelected>>", on_backend_change)

    # 장면 목록 (다중 선택)
    ttk.Label(frm, text="장면 (Ctrl/Shift로 다중 선택)").grid(row=5, column=0, sticky="w")
    row_tree = ttk.Frame(frm)
    row_tree.grid(row=6, column=0, columnspan=3, sticky="nsew", pady=(0, 6))
    frm.grid_rowconfigure(6, weight=1)
    row_tree.grid_columnconfigure(0, weight=1)
    row_tree.grid_rowconfigure(0, weight=1)

    columns = ("number", "title", "summary")
    tree = ttk.Treeview(row_tree, columns=columns, show="headings", selectmode="extended")
    tree.heading("number", text="번호")
    tree.heading("title", text="제목")
    tree.heading("summary", text="요지")
    tree.column("number", width=60, anchor="center", stretch=False)
    tree.column("title", width=240, anchor="w")
    tree.column("summary", width=360, anchor="w")
    tree.grid(row=0, column=0, sticky="nsew")
    sb = ttk.Scrollbar(row_tree, orient="vertical", command=tree.yview)
    sb.grid(row=0, column=1, sticky="ns")
    tree.configure(yscrollcommand=sb.set)

    # 진행률 / 상태
    prog = ttk.Progressbar(frm, mode="determinate", maximum=100, value=0, length=420)
    prog.grid(row=7, column=0, columnspan=3, sticky="ew", pady=(8, 4))
    lbl_status = ttk.Label(frm, textvariable=status_var)
    lbl_status.grid(row=8, column=0, columnspan=3, sticky="w")

    # 로그
    log = tk.Text(frm, height=6, wrap=tk.WORD, state=tk.DISABLED)
    log.grid(row=9, column=0, columnspan=3, sticky="nsew", pady=(6, 0))
    frm.grid_rowconfigure(9, weight=0)

    def log_line(msg: str) -> None:
        log.configure(state=tk.NORMAL)
        log.insert(tk.END, msg + "\n")
        log.see(tk.END)
        log.configure(state=tk.DISABLED)

    # 파일 선택
    def pick_md() -> None:
        p = filedialog.askopenfilename(
            title="이미지 프롬프트 마크다운 선택",
            filetypes=[("Markdown", "*.md"), ("모든 파일", "*.*")],
        )
        if p:
            md_path.set(p)
            load_md(Path(p))

    def pick_out() -> None:
        p = filedialog.askdirectory(title="저장 폴더 선택")
        if p:
            out_dir.set(p)

    btn_pick_md = ttk.Button(row1, text="파일 선택…", command=pick_md)
    btn_pick_md.grid(row=0, column=1)
    btn_pick_out = ttk.Button(row2, text="폴더 선택…", command=pick_out)
    btn_pick_out.grid(row=0, column=1)

    def load_md(path: Path) -> None:
        try:
            scenes = parse_markdown_file(path)
        except Exception as e:
            messagebox.showerror("마크다운 파싱", str(e))
            return
        for iid in tree.get_children():
            tree.delete(iid)
        state["scenes"] = scenes
        for s in scenes:
            tree.insert("", tk.END, iid=s.number, values=(s.number, s.display, s.summary))
        if not out_dir.get().strip():
            out_dir.set(str(path.parent / "assets"))
        status_var.set(f"장면 {len(scenes)}개 — 변환할 장면을 선택하세요.")

    def select_all() -> None:
        for iid in tree.get_children():
            tree.selection_add(iid)

    def select_none() -> None:
        tree.selection_remove(tree.selection())

    row_btns = ttk.Frame(frm)
    row_btns.grid(row=10, column=0, columnspan=3, sticky="ew", pady=(8, 0))
    ttk.Button(row_btns, text="모두 선택", command=select_all).pack(side=tk.LEFT)
    ttk.Button(row_btns, text="선택 해제", command=select_none).pack(side=tk.LEFT, padx=(6, 12))
    btn_run = ttk.Button(row_btns, text="이미지 생성", command=lambda: run_bg())
    btn_run.pack(side=tk.LEFT)
    btn_stop = ttk.Button(row_btns, text="중지", command=lambda: state.update(stop=True))
    btn_stop.pack(side=tk.LEFT, padx=(6, 0))
    btn_stop.configure(state=tk.DISABLED)

    def set_busy(on: bool) -> None:
        for w in (btn_pick_md, btn_pick_out, btn_run, ent_model, ent_size):
            w.configure(state=tk.DISABLED if on else tk.NORMAL)
        cb_backend.configure(state=tk.DISABLED if on else "readonly")
        btn_stop.configure(state=tk.NORMAL if on else tk.DISABLED)
        if on:
            prog.configure(value=0)
            state["stop"] = False

    def make_backend():
        if backend_var.get() == "openai":
            model = model_var.get().strip() or "gpt-image-1"
            size = size_var.get().strip() or "1024x1024"
            return OpenAIImageBackend(model=model, size=size)
        model = model_var.get().strip() or "flux"
        try:
            w, h = (int(x) for x in size_var.get().lower().split("x"))
        except Exception:
            w, h = 1024, 1024
        return PollinationsBackend(model=model, width=w, height=h)

    def run_bg() -> None:
        if not state["scenes"]:
            messagebox.showwarning("입력", "마크다운을 먼저 불러오세요.")
            return
        sel = tree.selection()
        if not sel:
            messagebox.showwarning("선택", "변환할 장면을 1개 이상 선택하세요.")
            return
        out = out_dir.get().strip()
        if not out:
            messagebox.showwarning("저장", "저장 폴더를 지정하세요.")
            return

        chosen: list[Scene] = [s for s in state["scenes"] if s.number in sel]
        out_path = Path(out)
        try:
            backend = make_backend()
        except Exception as e:
            messagebox.showerror("백엔드", str(e))
            return

        def on_progress(i: int, total: int, scene, path, err) -> None:
            pct = 0 if total <= 0 else int(100 * i / total)

            def ui() -> None:
                prog.configure(value=pct)
                if err is None and path is not None:
                    status_var.set(f"변환 중… {pct}% ({i}/{total}) — 장면 {scene.number}")
                    log_line(f"[{pct:>3}%] [{scene.number}] 저장: {path}")
                else:
                    status_var.set(f"변환 중… {pct}% ({i}/{total}) — 장면 {scene.number} 실패")
                    log_line(f"[{pct:>3}%] [{scene.number}] 실패: {err}")

            root.after(0, ui)

        def work() -> None:
            err: Exception | None = None
            saved: list[Path] = []
            try:
                saved = generate_scenes(
                    chosen,
                    backend,
                    out_path,
                    on_progress=on_progress,
                    stop_check=lambda: bool(state.get("stop")),
                )
            except Exception as e:
                err = e
                traceback.print_exc()

            def done() -> None:
                set_busy(False)
                if err:
                    log_line(f"오류: {err}")
                    messagebox.showerror("변환 실패", str(err))
                    status_var.set("오류")
                else:
                    log_line(f"완료: {len(saved)} / {len(chosen)} 장면 저장됨 → {out_path.resolve()}")
                    status_var.set(f"완료: {len(saved)} / {len(chosen)}")
                    if saved:
                        messagebox.showinfo(
                            "완료",
                            f"{len(saved)} / {len(chosen)} 장면을 저장했습니다.\n{out_path.resolve()}",
                        )

            root.after(0, done)

        set_busy(True)
        status_var.set(f"변환 중… 0% (0/{len(chosen)})")
        log_line(f"시작: {len(chosen)} 장면, 백엔드={backend_var.get()}, 모델={model_var.get()}")
        threading.Thread(target=work, daemon=True).start()

    # 기본 마크다운 자동 추정
    default_md = Path(__file__).resolve().parents[2] / "로스차일드_이미지프롬프트.md"
    if default_md.is_file():
        md_path.set(str(default_md))
        load_md(default_md)

    root.mainloop()
