from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field


class EvalCase(BaseModel):
    id: str
    question: str
    reference: str = Field(description="Reference answer written by course staff.")
    tags: list[str] = Field(default_factory=list)
    expect_tool: str | None = Field(
        default=None, description="Tool the agent is expected to call, if any."
    )


def load_cases(path: Path) -> list[EvalCase]:
    cases = []
    for line in Path(path).read_text().splitlines():
        if line.strip():
            cases.append(EvalCase.model_validate(json.loads(line)))
    ids = [c.id for c in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate case ids in eval set")
    return cases
