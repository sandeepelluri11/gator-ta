from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from typing import Any

import fakeredis.aioredis
import pytest

from gator_ta.chat.llm import StreamEvent, TextDelta, ToolCall, ToolCalls
from gator_ta.chat.memory import SessionMemory
from gator_ta.config import Settings
from gator_ta.container import Container
from gator_ta.retrieval.search import Passage
from gator_ta.tools.registry import Syllabus, ToolRegistry

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SYLLABUS = REPO_ROOT / "data/sample/syllabus.yaml"


class FakeLLM:
    """Replays scripted turns. Each turn is a list of StreamEvents; the last turn repeats."""

    def __init__(self, turns: list[list[StreamEvent]]) -> None:
        self.turns = turns
        self.requests: list[dict[str, Any]] = []

    async def stream(self, messages, tools=None) -> AsyncIterator[StreamEvent]:
        self.requests.append({"messages": list(messages), "tools": tools})
        turn = self.turns.pop(0) if len(self.turns) > 1 else self.turns[0]
        for event in turn:
            yield event


def text_turn(*pieces: str) -> list[StreamEvent]:
    return [TextDelta(p) for p in pieces]


def tool_turn(
    name: str, arguments: dict | None = None, call_id: str = "call_1"
) -> list[StreamEvent]:
    return [ToolCalls([ToolCall(call_id, name, json.dumps(arguments or {}))])]


class FakeRetriever:
    def __init__(self, passages: list[Passage] | None = None) -> None:
        self.passages = passages if passages is not None else default_passages()
        self.queries: list[str] = []

    async def search(self, query: str, k: int) -> list[Passage]:
        self.queries.append(query)
        return self.passages[:k]


def default_passages() -> list[Passage]:
    return [
        Passage(
            11, "02 Retrieval", "slides/02-retrieval.md", 6, "Hybrid retrieval", "RRF k=60", 0.03
        ),
        Passage(
            12, "02 Retrieval", "slides/02-retrieval.md", 3, "Chunking", "200-400 tokens", 0.02
        ),
    ]


class MemoryFeedbackStore:
    def __init__(self) -> None:
        self.rows: list[dict] = []

    async def add(self, session_id: str, message_id: str, rating: int, comment: str) -> None:
        self.rows.append(
            {
                "session_id": session_id,
                "message_id": message_id,
                "rating": rating,
                "comment": comment,
            }
        )


@pytest.fixture
def settings() -> Settings:
    return Settings(
        syllabus_path=SYLLABUS, top_k=2, max_tool_rounds=2, history_turns=3, _env_file=None
    )


@pytest.fixture
def redis():
    return fakeredis.aioredis.FakeRedis(decode_responses=True)


@pytest.fixture
def memory(redis, settings) -> SessionMemory:
    return SessionMemory(redis, settings.history_turns, settings.session_ttl_seconds)


@pytest.fixture
def tools() -> ToolRegistry:
    return ToolRegistry(Syllabus.load(SYLLABUS), today=lambda: date(2026, 10, 15))


@pytest.fixture
def make_container(settings, redis, tools):
    def _make(llm: FakeLLM, retriever: FakeRetriever | None = None) -> Container:
        retriever = retriever or FakeRetriever()

        @asynccontextmanager
        async def provide():
            yield retriever

        return Container(
            settings=settings,
            redis=redis,
            llm=llm,
            tools=tools,
            retriever=provide,
            feedback=MemoryFeedbackStore(),
        )

    return _make
