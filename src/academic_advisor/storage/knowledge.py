"""Transactional storage; a replacement activates only after embeddings succeed."""
from uuid import UUID, uuid4

import numpy as np

from academic_advisor.domain.documents import Document, Passage, SourceReference, Upload
from academic_advisor.storage.postgres import Database

COLUMNS = "id, filename, content_hash, media_type, size_bytes, passage_count, indexed_at"

class KnowledgeStore:
    def __init__(self, database: Database, signature: str):
        self.database = database
        self.signature = signature if signature.startswith(("gemini:", "openai:")) else f"gemini:{signature}"

    def documents(self) -> list[Document]:
        with self.database.connection() as conn:
            return [Document(**row) for row in conn.execute(f"SELECT {COLUMNS} FROM knowledge_documents ORDER BY filename")]

    def revision(self) -> int:
        with self.database.connection() as conn:
            row = conn.execute("SELECT revision FROM knowledge_state").fetchone()
            assert row is not None
            return int(row["revision"])

    def missing_documents(self) -> list[Document]:
        with self.database.connection() as conn:
            rows = conn.execute(f"""SELECT {', '.join('d.' + c.strip() for c in COLUMNS.split(','))}
                FROM knowledge_documents d WHERE d.passage_count != (
                    SELECT count(*) FROM knowledge_passages p JOIN knowledge_embeddings e ON e.passage_id=p.id
                    WHERE p.document_id=d.id AND e.signature=%s)
                ORDER BY d.filename""", (self.signature,))
            return [Document(**row) for row in rows]

    def check_signature(self) -> None:
        """Compatibility hook: several embedding spaces may now coexist."""

    def require_complete(self) -> None:
        if self.missing_documents():
            raise ValueError("Index existing documents for the active provider before asking a question.")

    def passages(self, document: Document) -> list[Passage]:
        with self.database.connection() as conn:
            rows = conn.execute("""SELECT p.content, p.location, p.page FROM knowledge_passages p
                JOIN knowledge_documents d ON d.id=p.document_id
                WHERE d.id=%s AND d.content_hash=%s ORDER BY p.ordinal""", (document.id, document.content_hash))
            passages = [Passage(row["content"], row["location"], row["page"]) for row in rows]
            if len(passages) != document.passage_count:
                raise ValueError("This document changed while indexing. Refresh and retry.")
            return passages

    def index_existing(self, document: Document, vectors: list[list[float]]) -> None:
        with self.database.connection() as conn:
            conn.execute("SELECT revision FROM knowledge_state FOR UPDATE")
            current = conn.execute("SELECT content_hash FROM knowledge_documents WHERE id=%s", (document.id,)).fetchone()
            if not current or current["content_hash"] != document.content_hash:
                raise ValueError("This document changed while indexing. Refresh and retry.")
            passages = conn.execute("SELECT id FROM knowledge_passages WHERE document_id=%s ORDER BY ordinal", (document.id,)).fetchall()
            if len(passages) != len(vectors):
                raise ValueError("Incomplete embeddings. Existing indexes have been preserved.")
            changed = False
            for passage, vector in zip(passages, vectors, strict=True):
                cursor = conn.execute("""INSERT INTO knowledge_embeddings(passage_id,signature,embedding)
                    VALUES (%s,%s,%s) ON CONFLICT DO NOTHING""", (passage["id"], self.signature, np.asarray(vector)))
                changed = changed or bool(cursor.rowcount)
            if changed:
                conn.execute("UPDATE knowledge_state SET revision=revision+1")

    def save(self, upload: Upload, passages: list[Passage], vectors: list[list[float]], *, replace: Document | None = None) -> bool:
        with self.database.connection() as conn:
            conn.execute("SELECT revision FROM knowledge_state FOR UPDATE")
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
                passage_id = uuid4()
                conn.execute("INSERT INTO knowledge_passages(id,document_id,ordinal,content,location,page) VALUES (%s,%s,%s,%s,%s,%s)", (passage_id, identifier, ordinal, passage.text, passage.location, passage.page))
                conn.execute("INSERT INTO knowledge_embeddings(passage_id,signature,embedding) VALUES (%s,%s,%s)", (passage_id, self.signature, np.asarray(vector)))
            conn.execute("UPDATE knowledge_state SET revision = revision + 1")
            return True

    def remove(self, document: Document) -> None:
        with self.database.connection() as conn:
            conn.execute("SELECT revision FROM knowledge_state FOR UPDATE")
            row = conn.execute("DELETE FROM knowledge_documents WHERE id = %s AND content_hash = %s RETURNING id", (document.id, document.content_hash)).fetchone()
            if not row:
                raise ValueError("This document changed. Refresh before removing it.")
            conn.execute("UPDATE knowledge_state SET revision = revision + 1")

    def original(self, identifier: UUID) -> bytes:
        with self.database.connection() as conn:
            row = conn.execute("SELECT original FROM knowledge_documents WHERE id = %s", (identifier,)).fetchone()
            if row is None:
                raise ValueError("This document is no longer available.")
            return bytes(row["original"])

    def search(self, vector: list[float], limit: int = 16) -> list[SourceReference]:
        # Each document's best match gets a slot before one long document dominates.
        with self.database.connection() as conn:
            rows = conn.execute("""WITH active AS MATERIALIZED (
                SELECT passage_id, embedding FROM knowledge_embeddings WHERE signature=%s
            ), ranked AS (
                SELECT p.*, d.filename, d.content_hash, e.embedding <=> %s AS distance,
                    row_number() OVER (PARTITION BY document_id ORDER BY e.embedding <=> %s) AS rank
                FROM active e JOIN knowledge_passages p ON p.id=e.passage_id
                JOIN knowledge_documents d ON d.id = p.document_id
            ) SELECT * FROM ranked ORDER BY (rank = 1) DESC, distance, filename, ordinal LIMIT %s""", (self.signature, np.asarray(vector), np.asarray(vector), limit)).fetchall()
            return [SourceReference(f"S{i}", row["document_id"], row["filename"], row["content_hash"], row["location"], row["content"], row["page"]) for i, row in enumerate(rows, 1)]
