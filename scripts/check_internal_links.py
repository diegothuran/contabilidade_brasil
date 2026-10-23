#!/usr/bin/env python3
"""Check relative Markdown links in the specification package."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r"\[[^\]]+\]\(([^)#]+)(?:#[^)]+)?\)")


def main() -> None:
    missing: list[str] = []
    for path in ROOT.rglob("*.md"):
        if any(part in {".git", ".pytest_cache", "__pycache__", "node_modules", "dist", "playwright-report", "test-results", "blob-report"} for part in path.parts):
            continue
        for target in LINK.findall(path.read_text(encoding="utf-8")):
            if "://" in target or target.startswith("mailto:"):
                continue
            resolved = (path.parent / target).resolve()
            if not resolved.exists():
                missing.append(f"{path.relative_to(ROOT)} -> {target}")
    if missing:
        raise SystemExit("Missing internal links:\n" + "\n".join(missing))
    print("OK: internal Markdown links resolve")


if __name__ == "__main__":
    main()
