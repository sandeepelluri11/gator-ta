from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class OfficeHour(BaseModel):
    staff: str
    role: str
    day: str
    start: str
    end: str
    location: str


class Deadline(BaseModel):
    name: str
    kind: str
    due: date
    notes: str = ""


class GradingPolicy(BaseModel):
    breakdown: dict[str, int]
    late_policy: str
    collaboration_policy: str


class Syllabus(BaseModel):
    course_id: str
    title: str
    term: str
    office_hours: list[OfficeHour] = Field(default_factory=list)
    deadlines: list[Deadline] = Field(default_factory=list)
    grading: GradingPolicy

    @classmethod
    def load(cls, path: Path) -> Syllabus:
        return cls.model_validate(yaml.safe_load(Path(path).read_text()))


class ToolRegistry:
    """Maps tool names to implementations over a loaded syllabus."""

    def __init__(self, syllabus: Syllabus, today: Callable[[], date] = date.today) -> None:
        self.syllabus = syllabus
        self._today = today
        self._handlers: dict[str, Callable[..., Any]] = {
            "get_office_hours": self.get_office_hours,
            "get_deadlines": self.get_deadlines,
            "get_grading_policy": self.get_grading_policy,
        }

    @property
    def names(self) -> list[str]:
        return list(self._handlers)

    def get_office_hours(self, day: str | None = None) -> list[dict]:
        hours = self.syllabus.office_hours
        if day:
            hours = [h for h in hours if h.day.lower().startswith(day.lower()[:3])]
        return [h.model_dump() for h in hours]

    def get_deadlines(self, upcoming_only: bool = False) -> list[dict]:
        items = sorted(self.syllabus.deadlines, key=lambda d: d.due)
        if upcoming_only:
            today = self._today()
            items = [d for d in items if d.due >= today]
        return [d.model_dump(mode="json") for d in items]

    def get_grading_policy(self) -> dict:
        return self.syllabus.grading.model_dump()

    def dispatch(self, name: str, arguments: str | dict | None) -> str:
        """Run a tool by name and return a JSON string suitable for a tool message."""
        handler = self._handlers.get(name)
        if handler is None:
            return json.dumps({"error": f"unknown tool: {name}"})
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments or "{}")
            except json.JSONDecodeError:
                return json.dumps({"error": "arguments were not valid JSON"})
        try:
            return json.dumps(handler(**(arguments or {})), default=str)
        except TypeError as exc:
            return json.dumps({"error": f"bad arguments for {name}: {exc}"})
