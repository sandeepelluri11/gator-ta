from gator_ta.chat.prompts import format_excerpts
from gator_ta.retrieval.search import Passage, reciprocal_rank_fusion


def test_rrf_prefers_items_present_in_both_lists():
    fused = reciprocal_rank_fusion([["a", "b", "c"], ["c", "d", "a"]], k=60)
    order = [item for item, _ in fused]
    assert order[:2] == ["a", "c"]
    assert set(order) == {"a", "b", "c", "d"}


def test_rrf_scores_match_formula():
    fused = dict(reciprocal_rank_fusion([["x"], ["x"]], k=10))
    assert fused["x"] == 2 / 11


def test_rrf_handles_empty_lists():
    assert reciprocal_rank_fusion([[], []]) == []


def test_excerpts_are_numbered_with_labels():
    passages = [
        Passage(1, "01 Intro", "s", 4, "Structured output", "Ask for JSON.", 0.1),
        Passage(2, "01 Intro", "s", None, "", "No page here.", 0.1),
    ]
    rendered = format_excerpts(passages)
    assert rendered.startswith("[1] 01 Intro (p. 4) - Structured output\nAsk for JSON.")
    assert "[2] 01 Intro (doc)\nNo page here." in rendered
    assert format_excerpts([]).startswith("(no relevant")
