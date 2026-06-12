# -*- coding: utf-8 -*-
"""드라이브·기본 경로."""

from __future__ import annotations

from pathlib import Path

SOURCE_DRIVES: tuple[str, ...] = ("C:", "S:", "T:", "U:", "X:")
DEFAULT_DEST_DRIVE = "W:"


def drive_root(letter: str) -> Path:
    d = letter.strip().rstrip("\\/")
    if not d.endswith(":"):
        d = f"{d}:"
    return Path(f"{d}/")


def default_dest_dir() -> Path:
    w = drive_root(DEFAULT_DEST_DRIVE)
    return w if w.exists() else Path.home()


def available_source_drives() -> list[str]:
    out: list[str] = []
    for letter in SOURCE_DRIVES:
        if drive_root(letter).exists():
            out.append(letter)
    return out


def first_available_source() -> Path:
    for letter in SOURCE_DRIVES:
        root = drive_root(letter)
        if root.exists():
            return root
    return drive_root("C:")
