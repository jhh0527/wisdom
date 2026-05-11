"""TTS용 텍스트 파일 선택·음성 변환 GUI (Tkinter)."""

from __future__ import annotations

import asyncio
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, font as tkfont, messagebox, ttk

from txt2audio import __version__
from txt2audio.backends.chatterbox import (
    ChatterboxHttpBackend,
    ChatterboxLocalBackend,
    chatterbox_local_prereq_message,
)
from txt2audio.backends.edge import EdgeTtsBackend, list_voices as list_edge_voices

# (표시 이름, 내부 id)
_BACKEND_OPTIONS: tuple[tuple[str, str], ...] = (
    ("Edge TTS (Microsoft 온라인)", "edge"),
    ("Chatterbox 로컬 설치 (Python·GPU)", "chatterbox_local"),
    ("Chatterbox HTTP (로컬 서버)", "chatterbox_http"),
)
_BACKEND_LABELS: tuple[str, ...] = tuple(x[0] for x in _BACKEND_OPTIONS)
_BACKEND_LABEL_TO_ID: dict[str, str] = {a: b for a, b in _BACKEND_OPTIONS}


def _project_root_dir() -> Path:
    """tts_audio_pipeline 루트 (dist 안의 exe → 상위 폴더)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent.parent
    return Path(__file__).resolve().parent.parent


def _chatterbox_venv_python() -> Path | None:
    p = _project_root_dir() / ".venv_chatterbox" / "Scripts" / "python.exe"
    return p if p.is_file() else None


def _default_font() -> tuple[str, int]:
    try:
        f = tkfont.nametofont("TkDefaultFont")
        return (f.actual("family"), max(10, int(f.actual("size"))))
    except tk.TclError:
        return ("맑은 고딕", 10)


def main() -> None:
    root = tk.Tk()
    root.title(f"txt2audio GUI {__version__}")
    root.minsize(620, 420)
    root.geometry("720x440")

    fam, sz = _default_font()
    root.option_add("*Font", (fam, sz))

    in_path = tk.StringVar()
    out_path = tk.StringVar()
    backend_var = tk.StringVar(value=_BACKEND_LABELS[0])
    voice_var = tk.StringVar(value="ko-KR-SunHiNeural")
    cb_model_var = tk.StringVar(value="multilingual")
    cb_lang_var = tk.StringVar(value="ko")
    voice_prompt_var = tk.StringVar()
    http_base_var = tk.StringVar(value="http://127.0.0.1:8000")
    http_path_var = tk.StringVar(value="/tts")
    http_key_var = tk.StringVar()
    http_json_var = tk.BooleanVar(value=False)
    status_var = tk.StringVar(value="대기 중")

    frm = ttk.Frame(root, padding=10)
    frm.grid(row=0, column=0, sticky="nsew")
    root.grid_rowconfigure(0, weight=1)
    root.grid_columnconfigure(0, weight=1)

    ttk.Label(frm, text="입력 텍스트 (UTF-8)").grid(row=0, column=0, sticky="w")
    row_in = ttk.Frame(frm)
    row_in.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(0, 8))
    ent_in = ttk.Entry(row_in, textvariable=in_path)
    ent_in.grid(row=0, column=0, sticky="ew", padx=(0, 6))
    row_in.grid_columnconfigure(0, weight=1)

    def pick_input() -> None:
        p = filedialog.askopenfilename(
            title="TTS용 텍스트 파일",
            filetypes=[("텍스트", "*.txt"), ("모든 파일", "*.*")],
        )
        if p:
            in_path.set(p)
            if not out_path.get().strip():
                base = Path(p).stem
                out_path.set(str(Path(p).with_name(f"{base}.mp3")))

    btn_pick_in = ttk.Button(row_in, text="파일 선택…", command=pick_input)
    btn_pick_in.grid(row=0, column=1)

    ttk.Label(frm, text="출력 음성 파일").grid(row=2, column=0, sticky="w")
    row_out = ttk.Frame(frm)
    row_out.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(0, 8))
    ent_out = ttk.Entry(row_out, textvariable=out_path)
    ent_out.grid(row=0, column=0, sticky="ew", padx=(0, 6))
    row_out.grid_columnconfigure(0, weight=1)

    def pick_output() -> None:
        initial = out_path.get().strip() or "output.mp3"
        p = filedialog.asksaveasfilename(
            title="저장할 음성 파일",
            defaultextension=".mp3",
            initialfile=Path(initial).name,
            filetypes=[
                ("MP3", "*.mp3"),
                ("WAV", "*.wav"),
                ("모든 파일", "*.*"),
            ],
        )
        if p:
            out_path.set(p)

    btn_pick_out = ttk.Button(row_out, text="저장 위치…", command=pick_output)
    btn_pick_out.grid(row=0, column=1)

    ttk.Label(frm, text="백엔드 (음성 엔진)").grid(row=4, column=0, sticky="w", pady=(4, 0))
    backend_cb = ttk.Combobox(
        frm,
        textvariable=backend_var,
        values=_BACKEND_LABELS,
        width=40,
        state="readonly",
    )
    backend_cb.grid(row=5, column=0, columnspan=2, sticky="w", pady=(0, 6))

    edge_opts = ttk.LabelFrame(frm, text="Edge TTS", padding=6)
    ttk.Label(edge_opts, text="목소리").grid(row=0, column=0, sticky="w")
    voice_cb = ttk.Combobox(edge_opts, textvariable=voice_var, width=46, state="readonly")
    voice_cb.grid(row=1, column=0, columnspan=2, sticky="ew")

    cb_local_opts = ttk.LabelFrame(frm, text="Chatterbox 로컬 설치 (venv)", padding=6)
    ttk.Label(cb_local_opts, text="모델").grid(row=0, column=0, sticky="w")
    ttk.Combobox(
        cb_local_opts,
        textvariable=cb_model_var,
        values=("multilingual", "english", "turbo"),
        width=18,
        state="readonly",
    ).grid(row=0, column=1, sticky="w", padx=(8, 0))
    ttk.Label(cb_local_opts, text="language_id (다국어)").grid(row=1, column=0, sticky="w", pady=(6, 0))
    ttk.Entry(cb_local_opts, textvariable=cb_lang_var, width=10).grid(row=1, column=1, sticky="w", padx=(8, 0), pady=(6, 0))
    ttk.Label(cb_local_opts, text="참조 음성 (선택, 복제용)").grid(row=2, column=0, sticky="w", pady=(6, 0))
    row_prompt = ttk.Frame(cb_local_opts)
    row_prompt.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(4, 0))
    ent_prompt = ttk.Entry(row_prompt, textvariable=voice_prompt_var)
    ent_prompt.grid(row=0, column=0, sticky="ew", padx=(0, 6))
    row_prompt.grid_columnconfigure(0, weight=1)

    def pick_prompt() -> None:
        p = filedialog.askopenfilename(
            title="참조 음성 (WAV 등)",
            filetypes=[("오디오", "*.wav *.mp3 *.flac"), ("모든 파일", "*.*")],
        )
        if p:
            voice_prompt_var.set(p)

    ttk.Button(row_prompt, text="찾기…", command=pick_prompt).grid(row=0, column=1)
    ttk.Label(
        cb_local_opts,
        text="Turbo 모델은 참조 음성이 필수입니다. MP3 출력 시 ffmpeg가 필요합니다.",
        wraplength=640,
    ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(8, 0))

    cb_http_opts = ttk.LabelFrame(frm, text="Chatterbox (HTTP)", padding=6)
    ttk.Label(cb_http_opts, text="베이스 URL").grid(row=0, column=0, sticky="w")
    ttk.Entry(cb_http_opts, textvariable=http_base_var, width=50).grid(row=0, column=1, sticky="ew", padx=(8, 0))
    ttk.Label(cb_http_opts, text="경로").grid(row=1, column=0, sticky="w", pady=(6, 0))
    ttk.Entry(cb_http_opts, textvariable=http_path_var, width=24).grid(row=1, column=1, sticky="w", padx=(8, 0), pady=(6, 0))
    ttk.Label(cb_http_opts, text="Bearer 토큰 (선택)").grid(row=2, column=0, sticky="w", pady=(6, 0))
    ttk.Entry(cb_http_opts, textvariable=http_key_var, width=50, show="*").grid(row=2, column=1, sticky="ew", padx=(8, 0), pady=(6, 0))
    ttk.Checkbutton(cb_http_opts, text="JSON 요청 (audio_prompt_base64)", variable=http_json_var).grid(
        row=3, column=0, columnspan=2, sticky="w", pady=(6, 0)
    )
    ttk.Label(
        cb_http_opts,
        text="HTTP 사용 시: run_chatterbox_server.bat 로 서버를 띄운 뒤 변환하세요. "
        "직접 합성은 백엔드에서 「Chatterbox 로컬 설치」를 고르거나 Chatterbox_로컬_GUI.bat 을 실행하세요. "
        "모델·언어·참조 음성은 위 로컬 패널과 동일합니다.",
        wraplength=640,
    ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(6, 0))
    cb_http_opts.grid_columnconfigure(1, weight=1)

    edge_opts.grid(row=6, column=0, columnspan=3, sticky="ew", pady=(0, 6))
    cb_local_opts.grid(row=6, column=0, columnspan=3, sticky="ew", pady=(0, 6))
    cb_http_opts.grid(row=7, column=0, columnspan=3, sticky="ew", pady=(0, 6))
    edge_opts.grid_remove()
    cb_local_opts.grid_remove()
    cb_http_opts.grid_remove()

    prog = ttk.Progressbar(frm, mode="determinate", maximum=100, value=0, length=320)
    prog.grid(row=10, column=0, columnspan=2, sticky="ew", pady=(0, 6))

    log = tk.Text(frm, height=5, wrap=tk.WORD, state=tk.DISABLED)
    log.grid(row=11, column=0, columnspan=3, sticky="nsew", pady=(4, 0))
    frm.grid_rowconfigure(11, weight=1)

    def log_line(msg: str) -> None:
        log.configure(state=tk.NORMAL)
        log.insert(tk.END, msg + "\n")
        log.see(tk.END)
        log.configure(state=tk.DISABLED)

    def set_busy(on: bool) -> None:
        btn_convert.configure(state=tk.DISABLED if on else tk.NORMAL)
        btn_pick_in.configure(state=tk.DISABLED if on else tk.NORMAL)
        btn_pick_out.configure(state=tk.DISABLED if on else tk.NORMAL)
        backend_cb.configure(state=tk.DISABLED if on else "readonly")
        voice_cb.configure(state=tk.DISABLED if on else "readonly")
        ent_prompt.configure(state=tk.DISABLED if on else tk.NORMAL)
        if on:
            prog.configure(mode="determinate", maximum=100, value=0)
        else:
            prog.configure(value=0)
            apply_backend_ui()

    def _backend_id() -> str:
        return _BACKEND_LABEL_TO_ID.get(backend_var.get().strip(), "edge")

    def apply_backend_ui() -> None:
        b = _backend_id()
        edge_opts.grid_remove()
        cb_local_opts.grid_remove()
        cb_http_opts.grid_remove()
        if b == "edge":
            edge_opts.grid(row=6, column=0, columnspan=3, sticky="ew", pady=(0, 6))
        elif b == "chatterbox_local":
            cb_local_opts.grid(row=6, column=0, columnspan=3, sticky="ew", pady=(0, 6))
        else:
            cb_local_opts.grid(row=6, column=0, columnspan=3, sticky="ew", pady=(0, 6))
            cb_http_opts.grid(row=7, column=0, columnspan=3, sticky="ew", pady=(0, 6))

    def on_backend_change(_evt: object | None = None) -> None:
        apply_backend_ui()

    backend_cb.bind("<<ComboboxSelected>>", on_backend_change)

    voices_loaded = {"ok": False}

    def load_voices_bg() -> None:
        def work() -> None:
            try:
                rows = asyncio.run(list_edge_voices(language_prefix="ko"))
                names = [r["ShortName"] for r in rows]
                if not names:
                    rows = asyncio.run(list_edge_voices(language_prefix=None))
                    names = [r["ShortName"] for r in rows[:80]]
            except Exception as e:
                root.after(0, lambda: messagebox.showerror("음성 목록", str(e)))
                return

            def apply() -> None:
                voice_cb.configure(values=names)
                cur = voice_var.get()
                if cur in names:
                    voice_var.set(cur)
                elif names:
                    voice_var.set(names[0])
                voices_loaded["ok"] = True
                status_var.set("준비됨")

            root.after(0, apply)

        status_var.set("음성 목록 불러오는 중…")
        threading.Thread(target=work, daemon=True).start()

    def convert_bg() -> None:
        ip = Path(in_path.get().strip())
        op = Path(out_path.get().strip())
        if not ip.is_file():
            messagebox.showwarning("입력", "텍스트 파일을 선택하세요.")
            return
        if not str(op).strip():
            messagebox.showwarning("출력", "저장할 음성 파일 경로를 지정하세요.")
            return

        text = ip.read_text(encoding="utf-8", errors="replace")
        if not text.strip():
            messagebox.showwarning("내용", "파일 내용이 비어 있습니다.")
            return

        bid = _backend_id()
        if bid == "edge":
            if op.suffix.lower() != ".mp3":
                if not messagebox.askyesno(
                    "확장자",
                    "MP3가 아닙니다. 그래도 저장할까요?\n(긴 원고는 .mp3 권장)",
                ):
                    return
            voice = voice_var.get().strip()
            if not voice:
                messagebox.showwarning("목소리", "목소리를 선택하세요.")
                return
        elif bid == "chatterbox_local":
            variant = cb_model_var.get().strip()
            if variant == "turbo":
                pp = Path(voice_prompt_var.get().strip()) if voice_prompt_var.get().strip() else None
                if pp is None or not pp.is_file():
                    messagebox.showwarning("참조 음성", "Chatterbox-Turbo는 참조 음성 파일이 필요합니다.")
                    return
        elif bid == "chatterbox_http":
            if not http_base_var.get().strip():
                messagebox.showwarning("URL", "HTTP 베이스 URL을 입력하세요.")
                return

        if bid == "chatterbox_local" and getattr(sys, "frozen", False):
            vpy = _chatterbox_venv_python()
            if vpy is not None:
                if messagebox.askyesno(
                    "Chatterbox 로컬 설치",
                    "지금 실행 중인 파일은 단일 exe라 PyTorch·Chatterbox가 들어 있지 않습니다.\n\n"
                    f"가상환경 Python을 찾았습니다:\n{vpy}\n\n"
                    "이 경로로 「로컬 설치용 GUI」를 새로 띄울까요?\n"
                    "(아니요 → 변환 취소)",
                ):
                    import subprocess

                    subprocess.Popen(
                        [str(vpy), "-m", "txt2audio", "--gui"],
                        cwd=str(_project_root_dir()),
                    )
                    messagebox.showinfo(
                        "실행",
                        "로컬 GUI 창을 띄웠습니다. 그 창에서 백엔드를\n"
                        f"「{_BACKEND_LABELS[1]}」로 두고 변환하세요.",
                    )
                return
            pre = chatterbox_local_prereq_message()
            if pre:
                messagebox.showerror("Chatterbox 로컬", pre)
                return

        if bid == "chatterbox_local":
            pre = chatterbox_local_prereq_message()
            if pre:
                messagebox.showerror("Chatterbox 로컬", pre)
                return

        def work() -> None:
            err: Exception | None = None

            def on_progress(done: int, total: int) -> None:
                pct = 0 if total <= 0 else min(100, int(100 * done / total))

                def ui() -> None:
                    prog.configure(value=pct)
                    status_var.set(f"변환 중… {pct}% ({done}/{total})")

                root.after(0, ui)

            try:
                if bid == "edge":
                    backend = EdgeTtsBackend(voice_var.get().strip())
                    asyncio.run(backend.synthesize_file(text, op, on_progress=on_progress))
                elif bid == "chatterbox_local":
                    pp = Path(voice_prompt_var.get().strip()) if voice_prompt_var.get().strip() else None
                    prompt_path = pp if (pp is not None and pp.is_file()) else None
                    v = cb_model_var.get().strip() or "multilingual"
                    backend = ChatterboxLocalBackend(
                        variant=v,  # type: ignore[arg-type]
                        device="auto",
                        language_id=cb_lang_var.get().strip() or "ko",
                        audio_prompt_path=prompt_path,
                    )
                    asyncio.run(backend.synthesize_file(text, op, on_progress=on_progress))
                else:
                    pp = Path(voice_prompt_var.get().strip()) if voice_prompt_var.get().strip() else None
                    prompt_path = pp if (pp is not None and pp.is_file()) else None
                    backend = ChatterboxHttpBackend(
                        http_base_var.get().strip().rstrip("/"),
                        path=http_path_var.get().strip() or "/tts",
                        language_id=cb_lang_var.get().strip() or "ko",
                        model_variant=cb_model_var.get().strip() or "multilingual",
                        audio_prompt_path=prompt_path,
                        api_key=http_key_var.get().strip(),
                        prefer_json=bool(http_json_var.get()),
                    )
                    asyncio.run(backend.synthesize_file(text, op, on_progress=on_progress))
            except Exception as e:
                err = e

            def done() -> None:
                set_busy(False)
                if err:
                    log_line(f"오류: {err}")
                    messagebox.showerror("변환 실패", str(err))
                    status_var.set("오류")
                else:
                    log_line(f"완료: {op.resolve()}")
                    messagebox.showinfo("완료", f"저장했습니다.\n{op.resolve()}")
                    status_var.set("완료")

            root.after(0, done)

        set_busy(True)
        if bid == "edge":
            status_var.set("변환 중… (인터넷 필요)")
        elif bid == "chatterbox_local":
            status_var.set("변환 중… (Chatterbox 로컬, GPU/CPU)")
        else:
            status_var.set("변환 중… (Chatterbox HTTP)")
        log_line("변환 시작…")
        threading.Thread(target=work, daemon=True).start()

    row_btn = ttk.Frame(frm)
    row_btn.grid(row=12, column=0, columnspan=3, sticky="ew", pady=(8, 0))
    btn_convert = ttk.Button(row_btn, text="음성으로 변환", command=convert_bg)
    btn_convert.pack(side=tk.LEFT)
    ttk.Label(row_btn, textvariable=status_var).pack(side=tk.LEFT, padx=12)

    apply_backend_ui()
    load_voices_bg()
    root.mainloop()
