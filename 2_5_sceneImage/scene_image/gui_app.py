# -*- coding: utf-8 -*-
"""2_5_sceneImage GUI — 루트/stt·mp3·png + 모듈 md → Genspark 생성."""

from __future__ import annotations

import os
import re
import subprocess
import sys
import threading
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, font as tkfont, ttk

from scene_image import __version__
from scene_image.credentials import load_credentials, save_credentials
from scene_image.genspark_image import (
    build_generate_command_from_sources,
    close_chrome_debug,
    get_image_session,
    has_playwright,
    image_profile_dir,
    open_browser_for_account,
    preferred_genspark_url,
    set_tab_log_png_dir,
)
from scene_image.chrome_slot import (
    count_claimable_slots,
    ensure_chrome_slot,
    get_active_slot,
    release_chrome_slot,
)
from scene_image.image_log import append_fail_log, append_image_log
from scene_image.limit_detect import (
    AiImageLimitError,
    format_reset_at,
    parse_session_start_hm,
    resolve_limit_reset_at,
    text_is_near_limit_only,
    text_looks_like_limit,
)
from scene_image.paths import (
    GENSPARK_AI_IMAGE_URL,
    build_paste_payload,
    default_png_dir,
    default_root_dir,
    ensure_root_layout,
    find_default_srt,
    find_image_prompt_file,
    find_prompt_in_md,
    load_scene_text,
    module_md_dir,
    paste_payload_stats,
    png_dir_under_root,
)
from scene_image.pipeline_config import load_pipeline_config, model_name_variants
from scene_image.scene_parse import (
    SceneLine,
    build_interval_scenes,
    parse_scene_script,
    parse_sec_selection,
    png_already_exists,
    scene_png_path,
)
from scene_image.settings import (
    load_gui_settings,
    load_model_selector,
    save_gui_settings,
    set_config_slot,
)
from wisdom_workspace import folder_dialog_initial, touch_workspace_from_path

_SCENE_INTERVAL_SEC = 20
# 한도: 배너 감지 → 재설정 시각까지 대기 (매시간 시험 없음)
_LIMIT_FAIL_STREAK = 2
_LIMIT_WAIT_CHUNK_SEC = 15
_LIMIT_RESET_BUFFER_SEC = 30
_SHUTDOWN_DELAY_SEC = 60  # 완료 후 종료까지 여유(취소: shutdown /a)
_LIMIT_ERR_RE = re.compile(
    r"rate\s*limit|usage\s*limit|fair[\s-]*use|try\s*again\s*later|"
    r"too\s*many|5[\s-]*hour|quota|"
    r"AI\s*Image|"
    r"한도|5\s*시간\s*제한|제한에\s*도달|재설정됩니다|"
    r"사용\s*제한|이용\s*제한|나중에\s*다시|제한에\s*걸",
    re.IGNORECASE,
)


def _schedule_pc_shutdown(*, delay_sec: int) -> None:
    """Windows: shutdown /s /t N — 취소는 shutdown /a."""
    sec = max(1, int(delay_sec))
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    subprocess.run(
        ["shutdown", "/s", "/t", str(sec)],
        check=False,
        creationflags=flags,
    )


def _load_shutdown_after_complete(cfg: dict[str, str]) -> bool:
    """체크박스 · 구버전(시간 콤보) 설정도 켜짐으로 인식."""
    if (cfg.get("shutdown_after_complete") or "0").strip() in (
        "1",
        "true",
        "True",
        "yes",
        "on",
    ):
        return True
    raw = (cfg.get("shutdown_after_hours") or "").strip()
    if raw.isdigit() and int(raw) > 0:
        return True
    return False


def _looks_like_limit_error(err: str) -> bool:
    if isinstance(err, AiImageLimitError):
        return True
    s = err if isinstance(err, str) else str(err or "")
    # 「5시간 제한에 근접했습니다」는 한도 대기·브라우저 종료 대상 아님
    if text_is_near_limit_only(s):
        return False
    return bool(_LIMIT_ERR_RE.search(s)) or text_looks_like_limit(s)


def _resolve_scene_image_exe() -> Path | None:
    """독립 2_5_sceneImage_gui.exe 경로 (허브·소스 실행 포함)."""
    if getattr(sys, "frozen", False):
        exe = Path(sys.executable).resolve()
        if exe.name.casefold() == "2_5_sceneimage_gui.exe":
            return exe
    try:
        from wisdom_root import resolve_wisdom_root

        cand = resolve_wisdom_root() / "2_5_sceneImage" / "dist" / "2_5_sceneImage_gui.exe"
        if cand.is_file():
            return cand
    except Exception:
        pass
    cand = Path(__file__).resolve().parents[1] / "dist" / "2_5_sceneImage_gui.exe"
    return cand if cand.is_file() else None


def _spawn_scene_image_instance() -> None:
    """다른 Chrome 슬롯으로 2_5_sceneImage 를 병렬 실행."""
    free = count_claimable_slots()
    if free <= 0:
        raise RuntimeError(
            "ChromeDebug 슬롯이 모두 사용 중입니다 (최대 8개).\n"
            "다른 sceneImage 창을 닫은 뒤 다시 시도하세요."
        )
    exe = _resolve_scene_image_exe()
    module_dir = Path(__file__).resolve().parents[1]
    kwargs: dict = {"close_fds": True}
    if sys.platform == "win32":
        kwargs["creationflags"] = (
            subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        )
    if exe is not None:
        kwargs["cwd"] = str(exe.parent)
        subprocess.Popen([str(exe)], **kwargs)
        return
    launcher = module_dir / "run_scene_image_gui.py"
    if not launcher.is_file():
        raise RuntimeError(
            "2_5_sceneImage_gui.exe 를 찾을 수 없습니다.\n"
            f"build 후 dist 에 exe 가 있어야 합니다.\n({module_dir / 'dist'})"
        )
    env = os.environ.copy()
    env["SCENE_IMAGE_GUI_SOURCE"] = "1"
    kwargs["cwd"] = str(module_dir)
    kwargs["env"] = env
    subprocess.Popen([sys.executable, str(launcher)], **kwargs)


def _default_font() -> tuple[str, int]:
    try:
        f = tkfont.nametofont("TkDefaultFont")
        return (f.actual("family"), max(10, int(f.actual("size"))))
    except tk.TclError:
        return ("맑은 고딕", 10)


def _parse_manual_secs(text: str, available_secs: list[int] | None = None) -> list[int]:
    return parse_sec_selection(text, available_secs)


