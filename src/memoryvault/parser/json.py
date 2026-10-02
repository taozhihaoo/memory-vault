"""JSON parser: flattens the document into searchable key/value text."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from memoryvault.parser.base import ParsedDocument, ParsingError, Parser, register
from memoryvault.textutil import normalize_whitespace

_TITLE_KEYS = ("title", "name", "headline", "subject")


def _flatten(obj: Any, prefix: str = "", depth: int = 0) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    if depth > 8:
        return out
    if isinstance(obj, dict):
        for key, value in obj.items():
            out.extend(_flatten(value, f"{prefix}{key}." if not isinstance(value, (dict, list)) else f"{prefix}{key}.", depth + 1))
    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            out.extend(_flatten(value, prefix, depth + 1))
    else:
        key = prefix.rstrip(".") or "value"
        out.append((key, str(obj)))
    return out


@register
class JSONParser(Parser):
    extensions = ("json",)
    content_type = "json"

    def parse(self, path: Path, raw: bytes) -> ParsedDocument:
        try:
            data = json.loads(self.decode(raw))
        except json.JSONDecodeError as exc:
            raise ParsingError(f"invalid JSON in {path.name}: {exc}") from exc

        meta: dict[str, Any] = {}
        title = ""
        probe = data if isinstance(data, dict) else {}
        for key in _TITLE_KEYS:
            value = probe.get(key)
            if isinstance(value, str) and value.strip():
                title = value.strip()
                break
        for key in ("tags", "keywords"):
            value = probe.get(key)
            if isinstance(value, list) and all(isinstance(v, str) for v in value):
                meta[key] = value
        for key in ("author", "created", "date", "category"):
            value = probe.get(key)
            if isinstance(value, str):
                meta[key] = value
        if isinstance(data, dict):
            meta["keys"] = list(data.keys())[:50]

        if isinstance(data, dict):
            for key in ("content", "body", "text"):
                value = data.get(key)
                if isinstance(value, str) and value.strip():
                    body = value
                    break
            else:
                body = "\n".join(f"{k}: {v}" for k, v in _flatten(data))
        else:
            body = "\n".join(f"{k}: {v}" for k, v in _flatten(data))

        if not title:
            title = self.fallback_title(path)
        return ParsedDocument(
            title=title, content=normalize_whitespace(body), metadata=meta
        )
