"""Write chunked, embedded documents into Postgres (idempotent per source path)."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from gator_ta.ingest.chunking import ChunkRecord
from gator_ta.models import Chunk, Document


async def upsert_document(
    session: AsyncSession,
    course_id: str,
    title: str,
    source: str,
    chunks: list[ChunkRecord],
    embeddings: list[list[float]],
) -> Document:
    if len(chunks) != len(embeddings):
        raise ValueError("chunks and embeddings must have the same length")

    existing = await session.scalar(select(Document).where(Document.source == source))
    if existing is not None:
        await session.execute(delete(Chunk).where(Chunk.document_id == existing.id))
        existing.title = title
        existing.course_id = course_id
        document = existing
    else:
        document = Document(course_id=course_id, title=title, source=source)
        session.add(document)
        await session.flush()

    session.add_all(
        Chunk(
            document_id=document.id,
            ordinal=c.ordinal,
            page=c.page,
            heading=c.heading,
            content=c.content,
            embedding=vec,
        )
        for c, vec in zip(chunks, embeddings, strict=True)
    )
    await session.commit()
    return document
