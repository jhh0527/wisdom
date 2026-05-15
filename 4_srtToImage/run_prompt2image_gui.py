#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GUI 실행 파일 진입점 (콘솔 없음)."""

from __future__ import annotations

import sys
import traceback


def main() -> None:
    try:
        from prompt2image.gui_app import main as gui_main

        gui_main()
    except Exception:
        if getattr(sys, "frozen", False):
            try:
                import tkinter as tk
                from tkinter import messagebox

                root = tk.Tk()
                root.withdraw()
                messagebox.showerror("4_srtToImage GUI", traceback.format_exc())
                root.destroy()
            except Exception:
                pass
        else:
            traceback.print_exc()
            raise


if __name__ == "__main__":
    main()
