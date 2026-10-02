"""CLI tests — every command runs against a temp vault."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from memoryvault.cli import main


@pytest.fixture()
def db(tmp_path: Path) -> Path:
    return tmp_path / "cli-vault.db"


def test_index_command(db: Path, docs_dir: Path, capsys):
    rc = main(["--db", str(db), "index", str(docs_dir)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "8 created" in out


def test_index_command_json(db: Path, docs_dir: Path, capsys):
    rc = main(["--db", str(db), "index", str(docs_dir), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0 and payload["created"] == 8


def test_index_twice_reports_unchanged(db: Path, docs_dir: Path, capsys):
    main(["--db", str(db), "index", str(docs_dir)])
    capsys.readouterr()
    main(["--db", str(db), "index", str(docs_dir)])
    assert "8 unchanged" in capsys.readouterr().out


def test_search_command(db: Path, docs_dir: Path, capsys):
    main(["--db", str(db), "index", str(docs_dir)])
    rc = main(["--db", str(db), "search", "quantum"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Quantum Computing" in out


def test_search_command_json(db: Path, docs_dir: Path, capsys):
    main(["--db", str(db), "index", str(docs_dir)])
    capsys.readouterr()
    main(["--db", str(db), "search", "quantum", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["total"] == 1
    assert payload["results"][0]["title"] == "Quantum Computing"


def test_search_no_results(db: Path, docs_dir: Path, capsys):
    main(["--db", str(db), "index", str(docs_dir)])
    capsys.readouterr()
    assert main(["--db", str(db), "search", "zzzznotfound"]) == 0
    assert "no results" in capsys.readouterr().out


def test_stats_command(db: Path, docs_dir: Path, capsys):
    main(["--db", str(db), "index", str(docs_dir)])
    capsys.readouterr()
    main(["--db", str(db), "stats"])
    stats = json.loads(capsys.readouterr().out)
    assert stats["documents"] == 8


def test_show_command(db: Path, docs_dir: Path, capsys):
    main(["--db", str(db), "index", str(docs_dir)])
    capsys.readouterr()
    rc = main(["--db", str(db), "show", "1"])
    out = capsys.readouterr().out
    assert rc == 0
    assert out.startswith("# ")


def test_show_missing_document(db: Path, capsys):
    rc = main(["--db", str(db), "show", "42"])
    assert rc == 1
    assert "not found" in capsys.readouterr().err


def test_duplicates_command(db: Path, docs_dir: Path, capsys):
    main(["--db", str(db), "index", str(docs_dir)])
    capsys.readouterr()
    main(["--db", str(db), "duplicates"])
    out = capsys.readouterr().out
    assert "EXACT" in out
    assert "SIMILAR" in out


def test_graph_command_exports_file(db: Path, docs_dir: Path, tmp_path: Path, capsys):
    main(["--db", str(db), "index", str(docs_dir)])
    capsys.readouterr()
    out_file = tmp_path / "graph.json"
    main(["--db", str(db), "graph", "--out", str(out_file)])
    graph = json.loads(out_file.read_text(encoding="utf-8"))
    assert graph["meta"]["document_count"] == 8
    assert "graph written" in capsys.readouterr().out


def test_timeline_command(db: Path, docs_dir: Path, capsys):
    main(["--db", str(db), "index", str(docs_dir)])
    capsys.readouterr()
    rc = main(["--db", str(db), "timeline"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "recent events" in out


def test_tags_command(db: Path, docs_dir: Path, capsys):
    main(["--db", str(db), "index", str(docs_dir)])
    capsys.readouterr()
    main(["--db", str(db), "tags"])
    out = capsys.readouterr().out
    assert "research" in out
    assert "█" in out


def test_scan_command(db: Path, docs_dir: Path, capsys):
    main(["--db", str(db), "index", str(docs_dir)])
    capsys.readouterr()
    rc = main(["--db", str(db), "scan", str(docs_dir), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0 and payload["unchanged"] == 8


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert "memoryvault" in capsys.readouterr().out
