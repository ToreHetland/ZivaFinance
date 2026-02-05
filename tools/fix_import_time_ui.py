#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path
import shutil
import argparse

ROOT = Path(__file__).resolve().parents[1]

# Matches:
# lang = st.session_state.get("language", "no")
# st.subheader(t("settings.language_region", lang))
PATTERN = re.compile(
    r"""
(^\s*lang\s*=\s*st\.session_state\.get\(\s*["']language["']\s*,\s*["'][^"']+["']\s*\)\s*$\n)?
^\s*st\.subheader\(\s*t\(\s*["']settings\.language_region["']\s*,\s*lang\s*\)\s*\)\s*$
""",
    re.MULTILINE | re.VERBOSE,
)

def iter_py_files():
    for p in ROOT.rglob("*.py"):
        if any(part in {".venv", "venv", "__pycache__", ".git", "_backup_import_ui"} for part in p.parts):
            continue
        yield p

def backup_file(src: Path, backup_dir: Path):
    rel = src.relative_to(ROOT)
    dst = backup_dir / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--backup", action="store_true")
    args = ap.parse_args()

    backup_dir = ROOT / "_backup_import_ui"
    changed = []

    for p in iter_py_files():
        txt = p.read_text(encoding="utf-8", errors="ignore")
        new = PATTERN.sub("", txt)
        if new != txt:
            changed.append(p)
            if args.apply:
                if args.backup:
                    backup_file(p, backup_dir)
                # Clean up extra blank lines
                new = re.sub(r"\n{3,}", "\n\n", new)
                p.write_text(new, encoding="utf-8")

    print(f"Files with removed import-time UI blocks: {len(changed)}")
    for p in changed:
        print(" -", p.relative_to(ROOT))

    if not args.apply:
        print("\nDry run only. Re-run with --apply to write changes.")
    else:
        if args.backup:
            print(f"\nBackups stored in: {backup_dir}")
        print("\nDone.")

if __name__ == "__main__":
    main()
