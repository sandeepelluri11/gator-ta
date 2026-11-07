"""Run the graded question set, judge answers, write a report, and gate on accuracy.

    gator-eval data/eval/course_qa.jsonl --min-accuracy 0.85 --out eval-results

Exit code 1 when accuracy falls below the threshold so the nightly workflow fails loudly.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from gator_ta.eval.dataset import EvalCase, load_cases
from gator_ta.eval.judge import Judge

Answerer = Callable[[EvalCase], Awaitable[tuple[str, list[dict], list[str]]]]
"""Returns (answer, citations, tool names called) for a case."""


@dataclass
class CaseResult:
    id: str
    question: str
    reference: str
    answer: str
    correct: bool
    reasoning: str
    tags: list[str]
    tools_called: list[str]
    expected_tool: str | None
    tool_ok: bool
    n_citations: int


@dataclass
class Summary:
    total: int
    correct: int
    accuracy: float
    tool_accuracy: float
    by_tag: dict[str, float]
    generated_at: str


async def evaluate(cases: list[EvalCase], answerer: Answerer, judge: Judge) -> list[CaseResult]:
    results: list[CaseResult] = []
    for case in cases:
        answer, citations, tools = await answerer(case)
        verdict = await judge.grade(case.question, case.reference, answer)
        results.append(
            CaseResult(
                id=case.id,
                question=case.question,
                reference=case.reference,
                answer=answer,
                correct=verdict.correct,
                reasoning=verdict.reasoning,
                tags=case.tags,
                tools_called=tools,
                expected_tool=case.expect_tool,
                tool_ok=case.expect_tool is None or case.expect_tool in tools,
                n_citations=len(citations),
            )
        )
    return results


def summarize(results: list[CaseResult]) -> Summary:
    total = len(results)
    correct = sum(r.correct for r in results)
    tool_cases = [r for r in results if r.expected_tool]
    tags: dict[str, list[bool]] = {}
    for r in results:
        for tag in r.tags:
            tags.setdefault(tag, []).append(r.correct)
    return Summary(
        total=total,
        correct=correct,
        accuracy=correct / total if total else 0.0,
        tool_accuracy=(sum(r.tool_ok for r in tool_cases) / len(tool_cases) if tool_cases else 1.0),
        by_tag={tag: sum(v) / len(v) for tag, v in sorted(tags.items())},
        generated_at=datetime.now(UTC).isoformat(timespec="seconds"),
    )


def render_markdown(summary: Summary, results: list[CaseResult]) -> str:
    lines = [
        "# GatorTA nightly eval",
        "",
        f"- Generated: {summary.generated_at}",
        f"- Accuracy: **{summary.accuracy:.1%}** ({summary.correct}/{summary.total})",
        f"- Tool routing accuracy: {summary.tool_accuracy:.1%}",
        "",
        "| Tag | Accuracy |",
        "|---|---|",
        *[f"| {tag} | {acc:.1%} |" for tag, acc in summary.by_tag.items()],
        "",
        "## Failures",
        "",
    ]
    failures = [r for r in results if not r.correct or not r.tool_ok]
    if not failures:
        lines.append("None.")
    for r in failures:
        lines += [
            f"### {r.id}",
            "",
            f"**Q.** {r.question}",
            "",
            f"**Reference.** {r.reference}",
            "",
            f"**Answer.** {r.answer}",
            "",
            f"**Judge.** {r.reasoning}",
        ]
        if not r.tool_ok:
            lines.append(f"**Tool routing.** expected `{r.expected_tool}`, got {r.tools_called}")
        lines.append("")
    return "\n".join(lines)


def write_report(out_dir: Path, summary: Summary, results: list[CaseResult]) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    payload = {"summary": asdict(summary), "results": [asdict(r) for r in results]}
    (out_dir / f"{stamp}.json").write_text(json.dumps(payload, indent=2))
    md_path = out_dir / f"{stamp}.md"
    md_path.write_text(render_markdown(summary, results))
    (out_dir / "latest.md").write_text(render_markdown(summary, results))
    return md_path


async def _live_answerer():
    """Build an answerer wired to the real container (DB, Redis, OpenAI)."""
    from gator_ta.chat.agent import Agent
    from gator_ta.chat.memory import SessionMemory
    from gator_ta.config import get_settings
    from gator_ta.container import build_container

    settings = get_settings()
    container = build_container(settings)
    memory = SessionMemory(container.redis, settings.history_turns, settings.session_ttl_seconds)

    async def answer(case: EvalCase) -> tuple[str, list[dict], list[str]]:
        session_id = f"eval-{uuid.uuid4().hex}"
        tools: list[str] = []
        citations: list[dict] = []
        text = ""
        async with container.retriever() as retriever:
            agent = Agent(container.llm, retriever, container.tools, memory, settings.top_k)
            async for event in agent.answer(session_id, case.question):
                if event["type"] == "tool_call":
                    tools.append(event["name"])
                elif event["type"] == "citations":
                    citations = event["citations"]
                elif event["type"] == "done":
                    text = event["answer"]
        await memory.clear(session_id)
        return text, citations, tools

    return answer, container


async def _main(args: argparse.Namespace) -> int:
    from openai import AsyncOpenAI

    from gator_ta.config import get_settings
    from gator_ta.eval.judge import OpenAIJudge

    settings = get_settings()
    cases = load_cases(args.dataset)
    answerer, container = await _live_answerer()
    judge = OpenAIJudge(AsyncOpenAI(api_key=settings.openai_api_key or None), settings.judge_model)
    try:
        results = await evaluate(cases, answerer, judge)
    finally:
        await container.close()

    summary = summarize(results)
    report = write_report(args.out, summary, results)
    print(f"accuracy {summary.accuracy:.1%} ({summary.correct}/{summary.total}) -> {report}")
    if summary.accuracy < args.min_accuracy:
        print(f"FAIL: accuracy below threshold {args.min_accuracy:.0%}", file=sys.stderr)
        return 1
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--out", type=Path, default=Path("eval-results"))
    parser.add_argument("--min-accuracy", type=float, default=0.85)
    args = parser.parse_args()
    sys.exit(asyncio.run(_main(args)))


if __name__ == "__main__":
    main()
