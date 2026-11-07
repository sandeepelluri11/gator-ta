"""Token-budgeted chunking with overlap.

Chunks never cross a section (slide / page) boundary, so every chunk carries a page number
and heading the answer can cite. Within a section, paragraphs are packed greedily up to the
token budget; an oversized paragraph is split on sentence boundaries.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from gator_ta.ingest.loaders import Section

TokenCounter = Callable[[str], int]

_SENTENCE = re.compile(r"(?<=[.!?])\s+")


def approx_token_count(text: str) -> int:
    """Cheap offline estimate (~4 chars per token) used when tiktoken is unavailable."""
    return max(1, len(text) // 4)


def tiktoken_counter(model: str = "cl100k_base") -> TokenCounter:
    try:
        import tiktoken

        enc = tiktoken.get_encoding(model)
        return lambda text: len(enc.encode(text))
    except Exception:  # noqa: BLE001 - offline or missing encoding; fall back
        return approx_token_count


@dataclass(frozen=True)
class ChunkRecord:
    ordinal: int
    content: str
    page: int | None
    heading: str


def _split_oversized(paragraph: str, budget: int, count: TokenCounter) -> list[str]:
    pieces: list[str] = []
    current: list[str] = []
    for sentence in _SENTENCE.split(paragraph):
        candidate = " ".join([*current, sentence])
        if current and count(candidate) > budget:
            pieces.append(" ".join(current))
            current = [sentence]
        else:
            current.append(sentence)
    if current:
        pieces.append(" ".join(current))
    return pieces


def _tail(text: str, overlap_tokens: int, count: TokenCounter) -> str:
    """Return the last ~overlap_tokens worth of words from ``text``."""
    if overlap_tokens <= 0:
        return ""
    words = text.split()
    tail: list[str] = []
    while words and count(" ".join([words[-1], *tail])) <= overlap_tokens:
        tail.insert(0, words.pop())
    return " ".join(tail)


def chunk_sections(
    sections: list[Section],
    budget_tokens: int = 350,
    overlap_tokens: int = 50,
    count: TokenCounter | None = None,
) -> list[ChunkRecord]:
    count = count or approx_token_count
    records: list[ChunkRecord] = []

    for section in sections:
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", section.text) if p.strip()]
        units: list[str] = []
        for paragraph in paragraphs:
            if count(paragraph) > budget_tokens:
                units.extend(_split_oversized(paragraph, budget_tokens, count))
            else:
                units.append(paragraph)

        current: list[str] = []
        for unit in units:
            candidate = "\n\n".join([*current, unit])
            if current and count(candidate) > budget_tokens:
                content = "\n\n".join(current)
                records.append(ChunkRecord(len(records), content, section.page, section.heading))
                # carry a tail for continuity, but never let it push the next chunk over budget
                room = budget_tokens - count(unit)
                carry = _tail(content, min(overlap_tokens, room), count) if room > 0 else ""
                current = [carry, unit] if carry else [unit]
            else:
                current.append(unit)
        if current:
            records.append(
                ChunkRecord(len(records), "\n\n".join(current), section.page, section.heading)
            )

    return records
