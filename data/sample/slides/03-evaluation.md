# Lecture 3: Evaluating LLM applications

CIS6930 - Building LLM Applications

You cannot improve what you do not measure. This lecture covers how to build a graded test set
and an automated judge, which is what HW3 asks you to implement.

---

## Building a graded set

- Collect real or realistic questions, not only easy ones
- Write a reference answer for each question; the reference is what the judge compares against
- Tag each question (topic, difficulty, whether a tool call is expected)
- Keep the set under version control and treat changes like code changes

---

## LLM-as-judge

A judge model reads the question, the reference answer and the candidate answer and returns a
verdict against a fixed rubric. Use a stronger model for the judge than for the system under
test when you can, and always ask the judge for a short written reason so failures are
debuggable.

---

## Known judge biases

- Position bias: when comparing two answers, judges prefer the first one shown
- Verbosity bias: longer answers are rated higher regardless of correctness
- Self-preference: a model rates its own outputs higher
- Central tendency: on numeric scales judges cluster around the middle values

Mitigations: grade one answer at a time against a reference, use binary or coarse scales, and
spot-check a sample by hand every week.

---

## Regression gating

Run the eval on a schedule (nightly) and on every change to prompts or retrieval settings.
Fail the run when accuracy drops below an agreed threshold. The threshold should be set from
a baseline run, not picked arbitrarily.

---

## What to report

- Overall accuracy and accuracy per tag
- Tool-routing accuracy for questions that should trigger a tool
- A list of failures with the judge's reasoning
