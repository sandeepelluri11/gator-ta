"""LLM-as-judge grading with a fixed rubric and strict JSON output."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Protocol

JUDGE_SYSTEM = """You grade answers from a course teaching-assistant bot against a reference \
answer written by course staff.

Rubric:
- correct = true when the candidate conveys the same key facts as the reference with no \
contradictions. Extra correct detail is fine. Different wording is fine.
- correct = false when the candidate contradicts the reference, omits a fact the question \
explicitly asks for, or invents specifics (dates, numbers, names) not supported by the reference.
- A candidate that honestly says the material does not cover the question is correct only if \
the reference also says so.

Reply with ONLY a JSON object: {"correct": true|false, "reasoning": "<one or two sentences>"}."""

JUDGE_USER = """Question:
{question}

Reference answer:
{reference}

Candidate answer:
{candidate}"""

_JSON = re.compile(r"\{.*\}", re.DOTALL)


@dataclass
class Verdict:
    correct: bool
    reasoning: str


def parse_verdict(raw: str) -> Verdict:
    match = _JSON.search(raw)
    if not match:
        return Verdict(False, f"judge returned no JSON: {raw[:120]}")
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return Verdict(False, f"judge returned invalid JSON: {raw[:120]}")
    return Verdict(bool(data.get("correct", False)), str(data.get("reasoning", "")))


class Judge(Protocol):
    async def grade(self, question: str, reference: str, candidate: str) -> Verdict: ...


class OpenAIJudge:
    def __init__(self, client, model: str) -> None:
        self._client = client
        self._model = model

    async def grade(self, question: str, reference: str, candidate: str) -> Verdict:
        response = await self._client.chat.completions.create(
            model=self._model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": JUDGE_SYSTEM},
                {
                    "role": "user",
                    "content": JUDGE_USER.format(
                        question=question, reference=reference, candidate=candidate
                    ),
                },
            ],
        )
        return parse_verdict(response.choices[0].message.content or "")
