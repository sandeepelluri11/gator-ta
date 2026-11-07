-- GatorTA initial schema. Apply with: psql "$DATABASE_URL" -f migrations/001_init.sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS documents (
    id          SERIAL PRIMARY KEY,
    course_id   VARCHAR(32)  NOT NULL,
    title       VARCHAR(256) NOT NULL,
    source      VARCHAR(512) NOT NULL UNIQUE,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS documents_course_idx ON documents (course_id);

CREATE TABLE IF NOT EXISTS chunks (
    id           SERIAL PRIMARY KEY,
    document_id  INTEGER NOT NULL REFERENCES documents (id) ON DELETE CASCADE,
    ordinal      INTEGER NOT NULL,
    page         INTEGER,
    heading      VARCHAR(256) NOT NULL DEFAULT '',
    content      TEXT NOT NULL,
    embedding    vector(1536) NOT NULL,
    content_tsv  tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED
);
CREATE INDEX IF NOT EXISTS chunks_document_idx  ON chunks (document_id);
CREATE INDEX IF NOT EXISTS chunks_embedding_idx ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS chunks_tsv_idx       ON chunks USING gin (content_tsv);

CREATE TABLE IF NOT EXISTS feedback (
    id          SERIAL PRIMARY KEY,
    session_id  VARCHAR(64) NOT NULL,
    message_id  VARCHAR(64) NOT NULL,
    rating      INTEGER NOT NULL CHECK (rating IN (-1, 1)),
    comment     TEXT NOT NULL DEFAULT '',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS feedback_session_idx ON feedback (session_id);
