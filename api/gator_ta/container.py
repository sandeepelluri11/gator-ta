"""Dependency wiring. Production builds real clients; tests build a container with fakes."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, Protocol

from gator_ta.chat.llm import ChatClient
from gator_ta.config import Settings
from gator_ta.db import Database
from gator_ta.retrieval.search import Retriever
from gator_ta.tools.registry import Syllabus, ToolRegistry


class FeedbackStore(Protocol):
    async def add(self, session_id: str, message_id: str, rating: int, comment: str) -> None: ...


class PostgresFeedbackStore:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def add(self, session_id: str, message_id: str, rating: int, comment: str) -> None:
        from gator_ta.models import Feedback

        async with self._db.sessions() as session:
            session.add(
                Feedback(
                    session_id=session_id, message_id=message_id, rating=rating, comment=comment
                )
            )
            await session.commit()


@dataclass
class Container:
    settings: Settings
    redis: Any
    llm: ChatClient
    tools: ToolRegistry
    retriever: Callable[[], Any]  # async context manager yielding a Retriever
    feedback: FeedbackStore
    db: Database | None = None

    async def close(self) -> None:
        if self.db is not None:
            await self.db.close()
        close = getattr(self.redis, "aclose", None) or getattr(self.redis, "close", None)
        if close is not None:
            await close()


def build_container(settings: Settings) -> Container:
    import redis.asyncio as aioredis
    from openai import AsyncOpenAI

    from gator_ta.chat.llm import OpenAIChatClient
    from gator_ta.ingest.embed import OpenAIEmbedder
    from gator_ta.retrieval.search import HybridRetriever

    db = Database(settings)
    client = AsyncOpenAI(api_key=settings.openai_api_key or None)
    embedder = OpenAIEmbedder(client, settings.embedding_model)

    @asynccontextmanager
    async def retriever() -> AsyncIterator[Retriever]:
        async with db.sessions() as session:
            yield HybridRetriever(session, embedder, settings.course_id, settings.candidate_k)

    return Container(
        settings=settings,
        redis=aioredis.from_url(settings.redis_url, decode_responses=True),
        llm=OpenAIChatClient(client, settings.chat_model),
        tools=ToolRegistry(Syllabus.load(settings.syllabus_path)),
        retriever=retriever,
        feedback=PostgresFeedbackStore(db),
        db=db,
    )