def main(*, container: tk.Misc | None = None) -> None:
    from wisdom_gui_host import (
        apply_window_chrome,
        bind_close,
        bind_hub_destroy,
        bind_path_entry_dnd,
        bind_path_row_dnd,
        run_mainloop,
        safe_after,
        safe_messagebox,
        show_toast,
        tk_host,
    )

    root, standalone = tk_host(container)
    if not standalone and getattr(root, "_scene_image_gui_built", False):
        return
    if not standalone:
        setattr(root, "_scene_image_gui_built", True)

    try:
        chrome_slot = ensure_chrome_slot()
    except RuntimeError as e:
        if standalone:
            from tkinter import messagebox

            messagebox.showerror("2_5 sceneImage", str(e))
            return
        raise
    set_config_slot(chrome_slot.index)

    apply_window_chrome(
        root,
        standalone,
        title=(
            f"2_5 sceneImage {__version__} "
            f"[{chrome_slot.label}]"
        ),
        minsize=(780, 560),
        geometry="960x700",
    )
    fam, sz = _default_font()
    root.option_add("*Font", (fam, sz))

    cfg = load_gui_settings()
    root_default = cfg.get("root_dir") or str(default_root_dir())
    png_default = cfg.get("png_dir") or str(png_dir_under_root(root_default))
    url_default = cfg.get("genspark_url") or GENSPARK_AI_IMAGE_URL
    srt_default = cfg.get("srt_path") or ""
    prompt_default = cfg.get("prompt_path") or ""
    hourly_retry_default = (cfg.get("hourly_limit_retry") or "1").strip() in (
        "1",
        "true",
        "True",
        "yes",
        "on",
    )
    session_start_default = cfg.get("limit_session_start") or ""
    shutdown_default = _load_shutdown_after_complete(cfg)
    manual_default = cfg.get("manual_secs") or ""
    scene_cache = cfg.get("scene_script") or ""

    if not srt_default:
        found = find_default_srt(root_default)
        if found is not None:
            srt_default = str(found)
    if not prompt_default:
        found_p = find_image_prompt_file()
        if found_p is not None:
            prompt_default = str(found_p)
    elif not Path(prompt_default).is_file():
        found_p = find_image_prompt_file()
        if found_p is not None:
            prompt_default = str(found_p)

    cred_email, cred_pw = load_credentials()

    def _sync_credentials_to_fields() -> None:
        """슬롯·포트가 바뀌어도 저장된 Genspark 계정을 필드에 유지."""
        nonlocal cred_email, cred_pw
        if not cred_email or not cred_pw:
            cred_email, cred_pw = load_credentials()
        if cred_email and not email_var.get().strip():
            email_var.set(cred_email)
        if cred_pw and not pw_var.get():
            pw_var.set(cred_pw)

    root_var = tk.StringVar(value=root_default)
    png_var = tk.StringVar(value=png_default)
    url_var = tk.StringVar(value=url_default)
    srt_var = tk.StringVar(value=srt_default)
    prompt_var = tk.StringVar(value=prompt_default)
    hourly_retry_var = tk.BooleanVar(value=hourly_retry_default)
    session_start_var = tk.StringVar(value=session_start_default)
    limit_reset_var = tk.StringVar(value="정상화 예상: —")
    shutdown_var = tk.BooleanVar(value=shutdown_default)
    manual_var = tk.StringVar(value=manual_default)
    email_var = tk.StringVar(value=cred_email)
    pw_var = tk.StringVar(value=cred_pw)
    _sync_credentials_to_fields()
    status_var = tk.StringVar(
        value=(
            f"슬롯 {chrome_slot.index} · CDP :{chrome_slot.port} · "
            f"{chrome_slot.user_data} — 「실행」로 시작"
        )
    )
    scene_var = tk.StringVar(value="")
    busy = {"v": False}
    wait_cancel = {"v": False}
    waiting_limit = {"v": False}
    browser_ready = {"v": False}
    # 브라우저 열기로 입력창에 SRT·프롬프트+명령이 준비됨(미전송)
    input_prepared = {"v": False, "cmd_sec": None}
    scenes: list[SceneLine] = []
    collected: list[tuple[int | None, str]] = []
    scene_text_cache = {"v": scene_cache}

    frm = ttk.Frame(root, padding=10)
    frm.pack(fill=tk.BOTH, expand=True)
    frm.grid_columnconfigure(0, weight=1)
    frm.grid_rowconfigure(3, weight=1)

    def persist() -> None:
        nonlocal cred_email, cred_pw
        save_gui_settings(
            root_dir=root_var.get().strip(),
            png_dir=png_var.get().strip(),
            genspark_url=url_var.get().strip(),
            srt_path=srt_var.get().strip(),
            prompt_path=prompt_var.get().strip(),
            hourly_limit_retry="1" if hourly_retry_var.get() else "0",
            limit_session_start=session_start_var.get().strip(),
            shutdown_after_hours="0",
            shutdown_after_complete="1" if shutdown_var.get() else "0",
            manual_secs=manual_var.get().strip(),
            scene_script=scene_text_cache["v"],
            scene_index=str(
                max(0, scene_list.curselection()[0]) if scene_list.curselection() else 0
            ),
        )
        email = email_var.get().strip()
        password = pw_var.get()
        if email and password:
            save_credentials(email, password)
            cred_email, cred_pw = email, password
        elif not email or not password:
            _sync_credentials_to_fields()

    def set_status(msg: str) -> None:
        status_var.set(msg)

    def set_busy(v: bool) -> None:
        busy["v"] = v
        state = tk.DISABLED if v else tk.NORMAL
        for b in (btn_browser, btn_manual):
            try:
                b.configure(state=state)
            except tk.TclError:
                pass
        if not v:
            waiting_limit["v"] = False
            try:
                btn_cancel_wait.configure(state=tk.DISABLED)
            except tk.TclError:
                pass

    def set_limit_reset_display(reset_at: datetime | None) -> None:
        limit_reset_var.set(f"정상화 예상: {format_reset_at(reset_at)}")

    def set_limit_waiting(on: bool) -> None:
        waiting_limit["v"] = on
        try:
            btn_cancel_wait.configure(state=tk.NORMAL if on else tk.DISABLED)
        except tk.TclError:
            pass

    def cancel_limit_wait() -> None:
        if not waiting_limit["v"]:
            return
        wait_cancel["v"] = True
        set_status("한도 대기 취소 요청…")

    def profile_dir() -> Path:
        base = Path(__file__).resolve().parents[1] / "dist"
        if not standalone:
            try:
                from wisdom_root import resolve_wisdom_root

                base = resolve_wisdom_root() / "2_5_sceneImage" / "dist"
            except Exception:
                pass
        base.mkdir(parents=True, exist_ok=True)
        return image_profile_dir(base)

    def append_collected_path(sec: int, path: str) -> None:
        label = f"SRT_{sec:03d}"
        short = path if len(path) < 90 else path[:87] + "…"
        link_list.insert(tk.END, f"{label}  |  {short}")
        collected.append((sec, path))

    def apply_root(*, force: bool = True) -> None:
        """루트 지정 시 png·대본(SRT)·이미지프롬프트를 루트 기준으로 맞춘다."""
        raw = root_var.get().strip()
        if not raw:
            return
        r = Path(raw).expanduser()
        try:
            r_resolved = r.resolve()
        except OSError:
            r_resolved = r
        layout = ensure_root_layout(r)
        png_var.set(str(layout["png"]))

        def _under_root(path_str: str) -> bool:
            if not path_str.strip():
                return False
            try:
                return Path(path_str).expanduser().resolve().is_relative_to(r_resolved)
            except (OSError, ValueError, AttributeError):
                try:
                    p = str(Path(path_str).expanduser().resolve())
                    root_s = str(r_resolved)
                    return p == root_s or p.startswith(root_s + os.sep)
                except OSError:
                    return False

        cur_srt = srt_var.get().strip()
        if force or not cur_srt or not _under_root(cur_srt):
            srt = find_default_srt(r)
            if srt is not None:
                srt_var.set(str(srt))
            elif force:
                srt_var.set(str((layout.get("mp3") or (r / "mp3")) / "new.srt"))

        cur_prompt = prompt_var.get().strip()
        if force or not cur_prompt or not _under_root(cur_prompt):
            prompt = find_prompt_in_md(r) or find_image_prompt_file(root=r)
            if prompt is not None:
                prompt_var.set(str(prompt))

        reload_scenes()
        persist()
        set_status(
            f"루트 → png:{layout['png'].name} · "
            f"srt:{Path(srt_var.get()).name if srt_var.get().strip() else '—'} · "
            f"prompt:{Path(prompt_var.get()).name if prompt_var.get().strip() else '—'} · {r}"
        )

    def auto_assign_from_png(*, force: bool = False) -> None:
        # 호환: png 변경 시 부모를 루트로 간주
        png = png_var.get().strip()
        if not png:
            return
        p = Path(png)
        r = p.parent if p.name.casefold() == "png" else p
        root_var.set(str(r))
        apply_root(force=force)

    def pick_root() -> None:
        init = folder_dialog_initial(
            Path(root_var.get()) if root_var.get().strip() else default_root_dir()
        )
        p = filedialog.askdirectory(parent=root, title="루트 폴더", initialdir=init)
        if p:
            root_var.set(p)
            touch_workspace_from_path(p)
            apply_root(force=True)

    def pick_png() -> None:
        init = folder_dialog_initial(
            Path(png_var.get()) if png_var.get().strip() else default_png_dir()
        )
        p = filedialog.askdirectory(parent=root, title="png 저장 폴더", initialdir=init)
        if p:
            png_var.set(p)
            touch_workspace_from_path(p)
            auto_assign_from_png(force=False)
            set_status(f"png 지정 → {p}")

    def pick_srt() -> None:
        root_p = Path(root_var.get().strip()) if root_var.get().strip() else default_root_dir()
        init = folder_dialog_initial(
            Path(srt_var.get()).parent
            if srt_var.get().strip()
            else (root_p / "mp3" if (root_p / "mp3").is_dir() else root_p / "stt")
        )
        p = filedialog.askopenfilename(
            parent=root,
            title="대본 SRT (new.srt / all.srt)",
            initialdir=init,
            filetypes=[("SRT", "*.srt"), ("모든 파일", "*.*")],
        )
        if p:
            srt_var.set(p)
            persist()

    def pick_prompt() -> None:
        md = module_md_dir()
        md.mkdir(parents=True, exist_ok=True)
        init = folder_dialog_initial(
            Path(prompt_var.get()).parent if prompt_var.get().strip() else md
        )
        p = filedialog.askopenfilename(
            parent=root,
            title="이미지프롬프트 (모듈 md)",
            initialdir=init,
            filetypes=[("텍스트", "*.txt;*.md"), ("모든 파일", "*.*")],
        )
        if p:
            prompt_var.set(p)
            reload_scenes()
            persist()

    # --- paths ---
    path_fr = ttk.LabelFrame(frm, text="경로", padding=(8, 6))
    path_fr.grid(row=0, column=0, sticky="ew", pady=(0, 8))
    path_fr.grid_columnconfigure(1, weight=1)

    ttk.Label(path_fr, text="루트 폴더", width=14).grid(row=0, column=0, sticky="w")
    root_ent = ttk.Entry(path_fr, textvariable=root_var)
    root_ent.grid(row=0, column=1, sticky="ew", padx=(4, 6), pady=2)
    ttk.Button(path_fr, text="찾기…", width=8, command=pick_root).grid(
        row=0, column=2, sticky="e"
    )
    bind_path_entry_dnd(
        root_ent,
        root_var,
        mode="dir",
        on_set=lambda _p: apply_root(force=True),
    )
    bind_path_row_dnd(
        root_ent,
        path_fr,
        root_var,
        mode="dir",
        on_set=lambda _p: apply_root(force=True),
    )

    ttk.Label(path_fr, text="png 폴더", width=14).grid(row=1, column=0, sticky="w")
    png_ent = ttk.Entry(path_fr, textvariable=png_var)
    png_ent.grid(row=1, column=1, sticky="ew", padx=(4, 6), pady=2)
    ttk.Button(path_fr, text="찾기…", width=8, command=pick_png).grid(
        row=1, column=2, sticky="e"
    )
    bind_path_entry_dnd(png_ent, png_var, mode="dir")
    bind_path_row_dnd(png_ent, path_fr, png_var, mode="dir")

    ttk.Label(path_fr, text="대본 (new.srt)", width=14).grid(row=2, column=0, sticky="w")
    srt_ent = ttk.Entry(path_fr, textvariable=srt_var)
    srt_ent.grid(row=2, column=1, sticky="ew", padx=(4, 6), pady=2)
    ttk.Button(path_fr, text="찾기…", width=8, command=pick_srt).grid(
        row=2, column=2, sticky="e"
    )
    bind_path_entry_dnd(srt_ent, srt_var, mode="file")

    ttk.Label(path_fr, text="이미지프롬프트", width=14).grid(row=3, column=0, sticky="w")
    prompt_ent = ttk.Entry(path_fr, textvariable=prompt_var)
    prompt_ent.grid(row=3, column=1, sticky="ew", padx=(4, 6), pady=2)
    ttk.Button(path_fr, text="찾기…", width=8, command=pick_prompt).grid(
        row=3, column=2, sticky="e"
    )
    bind_path_entry_dnd(prompt_ent, prompt_var, mode="file")

    ttk.Checkbutton(
        path_fr,
        text="한도 시 재설정까지 대기",
        variable=hourly_retry_var,
        command=persist,
    ).grid(row=4, column=1, columnspan=2, sticky="w", padx=(4, 0), pady=2)

    limit_row = ttk.Frame(path_fr)
    limit_row.grid(row=5, column=0, columnspan=3, sticky="ew", pady=(0, 2))
    ttk.Label(limit_row, textvariable=limit_reset_var, width=28).pack(side=tk.LEFT)
    ttk.Label(limit_row, text="실행 시작(미표시 시)", foreground="#555").pack(
        side=tk.LEFT, padx=(12, 4)
    )
    session_start_ent = ttk.Entry(limit_row, textvariable=session_start_var, width=8)
    session_start_ent.pack(side=tk.LEFT)
    ttk.Label(limit_row, text="예: 14:30", foreground="#888").pack(side=tk.LEFT, padx=(4, 0))
    session_start_var.trace_add("write", lambda *_a: persist())

    ttk.Label(path_fr, text="브라우저 주소", width=14).grid(row=6, column=0, sticky="w")
    url_ent = ttk.Entry(path_fr, textvariable=url_var)
    url_ent.grid(row=6, column=1, columnspan=2, sticky="ew", padx=(4, 0), pady=2)

    ttk.Label(path_fr, text="Chrome 계정", width=14).grid(row=7, column=0, sticky="w")
    ttk.Entry(path_fr, textvariable=email_var).grid(
        row=7, column=1, columnspan=2, sticky="ew", padx=(4, 0), pady=2
    )
    ttk.Label(path_fr, text="비밀번호(선택)", width=14).grid(row=8, column=0, sticky="w")
    ttk.Entry(path_fr, textvariable=pw_var, show="*").grid(
        row=8, column=1, columnspan=2, sticky="ew", padx=(4, 0), pady=2
    )

    def on_root_path_change(*_a: object) -> None:
        p = root_var.get().strip()
        if not p:
            return
        # 존재하는 폴더로 바뀌면 png·srt·프롬프트를 루트 기준으로 맞춤
        try:
            force = Path(p).expanduser().is_dir()
        except OSError:
            force = False
        apply_root(force=force)

    def on_png_path_change(*_a: object) -> None:
        p = png_var.get().strip()
        if p:
            persist()
            touch_workspace_from_path(p)

    png_var.trace_add("write", on_png_path_change)
    root_var.trace_add("write", on_root_path_change)

    # --- actions ---
    act = ttk.Frame(frm)
    act.grid(row=1, column=0, sticky="ew", pady=(0, 6))

    def selected_scene() -> SceneLine | None:
        sel = scene_list.curselection()
        if not sel:
            return None
        i = int(sel[0])
        if 0 <= i < len(scenes):
            return scenes[i]
        return None

    def reload_scenes() -> None:
        nonlocal scenes
        text = load_scene_text(
            prompt_path=prompt_var.get().strip() or None,
            png_dir=png_var.get().strip() or None,
            fallback_text=scene_text_cache["v"],
        )
        if text.strip():
            scene_text_cache["v"] = text
        parsed = parse_scene_script(text)
        scenes = build_interval_scenes(
            parsed,
            srt_path=srt_var.get().strip() or None,
            interval_sec=_SCENE_INTERVAL_SEC,
        )
        scene_list.delete(0, tk.END)
        png_dir = Path(png_var.get().strip() or ".")
        for sc in scenes:
            mark = "✓ " if png_already_exists(png_dir, sc.sec) else ""
            scene_list.insert(tk.END, f"{mark}{sc.list_label()}")
        if scenes:
            idx = 0
            raw = cfg.get("scene_index", "0")
            try:
                idx = max(0, min(len(scenes) - 1, int(raw)))
            except ValueError:
                idx = 0
            scene_list.selection_set(idx)
            on_scene_select()
            set_status(
                f"씬 {len(scenes)}개 · {scenes[0].label}…{scenes[-1].label}"
            )
        else:
            scene_var.set("")
            set_status(
                "생성할 씬이 없습니다. 이미지프롬프트·SRT(new.srt)를 확인하세요."
            )
        persist()

    def _account() -> tuple[str, str] | None:
        _sync_credentials_to_fields()
        email = email_var.get().strip()
        password = pw_var.get()
        if not email or not password:
            _e, _p = load_credentials()
            if not email and _e:
                email = _e
                email_var.set(_e)
            if not password and _p:
                password = _p
                pw_var.set(_p)
        if not email:
            safe_messagebox(
                root, "showwarning", "2_5 sceneImage", "계정 이메일을 입력하세요."
            )
            return None
        return email, password

    def _ensure_browser_and_paste(
        *,
        email: str,
        password: str,
        url: str,
        model_sel: str,
        model_texts: list[str] | tuple[str, ...],
        pipe: dict,
        png_dir: Path,
        force_paste: bool = True,
        first_command_sec: int | None = None,
        first_scene_prompt: str | None = None,
        submit_context: bool = True,
        force_reopen: bool = False,
    ) -> tuple[object, bool]:
        """브라우저 오픈 + 프롬프트/대본 붙여넣기 (+ 선택: 첫 명령 입력).

        ``force_reopen=True`` 이면 기존 ChromeDebug·세션을 종료하고 새로 연다.
        """
        if force_reopen:
            browser_ready["v"] = False
            info = open_browser_for_account(
                url, email=email, restart_chrome=True
            )
            # CDP 준비는 open_chrome_debug 내부에서 대기함
            time.sleep(0.5)
            append_image_log(
                png_dir,
                f"ChromeDebug 재시작 slot={info.get('slot')} "
                f"port={info.get('debug_port')} "
                f"user_data={info.get('user_data')} reused={info.get('reused')}",
            )
        elif not browser_ready["v"]:
            info = open_browser_for_account(url, email=email)
            time.sleep(0.5)
            append_image_log(
                png_dir,
                f"ChromeDebug 열림 slot={info.get('slot')} "
                f"port={info.get('debug_port')} "
                f"user_data={info.get('user_data')} reused={info.get('reused')}",
            )
        if not has_playwright():
            raise RuntimeError("Playwright가 필요합니다.")

        sess = get_image_session(profile_dir())
        if not browser_ready["v"]:
            safe_after(root, lambda: set_status("Genspark 페이지 연결·로그인…"))
            result = sess.open_and_select_model(
                url=url,
                model_selector=model_sel,
                email=email,
                password=password,
                model_texts=model_texts,
            )
            logged_in = bool(isinstance(result, dict) and result.get("logged_in"))
            model_ok = bool(isinstance(result, dict) and result.get("model_auto"))
            append_image_log(
                png_dir,
                f"세션 준비 — login={'OK' if logged_in else '확인'} "
                f"model={pipe.get('model')} auto={model_ok}",
            )
            browser_ready["v"] = True
        else:
            model_ok = True

        # 붙여넣기 직전: 없는 SRT/프롬프트 경로를 루트·모듈에서 재탐색
        prompt_path = prompt_var.get().strip()
        srt_path = srt_var.get().strip()
        if not prompt_path or not Path(prompt_path).is_file():
            found_p = find_image_prompt_file(preferred=prompt_path or None)
            if found_p is not None:
                prompt_path = str(found_p)
                prompt_var.set(prompt_path)
        if not srt_path or not Path(srt_path).is_file():
            found_s = find_default_srt(root_var.get().strip() or ".")
            if found_s is not None:
                srt_path = str(found_s)
                srt_var.set(srt_path)
                append_image_log(png_dir, f"SRT 경로 재지정 → {srt_path}")

        stats = paste_payload_stats(prompt_path, srt_path)
        paste = build_paste_payload(prompt_path, srt_path)
        if force_paste:
            if not stats["prompt_ok"]:
                raise RuntimeError(
                    "이미지프롬프트 파일을 읽을 수 없습니다.\n"
                    f"경로: {prompt_path or '(비어 있음)'}"
                )
            if not stats["srt_ok"]:
                raise RuntimeError(
                    "SRT 파일을 읽을 수 없습니다. (프롬프트만 붙여넣히던 원인)\n"
                    f"경로: {srt_path or '(비어 있음)'}\n"
                    "루트/mp3 또는 stt 의 new.srt · all.srt 를 확인하세요."
                )
            if not stats["has_srt_timecode"]:
                raise RuntimeError(
                    f"SRT에 타임코드(-->)가 없습니다.\n{srt_path}"
                )
            safe_after(
                root,
                lambda: set_status(
                    f"SRT·프롬프트 붙여넣기 중… ({stats['prompt_chars']}+{stats['srt_chars']}자)"
                ),
            )
            # 동일 입력창에 SRT·프롬프트만 붙여넣기 (실행은 SRT_XXX 명령에서)
            if submit_context:
                sess.submit_prompt(
                    url=url,
                    prompt=paste,
                    model_selector=model_sel,
                    try_model_select=not model_ok,
                    model_texts=model_texts,
                )
            else:
                sess.paste_text(
                    url=url,
                    text=paste,
                    model_selector=model_sel,
                    try_model_select=not model_ok,
                    model_texts=model_texts,
                )
            append_image_log(
                png_dir,
                f"입력창 붙여넣기 — 프롬프트 {stats['prompt_chars']}자"
                f" + SRT {stats['srt_chars']}자"
                f" = 합계 {len(paste)}자"
                f"\n  prompt={prompt_path}\n  srt={srt_path}",
            )
            time.sleep(1.0)

        if first_command_sec is not None:
            cmd = build_generate_command_from_sources(
                first_command_sec,
                scene_prompt=first_scene_prompt,
                srt_path=srt_path,
                png_dir=png_dir,
                prompt_path=prompt_path or None,
            )
            # SRT·프롬프트가 들어 있는 동일 입력창 끝에 명령만 추가 (실행 안 함)
            sess.paste_text(
                url=url,
                text=cmd,
                model_selector=model_sel,
                try_model_select=False,
                model_texts=model_texts,
                append=True,
            )
            append_image_log(
                png_dir,
                f"동일 입력창에 명령 추가(미실행): {cmd[:180]}"
                + ("…" if len(cmd) > 180 else ""),
            )
            input_prepared["v"] = True
            input_prepared["cmd_sec"] = int(first_command_sec)
            time.sleep(0.5)
        return sess, model_ok

    def _run_scenes(
        todo: list[SceneLine],
        *,
        open_browser_first: bool,
        title: str,
        force_reopen: bool = False,
    ) -> None:
        if busy["v"] and not force_reopen:
            safe_messagebox(
                root,
                "showinfo",
                "2_5 sceneImage",
                "이미 작업 중입니다. 끝난 뒤 「실행」를 다시 누르세요.",
            )
            return
        acc = _account()
        if acc is None:
            return
        email, password = acc
        png_dir = Path(png_var.get().strip())
        if not str(png_dir):
            safe_messagebox(root, "showwarning", "2_5 sceneImage", "png 폴더를 지정하세요.")
            return
        if not todo:
            safe_messagebox(
                root, "showinfo", "2_5 sceneImage", "생성할 씬이 없거나 모두 이미 있습니다."
            )
            return
        pipe = load_pipeline_config()
        url = preferred_genspark_url(
            url_var.get().strip() or str(pipe.get("genspark_url") or "")
        )
        model_sel = load_model_selector()
        model_texts = model_name_variants(str(pipe.get("model") or "Nano Banana Pro"))
        do_limit_wait = bool(hourly_retry_var.get())
        gen_timeout = max(120, int(pipe.get("generate_timeout_sec") or 120))
        first_sec = int(todo[0].sec)
        # 입력창에 컨텍스트+명령이 없으면 붙여넣기 준비 (전송은 run_scene에서)
        need_prepare = (
            force_reopen
            or open_browser_first
            or (not browser_ready["v"])
            or (not input_prepared["v"])
            or (input_prepared.get("cmd_sec") != first_sec)
        )
        persist()
        wait_cancel["v"] = False

        def _session_start_hm() -> tuple[int, int] | None:
            return parse_session_start_hm(session_start_var.get())

        def _recover_reset_at_via_browser(*, reason: str) -> datetime | None:
            """정상화 시각 미확인 시 브라우저 종료·재오픈으로 배너에서 읽기."""
            max_tries = 3
            for attempt in range(1, max_tries + 1):
                if wait_cancel["v"] or not hourly_retry_var.get():
                    return None
                append_image_log(
                    png_dir,
                    f"정상화 시각 미확인 — 브라우저 재오픈으로 배너 확인 "
                    f"({attempt}/{max_tries}) — {reason}",
                )
                safe_after(
                    root,
                    lambda a=attempt: set_status(
                        f"한도 — 정상화 시각 확인 위해 브라우저 재오픈 ({a}/{max_tries})"
                    ),
                )
                try:
                    close_chrome_debug()
                except Exception as close_ex:
                    append_image_log(
                        png_dir, f"정상화 확인 전 브라우저 종료 경고: {close_ex}"
                    )
                browser_ready["v"] = False
                input_prepared["v"] = False
                input_prepared["cmd_sec"] = None
                try:
                    from scene_image.genspark_image import reset_image_session

                    reset_image_session()
                except Exception:
                    pass
                time.sleep(1.0)
                try:
                    info = open_browser_for_account(
                        url, email=email, restart_chrome=True
                    )
                    append_image_log(
                        png_dir,
                        f"정상화 확인용 ChromeDebug "
                        f"port={info.get('debug_port')} attempt={attempt}",
                    )
                    time.sleep(0.5)
                    sess = get_image_session(profile_dir())
                    sess.open_and_select_model(
                        url=url,
                        model_selector=model_sel,
                        email=email,
                        password=password,
                        model_texts=model_texts,
                    )
                    browser_ready["v"] = True
                    probed = sess.probe_limit_reset(
                        url=url, email=email, password=password
                    )
                    raw_at = (probed or {}).get("reset_at")
                    snip = ((probed or {}).get("snippet") or "")[:200]
                    append_image_log(
                        png_dir,
                        f"배너 probe reset_at={raw_at or '-'} "
                        f"is_limit={(probed or {}).get('is_limit')} "
                        f"snip={snip!r}",
                    )
                    if raw_at:
                        try:
                            return datetime.strptime(str(raw_at), "%Y-%m-%dT%H:%M:%S")
                        except ValueError:
                            pass
                        parsed = resolve_limit_reset_at(str(raw_at))
                        if parsed is not None:
                            return parsed
                    # 스니펫만으로도 파싱 시도
                    from scene_image.limit_detect import parse_reset_at

                    snip_full = (probed or {}).get("snippet") or ""
                    parsed2 = parse_reset_at(snip_full)
                    if parsed2 is not None:
                        return parsed2
                except Exception as probe_ex:
                    append_image_log(
                        png_dir,
                        f"정상화 시각 배너 확인 실패 ({attempt}/{max_tries}): {probe_ex}",
                    )
                finally:
                    try:
                        close_chrome_debug()
                    except Exception:
                        pass
                    browser_ready["v"] = False
                    input_prepared["v"] = False
                    input_prepared["cmd_sec"] = None
                    try:
                        from scene_image.genspark_image import reset_image_session

                        reset_image_session()
                    except Exception:
                        pass
                time.sleep(2.0)
            return None

        def _wait_until_reset(*, reset_at: datetime, reason: str) -> bool:
            """재설정 시각까지 대기. True=재개, False=취소."""
            now = datetime.now()
            wait_sec = int((reset_at - now).total_seconds()) + _LIMIT_RESET_BUFFER_SEC
            wait_sec = max(30, wait_sec)
            chunk = _LIMIT_WAIT_CHUNK_SEC
            label = format_reset_at(reset_at)
            append_image_log(
                png_dir,
                f"한도 대기 시작 — 정상화 예상 {label} ({wait_sec // 60}분) — {reason}",
            )
            safe_after(root, lambda: set_limit_reset_display(reset_at))
            safe_after(root, lambda: set_limit_waiting(True))
            elapsed = 0
            while elapsed < wait_sec:
                if wait_cancel["v"] or not hourly_retry_var.get():
                    safe_after(root, lambda: set_limit_waiting(False))
                    append_image_log(png_dir, "한도 대기 취소됨")
                    return False
                left = wait_sec - elapsed
                h, rem = divmod(left, 3600)
                m, s = divmod(rem, 60)
                safe_after(
                    root,
                    lambda hh=h, mm=m, ss=s, r=reason, lbl=label: set_status(
                        f"한도 대기 {hh:d}:{mm:02d}:{ss:02d} — "
                        f"정상화 예상 {lbl} — {r}"
                    ),
                )
                time.sleep(min(chunk, left))
                elapsed += chunk
            safe_after(root, lambda: set_limit_waiting(False))
            append_image_log(
                png_dir, f"한도 대기 종료 — 정상화 예상 {label} — 재시도"
            )
            return True

        def _wait_for_limit(reason: str, err: BaseException | str) -> bool:
            """재설정 시각까지 대기. 배너 시각이 없으면 브라우저 재오픈으로 확인."""
            session_hm = _session_start_hm()
            reset_at = resolve_limit_reset_at(
                err, session_start_hm=session_hm
            )
            if reset_at is None:
                reset_at = _recover_reset_at_via_browser(reason=reason)
            if reset_at is None and session_hm:
                # GUI에 수동 입력된 실행 시작이 있으면 최후 보조
                reset_at = resolve_limit_reset_at(
                    err, session_start_hm=session_hm
                )
            if reset_at is None:
                append_image_log(
                    png_dir,
                    "한도 대기 불가 — 브라우저 재오픈으로도 정상화 시각 확인 실패",
                )
                safe_after(
                    root,
                    lambda: set_status(
                        "한도 — 정상화 시각을 배너에서 읽지 못했습니다"
                    ),
                )
                return False
            safe_after(root, lambda ra=reset_at: set_limit_reset_display(ra))
            return _wait_until_reset(reset_at=reset_at, reason=reason)

        def work() -> None:
            try:
                if not has_playwright():
                    raise RuntimeError(
                        "Playwright가 없습니다. 수동으로 생성하세요."
                    )
                set_tab_log_png_dir(png_dir)
                append_image_log(
                    png_dir,
                    f"탭로그 ON — {title} · 씬 {len(todo)}개 · reopen={force_reopen}"
                    + (f" · 한도대기ON" if do_limit_wait else ""),
                )
                sess, model_ok = _ensure_browser_and_paste(
                    email=email,
                    password=password,
                    url=url,
                    model_sel=model_sel,
                    model_texts=model_texts,
                    pipe=pipe,
                    png_dir=png_dir,
                    force_paste=need_prepare,
                    first_command_sec=first_sec if need_prepare else None,
                    first_scene_prompt=(
                        todo[0].prompt if need_prepare and todo else None
                    ),
                    # 컨텍스트+명령은 입력만 — 전송은 아래 run_scene(첫 씬)
                    submit_context=False,
                    force_reopen=force_reopen,
                )
                saved_n = 0
                skipped_n = 0
                ran_n = 0
                failed_n = 0
                fail_streak = 0
                cancelled_wait = False
                remaining = list(todo)
                total_n = len(todo)

                while remaining:
                    sc = remaining[0]
                    if png_already_exists(png_dir, sc.sec):
                        skipped_n += 1
                        path = str(scene_png_path(png_dir, sc.sec))
                        append_image_log(
                            png_dir, f"{sc.label} 건너뜀 (기존 PNG) {path}"
                        )

                        def _skip(s=sc, p=path) -> None:
                            append_collected_path(s.sec, p)

                        safe_after(root, _skip)
                        remaining.pop(0)
                        continue
                    cmd = build_generate_command_from_sources(
                        sc.sec,
                        scene_prompt=sc.prompt,
                        srt_path=srt_var.get().strip() or None,
                        interval_sec=_SCENE_INTERVAL_SEC,
                        png_dir=png_dir,
                        prompt_path=prompt_var.get().strip() or None,
                    )
                    # 첫 실행·한도 재오픈 후: 입력창에 준비된 명령이 이 씬이면 그대로 전송
                    use_box = (
                        bool(input_prepared["v"])
                        and input_prepared.get("cmd_sec") == int(sc.sec)
                    )
                    done_i = total_n - len(remaining) + 1
                    safe_after(
                        root,
                        lambda s=sc, n=done_i, c=cmd, u=use_box: set_status(
                            f"{title} {n}/{total_n} — "
                            + ("입력창 전송 · " if u else "")
                            + c[:80]
                            + ("…" if len(c) > 80 else "")
                        ),
                    )
                    try:
                        out = sess.run_scene_with_retry(
                            url=url,
                            prompt=sc.prompt,
                            png_dir=png_dir,
                            srt_sec=sc.sec,
                            model_selector=model_sel,
                            model_texts=model_texts,
                            try_model_select=(ran_n == 0),
                            retry_count=1,
                            retry_wait_sec=0,
                            generate_timeout_sec=gen_timeout,
                            use_existing_input=use_box,
                            srt_path=srt_var.get().strip() or None,
                            interval_sec=_SCENE_INTERVAL_SEC,
                            prompt_path=prompt_var.get().strip() or None,
                        )
                    except Exception as scene_err:
                        failed_n += 1
                        fail_streak += 1
                        if use_box:
                            input_prepared["v"] = False
                            input_prepared["cmd_sec"] = None
                        ran_n += 1
                        err_s = str(scene_err)
                        is_limit = isinstance(scene_err, AiImageLimitError) or (
                            _looks_like_limit_error(err_s)
                        )
                        limit_hit = is_limit or (fail_streak >= _LIMIT_FAIL_STREAK)
                        # 실패 분석 로그
                        kind = "limit" if is_limit else (
                            "fail_streak" if limit_hit else "fail"
                        )
                        extra = f"streak={fail_streak}"
                        if isinstance(scene_err, AiImageLimitError):
                            if scene_err.reset_at:
                                extra += (
                                    " reset_at="
                                    + scene_err.reset_at.strftime("%Y-%m-%d %H:%M")
                                )
                            page_snip = scene_err.raw or ""
                        else:
                            page_snip = ""
                        append_fail_log(
                            png_dir,
                            scene=sc.label,
                            error=err_s,
                            kind=kind,
                            page_snip=page_snip,
                            extra=extra,
                        )
                        if do_limit_wait and limit_hit and hourly_retry_var.get():
                            if isinstance(scene_err, AiImageLimitError) and scene_err.reset_at:
                                safe_after(
                                    root,
                                    lambda ra=scene_err.reset_at: set_limit_reset_display(
                                        ra
                                    ),
                                )
                            append_image_log(
                                png_dir,
                                f"{sc.label} 실패(한도 "
                                f"{'확정' if is_limit else '추정'} "
                                f"streak={fail_streak}) "
                                f"— 브라우저 종료 후 대기·재오픈\n{err_s}",
                            )
                            safe_after(
                                root,
                                lambda s=sc, e=err_s: set_status(
                                    f"{s.label} 한도 — 브라우저 종료·대기 — {e[:50]}"
                                ),
                            )
                            # 한도 대기 전: 이미지용 브라우저·세션 종료
                            try:
                                close_chrome_debug()
                                append_image_log(
                                    png_dir, "한도 대기 전 ChromeDebug 종료"
                                )
                            except Exception as close_ex:
                                append_image_log(
                                    png_dir, f"브라우저 종료 경고: {close_ex}"
                                )
                            browser_ready["v"] = False
                            input_prepared["v"] = False
                            input_prepared["cmd_sec"] = None
                            if not _wait_for_limit(f"{sc.label} 한도", scene_err):
                                cancelled_wait = True
                                break
                            # 재개: 「실행」와 동일 — 재오픈·로그인·붙여넣기·이 씬 명령
                            append_image_log(
                                png_dir,
                                f"한도 대기 종료 — 브라우저 재오픈 후 {sc.label} 재개",
                            )
                            safe_after(
                                root,
                                lambda s=sc: set_status(
                                    f"한도 해제 추정 — 브라우저 재오픈 · {s.label}"
                                ),
                            )
                            try:
                                sess, model_ok = _ensure_browser_and_paste(
                                    email=email,
                                    password=password,
                                    url=url,
                                    model_sel=model_sel,
                                    model_texts=model_texts,
                                    pipe=pipe,
                                    png_dir=png_dir,
                                    force_paste=True,
                                    first_command_sec=int(sc.sec),
                                    first_scene_prompt=sc.prompt,
                                    submit_context=False,
                                    force_reopen=True,
                                )
                            except Exception as reopen_ex:
                                append_fail_log(
                                    png_dir,
                                    scene=sc.label,
                                    error=str(reopen_ex),
                                    kind="reopen_fail",
                                    extra="한도 대기 후 브라우저 재오픈 실패",
                                )
                                append_image_log(
                                    png_dir,
                                    f"재오픈 실패 — 중단\n{reopen_ex}",
                                )
                                cancelled_wait = True
                                break
                            fail_streak = 0
                            continue
                        # 한도 재시도 OFF 또는 한도 아님 → 다음 씬
                        remaining.pop(0)
                        append_image_log(
                            png_dir,
                            f"{sc.label} 실패 — 다음 씬 계속\n{err_s}",
                        )
                        safe_after(
                            root,
                            lambda s=sc, e=err_s: set_status(
                                f"{s.label} 실패 · 다음 씬 계속 — {e[:80]}"
                            ),
                        )
                        continue
                    if use_box:
                        input_prepared["v"] = False
                        input_prepared["cmd_sec"] = None
                    ran_n += 1
                    fail_streak = 0
                    remaining.pop(0)
                    paths = list((out or {}).get("saved") or [])
                    saved_n += len(paths)
                    show_paths = paths or [str(scene_png_path(png_dir, sc.sec))]
                    append_image_log(
                        png_dir,
                        f"{sc.label} 생성·다운로드 완료\n" + "\n".join(show_paths),
                    )

                    def _done_paths(s=sc, ps=list(show_paths)) -> None:
                        for p in ps:
                            append_collected_path(s.sec, p)

                    safe_after(root, _done_paths)

                # 마지막 씬까지 끝난 뒤: 늦은 이미지 회수 + PNG 존재로 실패 최종 확인
                fail_labels: list[str] = []
                recovered_n = 0
                if not cancelled_wait:
                    missing_secs = [
                        int(sc.sec)
                        for sc in todo
                        if not png_already_exists(png_dir, sc.sec)
                    ]
                    if missing_secs:
                        safe_after(
                            root,
                            lambda n=len(missing_secs): set_status(
                                f"{title} 완료 전 — 다운로드 실패 {n}건 확인·회수…"
                            ),
                        )
                        try:
                            salvage = sess.salvage_pending(
                                png_dir=png_dir, secs=missing_secs
                            ) or {}
                            recovered_n = int(salvage.get("recovered") or 0)
                            for p in list(salvage.get("saved") or []):
                                try:
                                    name = Path(str(p)).name
                                    m = re.match(
                                        r"SRT_(\d+)\.png$", name, re.IGNORECASE
                                    )
                                    sec_r = int(m.group(1)) if m else -1
                                except Exception:
                                    sec_r = -1

                                def _salvaged(sec=sec_r, path=str(p)) -> None:
                                    if sec >= 0:
                                        append_collected_path(sec, path)

                                safe_after(root, _salvaged)
                            if recovered_n:
                                append_image_log(
                                    png_dir,
                                    f"완료 전 회수 {recovered_n}개 — "
                                    + ", ".join(
                                        f"SRT_{int(s):03d}"
                                        for s in (
                                            salvage.get("recovered_secs") or []
                                        )[:20]
                                    ),
                                )
                        except Exception as salvage_ex:
                            append_image_log(
                                png_dir,
                                f"완료 전 회수 경고: {salvage_ex}",
                            )
                    # 예외 카운트 대신 실제 파일 기준으로 실패 확정
                    fail_scenes = [
                        sc
                        for sc in todo
                        if not png_already_exists(png_dir, sc.sec)
                    ]
                    fail_labels = [sc.label for sc in fail_scenes]
                    failed_n = len(fail_scenes)
                    saved_n = sum(
                        1 for sc in todo if png_already_exists(png_dir, sc.sec)
                    )
                    if fail_labels:
                        append_image_log(
                            png_dir,
                            f"다운로드 실패 확정 {failed_n}건: "
                            + ", ".join(fail_labels[:30])
                            + (f" 외 {failed_n - 30}" if failed_n > 30 else ""),
                        )
                    else:
                        append_image_log(
                            png_dir,
                            "다운로드 실패 없음 — 대상 씬 PNG 모두 확인",
                        )

                def done() -> None:
                    set_busy(False)
                    reload_scenes()
                    left_n = len(remaining) if cancelled_wait else 0
                    will_shutdown = bool(shutdown_var.get())
                    shutdown_note = ""
                    if will_shutdown:
                        delay_sec = _SHUTDOWN_DELAY_SEC
                        try:
                            close_chrome_debug()
                        except Exception:
                            pass
                        append_image_log(
                            png_dir,
                            f"PC 종료 예약 {delay_sec}초 후 "
                            f"(취소: shutdown /a)",
                        )
                        _schedule_pc_shutdown(delay_sec=delay_sec)
                        shutdown_note = (
                            f"\n\n약 {delay_sec}초 후 PC가 종료됩니다."
                            "\n취소: 명령 프롬프트에서 shutdown /a"
                        )
                    fail_note = ""
                    if fail_labels:
                        shown = ", ".join(fail_labels[:15])
                        extra = (
                            f" 외 {len(fail_labels) - 15}개"
                            if len(fail_labels) > 15
                            else ""
                        )
                        fail_note = f"\n다운로드 실패: {shown}{extra}"
                    recover_note = (
                        f" · 회수 {recovered_n}" if recovered_n else ""
                    )
                    set_status(
                        f"{title} "
                        + ("대기 취소 — " if cancelled_wait else "완료 — ")
                        + f"저장 {saved_n} · 건너뜀 {skipped_n}"
                        + (f" · 실패 {failed_n}" if failed_n else "")
                        + recover_note
                        + (f" · 남음 {left_n}" if left_n else "")
                        + (
                            f" · PC 종료 {_SHUTDOWN_DELAY_SEC}초 후"
                            if will_shutdown
                            else ""
                        )
                        + f" → {png_dir}"
                    )
                    msg = (
                        ("한도 대기 취소\n" if cancelled_wait else "")
                        + f"저장 {saved_n}개 · 건너뜀 {skipped_n}개"
                        + (f" · 실패 {failed_n}개" if failed_n else "")
                        + (f" · 회수 {recovered_n}개" if recovered_n else "")
                        + (f" · 남음 {left_n}개" if left_n else "")
                        + fail_note
                        + f"\n{png_dir}"
                        + shutdown_note
                    )
                    show_toast(
                        root,
                        msg,
                        title="2_5 sceneImage · 완료",
                    )

                safe_after(root, done)
            except Exception as e:
                err = str(e)
                try:
                    append_image_log(png_dir, f"{title} 오류: {err}")
                except Exception:
                    pass

                def fail() -> None:
                    set_busy(False)
                    set_status(f"오류: {err}")
                    safe_messagebox(root, "showerror", "2_5 sceneImage", err)

                safe_after(root, fail)

        set_busy(True)
        set_status(
            f"{title} 준비 — {len(todo)}개"
            + (" · 입력창 준비" if need_prepare else " · 입력창 전송")
            + (" · 한도대기ON" if do_limit_wait else "")
        )
        threading.Thread(target=work, daemon=True).start()

    def add_instance() -> None:
        """다른 장(루트)용 sceneImage 창을 병렬 실행."""
        try:
            before = count_claimable_slots()
            _spawn_scene_image_instance()
        except Exception as e:
            safe_messagebox(root, "showerror", "2_5 sceneImage", str(e))
            return
        slot = get_active_slot()
        slot_lbl = slot.label if slot else "?"
        left = max(0, before - 1)
        set_status(
            f"새 인스턴스 실행 — 이 창 [{slot_lbl}] · "
            f"남은 슬롯 {left}개 · 장(루트)만 다르게 지정"
        )

    def open_browser() -> None:
        """재오픈 → SRT·프롬프트·명령 → 생성·다운로드·요청대기 반복까지 일괄."""
        if busy["v"]:
            safe_messagebox(
                root,
                "showinfo",
                "2_5 sceneImage",
                "이미 작업 중입니다. 끝난 뒤 다시 누르세요.",
            )
            return
        browser_ready["v"] = False
        input_prepared["v"] = False
        input_prepared["cmd_sec"] = None
        try:
            apply_root(force=True)
        except Exception:
            reload_scenes()
        png_dir = Path(png_var.get().strip() or ".")
        if not str(png_dir).strip() or png_dir == Path("."):
            safe_messagebox(root, "showwarning", "2_5 sceneImage", "png 폴더를 지정하세요.")
            return
        srt_now = srt_var.get().strip()
        if not srt_now or not Path(srt_now).is_file():
            found = find_default_srt(root_var.get().strip() or ".")
            if found is not None:
                srt_var.set(str(found))
            else:
                safe_messagebox(
                    root,
                    "showwarning",
                    "2_5 sceneImage",
                    "SRT 파일이 없습니다.\n"
                    "루트 하위 mp3/new.srt 또는 all.srt 를 지정하세요.",
                )
                return
        todo = [sc for sc in scenes if not png_already_exists(png_dir, sc.sec)]
        sel = _parse_manual_secs(manual_var.get(), [sc.sec for sc in scenes])
        if sel:
            sel_set = set(sel)
            todo = [sc for sc in todo if sc.sec in sel_set]
            if not todo:
                safe_messagebox(
                    root,
                    "showinfo",
                    "2_5 sceneImage",
                    "구간 내 생성할 씬이 없거나 PNG가 이미 있습니다.\n"
                    f"구간: {manual_var.get().strip()}",
                )
                return
        _run_scenes(
            todo,
            open_browser_first=True,
            title="실행·생성",
            force_reopen=True,
        )

    def manual_generate() -> None:
        if busy["v"]:
            return
        reload_scenes()
        avail = [sc.sec for sc in scenes]
        secs = _parse_manual_secs(manual_var.get(), avail)
        if not secs:
            safe_messagebox(
                root,
                "showwarning",
                "2_5 sceneImage",
                "초·구간을 입력하세요.\n예: 10,20,120 · 220~500 · 720~",
            )
            return
        by_sec = {sc.sec: sc for sc in scenes}
        todo: list[SceneLine] = []
        missing: list[int] = []
        for sec in secs:
            sc = by_sec.get(sec)
            if sc is None:
                missing.append(sec)
            else:
                todo.append(sc)
        if missing:
            safe_messagebox(
                root,
                "showwarning",
                "2_5 sceneImage",
                "씬 목록에 없는 초: "
                + ", ".join(str(s) for s in missing)
                + "\n이미지프롬프트·SRT 간격을 확인하세요.",
            )
            if not todo:
                return
        persist()
        _run_scenes(todo, open_browser_first=False, title="수동 생성")

    btn_browser = ttk.Button(act, text="실행", command=open_browser)
    btn_browser.pack(side=tk.LEFT, padx=(0, 6))
    ttk.Button(act, text="인스턴스추가", command=add_instance).pack(
        side=tk.LEFT, padx=(0, 6)
    )
    btn_cancel_wait = ttk.Button(
        act, text="대기 취소", width=10, command=cancel_limit_wait, state=tk.DISABLED
    )
    btn_cancel_wait.pack(side=tk.LEFT, padx=(0, 6))
    ttk.Checkbutton(
        act,
        text="완료후 PC종료",
        variable=shutdown_var,
        command=persist,
    ).pack(side=tk.LEFT, padx=(8, 0))

    ttk.Label(frm, textvariable=scene_var).grid(row=2, column=0, sticky="w", pady=(0, 4))

    # --- main panes ---
    paned = ttk.Panedwindow(frm, orient=tk.VERTICAL)
    paned.grid(row=3, column=0, sticky="nsew")

    manual_fr = ttk.LabelFrame(
        paned, text="이미지 구간 생성 (10,20 / 220~500 / 720~ …)", padding=4
    )
    lists_fr = ttk.Frame(paned)
    paned.add(manual_fr, weight=1)
    paned.add(lists_fr, weight=3)

    manual_fr.grid_columnconfigure(0, weight=1)
    ttk.Label(
        manual_fr,
        text="특정 초·구간만 생성 — 비우면 「실행」은 전체 미생성 씬.",
        foreground="#555",
    ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 4))
    manual_ent = ttk.Entry(manual_fr, textvariable=manual_var)
    manual_ent.grid(row=1, column=0, sticky="ew", padx=(0, 6))
    btn_manual = ttk.Button(manual_fr, text="선택 생성", width=10, command=manual_generate)
    btn_manual.grid(row=1, column=1, sticky="e")

    lists_fr.grid_columnconfigure(0, weight=1)
    lists_fr.grid_columnconfigure(1, weight=1)
    lists_fr.grid_rowconfigure(0, weight=1)

    left = ttk.LabelFrame(lists_fr, text="파싱된 씬", padding=4)
    right = ttk.LabelFrame(lists_fr, text="저장된 경로", padding=4)
    left.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
    right.grid(row=0, column=1, sticky="nsew")
    left.grid_columnconfigure(0, weight=1)
    left.grid_rowconfigure(0, weight=1)
    right.grid_columnconfigure(0, weight=1)
    right.grid_rowconfigure(0, weight=1)

    scene_list = tk.Listbox(left, activestyle="dotbox", exportselection=False)
    scene_sb = ttk.Scrollbar(left, orient=tk.VERTICAL, command=scene_list.yview)
    scene_list.configure(yscrollcommand=scene_sb.set)
    scene_list.grid(row=0, column=0, sticky="nsew")
    scene_sb.grid(row=0, column=1, sticky="ns")

    link_list = tk.Listbox(right, activestyle="dotbox", exportselection=False)
    link_sb = ttk.Scrollbar(right, orient=tk.VERTICAL, command=link_list.yview)
    link_list.configure(yscrollcommand=link_sb.set)
    link_list.grid(row=0, column=0, sticky="nsew")
    link_sb.grid(row=0, column=1, sticky="ns")

    def on_scene_select(_event: tk.Event | None = None) -> None:
        sc = selected_scene()
        if sc is None:
            scene_var.set("")
            return
        exists = png_already_exists(Path(png_var.get().strip() or "."), sc.sec)
        mark = " · 이미 있음" if exists else ""
        scene_var.set(f"{sc.label} → {sc.png_name}  |  {len(sc.prompt)}자{mark}")
        persist()

    scene_list.bind("<<ListboxSelect>>", on_scene_select)

    ttk.Label(frm, textvariable=status_var).grid(row=4, column=0, sticky="ew", pady=(8, 0))
    tip = (
        "「실행」= 재오픈 → 생성·다운로드 반복"
        " · 「인스턴스추가」= 다른 장(루트) 병렬 다운로드 · 슬롯(포트) 자동 분리"
        " · 한도 시: 브라우저 종료 → 정상화 시각 확인(배너·필요 시 재오픈) → 대기 → 재개"
        " · 완료후 PC종료: 체크 시 실행 종료 후 약 60초 뒤 · 취소 shutdown /a"
        " · 실패 로그: image_fail.log"
    )
    ttk.Label(frm, text=tip, foreground="#555").grid(row=5, column=0, sticky="w", pady=(4, 0))

    def on_close() -> None:
        persist()
        release_chrome_slot()

    if standalone:
        bind_close(root, standalone, on_close)
    else:
        bind_hub_destroy(root, on_close)

    def _boot() -> None:
        if root_var.get().strip():
            apply_root(force=False)
        elif png_var.get().strip():
            auto_assign_from_png(force=False)
        else:
            reload_scenes()

    root.after(150, _boot)
    run_mainloop(root, standalone)
