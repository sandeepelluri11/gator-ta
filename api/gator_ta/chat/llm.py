"""Thin streaming interface over the OpenAI chat API so the agent can be tested with fakes."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: str  # raw JSON string as produced by the model

    def as_message_part(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": "function",
            "function": {"name": self.name, "arguments": self.arguments},
        }


@dataclass
class TextDelta:
    text: str


@dataclass
class ToolCalls:
    calls: list[ToolCall] = field(default_factory=list)


StreamEvent = TextDelta | ToolCalls


class ChatClient(Protocol):
    def stream(
        self, messages: list[dict[str, Any]], tools: list[dict] | None = None
    ) -> AsyncIterator[StreamEvent]: ...


class OpenAIChatClient:
    def __init__(self, client, model: str, temperature: float = 0.2) -> None:
        self._client = client
        self._model = model
        self._temperature = temperature

    async def stream(
        self, messages: list[dict[str, Any]], tools: list[dict] | None = None
    ) -> AsyncIterator[StreamEvent]:
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": self._temperature,
            "stream": True,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        pending: dict[int, dict[str, str]] = {}
        response = await self._client.chat.completions.create(**kwargs)
        async for chunk in response:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta.content:
                yield TextDelta(delta.content)
            for tc in delta.tool_calls or []:
                slot = pending.setdefault(tc.index, {"id": "", "name": "", "arguments": ""})
                if tc.id:
                    slot["id"] = tc.id
                if tc.function and tc.function.name:
                    slot["name"] += tc.function.name
                if tc.function and tc.function.arguments:
                    slot["arguments"] += tc.function.arguments

        if pending:
            yield ToolCalls(
                [
                    ToolCall(slot["id"], slot["name"], slot["arguments"] or "{}")
                    for _, slot in sorted(pending.items())
                ]
            )


def tool_result_message(call: ToolCall, result: str) -> dict[str, Any]:
    return {"role": "tool", "tool_call_id": call.id, "content": result}


def parse_arguments(call: ToolCall) -> dict[str, Any]:
    try:
        parsed = json.loads(call.arguments or "{}")
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}
