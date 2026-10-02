"""DOCX parser built on python-docx."""

from __future__ import annotations

from pathlib import Path

from memoryvault.parser.base import ParsedDocument, ParsingError, Parser, register
from memoryvault.textutil import normalize_whitespace


@register
class DOCXParser(Parser):
    extensions = ("docx",)
    content_type = "docx"

    def parse(self, path: Path, raw: bytes) -> ParsedDocument:
        try:
            import io

            import docx
        except ImportError as exc:  # pragma: no cover - python-docx is a hard dep
            raise ParsingError("python-docx is not installed") from exc

        try:
            document = docx.Document(io.BytesIO(raw))
        except Exception as exc:
            raise ParsingError(f"cannot parse DOCX {path.name}: {exc}") from exc

        paragraphs = [p.text for p in document.paragraphs]
        tables_text: list[str] = []
        for table in document.tables:
            for row in table.rows:
                cells = [c.text.strip() for c in row.cells]
                if any(cells):
                    tables_text.append(" | ".join(cells))

        text = normalize_whitespace("\n".join(paragraphs + tables_text))

        meta: dict = {}
        try:
            core = document.core_properties
            for prop in ("author", "subject", "category", "comments", "keywords"):
                value = getattr(core, prop, None)
                if value:
                    meta[prop] = str(value)
        except Exception:
            pass

        title = ""
        try:
            core_title = document.core_properties.title
        except Exception:
            core_title = None
        if core_title and core_title.strip():
            title = core_title.strip()

        headings = [
            p.text.strip()
            for p in document.paragraphs
            if p.style is not None and p.style.name.startswith("Heading") and p.text.strip()
        ]
        if headings:
            meta["headings"] = headings

        if not title:
            for para in paragraphs:
                para = para.strip()
                if para and len(para) <= 120:
                    title = para
                    break
        if not title:
            title = self.fallback_title(path)
        return ParsedDocument(title=title, content=text, metadata=meta)
