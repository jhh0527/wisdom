#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""3_ttsToVoice GUI 진입점 (PyInstaller onefile)."""

from __future__ import annotations

import sys
import traceback


def main() -> None:
    try:
        from elsub.gui_app import main as gui_main

        gui_main()
    except Exception:
        if getattr(sys, "frozen", False):
            try:
                import tkinter as tk
                from tkinter import messagebox

                r = tk.Tk()
                r.withdraw()
                messagebox.showerror("3_ttsToVoice GUI", traceback.format_exc())
                r.destroy()
            except Exception:
                pass
        else:
            traceback.print_exc()
            raise


if __name__ == "__main__":
    main()
