"""CLI: ``gator-ingest data/sample/slides --course CIS6930``."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from openai import AsyncOpenAI

from gator_ta.config import get_settings
from gator_ta.db import Database
from gator_ta.ingest.chunking import chunk_sections, tiktoken_counter
from gator_ta.ingest.embed import OpenAIEmbedder
from gator_ta.ingest.loaders import LOADERS, load_file
from gator_ta.ingest.store import upsert_document


def discover(paths: list[Path]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        if path.is_dir():
            files.extend(p for p in sorted(path.rglob("*")) if p.suffix.lower() in LOADERS)
        elif path.suffix.lower() in LOADERS:
            files.append(path)
    return files


async def ingest(paths: list[Path], course_id: str) -> int:
    settings = get_settings()
    db = Database(settings)
    client = AsyncOpenAI(api_key=settings.openai_api_key or None)
    embedder = OpenAIEmbedder(client, settings.embedding_model)
    count = tiktoken_counter()

    total = 0
    try:
        async with db.sessions() as session:
            for file in discover(paths):
                sections = load_file(file)
                chunks = chunk_sections(
                    sections, settings.chunk_tokens, settings.chunk_overlap_tokens, count
                )
                if not chunks:
                    continue
                vectors = await embedder.embed([c.content for c in chunks])
                await upsert_document(
                    session,
                    course_id=course_id,
                    title=file.stem.replace("-", " ").replace("_", " ").title(),
                    source=str(file.resolve()),
                    chunks=chunks,
                    embeddings=vectors,
                )
                total += len(chunks)
                print(f"{file.name}: {len(sections)} sections -> {len(chunks)} chunks")
    finally:
        await db.close()
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest lecture material into GatorTA.")
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--course", default=get_settings().course_id)
    args = parser.parse_args()
    total = asyncio.run(ingest(args.paths, args.course))
    print(f"ingested {total} chunks for {args.course}")


if __name__ == "__main__":
    main()
