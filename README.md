# GatorTA

A course Q&A assistant for a university class. Students ask questions in a chat UI; the service
answers from the lecture slides (with citations back to the specific slide) and from the course
syllabus (deadlines, office hours, grading and late policies) via tool calls. A graded question
set is run nightly against the live system so regressions in answer quality are caught
automatically.

Stack: **Python / FastAPI**, **Next.js** (TypeScript), **PostgreSQL + pgvector**, **Redis**,
**OpenAI API**.

## How a question is answered

```
browser ──POST /chat (SSE)──▶ FastAPI
                               │
                               ├─ 1. retrieve   pgvector cosine search  ┐
                               │                Postgres full-text      ├─ fused with RRF → top-k passages
                               │                                        ┘
                               ├─ 2. prompt     system rules + numbered passages + last N turns (Redis)
                               │
                               ├─ 3. tool loop  model may call get_deadlines / get_office_hours /
                               │                get_grading_policy (answered from syllabus.yaml)
                               │
                               └─ 4. stream     tokens → client; final answer appended to session memory
```

Events on the stream, in order: `session`, `citations`, zero or more `tool_call`, `token`
(repeated), `done` (or `error`). The UI renders only the citations the answer actually
references (`[n]`).

### Retrieval

Lecture material is split into slides, chunked under a token budget with a small overlap, and
embedded with `text-embedding-3-small`. At query time the service runs two searches in Postgres,
a cosine nearest-neighbour search over the `vector` column (HNSW index) and a `websearch_to_tsquery`
match over a generated `tsvector` column, and merges the two ranked lists with reciprocal rank
fusion. The fused list is what the model sees, numbered, with slide and page provenance.

### Tools

Questions about logistics should not be answered from embeddings. The model is given three
function schemas backed by the syllabus file. Each returns a compact JSON payload (for example
the next deadlines relative to today, or whether a late day may be used on a given assignment),
and the final answer is grounded in that payload. `GATOR_MAX_TOOL_ROUNDS` bounds the loop.

### Evaluation

`data/eval/course_qa.jsonl` holds questions written against the sample material, each with a
reference answer, tags, and optionally the tool the agent is expected to call. `gator-eval`
answers every case through the real agent, asks a judge model for a binary correct/incorrect
verdict against the reference, checks tool routing, and writes a Markdown + JSON report with
overall and per-tag accuracy. It exits non-zero when accuracy falls below `--min-accuracy`.
`.github/workflows/eval.yml` runs this every night against a fresh pgvector database and uploads
the report.

## Repository layout

```
api/                   FastAPI service (package gator_ta)
  gator_ta/ingest/     loaders (markdown / pdf / txt), chunking, embedding, upsert, gator-ingest CLI
  gator_ta/retrieval/  hybrid pgvector + full-text retriever with RRF
  gator_ta/tools/      syllabus-backed tool schemas and dispatch
  gator_ta/chat/       prompts, Redis session memory, streaming OpenAI client, agent loop
  gator_ta/eval/       dataset, LLM judge, gator-eval runner and report
  migrations/          001_init.sql (pgvector extension, documents, chunks, feedback)
  tests/               pytest suite with scripted LLM / retriever fakes and fakeredis
web/                   Next.js app: chat UI, SSE client, citations, feedback
data/sample/           syllabus.yaml and three slide decks used for local runs and the nightly eval
data/eval/             course_qa.jsonl graded question set
.github/workflows/     ci.yml (tests, lint, build) and eval.yml (nightly quality gate)
```

## Running it

### With Docker

```bash
cp .env.example .env          # add your OPENAI_API_KEY
docker compose up --build      # db (pgvector), redis, api :8000, web :3000
docker compose run --rm api gator-ingest /data/sample/slides
```

Open http://localhost:3000. The schema in `api/migrations/` is applied automatically when the
database volume is first created.

### Locally

```bash
make setup                     # venv + api[dev] + web deps
make infra                     # Postgres (pgvector) and Redis in Docker
cp .env.example .env
make ingest                    # embed data/sample/slides
make api                       # http://localhost:8000  (docs at /docs)
make web                       # http://localhost:3000
```

### Tests and lint

```bash
make test                      # pytest (api) + tsc (web)
make lint
```

The test suite does not need Postgres, Redis, or an API key. The retriever and the LLM are
replaced with scripted fakes and Redis with `fakeredis`, so the agent loop, tool dispatch,
SSE endpoint, chunking, rank fusion, and evaluation scoring are all exercised offline.

### Evaluation

```bash
make eval                      # writes eval-results/<timestamp>.{md,json} and latest.md
```

To enable the nightly run on a fork, add an `OPENAI_API_KEY` repository secret. The workflow
skips itself when the secret is absent.

## Configuration

All settings are environment variables with the `GATOR_` prefix (see `api/gator_ta/config.py`).

| Variable | Default | Purpose |
| --- | --- | --- |
| `OPENAI_API_KEY` | – | Required for chat, embeddings, and the judge |
| `GATOR_DATABASE_URL` | `postgresql+asyncpg://gator:gator@localhost:5432/gator` | Postgres with pgvector |
| `GATOR_REDIS_URL` | `redis://localhost:6379/0` | Session memory |
| `GATOR_CHAT_MODEL` / `GATOR_JUDGE_MODEL` | `gpt-4o-mini` / `gpt-4o` | Answering and judging models |
| `GATOR_EMBEDDING_MODEL` | `text-embedding-3-small` | Must match the 1536-dim column |
| `GATOR_SYLLABUS_PATH` | `data/sample/syllabus.yaml` | Source for the logistics tools |
| `GATOR_TOP_K` / `GATOR_CANDIDATE_K` | `6` / `20` | Passages shown to the model / fetched per search |
| `GATOR_CHUNK_TOKENS` / `GATOR_CHUNK_OVERLAP_TOKENS` | `350` / `50` | Ingest chunking |
| `GATOR_MAX_TOOL_ROUNDS` | `3` | Cap on tool-call iterations per answer |
| `GATOR_HISTORY_TURNS` / `GATOR_SESSION_TTL_SECONDS` | `8` / `21600` | Conversation memory |
| `GATOR_CORS_ORIGINS` | `["http://localhost:3000"]` | JSON list of allowed origins |

## Adapting it to another course

Replace `data/sample/syllabus.yaml` with your own (same keys), point `gator-ingest` at your
slides (`.md` split on `---`, `.pdf`, or `.txt`), and rewrite `data/eval/course_qa.jsonl` so the
nightly gate measures your material rather than the sample.

## License

MIT
