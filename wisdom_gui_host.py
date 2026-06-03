# -*- coding: utf-8 -*-
"""모듈 GUI — 단독 창(Tk) 또는 wisdom 허브 탭(Frame) 에 붙일 때 공통 처리."""

from __future__ import annotations

from typing import Callable

import tkinter as tk

_hub_shutting_down = False


def is_hub_shutting_down() -> bool:
    return _hub_shutting_down


def request_shutdown(root: tk.Misc) -> None:
    """허브 종료 시 예약 콜백·Toplevel·기본 루트 정리 (다른 창이 뜨는 현상 방지)."""
    global _hub_shutting_down
    _hub_shutting_down = True
    top = root.winfo_toplevel()
    try:
        for aid in top.tk.call("after", "info"):
            try:
                top.after_cancel(aid)
            except tk.TclError:
                pass
    except tk.TclError:
        pass
    _destroy_toplevels(top)
    try:
        tk._default_root = None  # type: ignore[attr-defined]
    except Exception:
        pass


def _destroy_toplevels(widget: tk.Misc) -> None:
    for child in widget.winfo_children():
        _destroy_toplevels(child)
        try:
            if child.winfo_class() == "Toplevel":
                child.destroy()
        except tk.TclError:
            pass


def tk_host(container: tk.Misc | None) -> tuple[tk.Misc, bool]:
    """자식 위젯의 부모. ``standalone`` 이면 ``tk.Tk()``."""
    standalone = container is None
    host = tk.Tk() if standalone else container
    return host, standalone


def apply_window_chrome(
    host: tk.Misc,
    standalone: bool,
    *,
    title: str | None = None,
    geometry: str | None = None,
    minsize: tuple[int, int] | None = None,
) -> None:
    if not standalone:
        return
    if title:
        host.title(title)
    if minsize:
        host.minsize(*minsize)
    if geometry:
        host.geometry(geometry)


def bind_close(
    host: tk.Misc,
    standalone: bool,
    on_close: Callable[[], None],
) -> None:
    if not standalone:
        return

    def _wrapped() -> None:
        on_close()
        try:
            host.destroy()
        except tk.TclError:
            pass

    host.protocol("WM_DELETE_WINDOW", _wrapped)


def run_mainloop(host: tk.Misc, standalone: bool) -> None:
    if standalone:
        host.mainloop()
