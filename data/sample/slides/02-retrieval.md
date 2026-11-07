# Lecture 2: Retrieval-augmented generation

CIS6930 - Building LLM Applications

Retrieval-augmented generation (RAG) supplies the model with passages fetched at request time
so that answers are grounded in a specific corpus rather than in the model's training data.

---

## Why retrieve

- The corpus changes faster than the model can be retrained
- The corpus may be private
- Citations: the answer can point at the passage it came from, which makes it checkable

---

## Chunking

Documents are split into chunks before indexing. Guidelines we use in HW2:

- Keep a chunk inside one logical unit (one slide, one page, one section)
- Budget 200 to 400 tokens per chunk
- Overlap neighbouring chunks by roughly 10 to 15 percent so a sentence that straddles a
  boundary is still retrievable
- Store page number and heading as metadata so the answer can cite them

---

## Dense retrieval

Each chunk is embedded into a vector. At query time the question is embedded with the same
model and the nearest chunks by cosine similarity are returned. Dense retrieval handles
paraphrase well but can miss exact identifiers such as error codes or function names.

---

## Sparse retrieval

Full-text search (BM25 or Postgres tsvector ranking) scores chunks by term overlap. It is
excellent at exact identifiers and rare words and weak at paraphrase.

---

## Hybrid retrieval and reciprocal rank fusion

Run dense and sparse retrieval separately, then fuse the ranked lists with reciprocal rank
fusion (RRF):

score(d) = sum over lists of 1 / (k + rank_list(d)), with k = 60 by default.

RRF needs no score calibration between the two systems, which is why it is the default fusion
method in this course. Chunks that rank well in both lists rise to the top.

---

## Failure modes to check in your error analysis

- Retrieval miss: the right chunk exists but was not in the top k
- Chunk too small: the retrieved chunk lacks the context needed to answer
- Distractor: a retrieved chunk is topically similar but answers a different question
- Faithfulness: the model answers from memory and ignores the retrieved passages
