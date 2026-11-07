from pathlib import Path

from gator_ta.eval.dataset import load_cases
from gator_ta.eval.judge import Verdict, parse_verdict
from gator_ta.eval.run import evaluate, render_markdown, summarize, write_report

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


class ScriptedJudge:
    def __init__(self, correct_ids: set[str]) -> None:
        self.correct_ids = correct_ids

    async def grade(self, question, reference, candidate):
        ok = any(cid in candidate for cid in self.correct_ids)
        return Verdict(ok, "scripted")


def test_parse_verdict_tolerates_prose_and_garbage():
    assert parse_verdict('ok {"correct": true, "reasoning": "fine"} bye') == Verdict(True, "fine")
    assert parse_verdict("nothing here").correct is False
    assert parse_verdict("{not json}").correct is False


def test_sample_dataset_loads_with_unique_ids():
    cases = load_cases(REPO_ROOT / "data/eval/course_qa.jsonl")
    assert len(cases) >= 10
    assert any(c.expect_tool == "get_office_hours" for c in cases)


async def test_evaluate_scores_accuracy_tags_and_tool_routing(tmp_path: Path):
    cases = (
        load_cases(REPO_ROOT / "data/eval/course_qa.jsonl")[:4]
        + [c for c in load_cases(REPO_ROOT / "data/eval/course_qa.jsonl") if c.expect_tool][:2]
    )

    async def answerer(case):
        tools = ["get_office_hours"] if case.id == "logistics-01" else []
        return f"answer for {case.id}", [{"n": 1}], tools

    judge = ScriptedJudge({"intro-01", "intro-02", "logistics-01", "logistics-02"})
    results = await evaluate(cases, answerer, judge)
    summary = summarize(results)

    assert summary.total == 6
    assert summary.correct == 4
    assert abs(summary.accuracy - 4 / 6) < 1e-9
    # logistics-02 expected get_deadlines but nothing was called
    assert summary.tool_accuracy == 0.5
    assert summary.by_tag["lecture-1"] == 2 / 3

    md = render_markdown(summary, results)
    assert "Accuracy: **66.7%** (4/6)" in md
    assert "### intro-03" in md
    assert "expected `get_deadlines`" in md

    report = write_report(tmp_path, summary, results)
    assert report.exists()
    assert (tmp_path / "latest.md").read_text() == md
    assert len(list(tmp_path.glob("*.json"))) == 1
