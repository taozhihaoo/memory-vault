"""Parser base class and format registry."""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Type

from memoryvault.textutil import count_words, decode_bytes


class ParsingError(Exception):
    """Raised when a file cannot be parsed."""


@dataclass(slots=True)
class ParsedDocument:
    """The format-independent result of parsing one file."""

    title: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None
    modified_at: datetime | None = None

    @property
    def word_count(self) -> int:
        return count_words(self.content)


class Parser(ABC):
    """Base class for all file-format parsers."""

    #: Lowercase extensions (without dot) this parser handles.
    extensions: tuple[str, ...] = ()
    #: Canonical content-type name stored in the database.
    content_type: str = "unknown"

    def handles(self, path: Path) -> bool:
        return path.suffix.lower().lstrip(".") in self.extensions

    def parse_path(self, path: Path) -> ParsedDocument:
        """Read *path* from disk and parse it."""
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise ParsingError(f"cannot read {path}: {exc}") from exc
        parsed = self.parse(path, raw)
        stat = path.stat()
        if parsed.created_at is None:
            parsed.created_at = datetime.fromtimestamp(stat.st_mtime).astimezone()
        if parsed.modified_at is None:
            parsed.modified_at = datetime.fromtimestamp(stat.st_mtime).astimezone()
        parsed.metadata.setdefault("file_name", path.name)
        parsed.metadata.setdefault("extension", path.suffix.lower().lstrip("."))
        return parsed

    @abstractmethod
    def parse(self, path: Path, raw: bytes) -> ParsedDocument:
        """Parse raw bytes into a :class:`ParsedDocument`."""

    # ------------------------------------------------------------ helpers
    @staticmethod
    def sha256(raw: bytes) -> str:
        return hashlib.sha256(raw).hexdigest()

    @staticmethod
    def decode(raw: bytes) -> str:
        return decode_bytes(raw)

    @staticmethod
    def fallback_title(path: Path) -> str:
        return path.stem.replace("_", " ").replace("-", " ").strip() or path.name


_REGISTRY: dict[str, Type[Parser]] = {}


def register(parser_cls: Type[Parser]) -> Type[Parser]:
    """Class decorator adding a parser to the format registry."""
    for ext in parser_cls.extensions:
        _REGISTRY[ext] = parser_cls
    return parser_cls


def get_parser(path: Path) -> Parser:
    """Return the parser registered for *path*'s extension."""
    ext = path.suffix.lower().lstrip(".")
    parser_cls = _REGISTRY.get(ext)
    if parser_cls is None:
        raise ParsingError(f"no parser for extension '{ext}' ({path.name})")
    return parser_cls()


def supported_extensions() -> tuple[str, ...]:
    return tuple(sorted(_REGISTRY))


def parse_file(path: Path) -> ParsedDocument:
    """Parse any supported file with the right parser."""
    return get_parser(path).parse_path(Path(path))


def compute_hash(path: Path) -> str:
    """SHA-256 of a file, streamed, without parsing it."""
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()
