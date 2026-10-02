"""Plain-text parser: title is the first meaningful line."""

from __future__ import annotations

from pathlib import Path

from memoryvault.parser.base import ParsedDocument, Parser, register
from memoryvault.textutil import normalize_whitespace

_MAX_TITLE_LEN = 120


@register
class TextParser(Parser):
    extensions = ("txt", "text", "log")
    content_type = "text"

    def parse(self, path: Path, raw: bytes) -> ParsedDocument:
        text = normalize_whitespace(self.decode(raw))
        title = self.fallback_title(path)
        for line in text.splitlines():
            line = line.strip()
            if line and len(line) <= _MAX_TITLE_LEN:
                title = line
                break
        return ParsedDocument(title=title, content=text, metadata={})
