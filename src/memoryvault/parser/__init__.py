"""Document parsers: turn raw files into :class:`ParsedDocument` objects."""

from memoryvault.parser.base import (
    ParsedDocument,
    Parser,
    ParsingError,
    get_parser,
    parse_file,
    register,
    supported_extensions,
)
from memoryvault.parser.text import TextParser
from memoryvault.parser.markdown import MarkdownParser
from memoryvault.parser.html import HTMLParser
from memoryvault.parser.pdf import PDFParser
from memoryvault.parser.docx import DOCXParser
from memoryvault.parser.json import JSONParser
from memoryvault.parser.csv import CSVParser

__all__ = [
    "ParsedDocument",
    "Parser",
    "ParsingError",
    "parse_file",
    "register",
    "get_parser",
    "supported_extensions",
    "TextParser",
    "MarkdownParser",
    "HTMLParser",
    "PDFParser",
    "DOCXParser",
    "JSONParser",
    "CSVParser",
]
