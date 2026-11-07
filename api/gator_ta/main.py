from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from gator_ta import __version__
from gator_ta.chat.agent import Agent
from gator_ta.chat.memory import SessionMemory
from gator_ta.config import Settings, get_settings
from gator_ta.container import Container, build_container


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    session_id: str | None = Field(default=None, max_length=64)


class FeedbackRequest(BaseModel):
    session_id: str = Field(max_length=64)
    message_id: str = Field(max_length=64)
    rating: int = Field(ge=-1, le=1)
    comment: str = Field(default="", max_length=2000)


def sse(event: dict) -> str:
    return f"data: {json.dumps(event)}\n\n"


def create_app(container: Container | None = None, settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.container = container or build_container(settings)
        try:
            yield
        finally:
            await app.state.container.close()

    app = FastAPI(title="GatorTA API", version=__version__, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def memory(c: Container) -> SessionMemory:
        return SessionMemory(c.redis, c.settings.history_turns, c.settings.session_ttl_seconds)

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok", "version": __version__}

    @app.post("/chat")
    async def chat(body: ChatRequest, request: Request) -> StreamingResponse:
        c: Container = request.app.state.container
        session_id = body.session_id or uuid.uuid4().hex

        async def events() -> AsyncIterator[str]:
            yield sse({"type": "session", "session_id": session_id})
            try:
                async with c.retriever() as retriever:
                    agent = Agent(
                        c.llm,
                        retriever,
                        c.tools,
                        memory(c),
                        top_k=c.settings.top_k,
                        max_tool_rounds=c.settings.max_tool_rounds,
                    )
                    async for event in agent.answer(session_id, body.question):
                        yield sse(event)
            except Exception as exc:  # noqa: BLE001 - surfaced to the client as an event
                yield sse({"type": "error", "message": str(exc)})

        return StreamingResponse(
            events(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.get("/sessions/{session_id}")
    async def session_history(session_id: str, request: Request) -> dict:
        c: Container = request.app.state.container
        return {"session_id": session_id, "messages": await memory(c).history(session_id)}

    @app.delete("/sessions/{session_id}", status_code=204)
    async def clear_session(session_id: str, request: Request) -> None:
        c: Container = request.app.state.container
        await memory(c).clear(session_id)

    @app.post("/feedback", status_code=201)
    async def feedback(body: FeedbackRequest, request: Request) -> dict:
        c: Container = request.app.state.container
        if body.rating == 0:
            raise HTTPException(status_code=422, detail="rating must be -1 or 1")
        await c.feedback.add(body.session_id, body.message_id, body.rating, body.comment)
        return {"ok": True}

    return app


app = create_app()
