import json

import httpx
import pytest
from asgi_lifespan import LifespanManager

from gator_ta.main import create_app
from tests.conftest import FakeLLM, text_turn, tool_turn


def parse_sse(body: str) -> list[dict]:
    return [
        json.loads(line[len("data: ") :]) for line in body.splitlines() if line.startswith("data: ")
    ]


@pytest.fixture
async def client(make_container, settings):
    llm = FakeLLM(
        [tool_turn("get_deadlines", {"upcoming_only": True}), text_turn("Midterm is Oct 22 [1].")]
    )
    app = create_app(container=make_container(llm), settings=settings)
    async with LifespanManager(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            c.app = app  # type: ignore[attr-defined]
            yield c


async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


async def test_chat_streams_sse_and_persists_session(client):
    r = await client.post("/chat", json={"question": "When is the midterm?"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")

    events = parse_sse(r.text)
    types = [e["type"] for e in events]
    assert types[0] == "session"
    assert types[1] == "citations"
    assert "tool_call" in types
    assert types[-1] == "done"
    session_id = events[0]["session_id"]

    history = await client.get(f"/sessions/{session_id}")
    assert [m["role"] for m in history.json()["messages"]] == ["user", "assistant"]
    assert history.json()["messages"][1]["content"] == "Midterm is Oct 22 [1]."

    cleared = await client.delete(f"/sessions/{session_id}")
    assert cleared.status_code == 204
    assert (await client.get(f"/sessions/{session_id}")).json()["messages"] == []


async def test_chat_validates_input(client):
    assert (await client.post("/chat", json={"question": ""})).status_code == 422


async def test_feedback_is_stored(client):
    r = await client.post(
        "/feedback",
        json={"session_id": "s", "message_id": "m", "rating": 1, "comment": "helpful"},
    )
    assert r.status_code == 201
    store = client.app.state.container.feedback
    assert store.rows == [{"session_id": "s", "message_id": "m", "rating": 1, "comment": "helpful"}]

    bad = await client.post("/feedback", json={"session_id": "s", "message_id": "m", "rating": 0})
    assert bad.status_code == 422


async def test_chat_reports_errors_as_events(make_container, settings):
    class BrokenLLM:
        async def stream(self, messages, tools=None):
            raise RuntimeError("upstream down")
            yield  # pragma: no cover

    app = create_app(container=make_container(BrokenLLM()), settings=settings)
    async with LifespanManager(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://t"
        ) as c:
            r = await c.post("/chat", json={"question": "hi"})
    events = parse_sse(r.text)
    assert events[-1] == {"type": "error", "message": "upstream down"}
