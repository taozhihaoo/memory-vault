"""Shared fixtures: sample vaults, documents and temp directories."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from memoryvault import Vault

# --------------------------------------------------------------------- data

MD_DOC = """---
title: Alpha Report
tags: [research, ml]
---
# Alpha Report

Deep learning drives [[beta-notes]] forward in modern research.
#experiment
"""

MD_BETA = """# Beta Notes

Machine learning and neural networks are transformative
for knowledge management systems.
"""

HTML_DOC = """<html>
  <head><title>Quantum Computing</title>
  <meta name="author" content="Alice">
  </head>
  <body><h1>Quantum Computing</h1>
  <p>Qubits superposition entanglement notes for the seminar.</p>
  </body></html>
"""

JSON_DOC = {
    "title": "Sensor Dataset",
    "tags": ["iot", "sensors"],
    "content": "temperature readings from the greenhouse deployment",
    "author": "Bob",
}

CSV_DOC = "name,quantity,price\nbolt,12,0.10\nnut,7,0.05\n"

TXT_DOC = "Meeting minutes\n\nWe discussed the quarterly roadmap and budget.\n"

def _minimal_pdf(text: str) -> bytes:
    """Build a valid single-page PDF (correct xref) containing *text*."""
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n"
        + stream + b"\nendstream",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_pos = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_pos}\n%%EOF\n"
    ).encode()
    return bytes(out)


MINIMAL_PDF = _minimal_pdf("PDF extraction greenhouse tomato")


def _write(path: Path, text) -> Path:
    if isinstance(text, bytes):
        path.write_bytes(text)
    else:
        path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture()
def docs_dir(tmp_path: Path) -> Path:
    """A directory with one file of every supported format."""
    root = tmp_path / "docs"
    root.mkdir()
    _write(root / "alpha.md", MD_DOC)
    _write(root / "beta-notes.md", MD_BETA)
    _write(root / "beta-copy.md", MD_BETA)  # exact duplicate of beta
    _write(root / "quantum.html", HTML_DOC)
    _write(root / "sensors.json", json.dumps(JSON_DOC))
    _write(root / "parts.csv", CSV_DOC)
    _write(root / "minutes.txt", TXT_DOC)
    _write(root / "paper.pdf", MINIMAL_PDF)
    return root


@pytest.fixture()
def vault() -> Vault:
    """An in-memory vault indexed with the sample documents."""
    v = Vault.in_memory()
    yield v
    v.close()


@pytest.fixture()
def indexed_vault(vault: Vault, docs_dir: Path) -> Vault:
    vault.index(docs_dir)
    return vault
