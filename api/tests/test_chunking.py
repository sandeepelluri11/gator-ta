from pathlib import Path

from gator_ta.ingest.chunking import approx_token_count, chunk_sections
from gator_ta.ingest.loaders import Section, load_file, load_markdown_slides

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def words(n: int) -> str:
    return " ".join(f"w{i}" for i in range(n))


def count_words(text: str) -> int:
    return len(text.split())


def test_markdown_slides_split_on_rules():
    sections = load_markdown_slides(REPO_ROOT / "data/sample/slides/02-retrieval.md")
    assert len(sections) == 7
    assert sections[0].page == 1
    assert sections[0].heading == "Lecture 2: Retrieval-augmented generation"
    assert sections[5].heading == "Hybrid retrieval and reciprocal rank fusion"


def test_chunks_never_cross_sections():
    sections = [Section("a a a", page=1, heading="A"), Section("b b b", page=2, heading="B")]
    chunks = chunk_sections(sections, budget_tokens=100, count=count_words)
    assert [(c.page, c.heading, c.content) for c in chunks] == [
        (1, "A", "a a a"),
        (2, "B", "b b b"),
    ]


def test_paragraphs_pack_up_to_budget_with_overlap():
    paragraphs = [words(30) for _ in range(4)]
    section = Section("\n\n".join(paragraphs), page=1)
    chunks = chunk_sections([section], budget_tokens=65, overlap_tokens=5, count=count_words)

    assert len(chunks) == 2
    assert all(count_words(c.content) <= 65 for c in chunks)
    # the second chunk starts with the 5-word tail of the first for continuity
    assert chunks[1].content.split()[:5] == chunks[0].content.split()[-5:]
    assert [c.ordinal for c in chunks] == [0, 1]


def test_oversized_paragraph_is_split_on_sentences():
    paragraph = " ".join(f"Sentence number {i} is here." for i in range(20))
    chunks = chunk_sections([Section(paragraph, page=3)], budget_tokens=25, count=count_words)
    assert len(chunks) > 1
    assert all(count_words(c.content) <= 25 for c in chunks)
    assert all(c.page == 3 for c in chunks)


def test_approx_counter_is_monotonic():
    assert approx_token_count("") == 1
    assert approx_token_count("x" * 400) == 100


def test_load_file_rejects_unknown_suffix(tmp_path: Path):
    bad = tmp_path / "deck.pptx"
    bad.write_bytes(b"")
    try:
        load_file(bad)
    except ValueError as exc:
        assert "unsupported" in str(exc)
    else:
        raise AssertionError("expected ValueError")
