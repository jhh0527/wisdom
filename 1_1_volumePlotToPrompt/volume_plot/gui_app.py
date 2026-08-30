# -*- coding: utf-8 -*-
"""1_1_volumePlotToPrompt GUI — 부 줄거리 합본·저장."""

from __future__ import annotations

import hashlib
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, font as tkfont, messagebox, scrolledtext, ttk

from volume_plot import __version__
from volume_plot import diag_log
from volume_plot.paths import (
    default_log_path,
    default_novel_root,
    find_volume_plot_file,
    infer_novel_root_from_path,
    parse_volume_from_path,
    volume_plot_path,
)
from volume_plot.settings import load_gui_settings, save_gui_settings
from volume_plot.volume_packet import (
    VOLUME_END,
    VOLUME_START,
    build_volume_packet,
    extract_volume_body,
    save_volume_plot,
)


def _default_font() -> tuple[str, int]:
    try:
        f = tkfont.nametofont("TkDefaultFont")
        return (f.actual("family"), max(10, int(f.actual("size"))))
    except tk.TclError:
        return ("맑은 고딕", 10)


def _clipboard_set(root: tk.Misc, text: str) -> None:
    root.clipboard_clear()
    root.clipboard_append(text)
    root.update_idletasks()


def main(*, container: tk.Misc | None = None) -> None:
    from wisdom_gui_host import apply_window_chrome, bind_close, run_mainloop, tk_host
    from wisdom_workspace import folder_dialog_initial, touch_workspace_from_path

    cfg = load_gui_settings()
    novel_default = Path(cfg["novel_root"]) if cfg.get("novel_root") else default_novel_root()
    if not novel_default.is_dir():
        novel_default = default_novel_root()
    vol_default = (cfg.get("volume") or "3").strip() or "3"
    range_default = (cfg.get("chapter_range") or "").strip()
    watch_default = (cfg.get("clip_watch") or "1").strip() in (
        "1",
        "true",
        "True",
        "yes",
        "on",
    )

    root, standalone = tk_host(container)
    apply_window_chrome(
        root,
        standalone,
        title=f"1_1_volumePlotToPrompt {__version__}",
        minsize=(720, 600),
        geometry="900x740",
    )
    fam, sz = _default_font()
    root.option_add("*Font", (fam, sz))

    log_file = diag_log.start_session(
        default_log_path(),
        title=f"1_1_volumePlotToPrompt {__version__}",
    )
    diag_log.log(f"시작 novel={novel_default} vol={vol_default}")

    novel_var = tk.StringVar(value=str(novel_default))
    volume_var = tk.StringVar(value=vol_default)
    range_var = tk.StringVar(value=range_default)
    status_var = tk.StringVar(
        value="부 번호·장 범위·목표를 넣고 합본 → 젠스파크 → VOLUME_START/END 저장."
    )
    progress_var = tk.StringVar(value="대기")
    save_path_var = tk.StringVar(value="")
    watch_var = tk.BooleanVar(value=watch_default)
    wr_var = tk.BooleanVar(value=True)
    chars_var = tk.BooleanVar(value=True)
    fs_var = tk.BooleanVar(value=True)
    ev_var = tk.BooleanVar(value=True)

    outer = ttk.Frame(root, padding=10)
    outer.pack(fill=tk.BOTH, expand=True)

    prog_fr = ttk.Frame(outer)
    prog_fr.pack(fill=tk.X, side=tk.BOTTOM, pady=(6, 0))
    ttk.Label(prog_fr, text="진척").pack(side=tk.LEFT)
    progress = ttk.Progressbar(prog_fr, mode="determinate", maximum=100, length=180)
    progress.pack(side=tk.LEFT, padx=6)
    ttk.Label(prog_fr, textvariable=progress_var, width=28).pack(side=tk.LEFT)
    ttk.Label(outer, textvariable=status_var, wraplength=860).pack(
        fill=tk.X, side=tk.BOTTOM, pady=(2, 0)
    )

    log_box = scrolledtext.ScrolledText(outer, height=5, wrap=tk.WORD)
    log_box.pack(fill=tk.X, side=tk.BOTTOM, pady=(4, 0))

    def _on_log(line: str) -> None:
        log_box.insert(tk.END, line + "\n")
        log_box.see(tk.END)

    diag_log.add_listener(_on_log)
    diag_log.log(f"로그 파일 {log_file}")

    path_fr = ttk.LabelFrame(outer, text="경로", padding=6)
    path_fr.pack(fill=tk.X)

    def _browse_novel() -> None:
        init = folder_dialog_initial(novel_var.get())
        d = filedialog.askdirectory(title="작품 폴더", initialdir=init or None)
        if d:
            novel_var.set(d)
            touch_workspace_from_path(d)
            _refresh_save_hint()
            _persist()

    row0 = ttk.Frame(path_fr)
    row0.pack(fill=tk.X)
    ttk.Label(row0, text="작품 폴더", width=10).pack(side=tk.LEFT)
    ttk.Entry(row0, textvariable=novel_var).pack(
        side=tk.LEFT, fill=tk.X, expand=True, padx=4
    )
    ttk.Button(row0, text="찾기", command=_browse_novel, width=8).pack(side=tk.LEFT)

    row1 = ttk.Frame(path_fr)
    row1.pack(fill=tk.X, pady=(4, 0))
    ttk.Label(row1, text="부", width=10).pack(side=tk.LEFT)
    ttk.Spinbox(row1, from_=1, to=20, textvariable=volume_var, width=6).pack(
        side=tk.LEFT, padx=4
    )
    ttk.Label(row1, text="장 범위(선택)").pack(side=tk.LEFT, padx=(12, 0))
    ttk.Entry(row1, textvariable=range_var, width=16).pack(side=tk.LEFT, padx=4)
    ttk.Label(row1, text="예: 23~40").pack(side=tk.LEFT)

    ttk.Label(path_fr, textvariable=save_path_var, foreground="#444").pack(
        anchor=tk.W, pady=(4, 0)
    )

    def _parse_volume() -> int | None:
        try:
            v = int(str(volume_var.get()).strip())
        except ValueError:
            return None
        return v if v >= 1 else None

    def _refresh_save_hint() -> None:
        novel = Path(novel_var.get().strip() or ".")
        v = _parse_volume()
        if v is None:
            save_path_var.set("저장 경로: (부 번호 확인)")
            return
        p = volume_plot_path(novel, v)
        existing = find_volume_plot_file(novel, v)
        extra = f" · 기존 {existing.name}" if existing and existing != p else ""
        save_path_var.set(f"저장: {p}{extra}")

    def _persist() -> None:
        save_gui_settings(
            novel_root=novel_var.get().strip(),
            volume=str(volume_var.get()).strip(),
            chapter_range=range_var.get().strip(),
            clip_watch=watch_var.get(),
        )

    volume_var.trace_add("write", lambda *_: (_refresh_save_hint(), _persist()))
    novel_var.trace_add("write", lambda *_: _refresh_save_hint())
    _refresh_save_hint()

    nb = ttk.Notebook(outer)
    nb.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

    # --- tab 1: packet ---
    tab1 = ttk.Frame(nb, padding=6)
    nb.add(tab1, text="1. 합본 만들기")

    opt = ttk.Frame(tab1)
    opt.pack(fill=tk.X)
    ttk.Checkbutton(opt, text="WRITE_RULES", variable=wr_var).pack(side=tk.LEFT)
    ttk.Checkbutton(opt, text="characters", variable=chars_var).pack(
        side=tk.LEFT, padx=8
    )
    ttk.Checkbutton(opt, text="foreshadowing", variable=fs_var).pack(side=tk.LEFT)
    ttk.Checkbutton(opt, text="events 끝", variable=ev_var).pack(side=tk.LEFT, padx=8)

    ttk.Label(tab1, text="이번 부 목표·제약 (선택)").pack(anchor=tk.W, pady=(6, 0))
    goals = scrolledtext.ScrolledText(tab1, height=5, wrap=tk.WORD)
    goals.pack(fill=tk.X, pady=(2, 4))
    goals.insert(
        "1.0",
        "직전 부 말미와 이어서 쓸 것. 사망·납치·환/현무/묵허 정체 유지.\n"
        "유튜브 제목 표 + 마스터 줄기 + 장별 절. 새 주요 인물은 승인 대기로.",
    )

    ttk.Label(tab1, text="합본 미리보기").pack(anchor=tk.W)
    packet_box = scrolledtext.ScrolledText(tab1, height=16, wrap=tk.WORD)
    packet_box.pack(fill=tk.BOTH, expand=True, pady=(2, 4))

    btn1 = ttk.Frame(tab1)
    btn1.pack(fill=tk.X)

    def _set_progress(pct: int, label: str) -> None:
        progress["value"] = pct
        progress_var.set(label)

    def _do_build() -> None:
        novel = Path(novel_var.get().strip())
        if not novel.is_dir():
            messagebox.showerror("합본", "작품 폴더를 확인하세요.")
            return
        vol = _parse_volume()
        if vol is None:
            messagebox.showerror("합본", "부 번호가 올바르지 않습니다.")
            return
        inferred = infer_novel_root_from_path(novel)
        if inferred is not None:
            novel = inferred
            novel_var.set(str(novel))
        _set_progress(20, "합본 생성…")
        try:
            text, notes = build_volume_packet(
                novel_root=novel,
                volume=vol,
                chapter_range=range_var.get().strip(),
                goals=goals.get("1.0", "end-1c"),
                include_write_rules=wr_var.get(),
                include_characters=chars_var.get(),
                include_foreshadowing=fs_var.get(),
                include_events_tail=ev_var.get(),
            )
        except Exception as e:
            diag_log.log(f"합본 실패: {e}")
            messagebox.showerror("합본", str(e))
            _set_progress(0, "실패")
            return
        packet_box.delete("1.0", "end")
        packet_box.insert("1.0", text)
        for n in notes:
            diag_log.log(f"note: {n}")
        _persist()
        _refresh_save_hint()
        _set_progress(100, "합본 완료")
        status_var.set(f"제{vol}부 합본 생성. notes={len(notes)}")
        diag_log.log(f"합본 OK vol={vol} chars={len(text)}")

    def _do_copy() -> None:
        text = packet_box.get("1.0", "end-1c").strip()
        if not text:
            _do_build()
            text = packet_box.get("1.0", "end-1c").strip()
        if not text:
            return
        _clipboard_set(root, text)
        status_var.set("합본을 클립보드에 복사했습니다. 젠스파크에 붙여넣으세요.")
        diag_log.log("합본 복사")

    ttk.Button(btn1, text="합본 만들기", command=_do_build).pack(side=tk.LEFT)
    ttk.Button(btn1, text="합본 복사", command=_do_copy).pack(side=tk.LEFT, padx=6)

    # --- tab 2: save ---
    tab2 = ttk.Frame(nb, padding=6)
    nb.add(tab2, text="2. 결과 저장")

    ttk.Label(
        tab2,
        text=f"젠스파크 출력을 복사한 뒤 {VOLUME_START} … {VOLUME_END} 로 저장합니다.",
    ).pack(anchor=tk.W)

    ttk.Checkbutton(
        tab2,
        text="클립보드 감시 (START/END 자동 저장 · 단독 exe)",
        variable=watch_var,
        command=_persist,
    ).pack(anchor=tk.W, pady=(4, 0))

    ttk.Label(tab2, text="추출·편집 칸").pack(anchor=tk.W, pady=(6, 0))
    body_box = scrolledtext.ScrolledText(tab2, height=18, wrap=tk.WORD)
    body_box.pack(fill=tk.BOTH, expand=True, pady=(2, 4))

    btn2 = ttk.Frame(tab2)
    btn2.pack(fill=tk.X)
    _last_clip_hash = {"h": ""}

    def _save_text(raw: str, *, source: str) -> None:
        novel = Path(novel_var.get().strip())
        vol = _parse_volume()
        if vol is None or not novel.is_dir():
            messagebox.showerror("저장", "작품 폴더·부 번호를 확인하세요.")
            return
        body = extract_volume_body(raw) or raw.strip()
        if not body:
            messagebox.showwarning("저장", "저장할 본문이 없습니다.")
            return
        try:
            path = save_volume_plot(novel, vol, body)
        except OSError as e:
            messagebox.showerror("저장", str(e))
            return
        body_box.delete("1.0", "end")
        body_box.insert("1.0", body)
        _refresh_save_hint()
        _persist()
        status_var.set(f"저장됨 ({source}): {path}")
        diag_log.log(f"저장 {path} ({source}) chars={len(body)}")
        _set_progress(100, "저장 완료")

    def _save_from_clipboard() -> None:
        try:
            raw = root.clipboard_get()
        except tk.TclError:
            messagebox.showwarning("저장", "클립보드가 비어 있습니다.")
            return
        if VOLUME_START not in raw or VOLUME_END not in raw:
            if not messagebox.askyesno(
                "저장",
                "START/END 구분자가 없습니다. 클립보드 전체를 저장할까요?",
            ):
                return
        _save_text(raw, source="클립보드")

    def _save_from_box() -> None:
        _save_text(body_box.get("1.0", "end-1c"), source="칸")

    def _load_existing() -> None:
        novel = Path(novel_var.get().strip())
        vol = _parse_volume()
        if vol is None:
            return
        p = find_volume_plot_file(novel, vol) or volume_plot_path(novel, vol)
        if not p.is_file():
            messagebox.showinfo("불러오기", f"파일 없음: {p}")
            return
        body_box.delete("1.0", "end")
        body_box.insert("1.0", p.read_text(encoding="utf-8-sig"))
        status_var.set(f"불러옴: {p}")

    ttk.Button(btn2, text="START/END로 저장", command=_save_from_clipboard).pack(
        side=tk.LEFT
    )
    ttk.Button(btn2, text="칸 내용 저장", command=_save_from_box).pack(
        side=tk.LEFT, padx=6
    )
    ttk.Button(btn2, text="기존 파일 불러오기", command=_load_existing).pack(
        side=tk.LEFT
    )

    def _poll_clipboard() -> None:
        if standalone and watch_var.get():
            try:
                raw = root.clipboard_get()
            except tk.TclError:
                raw = ""
            if (
                raw
                and VOLUME_START in raw
                and VOLUME_END in raw
                and extract_volume_body(raw)
            ):
                h = hashlib.sha1(raw.encode("utf-8", errors="replace")).hexdigest()
                if h != _last_clip_hash["h"]:
                    _last_clip_hash["h"] = h
                    try:
                        _save_text(raw, source="감시")
                    except Exception as e:
                        diag_log.log(f"감시 저장 실패: {e}")
        root.after(1500, _poll_clipboard)

    if standalone:
        root.after(1500, _poll_clipboard)

    # path may include volume folder
    v_from_path = parse_volume_from_path(novel_var.get())
    if v_from_path and not cfg.get("volume"):
        volume_var.set(str(v_from_path))

    def _on_close() -> None:
        _persist()
        diag_log.remove_listener(_on_log)

    bind_close(root, standalone, on_close=_on_close)
    run_mainloop(root, standalone)
