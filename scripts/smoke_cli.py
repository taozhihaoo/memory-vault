"""Cross-platform CLI smoke test used by GitHub Actions.

The old CI step used ``mkdir -p /tmp/demo`` and ``printf`` — POSIX-only and
broken on ``windows-latest`` (which runs ``pwsh`` by default). This script
uses ``tempfile`` and subprocesses instead, so the exact same check runs on
Linux, macOS and Windows.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


def run(*args: str) -> str:
    result = subprocess.run(
        [sys.executable, "-m", "memoryvault", *args],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise SystemExit(
            f"command failed: {' '.join(args)}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result.stdout


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="memoryvault-smoke-") as tmp:
        root = Path(tmp)
        docs = root / "docs"
        docs.mkdir()
        (docs / "demo.md").write_text(
            "# Demo\n\nhello vault content quantum\n", encoding="utf-8"
        )
        db = root / "vault.db"

        run("--db", str(db), "index", str(docs))
        payload = json.loads(run("--db", str(db), "search", "hello", "--json"))
        assert payload["total"] == 1, f"unexpected search total: {payload}"
        assert payload["results"][0]["title"] == "Demo"

        stats = json.loads(run("--db", str(db), "stats"))
        assert stats["documents"] == 1, f"unexpected stats: {stats}"

        # Root-less scan must reuse the directory recorded by `index`.
        scan = json.loads(run("--db", str(db), "scan", "--json"))
        assert scan["unchanged"] == 1, f"unexpected scan result: {scan}"

        run("--db", str(db), "graph", "--out", str(root / "graph.json"))
        graph = json.loads((root / "graph.json").read_text(encoding="utf-8"))
        assert graph["meta"]["document_count"] == 1

        run("--db", str(db), "duplicates")
        run("--db", str(db), "timeline")

    print("CLI smoke test passed (index, search, stats, scan, graph, timeline)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
