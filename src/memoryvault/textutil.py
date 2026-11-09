"""Shared text utilities used by parsers and the indexer."""

from __future__ import annotations

import re
import unicodedata

_WORD_RE = re.compile(r"\b[\w']+\b", re.UNICODE)
_CJK_CHAR_RE = re.compile(r"[\u3400-\u9fff]")

_FALLBACK_ENCODINGS = ("utf-8", "utf-8-sig", "cp1252", "latin-1")


def decode_bytes(raw: bytes) -> str:
    """Decode bytes to text, trying UTF-8 first then common fallbacks.

    A UTF-16 BOM is also honoured so Windows-exported files decode cleanly.
    """
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        return raw.decode("utf-16")
    for enc in _FALLBACK_ENCODINGS:
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", errors="replace")


def count_words(text: str) -> int:
    """Deterministic word count.

    Space-delimited words are counted as usual; CJK characters are counted
    individually because a whole Chinese sentence would otherwise be a
    single "word" under ``\\b\\w+\\b``.
    """
    latin_part = _CJK_CHAR_RE.sub(" ", text)
    return len(_WORD_RE.findall(latin_part)) + len(_CJK_CHAR_RE.findall(text))


def normalize_whitespace(text: str) -> str:
    return re.sub(r"[ \t]+", " ", re.sub(r"\r\n?", "\n", text)).strip()


def strip_controls(text: str) -> str:
    return "".join(ch for ch in text if ch == "\n" or not unicodedata.category(ch).startswith("C"))
