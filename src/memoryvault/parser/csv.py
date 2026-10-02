"""CSV parser: rows become searchable text, header info lands in metadata."""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any

from memoryvault.parser.base import ParsedDocument, ParsingError, Parser, register
from memoryvault.textutil import normalize_whitespace

_SNIFF_BYTES = 8192


@register
class CSVParser(Parser):
    extensions = ("csv", "tsv")
    content_type = "csv"

    def parse(self, path: Path, raw: bytes) -> ParsedDocument:
        text = self.decode(raw)
        delimiter = self._sniff_delimiter(text, path)
        try:
            reader = csv.reader(io.StringIO(text), delimiter=delimiter)
            rows = [row for row in reader if any(cell.strip() for cell in row)]
        except csv.Error as exc:
            raise ParsingError(f"cannot parse CSV {path.name}: {exc}") from exc

        header: list[str] = []
        data_rows: list[list[str]] = []
        if rows:
            header = [cell.strip() for cell in rows[0]]
            data_rows = rows[1:]

        lines = [", ".join(header)] if header else []
        for row in data_rows:
            lines.append(", ".join(cell.strip() for cell in row))

        meta: dict[str, Any] = {
            "columns": header,
            "rows": len(data_rows),
            "delimiter": delimiter,
        }
        return ParsedDocument(
            title=self.fallback_title(path),
            content=normalize_whitespace("\n".join(lines)),
            metadata=meta,
        )

    @staticmethod
    def _sniff_delimiter(text: str, path: Path) -> str:
        if path.suffix.lower() == ".tsv":
            return "\t"
        try:
            sample = text[:_SNIFF_BYTES]
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
            return dialect.delimiter
        except csv.Error:
            return ","
