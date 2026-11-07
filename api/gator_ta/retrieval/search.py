from __future__ import annotations

from collections.abc import Hashable, Sequence
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class Passage:
    chunk_id: int
    document_title: str
    source: str
    page: int | None
    heading: str
    content: str
    score: float

    @property
    def label(self) -> str:
        where = f"p. {self.page}" if self.page is not None else "doc"
        return f"{self.document_title} ({where})"


class Retriever(Protocol):
    async def search(self, query: str, k: int) -> list[Passage]: ...


def reciprocal_rank_fusion(
    rankings: Sequence[Sequence[Hashable]], k: int = 60
) -> list[tuple[Hashable, float]]:
    """Fuse ranked id lists. Items ranked highly in several lists float to the top."""
    scores: dict[Hashable, float] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda pair: (-pair[1], str(pair[0])))


_VECTOR_SQL = text(
    """
    SELECT c.id
    FROM chunks c JOIN documents d ON d.id = c.document_id
    WHERE d.course_id = :course_id
    ORDER BY c.embedding <=> CAST(:query_vec AS vector)
    LIMIT :limit
    """
)

_FTS_SQL = text(
    """
    SELECT c.id
    FROM chunks c JOIN documents d ON d.id = c.document_id
    WHERE d.course_id = :course_id
      AND c.content_tsv @@ websearch_to_tsquery('english', :query)
    ORDER BY ts_rank_cd(c.content_tsv, websearch_to_tsquery('english', :query)) DESC
    LIMIT :limit
    """
)

_FETCH_SQL = text(
    """
    SELECT c.id, d.title, d.source, c.page, c.heading, c.content
    FROM chunks c JOIN documents d ON d.id = c.document_id
    WHERE c.id = ANY(:ids)
    """
)


class HybridRetriever:
    def __init__(self, session: AsyncSession, embedder, course_id: str, candidate_k: int = 20):
        self._session = session
        self._embedder = embedder
        self._course_id = course_id
        self._candidate_k = candidate_k

    async def search(self, query: str, k: int) -> list[Passage]:
        [query_vec] = await self._embedder.embed([query])
        vec_rows = await self._session.execute(
            _VECTOR_SQL,
            {
                "course_id": self._course_id,
                "query_vec": "[" + ",".join(f"{x:.7f}" for x in query_vec) + "]",
                "limit": self._candidate_k,
            },
        )
        fts_rows = await self._session.execute(
            _FTS_SQL, {"course_id": self._course_id, "query": query, "limit": self._candidate_k}
        )
        fused = reciprocal_rank_fusion([[r[0] for r in vec_rows], [r[0] for r in fts_rows]])[:k]
        if not fused:
            return []

        ids = [int(cid) for cid, _ in fused]
        rows = {
            row.id: row for row in (await self._session.execute(_FETCH_SQL, {"ids": ids})).all()
        }
        return [
            Passage(
                chunk_id=row.id,
                document_title=row.title,
                source=row.source,
                page=row.page,
                heading=row.heading,
                content=row.content,
                score=score,
            )
            for cid, score in fused
            if (row := rows.get(int(cid))) is not None
        ]
