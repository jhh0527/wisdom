# -*- coding: utf-8 -*-
"""wisdom 통합 허브 — 파이프라인 GUI 를 탭으로 한 창에 표시."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from wisdom_gui_host import request_shutdown
from wisdom_hub.loaders import LOADERS
from wisdom_hub.pipeline import HUB_TABS


def main() -> None:
    root = tk.Tk()
    root.title("wisdom")
    root.minsize(1000, 640)
    root.geometry("1280x800")

    def on_hub_close() -> None:
        request_shutdown(root)
        try:
            root.quit()
        except tk.TclError:
            pass
        try:
            root.destroy()
        except tk.TclError:
            pass

    root.protocol("WM_DELETE_WINDOW", on_hub_close)

    nb = ttk.Notebook(root)
    nb.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

    tab_frames: dict[str, tk.Frame] = {}
    loaded: set[str] = set()

    for title, module in HUB_TABS:
        fr = ttk.Frame(nb, padding=0)
        nb.add(fr, text=title)
        tab_frames[module] = fr

    def ensure_loaded(module: str) -> None:
        if module in loaded:
            return
        fr = tab_frames[module]
        LOADERS[module](fr)
        loaded.add(module)

    def on_tab_changed(_event: object | None = None) -> None:
        try:
            idx = nb.index(nb.select())
        except tk.TclError:
            return
        if 0 <= idx < len(HUB_TABS):
            ensure_loaded(HUB_TABS[idx][1])

    nb.bind("<<NotebookTabChanged>>", on_tab_changed)
    ensure_loaded(HUB_TABS[0][1])
    root.mainloop()


if __name__ == "__main__":
    main()
