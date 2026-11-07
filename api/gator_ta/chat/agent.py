"""The GatorTA agent: retrieve -> (tool call)* -> cited, streamed answer."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

from gator_ta.chat.llm import ChatClient, TextDelta, ToolCalls, parse_arguments, tool_result_message
from gator_ta.chat.memory import SessionMemory
from gator_ta.chat.prompts import system_prompt, user_prompt
from gator_ta.retrieval.search import Passage, Retriever
from gator_ta.tools.registry import ToolRegistry
from gator_ta.tools.schemas import TOOL_SCHEMAS


def citation_payload(passages: list[Passage]) -> list[dict[str, Any]]:
    return [
        {
            "n": i,
            "chunk_id": p.chunk_id,
            "label": p.label,
            "heading": p.heading,
            "source": p.source,
            "page": p.page,
            "snippet": p.content[:240],
        }
        for i, p in enumerate(passages, start=1)
    ]


class Agent:
    def __init__(
        self,
        llm: ChatClient,
        retriever: Retriever,
        tools: ToolRegistry,
        memory: SessionMemory,
        top_k: int = 6,
        max_tool_rounds: int = 3,
    ) -> None:
        self._llm = llm
        self._retriever = retriever
        self._tools = tools
        self._memory = memory
        self._top_k = top_k
        self._max_tool_rounds = max_tool_rounds

    async def answer(self, session_id: str, question: str) -> AsyncIterator[dict[str, Any]]:
        """Yield SSE-ready events: citations, tool_call, token, done."""
        history = await self._memory.history(session_id)
        passages = await self._retriever.search(question, self._top_k)
        yield {"type": "citations", "citations": citation_payload(passages)}

        syllabus = self._tools.syllabus
        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": system_prompt(syllabus.course_id, syllabus.title, syllabus.term),
            },
            *history,
            {"role": "user", "content": user_prompt(question, passages)},
        ]

        answer_parts: list[str] = []
        rounds = 0
        while True:
            tools = TOOL_SCHEMAS if rounds < self._max_tool_rounds else None
            tool_calls: ToolCalls | None = None
            async for event in self._llm.stream(messages, tools=tools):
                if isinstance(event, TextDelta):
                    answer_parts.append(event.text)
                    yield {"type": "token", "text": event.text}
                elif isinstance(event, ToolCalls):
                    tool_calls = event

            if not tool_calls or not tool_calls.calls:
                break

            rounds += 1
            messages.append(
                {
                    "role": "assistant",
                    "content": "".join(answer_parts) or None,
                    "tool_calls": [c.as_message_part() for c in tool_calls.calls],
                }
            )
            for call in tool_calls.calls:
                args = parse_arguments(call)
                result = self._tools.dispatch(call.name, args)
                yield {"type": "tool_call", "name": call.name, "arguments": args}
                messages.append(tool_result_message(call, result))

        answer = "".join(answer_parts).strip()
        message_id = uuid.uuid4().hex
        await self._memory.append(
            session_id,
            {"role": "user", "content": question},
            {"role": "assistant", "content": answer},
        )
        yield {
            "type": "done",
            "message_id": message_id,
            "answer": answer,
            "tool_rounds": rounds,
        }


async def answer_text(agent: Agent, session_id: str, question: str) -> tuple[str, list[dict]]:
    """Collect a full answer (used by the eval harness and tests)."""
    answer, citations = "", []
    async for event in agent.answer(session_id, question):
        if event["type"] == "citations":
            citations = event["citations"]
        elif event["type"] == "done":
            answer = event["answer"]
    return answer, citations
