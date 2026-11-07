import json

from gator_ta.tools.schemas import TOOL_SCHEMAS


def test_schemas_match_registry(tools):
    assert sorted(t["function"]["name"] for t in TOOL_SCHEMAS) == sorted(tools.names)


def test_office_hours_filter_by_day(tools):
    assert len(tools.get_office_hours()) == 3
    wed = tools.get_office_hours(day="wednesday")
    assert [h["staff"] for h in wed] == ["Head TA"]
    assert tools.get_office_hours(day="Sun") == []


def test_upcoming_deadlines_use_injected_today(tools):
    upcoming = json.loads(tools.dispatch("get_deadlines", '{"upcoming_only": true}'))
    assert [d["name"] for d in upcoming][:2] == ["Midterm", "HW3 - Evaluation harness"]
    everything = json.loads(tools.dispatch("get_deadlines", {}))
    assert len(everything) == 6


def test_grading_policy_roundtrip(tools):
    policy = json.loads(tools.dispatch("get_grading_policy", None))
    assert policy["breakdown"]["project"] == 35
    assert "four late days" in policy["late_policy"]


def test_dispatch_errors_are_json_not_exceptions(tools):
    assert json.loads(tools.dispatch("nope", "{}"))["error"].startswith("unknown tool")
    assert "not valid JSON" in json.loads(tools.dispatch("get_office_hours", "{bad"))["error"]
    assert "bad arguments" in json.loads(tools.dispatch("get_office_hours", {"x": 1}))["error"]
