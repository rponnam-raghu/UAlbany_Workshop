-- The old document_chunks table is deliberately excluded from the new helpdesk.
CREATE TABLE knowledge_state (
    singleton BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (singleton),
    revision BIGINT NOT NULL DEFAULT 0,
    embedding_signature TEXT
);
INSERT INTO knowledge_state(singleton) VALUES (TRUE);
CREATE TABLE knowledge_documents (
    id UUID PRIMARY KEY,
    filename TEXT NOT NULL UNIQUE,
    content_hash TEXT NOT NULL UNIQUE,
    media_type TEXT NOT NULL,
    original BYTEA NOT NULL,
    size_bytes INTEGER NOT NULL,
    passage_count INTEGER NOT NULL,
    indexed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE knowledge_passages (
    id UUID PRIMARY KEY,
    document_id UUID NOT NULL REFERENCES knowledge_documents(id) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL,
    content TEXT NOT NULL,
    location TEXT NOT NULL,
    page INTEGER,
    embedding VECTOR NOT NULL,
    UNIQUE(document_id, ordinal)
);
CREATE INDEX knowledge_passages_document_idx ON knowledge_passages(document_id);
