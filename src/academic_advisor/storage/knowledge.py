"""Transactional storage; a replacement activates only after embeddings succeed."""
from uuid import UUID, uuid4

import numpy as np

from academic_advisor.domain.documents import Document, Passage, SourceReference, Upload
from academic_advisor.storage.postgres import Database

COLUMNS = "id, filename, content_hash, media_type, size_bytes, passage_count, indexed_at"

class KnowledgeStore:
    def __init__(self, database: Database, signature: str):
        self.database, self.signature = database, signature

    def documents(self) -> list[Document]:
        with self.database.connection() as conn:
            return [Document(**row) for row in conn.execute(f"SELECT {COLUMNS} FROM knowledge_documents ORDER BY filename")]

    def revision(self) -> int:
        with self.database.connection() as conn:
            row = conn.execute("SELECT revision FROM knowledge_state").fetchone()
            assert row is not None
            return int(row["revision"])

    def check_signature(self) -> None:
        with self.database.connection() as conn:
            row = conn.execute("SELECT embedding_signature FROM knowledge_state").fetchone()
            assert row is not None
            if row["embedding_signature"] not in (None, self.signature):
                raise ValueError("Embedding configuration changed. Restore the previous embedding settings, or remove all documents and upload them again.")

    def save(self, upload: Upload, passages: list[Passage], vectors: list[list[float]], *, replace: Document | None = None) -> bool:
        with self.database.connection() as conn:
            state = conn.execute("SELECT embedding_signature FROM knowledge_state FOR UPDATE").fetchone()
            assert state is not None
            if state["embedding_signature"] not in (None, self.signature):
                raise ValueError("Embedding configuration changed. Restore the previous settings before indexing.")
            duplicate = conn.execute("SELECT id FROM knowledge_documents WHERE content_hash = %s", (upload.content_hash,)).fetchone()
            if duplicate:
                if replace and duplicate["id"] != replace.id:
                    raise ValueError("Another document already contains this content. No replacement was made.")
                return False
            if replace:
                current = conn.execute("SELECT content_hash FROM knowledge_documents WHERE id = %s", (replace.id,)).fetchone()
                if not current or current["content_hash"] != replace.content_hash:
                    raise ValueError("This document changed while indexing. Refresh and try again.")
            collision = conn.execute("SELECT id FROM knowledge_documents WHERE filename = %s", (upload.filename,)).fetchone()
            if collision and (not replace or collision["id"] != replace.id):
                raise ValueError("A document with this name already exists. Use Replace on that document.")
            identifier = replace.id if replace else uuid4()
            if replace:
                conn.execute("DELETE FROM knowledge_documents WHERE id = %s", (identifier,))
            conn.execute("INSERT INTO knowledge_documents(id,filename,content_hash,media_type,original,size_bytes,passage_count) VALUES (%s,%s,%s,%s,%s,%s,%s)", (identifier, upload.filename, upload.content_hash, upload.media_type, upload.original, len(upload.original), len(passages)))
            for ordinal, passage in enumerate(passages):
                vector = vectors[ordinal]
                conn.execute("INSERT INTO knowledge_passages(id,document_id,ordinal,content,location,page,embedding) VALUES (%s,%s,%s,%s,%s,%s,%s)", (uuid4(), identifier, ordinal, passage.text, passage.location, passage.page, np.asarray(vector)))
            conn.execute("UPDATE knowledge_state SET revision = revision + 1, embedding_signature = %s", (self.signature,))
            return True

    def remove(self, document: Document) -> None:
        with self.database.connection() as conn:
            conn.execute("SELECT revision FROM knowledge_state FOR UPDATE")
            row = conn.execute("DELETE FROM knowledge_documents WHERE id = %s AND content_hash = %s RETURNING id", (document.id, document.content_hash)).fetchone()
            if not row:
                raise ValueError("This document changed. Refresh before removing it.")
            conn.execute("UPDATE knowledge_state SET revision = revision + 1, embedding_signature = CASE WHEN EXISTS(SELECT 1 FROM knowledge_documents) THEN embedding_signature ELSE NULL END")

    def original(self, identifier: UUID) -> bytes:
        with self.database.connection() as conn:
            row = conn.execute("SELECT original FROM knowledge_documents WHERE id = %s", (identifier,)).fetchone()
            if row is None:
                raise ValueError("This document is no longer available.")
            return bytes(row["original"])

    def search(self, vector: list[float], limit: int = 16) -> list[SourceReference]:
        # Each document's best match gets a slot before one long document dominates.
        with self.database.connection() as conn:
            rows = conn.execute("""WITH ranked AS (
                SELECT p.*, d.filename, d.content_hash, p.embedding <=> %s AS distance,
                    row_number() OVER (PARTITION BY document_id ORDER BY p.embedding <=> %s) AS rank
                FROM knowledge_passages p JOIN knowledge_documents d ON d.id = p.document_id
            ) SELECT * FROM ranked ORDER BY (rank = 1) DESC, distance, filename, ordinal LIMIT %s""", (np.asarray(vector), np.asarray(vector), limit)).fetchall()
            return [SourceReference(f"S{i}", row["document_id"], row["filename"], row["content_hash"], row["location"], row["content"], row["page"]) for i, row in enumerate(rows, 1)]
