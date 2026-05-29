"""Video Studio — Tkinter GUI."""

from __future__ import annotations

import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, font as tkfont, messagebox, scrolledtext, ttk

from videostudio import __version__
from videostudio import ffmpeg_tools as ff
from videostudio.subtitle_import import document_to_srt


def _default_font() -> tuple[str, int]:
    try:
        f = tkfont.nametofont("TkDefaultFont")
        return (f.actual("family"), max(10, int(f.actual("size"))))
    except tk.TclError:
        return ("맑은 고딕", 10)


def _parse_time(s: str) -> float:
    s = s.strip()
    if not s:
        return 0.0
    if ":" in s:
        parts = s.replace(",", ".").split(":")
        nums = [float(x) for x in parts]
        while len(nums) < 3:
            nums.insert(0, 0.0)
        h, m, sec = nums[-3], nums[-2], nums[-1]
        return h * 3600 + m * 60 + sec
    return float(s.replace(",", "."))


class VideoStudioApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"Video Studio {__version__}")
        self.minsize(720, 540)
        self.geometry("860x620")
        fam, sz = _default_font()
        self.option_add("*Font", (fam, sz))

        self._subtitle_path: Path | None = None

        nb = ttk.Notebook(self)
        nb.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        tab_video = ttk.Frame(nb, padding=8)
        tab_sub = ttk.Frame(nb, padding=8)
        tab_audio = ttk.Frame(nb, padding=8)
        nb.add(tab_video, text="영상")
        nb.add(tab_sub, text="자막(SRT)")
        nb.add(tab_audio, text="음성 추출·교체")

        self._build_video_tab(tab_video)
        self._build_subtitle_tab(tab_sub)
        self._build_audio_tab(tab_audio)

        self.log = scrolledtext.ScrolledText(self, height=8, wrap=tk.WORD, state=tk.DISABLED)
        self.log.pack(fill=tk.X, padx=8, pady=(0, 8))

        bar = ttk.Frame(self)
        bar.pack(fill=tk.X, padx=8, pady=(0, 6))
        ff_ok = ff.ffmpeg_path() is not None
        ttk.Label(
            bar,
            text=(
                "FFmpeg: 사용 가능"
                if ff_ok
                else "FFmpeg: 없음 — wisdom/tools/ffmpeg/bin 또는 PATH를 확인하세요"
            ),
            foreground="#063" if ff_ok else "#a00",
        ).pack(side=tk.LEFT)
        ttk.Button(bar, text="로그 지우기", command=self._clear_log).pack(side=tk.RIGHT)

    def _clear_log(self) -> None:
        self.log.configure(state=tk.NORMAL)
        self.log.delete("1.0", tk.END)
        self.log.configure(state=tk.DISABLED)

    def _log(self, msg: str) -> None:
        self.log.configure(state=tk.NORMAL)
        self.log.insert(tk.END, msg + "\n")
        self.log.see(tk.END)
        self.log.configure(state=tk.DISABLED)

    def _run_bg(self, title: str, fn) -> None:
        def work() -> None:
            err: str | None = None
            try:
                fn()
            except Exception as e:
                err = str(e)

            def done() -> None:
                if err:
                    self._log(f"[오류] {err}")
                    messagebox.showerror(title, err)
                else:
                    self._log(f"[완료] {title}")

            self.after(0, done)

        self._log(f"[시작] {title}…")
        threading.Thread(target=work, daemon=True).start()

    # --- 영상 탭 ---
    def _build_video_tab(self, f: ttk.Frame) -> None:
        r = 0
        ttk.Label(f, text="※ 입력·출력 경로는 UTF-8을 권장합니다. 한글 경로는 FFmpeg·자막 필터에서 실패할 수 있습니다.").grid(
            row=r, column=0, columnspan=3, sticky="w", pady=(0, 8)
        )
        r += 1

        self.v_in = tk.StringVar()
        ttk.Label(f, text="입력 영상").grid(row=r, column=0, sticky="w")
        ttk.Entry(f, textvariable=self.v_in, width=70).grid(row=r, column=1, sticky="ew", padx=4)
        ttk.Button(f, text="찾기…", command=self._pick_video).grid(row=r, column=2)
        r += 1

        self.v_out_trim = tk.StringVar()
        ttk.Label(f, text="출력 (자르기·자막)").grid(row=r, column=0, sticky="w")
        ttk.Entry(f, textvariable=self.v_out_trim, width=70).grid(row=r, column=1, sticky="ew", padx=4)
        ttk.Button(f, text="저장…", command=lambda: self._save_as(self.v_out_trim, [("MP4", "*.mp4")])).grid(row=r, column=2)
        r += 1

        self.v_ss = tk.StringVar(value="0")
        self.v_dur = tk.StringVar(value="")
        ttk.Label(f, text="시작 (초 또는 0:05)").grid(row=r, column=0, sticky="w")
        ttk.Entry(f, textvariable=self.v_ss, width=14).grid(row=r, column=1, sticky="w", padx=4)
        r += 1
        ttk.Label(f, text="길이(비우면 끝까지 초)").grid(row=r, column=0, sticky="w")
        ttk.Entry(f, textvariable=self.v_dur, width=14).grid(row=r, column=1, sticky="w", padx=4)
        r += 1

        bf = ttk.Frame(f)
        bf.grid(row=r, column=0, columnspan=3, sticky="w", pady=8)
        ttk.Button(bf, text="구간 자르기(무손실 copy)", command=self._do_trim).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(bf, text="자막 번인(MP4+H.264 재인코)", command=self._do_burn).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(bf, text="입력 영상 길이(ffprobe)", command=self._do_probe_duration).pack(side=tk.LEFT)

        self.v_srt = tk.StringVar()
        r += 1
        ttk.Label(f, text="SRT 파일").grid(row=r, column=0, sticky="w")
        ttk.Entry(f, textvariable=self.v_srt, width=70).grid(row=r, column=1, sticky="ew", padx=4)
        ttk.Button(f, text="찾기…", command=lambda: self._pick_file(self.v_srt, [("SRT", "*.srt")])).grid(row=r, column=2)
        r += 1

        ttk.Separator(f, orient=tk.HORIZONTAL).grid(row=r, column=0, columnspan=3, sticky="ew", pady=12)
        r += 1
        ttk.Label(f, text="여러 영상 이어붙이기 (concat)").grid(row=r, column=0, columnspan=3, sticky="w")
        r += 1
        self.concat_list = tk.Listbox(f, height=5, width=90)
        self.concat_list.grid(row=r, column=0, columnspan=2, sticky="ew", padx=(0, 4))
        cf = ttk.Frame(f)
        cf.grid(row=r, column=2, sticky="ns")
        ttk.Button(cf, text="파일 추가", command=self._concat_add).pack(fill=tk.X)
        ttk.Button(cf, text="선택 제거", command=self._concat_remove).pack(fill=tk.X, pady=4)
        r += 1
        self.v_out_concat = tk.StringVar()
        ttk.Label(f, text="출력 이어붙이기").grid(row=r, column=0, sticky="w")
        ttk.Entry(f, textvariable=self.v_out_concat, width=70).grid(row=r, column=1, sticky="ew", padx=4)
        ttk.Button(f, text="저장…", command=lambda: self._save_as(self.v_out_concat, [("MP4", "*.mp4")])).grid(row=r, column=2)
        r += 1
        ttk.Button(f, text="이어붙이기 실행 (-c copy)", command=self._do_concat).grid(row=r, column=0, sticky="w", pady=6)

        f.grid_columnconfigure(1, weight=1)

    def _pick_video(self) -> None:
        p = filedialog.askopenfilename(filetypes=[("영상", "*.mp4 *.mkv *.mov *.webm"), ("모든 파일", "*.*")])
        if p:
            self.v_in.set(p)

    def _pick_file(self, var: tk.StringVar, fts: list[tuple[str, str]]) -> None:
        p = filedialog.askopenfilename(filetypes=fts)
        if p:
            var.set(p)

    def _save_as(self, var: tk.StringVar, fts: list[tuple[str, str]]) -> None:
        p = filedialog.asksaveasfilename(defaultextension=".mp4", filetypes=fts)
        if p:
            var.set(p)

    def _do_trim(self) -> None:
        ip = Path(self.v_in.get().strip())
        op = Path(self.v_out_trim.get().strip())
        if not ip.is_file():
            messagebox.showwarning("입력", "입력 영상을 선택하세요.")
            return
        if not str(op):
            messagebox.showwarning("출력", "출력 경로를 지정하세요.")
            return
        start = _parse_time(self.v_ss.get())
        dur_s = self.v_dur.get().strip()
        dur = _parse_time(dur_s) if dur_s else None

        def job() -> None:
            ff.trim_video(ip, op, start, dur)

        self._run_bg("구간 자르기", job)

    def _do_burn(self) -> None:
        vp = Path(self.v_in.get().strip())
        sp = Path(self.v_srt.get().strip())
        op = Path(self.v_out_trim.get().strip())
        if not vp.is_file() or not sp.is_file():
            messagebox.showwarning("입력", "영상과 SRT를 모두 선택하세요.")
            return
        if not str(op):
            messagebox.showwarning("출력", "출력 경로를 지정하세요.")
            return

        def job() -> None:
            ff.burn_subtitles(vp, sp, op)

        self._run_bg("자막 번인", job)

    def _do_probe_duration(self) -> None:
        vp = Path(self.v_in.get().strip())
        if not vp.is_file():
            messagebox.showwarning("입력", "입력 영상을 선택하세요.")
            return

        def work() -> None:
            err: str | None = None
            sec: float | None = None
            try:
                sec = ff.ffprobe_duration_sec(vp)
            except Exception as e:
                err = str(e)

            def done() -> None:
                if err is not None:
                    self._log(f"[오류] ffprobe: {err}")
                    messagebox.showerror("ffprobe", err)
                else:
                    assert sec is not None
                    msg = f"재생 시간: {sec:.3f}초 ({sec / 60.0:.2f}분)"
                    self._log(f"[완료] ffprobe — {msg}")
                    messagebox.showinfo("영상 길이", msg)

            self.after(0, done)

        self._log("[시작] ffprobe 재생 시간…")
        threading.Thread(target=work, daemon=True).start()

    def _concat_add(self) -> None:
        paths = filedialog.askopenfilenames(filetypes=[("영상", "*.mp4 *.mkv *.mov"), ("모든 파일", "*.*")])
        for p in paths:
            self.concat_list.insert(tk.END, p)

    def _concat_remove(self) -> None:
        sel = list(self.concat_list.curselection())
        for i in reversed(sel):
            self.concat_list.delete(i)

    def _do_concat(self) -> None:
        items = [self.concat_list.get(i) for i in range(self.concat_list.size())]
        op = Path(self.v_out_concat.get().strip())
        if len(items) < 2:
            messagebox.showwarning("목록", "영상을 두 개 이상 추가하세요.")
            return
        if not str(op):
            messagebox.showwarning("출력", "출력 경로를 지정하세요.")
            return
        paths = [Path(x) for x in items]

        def job() -> None:
            ff.concat_videos(paths, op, copy_codec=True)

        self._run_bg("영상 이어붙이기", job)

    # --- 자막 탭 ---
    def _build_subtitle_tab(self, f: ttk.Frame) -> None:
        top = ttk.Frame(f)
        top.pack(fill=tk.X)
        ttk.Button(top, text="SRT 열기", command=self._sub_open).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(top, text="대본·JSON·MD 불러오기", command=self._sub_import_from_document).pack(
            side=tk.LEFT, padx=(0, 6)
        )
        ttk.Button(top, text="다른 이름으로 저장", command=self._sub_save_as).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(top, text="저장", command=self._sub_save).pack(side=tk.LEFT)
        self.sub_path_var = tk.StringVar(value="(파일 없음)")
        ttk.Label(top, textvariable=self.sub_path_var).pack(side=tk.LEFT, padx=12)

        opt = ttk.LabelFrame(f, text="타임코드 없는 대본 불러오기 설정", padding=6)
        opt.pack(fill=tk.X, pady=(0, 8))
        of = ttk.Frame(opt)
        of.pack(fill=tk.X)
        ttk.Label(of, text="블록당 초(균등 간격):").pack(side=tk.LEFT)
        self.sub_import_secs = tk.StringVar(value="5.0")
        ttk.Entry(of, textvariable=self.sub_import_secs, width=8).pack(side=tk.LEFT, padx=6)
        self.sub_fit_video_len = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            of,
            text="영상 탭의 입력 영상 길이에 맞춰 블록을 균등 배분(ffprobe)",
            variable=self.sub_fit_video_len,
        ).pack(side=tk.LEFT, padx=16)

        self.sub_txt = scrolledtext.ScrolledText(f, wrap=tk.WORD, height=26)
        self.sub_txt.pack(fill=tk.BOTH, expand=True, pady=8)
        ttk.Label(
            f,
            text="「대본 불러오기»: TXT는 빈 줄·단락으로 구분, MD는 헤더·구분선(---)·@image 제외 후 단락, JSON은 Whisper segments·scene.json(narration)·lines 등을 처리합니다.",
            foreground="#444",
        ).pack(anchor="w")
        ttk.Label(
            f,
            text="SRT 편집 시 번호·타임코드·텍스트 형식을 유지하세요. 자막 번인은 저장한 SRT를 영상 탭에서 지정하세요.",
            foreground="#444",
        ).pack(anchor="w")

    def _sub_import_from_document(self) -> None:
        p = filedialog.askopenfilename(
            parent=self,
            title="대본·JSON·Markdown 선택",
            filetypes=[
                ("대본·데이터", "*.txt *.md *.json *.markdown"),
                ("텍스트", "*.txt"),
                ("Markdown", "*.md *.markdown"),
                ("JSON", "*.json"),
                ("모든 파일", "*.*"),
            ],
        )
        if not p:
            return
        path = Path(p)
        total: float | None = None
        if self.sub_fit_video_len.get():
            vp = Path(self.v_in.get().strip())
            if not vp.is_file():
                messagebox.showwarning("입력 영상", "영상 탭에서 입력 영상을 먼저 선택하거나, 블록당 초만 사용하세요.")
                return
            try:
                total = ff.ffprobe_duration_sec(vp)
            except Exception as e:
                messagebox.showerror("ffprobe", str(e))
                return
        try:
            spb = float((self.sub_import_secs.get() or "5").strip().replace(",", "."))
        except ValueError:
            messagebox.showwarning("값 오류", "블록당 초는 숫자로 입력하세요.")
            return
        if spb <= 0:
            spb = 5.0
        try:
            srt = document_to_srt(path, seconds_per_block=spb, total_duration=total)
        except Exception as e:
            messagebox.showerror("불러오기", str(e))
            return

        self._subtitle_path = None
        self.sub_path_var.set(f"(가져옴) {path.name} — 저장으로 .srt 확정")
        self.sub_txt.delete("1.0", tk.END)
        self.sub_txt.insert("1.0", srt)
        self.v_srt.set("")
        self._log(f"[완료] 자막 추출·변환: {path.name} → 편집기({len(srt)}자)")

    def _sub_open(self) -> None:
        p = filedialog.askopenfilename(filetypes=[("SRT", "*.srt"), ("모든 파일", "*.*")])
        if not p:
            return
        path = Path(p)
        self._subtitle_path = path
        self.sub_path_var.set(str(path))
        self.sub_txt.delete("1.0", tk.END)
        self.sub_txt.insert("1.0", path.read_text(encoding="utf-8", errors="replace"))

    def _sub_save_as(self) -> None:
        p = filedialog.asksaveasfilename(defaultextension=".srt", filetypes=[("SRT", "*.srt")])
        if not p:
            return
        self._subtitle_path = Path(p)
        self.sub_path_var.set(str(self._subtitle_path))
        self._write_sub_file()

    def _sub_save(self) -> None:
        if self._subtitle_path is None:
            self._sub_save_as()
            return
        self._write_sub_file()
        messagebox.showinfo("저장", f"저장했습니다.\n{self._subtitle_path}")

    def _write_sub_file(self) -> None:
        if self._subtitle_path is None:
            raise RuntimeError("저장 경로가 없습니다.")
        text = self.sub_txt.get("1.0", tk.END)
        self._subtitle_path.parent.mkdir(parents=True, exist_ok=True)
        self._subtitle_path.write_text(text, encoding="utf-8")

    # --- 음성 탭 ---
    def _build_audio_tab(self, f: ttk.Frame) -> None:
        r = 0
        self.a_vid = tk.StringVar()
        ttk.Label(f, text="입력 영상").grid(row=r, column=0, sticky="w")
        ttk.Entry(f, textvariable=self.a_vid, width=70).grid(row=r, column=1, sticky="ew", padx=4)
        ttk.Button(f, text="찾기…", command=lambda: self._pick_into(self.a_vid, video=True)).grid(row=r, column=2)
        r += 1

        self.a_out_mp3 = tk.StringVar()
        ttk.Label(f, text="추출 MP3 저장").grid(row=r, column=0, sticky="w")
        ttk.Entry(f, textvariable=self.a_out_mp3, width=70).grid(row=r, column=1, sticky="ew", padx=4)
        ttk.Button(f, text="저장…", command=lambda: self._save_as(self.a_out_mp3, [("MP3", "*.mp3")])).grid(row=r, column=2)
        r += 1
        ttk.Button(f, text="영상에서 음성만 추출(MP3)", command=self._do_extract_audio).grid(row=r, column=0, columnspan=2, sticky="w", pady=6)
        r += 1

        ttk.Separator(f, orient=tk.HORIZONTAL).grid(row=r, column=0, columnspan=3, sticky="ew", pady=12)
        r += 1
        self.a_vid2 = tk.StringVar()
        self.a_mp3 = tk.StringVar()
        self.a_out_mux = tk.StringVar()
        ttk.Label(f, text="영상(영상트랙 유지)").grid(row=r, column=0, sticky="w")
        ttk.Entry(f, textvariable=self.a_vid2, width=70).grid(row=r, column=1, sticky="ew", padx=4)
        ttk.Button(f, text="찾기…", command=lambda: self._pick_into(self.a_vid2, video=True)).grid(row=r, column=2)
        r += 1
        ttk.Label(f, text="새 음성( mp3 / wav )").grid(row=r, column=0, sticky="w")
        ttk.Entry(f, textvariable=self.a_mp3, width=70).grid(row=r, column=1, sticky="ew", padx=4)
        ttk.Button(f, text="찾기…", command=lambda: self._pick_into(self.a_mp3, video=False)).grid(row=r, column=2)
        r += 1
        ttk.Label(f, text="출력 영상").grid(row=r, column=0, sticky="w")
        ttk.Entry(f, textvariable=self.a_out_mux, width=70).grid(row=r, column=1, sticky="ew", padx=4)
        ttk.Button(f, text="저장…", command=lambda: self._save_as(self.a_out_mux, [("MP4", "*.mp4")])).grid(row=r, column=2)
        r += 1
        ttk.Button(f, text="음성 트랙 교체(짧은 쪽에 맞춤)", command=self._do_replace_audio).grid(row=r, column=0, columnspan=2, sticky="w", pady=6)

        f.grid_columnconfigure(1, weight=1)

    def _pick_into(self, var: tk.StringVar, *, video: bool) -> None:
        if video:
            p = filedialog.askopenfilename(filetypes=[("영상", "*.mp4 *.mkv *.mov"), ("모든 파일", "*.*")])
        else:
            p = filedialog.askopenfilename(filetypes=[("오디오", "*.mp3 *.wav *.m4a"), ("모든 파일", "*.*")])
        if p:
            var.set(p)

    def _do_extract_audio(self) -> None:
        v = Path(self.a_vid.get().strip())
        o = Path(self.a_out_mp3.get().strip())
        if not v.is_file() or not str(o):
            messagebox.showwarning("입력", "영상과 MP3 저장 경로를 지정하세요.")
            return

        def job() -> None:
            ff.extract_audio(v, o)

        self._run_bg("음성 추출", job)

    def _do_replace_audio(self) -> None:
        v = Path(self.a_vid2.get().strip())
        a = Path(self.a_mp3.get().strip())
        o = Path(self.a_out_mux.get().strip())
        if not v.is_file() or not a.is_file() or not str(o):
            messagebox.showwarning("입력", "영상·음성·출력을 모두 지정하세요.")
            return

        def job() -> None:
            ff.replace_audio_track(v, a, o)

        self._run_bg("음성 교체", job)


def main() -> None:
    if sys.platform == "win32":
        for stream in (sys.stdout, sys.stderr):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (AttributeError, OSError, ValueError):
                pass
    ff.prepend_local_ffmpeg_bin_to_os_path()
    app = VideoStudioApp()
    app.mainloop()


if __name__ == "__main__":
    main()
