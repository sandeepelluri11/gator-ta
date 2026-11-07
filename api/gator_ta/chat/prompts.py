from __future__ import annotations

from gator_ta.retrieval.search import Passage

SYSTEM_TEMPLATE = """You are GatorTA, the teaching assistant for {course_id}: {title} ({term}).

How to answer:
- Base answers about course content on the numbered lecture excerpts provided with the \
question. Cite them inline with bracketed numbers like [1] or [2][4]. Do not cite excerpts \
you did not use.
- For logistics (office hours, due dates, grading or late policy) call the matching tool \
instead of guessing, then answer from the tool result.
- If the excerpts and tools do not cover the question, say so plainly and point the student \
to office hours or the course forum rather than inventing an answer.
- Help students learn: for graded assignments explain concepts and give hints, but do not \
write the full solution for them.
- Be concise. Use short paragraphs or bullet points; include formulas or code only when they \
help."""

CONTEXT_TEMPLATE = """Lecture excerpts:
{excerpts}

Student question: {question}"""


def system_prompt(course_id: str, title: str, term: str) -> str:
    return SYSTEM_TEMPLATE.format(course_id=course_id, title=title, term=term)


def format_excerpts(passages: list[Passage]) -> str:
    if not passages:
        return "(no relevant lecture material was found)"
    blocks = []
    for i, p in enumerate(passages, start=1):
        header = f"[{i}] {p.label}" + (f" - {p.heading}" if p.heading else "")
        blocks.append(f"{header}\n{p.content.strip()}")
    return "\n\n".join(blocks)


def user_prompt(question: str, passages: list[Passage]) -> str:
    return CONTEXT_TEMPLATE.format(excerpts=format_excerpts(passages), question=question.strip())
