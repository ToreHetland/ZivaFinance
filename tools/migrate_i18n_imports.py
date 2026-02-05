#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path
import shutil
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]  # tools/ -> project root

TARGET_EXTS = {".py"}

FIND_IMPORT_PATTERNS = [
    # exact common form
    (re.compile(r"^\s*from\s+core\.i18n\s+import\s+t\s*$", re.M), "from config.i18n import t"),
    # handle "from core.i18n import t, x" (we'll only rewrite if it imports t)
    (re.compile(r"^\s*from\s+core\.i18n\s+import\s+([^\n]+)\s*$", re.M), None),
]

def iter_py_files(root: Path):
    for p in root.rglob("*"):
        if p.suffix in TARGET_EXTS and p.is_file():
            # ignore venv, caches, git
            if any(part in {".venv", "venv", "__pycache__", ".git"} for part in p.parts):
                continue
            yield p

def rewrite_imports(text: str) -> tuple[str, bool]:
    changed = False

    # 1) exact match replacement
    new_text = FIND_IMPORT_PATTERNS[0][0].sub(FIND_IMPORT_PATTERNS[0][1], text)
    if new_text != text:
        changed = True
        text = new_text

    # 2) broader "from core.i18n import ..." rewrite if it includes t
    m = FIND_IMPORT_PATTERNS[1][0].search(text)
    if m:
        imported = m.group(1)
        # if 't' is among imports, rewrite whole line to config.i18n
        # keep any other imported names exactly as is.
        if re.search(r"(^|,\s*)t(\s*,|$)", imported.strip()):
            repl = f"from config.i18n import {imported.strip()}"
            text2 = FIND_IMPORT_PATTERNS[1][0].sub(repl, text)
            if text2 != text:
                changed = True
                text = text2

    return text, changed

def backup_file(path: Path, backup_dir: Path):
    rel = path.relative_to(PROJECT_ROOT)
    dest = backup_dir / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, dest)

def main():
    parser = argparse.ArgumentParser(description="Migrate imports from core.i18n to config.i18n")
    parser.add_argument("--apply", action="store_true", help="Apply changes (otherwise dry-run)")
    parser.add_argument("--backup", action="store_true", help="Create backups before modifying")
    parser.add_argument("--move-core-i18n", action="store_true", help="Move core/i18n.py aside to core/i18n.py.bak")
    args = parser.parse_args()

    backup_dir = PROJECT_ROOT / "_backup_i18n_migration"
    changed_files = []

    for file_path in iter_py_files(PROJECT_ROOT):
        original = file_path.read_text(encoding="utf-8", errors="ignore")
        updated, changed = rewrite_imports(original)

        # Fix header comment inside config/i18n.py if it mistakenly says "# core/i18n.py"
        if file_path.as_posix().endswith("config/i18n.py"):
            updated2 = updated.replace("# core/i18n.py", "# config/i18n.py")
            if updated2 != updated:
                updated = updated2
                changed = True

        if changed:
            changed_files.append(file_path)

            if args.apply:
                if args.backup:
                    backup_file(file_path, backup_dir)
                file_path.write_text(updated, encoding="utf-8")

    # Optionally move core/i18n.py out of the way (safe test)
    core_i18n = PROJECT_ROOT / "core" / "i18n.py"
    if args.apply and args.move_core_i18n and core_i18n.exists():
        target = PROJECT_ROOT / "core" / "i18n.py.bak"
        if args.backup:
            backup_file(core_i18n, backup_dir)
        core_i18n.rename(target)

    # Report
    print("\n=== i18n migration report ===")
    print(f"Project root: {PROJECT_ROOT}")
    print(f"Files changed: {len(changed_files)}")
    for p in changed_files:
        print(f" - {p.relative_to(PROJECT_ROOT)}")

    if not args.apply:
        print("\nDry-run only. Re-run with --apply to write changes.")
    else:
        if args.backup:
            print(f"\nBackups saved to: {backup_dir}")
        print("\nDone.")

if __name__ == "__main__":
    sys.exit(main())
