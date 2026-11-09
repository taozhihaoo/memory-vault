"""Verify that local file links in the READMEs actually resolve.

CI runs this so a renamed screenshot never silently becomes a broken image
in the rendered documentation.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = [ROOT / "README.md", ROOT / "README.zh-CN.md"]
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")


def main() -> int:
    missing: list[str] = []
    for document in DOCS:
        if not document.is_file():
            missing.append(str(document))
            continue
        for line_no, line in enumerate(document.read_text(encoding="utf-8").splitlines(), 1):
            for raw in LINK_RE.findall(line):
                target = raw.split("#", 1)[0].strip()
                if not target or "://" in target or target.startswith(("mailto:", "data:")):
                    continue
                resolved = (document.parent / target).resolve()
                if not resolved.exists():
                    missing.append(f"{document.name}:{line_no} -> {target}")
    if missing:
        print("Broken documentation links:", file=sys.stderr)
        for item in missing:
            print(f"  {item}", file=sys.stderr)
        return 1
    print(f"Documentation links verified ({len(DOCS)} READMEs)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
