-- Preserve shared passages and migrate the existing Gemini embedding space.
CREATE TABLE knowledge_embeddings (
    passage_id UUID NOT NULL REFERENCES knowledge_passages(id) ON DELETE CASCADE,
    signature TEXT NOT NULL,
    embedding VECTOR NOT NULL,
    PRIMARY KEY (passage_id, signature)
);
INSERT INTO knowledge_embeddings(passage_id, signature, embedding)
SELECT p.id, 'gemini:' || s.embedding_signature, p.embedding
FROM knowledge_passages p CROSS JOIN knowledge_state s
WHERE s.embedding_signature IS NOT NULL;
ALTER TABLE knowledge_passages DROP COLUMN embedding;
CREATE INDEX knowledge_embeddings_signature_idx ON knowledge_embeddings(signature);
-- Retain the old signature as migration metadata; runtime compatibility is per embedding row.
