"""Turn files into ``Section`` records (text + page/heading metadata) before chunking."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_SLIDE_BREAK = re.compile(r"^\s*---\s*$", re.MULTILINE)
_HEADING = re.compile(r"^#{1,6}\s+(.*)$", re.MULTILINE)


@dataclass(frozen=True)
class Section:
    text: str
    page: int | None = None
    heading: str = ""


def load_markdown_slides(path: Path) -> list[Section]:
    """Marp/reveal-style slide decks: one slide per ``---`` separated block."""
    text = Path(path).read_text()
    sections: list[Section] = []
    for i, block in enumerate(_SLIDE_BREAK.split(text), start=1):
        if not block.strip():
            continue
        heading_match = _HEADING.search(block)
        heading = heading_match.group(1).strip() if heading_match else ""
        sections.append(Section(text=block.strip(), page=i, heading=heading))
    return sections


def load_pdf(path: Path) -> list[Section]:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    sections: list[Section] = []
    for i, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if not text:
            continue
        first_line = text.splitlines()[0].strip()
        heading = first_line if len(first_line) <= 80 else ""
        sections.append(Section(text=text, page=i, heading=heading))
    return sections


def load_text(path: Path) -> list[Section]:
    return [Section(text=Path(path).read_text().strip(), page=None, heading="")]


LOADERS = {
    ".md": load_markdown_slides,
    ".markdown": load_markdown_slides,
    ".pdf": load_pdf,
    ".txt": load_text,
}


def load_file(path: Path) -> list[Section]:
    loader = LOADERS.get(Path(path).suffix.lower())
    if loader is None:
        raise ValueError(f"unsupported file type: {path}")
    return loader(Path(path))
