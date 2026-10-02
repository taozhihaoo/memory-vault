"""Markdown parser: frontmatter, headings, wikilinks and tags."""

from __future__ import annotations

import re
from pathlib import Path

from memoryvault.parser.base import ParsedDocument, Parser, register
from memoryvault.textutil import normalize_whitespace

_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.DOTALL)
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$", re.MULTILINE)
_WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:[|#][^\]]*)?\]\]")
_MD_TAG_RE = re.compile(r"(?<![\w#])#([A-Za-z][\w/-]+)")
_MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")


def _unquote(value: str) -> str:
    """Strip one pair of surrounding quotes, preserving inner quotes."""
    for quote in ("\"", "'"):
        if len(value) >= 2 and value.startswith(quote) and value.endswith(quote):
            return value[1:-1]
    return value


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Split simple YAML-ish frontmatter from the body.

    Supports ``key: value`` pairs and ``key: [a, b]`` lists — deliberately
    no YAML dependency, the deterministic core must stay lightweight.
    """
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    meta: dict = {}
    for line in match.group(1).splitlines():
        if ":" not in line or line.strip().startswith("#"):
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            items = [v.strip() for v in value[1:-1].split(",")]
            meta[key] = [_unquote(v) for v in items if v]
        else:
            meta[key] = _unquote(value)
    return meta, text[match.end():]


@register
class MarkdownParser(Parser):
    extensions = ("md", "markdown")
    content_type = "markdown"

    def parse(self, path: Path, raw: bytes) -> ParsedDocument:
        text = normalize_whitespace(self.decode(raw))
        meta, body = parse_frontmatter(text)

        headings = _HEADING_RE.findall(body)
        title = ""
        fm_title = meta.get("title")
        if isinstance(fm_title, str) and fm_title.strip():
            title = fm_title.strip()
        elif headings:
            title = headings[0][1].strip()
        if not title:
            title = self.fallback_title(path)

        # Tags: frontmatter "tags" list/comma string plus inline #tags.
        tags: list[str] = []
        fm_tags = meta.get("tags", [])
        if isinstance(fm_tags, str):
            fm_tags = [t for t in re.split(r"[,;]", fm_tags) if t.strip()]
        if isinstance(fm_tags, list):
            tags.extend(str(t).strip().lower() for t in fm_tags if str(t).strip())
        tags.extend(t.lower() for t in _MD_TAG_RE.findall(body))

        # Internal links for the knowledge graph.
        links = [m.strip() for m in _WIKILINK_RE.findall(body)]
        links += [target for _, target in _MARKDOWN_LINK_RE.findall(body)
                  if not re.match(r"^[a-z]+://", target)]

        metadata = dict(meta)
        metadata["headings"] = [h[1].strip() for h in headings]
        if links:
            metadata["links"] = list(dict.fromkeys(links))
        if tags:
            metadata["tags"] = list(dict.fromkeys(tags))

        content = _strip_markup(body)
        return ParsedDocument(title=title, content=content, metadata=metadata)


def _strip_markup(body: str) -> str:
    body = _FRONTMATTER_RE.sub("", body, count=1)
    body = _WIKILINK_RE.sub(r"\1", body)
    body = _MD_TAG_RE.sub(r"\1", body)
    body = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", body)
    body = _MARKDOWN_LINK_RE.sub(r"\1", body)
    body = re.sub(r"^#{1,6}\s+", "", body, flags=re.MULTILINE)
    body = re.sub(r"(\*\*|__)(.*?)\1", r"\2", body)
    body = re.sub(r"(\*|_)(.*?)\1", r"\2", body)
    body = re.sub(r"`{1,3}([^`]*)`{1,3}", r"\1", body)
    body = re.sub(r"^>\s?", "", body, flags=re.MULTILINE)
    body = re.sub(r"^\s*([-*+]|\d+\.)\s+", "", body, flags=re.MULTILINE)
    return body.strip()
