PY ?= python3.12
VENV ?= .venv
BIN := $(VENV)/bin

.PHONY: setup infra down api web ingest eval test lint fmt

setup: ## create venv, install api (dev extras) and web deps
	$(PY) -m venv $(VENV)
	$(BIN)/pip install -e "./api[dev]"
	cd web && npm install

infra: ## start Postgres (pgvector) and Redis; the schema is applied on first boot
	docker compose up -d db redis

down:
	docker compose down

api: ## run the API with reload
	cd api && ../$(BIN)/uvicorn gator_ta.main:app --reload

web: ## run the Next.js dev server
	cd web && npm run dev

ingest: ## embed the sample slide decks into Postgres
	$(BIN)/gator-ingest data/sample/slides

eval: ## run the graded question set and gate on accuracy
	$(BIN)/gator-eval data/eval/course_qa.jsonl --out eval-results --min-accuracy 0.85

test:
	cd api && ../$(BIN)/pytest
	cd web && npm run typecheck

lint:
	cd api && ../$(BIN)/ruff check . && ../$(BIN)/ruff format --check .

fmt:
	cd api && ../$(BIN)/ruff format . && ../$(BIN)/ruff check --fix .
