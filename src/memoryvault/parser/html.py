"""HTML parser built on BeautifulSoup/lxml."""

from __future__ import annotations

from pathlib import Path

from bs4 import BeautifulSoup

from memoryvault.parser.base import ParsedDocument, Parser, register
from memoryvault.textutil import normalize_whitespace

_DROP_TAGS = ("script", "style", "noscript", "template", "head")


@register
class HTMLParser(Parser):
    extensions = ("html", "htm", "xhtml")
    content_type = "html"

    def parse(self, path: Path, raw: bytes) -> ParsedDocument:
        text = self.decode(raw)
        soup = BeautifulSoup(text, "lxml")

        title = ""
        if soup.title and soup.title.string:
            title = soup.title.string.strip()
        if not title and soup.h1:
            title = soup.h1.get_text(" ", strip=True)
        if not title:
            title = self.fallback_title(path)

        meta: dict = {}
        for tag in soup.find_all("meta"):
            name = tag.get("name") or tag.get("property")
            content = tag.get("content")
            if name and content:
                meta[str(name)] = str(content)

        for node in soup(list(_DROP_TAGS)):
            node.decompose()
        body_text = normalize_whitespace(soup.get_text(" "))
        if not title:
            title = self.fallback_title(path)

        headings = [
            h.get_text(" ", strip=True)
            for h in soup.find_all(["h1", "h2", "h3"])
        ]
        if headings:
            meta["headings"] = headings
        return ParsedDocument(title=title, content=body_text, metadata=meta)
