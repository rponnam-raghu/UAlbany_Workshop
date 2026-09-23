CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS embedding_configuration (
    singleton BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (singleton),
    signature TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS document_chunks (
    chunk_id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    content TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    embedding vector NOT NULL
);
