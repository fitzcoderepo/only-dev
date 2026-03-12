#!/usr/bin/env python3
"""
Renames all occurrences of 'name1' -> 'name2' in file contents,
and renames any files/directories containing 'name1' in their name.

Run from project root:
    python rename.py
"""

import os
import sys
from pathlib import Path

OLD = ""
NEW = ""

# Directories to skip entirely
SKIP_DIRS = {".git", "venv", ".venv", "env", "__pycache__", ".egg-info"}

# File extensions to search inside
TEXT_EXTENSIONS = {
    ".py", ".toml", ".md", ".txt", ".html", ".js", ".css", ".json", ".cfg", ".ini", ".env"
}


def should_skip(path: Path) -> bool:
    for part in path.parts:
        if part in SKIP_DIRS or part.endswith(".egg-info"):
            return True
    return False


def replace_in_file(path: Path) -> bool:
    try:
        original = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, PermissionError):
        return False

    if OLD not in original:
        return False

    updated = original.replace(OLD, NEW)
    path.write_text(updated, encoding="utf-8")
    print(f"  updated contents: {path}")
    return True


def rename_path(path: Path) -> Path | None:
    if OLD in path.name:
        new_name = path.name.replace(OLD, NEW)
        new_path = path.parent / new_name
        path.rename(new_path)
        print(f"  renamed: {path} -> {new_path}")
        return new_path
    return None


def main():
    root = Path(".").resolve()
    print(f"Running in: {root}")
    print(f"Replacing '{OLD}' -> '{NEW}'\n")

    # Step 1: Replace contents in all text files
    print("── Step 1: Replacing in file contents ──")
    for path in sorted(root.rglob("*")):
        if should_skip(path):
            continue
        if path.is_file() and path.suffix in TEXT_EXTENSIONS:
            replace_in_file(path)

    # Step 2: Rename files containing OLD in their name
    print("\n── Step 2: Renaming files ──")
    for path in sorted(root.rglob("*"), reverse=True):
        if should_skip(path):
            continue
        if path.is_file() and OLD in path.name:
            rename_path(path)

    # Step 3: Rename directories containing OLD in their name (deepest first)
    print("\n── Step 3: Renaming directories ──")
    for path in sorted(root.rglob("*"), reverse=True):
        if path.is_dir() and OLD in path.name:
            if not should_skip(path):
                rename_path(path)

    print("\nDone.")


if __name__ == "__main__":
    main()