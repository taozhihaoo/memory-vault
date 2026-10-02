"""PDF parser built on pypdf."""

from __future__ import annotations

from pathlib import Path

from memoryvault.parser.base import ParsedDocument, ParsingError, Parser, register
from memoryvault.textutil import normalize_whitespace

_MAX_TITLE_LEN = 200


@register
class PDFParser(Parser):
    extensions = ("pdf",)
    content_type = "pdf"

    def parse(self, path: Path, raw: bytes) -> ParsedDocument:
        try:
            from pypdf import PdfReader
            from pypdf.errors import PdfReadError
        except ImportError as exc:  # pragma: no cover - pypdf is a hard dep
            raise ParsingError("pypdf is not installed") from exc

        import io

        try:
            reader = PdfReader(io.BytesIO(raw))
            pages = [(page.extract_text() or "") for page in reader.pages]
            info = reader.metadata or {}
        except Exception as exc:
            raise ParsingError(f"cannot parse PDF {path.name}: {exc}") from exc

        text = normalize_whitespace("\n\n".join(p for p in pages if p))

        meta: dict = {}
        for key in ("/Title", "/Author", "/Subject", "/Creator", "/Producer"):
            try:
                value = info.get(key)
            except Exception:
                value = None
            if value:
                meta[key.lstrip("/").lower()] = str(value)

        title = meta.get("title", "").strip()
        if not title:
            for line in text.splitlines():
                line = line.strip()
                if line and len(line) <= _MAX_TITLE_LEN:
                    title = line
                    break
        if not title:
            title = self.fallback_title(path)
        meta["pages"] = len(pages)
        return ParsedDocument(title=title, content=text, metadata=meta)
