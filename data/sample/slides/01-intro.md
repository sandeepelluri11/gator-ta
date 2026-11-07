# Lecture 1: What an LLM application is

CIS6930 - Building LLM Applications

An LLM application is a program that uses a language model as one component, surrounded by
ordinary software: input validation, retrieval, tool execution, output parsing, and monitoring.

---

## The model is not the product

Students often start by tuning prompts. In practice most of the engineering effort goes into:

- Getting the right context in front of the model
- Constraining the output so the rest of the system can consume it
- Measuring whether the system is actually correct

---

## Anatomy of a request

1. The user message is validated and normalised.
2. Relevant context is retrieved (documents, database rows, prior turns).
3. A prompt is assembled from a template, the context, and the message.
4. The model generates text, optionally calling tools.
5. The output is parsed and checked before it reaches the user.

Every one of these stages can fail independently, which is why we log each one.

---

## Structured output

When another program consumes the model output, ask for JSON and validate it against a schema.
Two techniques appear in this course:

- JSON mode / schema-constrained decoding, where the API guarantees syntactically valid JSON
- Validate-and-retry, where the application parses the output and, on failure, sends the
  validation error back to the model once

Validate-and-retry is model-agnostic and is what we use in HW1.

---

## Temperature

Temperature scales the logits before sampling. A temperature of 0 makes decoding greedy and
nearly deterministic; higher temperatures spread probability mass over more tokens. For
extraction and classification tasks we use temperature 0. For brainstorming tasks we use
0.7 or higher.

---

## Reading

- Course notes, chapter 1
- Optional: a survey of prompting techniques linked on the course site
