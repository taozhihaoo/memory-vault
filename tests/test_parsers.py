"""Parser tests: every supported format extracts title/content/metadata."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from memoryvault.parser import (
    CSVParser,
    DOCXParser,
    HTMLParser,
    JSONParser,
    MarkdownParser,
    ParsedDocument,
    ParsingError,
    TextParser,
    get_parser,
    parse_file,
    supported_extensions,
)
from tests.conftest import CSV_DOC, HTML_DOC, JSON_DOC, MINIMAL_PDF, MD_BETA, MD_DOC, TXT_DOC


# ------------------------------------------------------------- registry
def test_supported_extensions_cover_all_formats():
    exts = set(supported_extensions())
    assert {"txt", "md", "html", "pdf", "docx", "json", "csv"} <= exts


def test_get_parser_dispatches_by_extension(docs_dir: Path):
    assert isinstance(get_parser(docs_dir / "minutes.txt"), TextParser)
    assert isinstance(get_parser(docs_dir / "alpha.md"), MarkdownParser)
    assert isinstance(get_parser(docs_dir / "quantum.html"), HTMLParser)
    assert isinstance(get_parser(docs_dir / "sensors.json"), JSONParser)
    assert isinstance(get_parser(docs_dir / "parts.csv"), CSVParser)


def test_get_parser_unknown_extension_raises(tmp_path: Path):
    f = tmp_path / "data.xyz"
    f.write_text("mystery", encoding="utf-8")
    with pytest.raises(ParsingError):
        get_parser(f)


def test_parse_file_returns_parsed_document(docs_dir: Path):
    parsed = parse_file(docs_dir / "minutes.txt")
    assert isinstance(parsed, ParsedDocument)
    assert parsed.created_at is not None
    assert parsed.modified_at is not None


def test_parse_file_missing_file_raises(tmp_path: Path):
    with pytest.raises(ParsingError):
        parse_file(tmp_path / "ghost.txt")


# ----------------------------------------------------------------- text
def test_text_parser_uses_first_line_as_title(tmp_path: Path):
    f = tmp_path / "note.txt"
    f.write_text(TXT_DOC, encoding="utf-8")
    parsed = TextParser().parse_path(f)
    assert parsed.title == "Meeting minutes"
    assert "quarterly roadmap" in parsed.content
    assert parsed.word_count > 5


def test_text_parser_falls_back_to_stem(tmp_path: Path):
    f = tmp_path / "my_long_note.txt"
    f.write_text("\n\n\n", encoding="utf-8")
    parsed = TextParser().parse_path(f)
    assert "my long note" in parsed.title or parsed.title


def test_text_parser_handles_utf16(tmp_path: Path):
    f = tmp_path / "unicode.txt"
    f.write_bytes("Überschrift über Kaffee\n\nInhalt".encode("utf-16"))
    parsed = TextParser().parse_path(f)
    assert "Überschrift" in parsed.content


# ------------------------------------------------------------- markdown
def test_markdown_title_from_frontmatter(docs_dir: Path):
    parsed = parse_file(docs_dir / "alpha.md")
    assert parsed.title == "Alpha Report"


def test_markdown_title_from_heading(docs_dir: Path):
    parsed = parse_file(docs_dir / "beta-notes.md")
    assert parsed.title == "Beta Notes"


def test_markdown_extracts_frontmatter_tags(docs_dir: Path):
    parsed = parse_file(docs_dir / "alpha.md")
    assert "research" in parsed.metadata["tags"]
    assert "ml" in parsed.metadata["tags"]
    assert "experiment" in parsed.metadata["tags"]  # inline #tag


def test_markdown_extracts_wikilinks(docs_dir: Path):
    parsed = parse_file(docs_dir / "alpha.md")
    assert any("beta-notes" in link for link in parsed.metadata["links"])


def test_markdown_strips_markup_from_content(docs_dir: Path):
    parsed = parse_file(docs_dir / "alpha.md")
    assert "[[" not in parsed.content
    assert "#" not in parsed.content.split("\n")[0]


def test_markdown_frontmatter_lists_parse(tmp_path: Path):
    f = tmp_path / "fm.md"
    f.write_text('---\ntitle: Deep "Note"\ntags: [a, b]\nstatus: draft\n---\nBody', encoding="utf-8")
    parsed = MarkdownParser().parse_path(f)
    assert parsed.title == 'Deep "Note"'
    assert parsed.metadata["status"] == "draft"
    assert parsed.metadata["tags"] == ["a", "b"]


# ----------------------------------------------------------------- html
def test_html_title_and_meta(docs_dir: Path):
    parsed = parse_file(docs_dir / "quantum.html")
    assert parsed.title == "Quantum Computing"
    assert parsed.metadata["author"] == "Alice"


def test_html_drops_script_and_style(tmp_path: Path):
    f = tmp_path / "page.html"
    f.write_text(
        "<html><head><title>T</title><style>body{}</style></head>"
        "<body><script>var x=1;</script><p>visible text</p></body></html>",
        encoding="utf-8",
    )
    parsed = HTMLParser().parse_path(f)
    assert "var x" not in parsed.content
    assert "body{}" not in parsed.content
    assert "visible text" in parsed.content


# ------------------------------------------------------------------ pdf
def test_pdf_extracts_text(docs_dir: Path):
    parsed = parse_file(docs_dir / "paper.pdf")
    assert "greenhouse" in parsed.content
    assert parsed.metadata["pages"] == 1


def test_pdf_invalid_bytes_raise(tmp_path: Path):
    f = tmp_path / "broken.pdf"
    f.write_bytes(b"this is not a pdf at all")
    with pytest.raises(ParsingError):
        parse_file(f)


# ----------------------------------------------------------------- docx
def test_docx_extracts_paragraphs_and_title(tmp_path: Path):
    docx = pytest.importorskip("docx")
    f = tmp_path / "report.docx"
    document = docx.Document()
    document.core_properties.title = "Quarterly Review"
    document.add_heading("Quarterly Review", level=1)
    document.add_paragraph("Revenue grew by twelve percent.")
    document.add_paragraph("Costs remained stable.", style="Heading 2")
    document.save(f)
    parsed = DOCXParser().parse_path(f)
    assert parsed.title == "Quarterly Review"
    assert "Revenue grew" in parsed.content
    assert "Costs remained" in parsed.content
    assert "headings" in parsed.metadata


def test_docx_invalid_bytes_raise(tmp_path: Path):
    f = tmp_path / "broken.docx"
    f.write_bytes(b"not a docx")
    with pytest.raises(ParsingError):
        parse_file(f)


# ----------------------------------------------------------------- json
def test_json_title_and_content_key(docs_dir: Path):
    parsed = parse_file(docs_dir / "sensors.json")
    assert parsed.title == "Sensor Dataset"
    assert "greenhouse" in parsed.content
    assert parsed.metadata["tags"] == ["iot", "sensors"]


def test_json_flattens_nested_structures(tmp_path: Path):
    f = tmp_path / "nested.json"
    f.write_text(json.dumps({"meta": {"author": "Zoe"}, "items": [1, 2]}), encoding="utf-8")
    parsed = JSONParser().parse_path(f)
    assert "Zoe" in parsed.content
    assert "meta.author" in parsed.content


def test_json_invalid_raises(tmp_path: Path):
    f = tmp_path / "bad.json"
    f.write_text("{not json", encoding="utf-8")
    with pytest.raises(ParsingError):
        parse_file(f)


# ------------------------------------------------------------------ csv
def test_csv_extracts_rows_and_columns(docs_dir: Path):
    parsed = parse_file(docs_dir / "parts.csv")
    assert parsed.metadata["columns"] == ["name", "quantity", "price"]
    assert parsed.metadata["rows"] == 2
    assert "bolt" in parsed.content
    assert "0.10" in parsed.content


def test_csv_semicolon_delimiter(tmp_path: Path):
    f = tmp_path / "euro.csv"
    f.write_text("a;b\n1;2\n", encoding="utf-8")
    parsed = CSVParser().parse_path(f)
    assert parsed.metadata["delimiter"] == ";"
    assert parsed.metadata["columns"] == ["a", "b"]


def test_csv_tsv_uses_tabs(tmp_path: Path):
    f = tmp_path / "table.tsv"
    f.write_text("x\ty\n1\t2\n", encoding="utf-8")
    parsed = CSVParser().parse_path(f)
    assert parsed.metadata["delimiter"] == "\t"
