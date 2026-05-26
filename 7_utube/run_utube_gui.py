#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""7_utube GUI 진입점."""

from __future__ import annotations

import sys
import traceback
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    try:
        from utube.gui_app import main as app_main

        app_main()
    except Exception:
        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()
