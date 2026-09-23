"""A tiny exact-search RAG index; no approximate index needed for 17 passages."""

import hashlib
import re
from dataclasses import dataclass
from typing import Literal, Protocol

import numpy as np

from academic_advisor.config import Settings
from academic_advisor.storage.fixtures import Fixtures
from academic_advisor.storage.postgres import Database


class Embedder(Protocol):
    def embed(
        self, texts: list[str], task: Literal["RETRIEVAL_DOCUMENT", "RETRIEVAL_QUERY"]
    ) -> list[list[float]]: ...


@dataclass(frozen=True)
class Passage:
    id: str
    source: str
    text: str

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.text.encode()).hexdigest()


def passages(fixtures: Fixtures) -> list[Passage]:
    return [
        Passage("degree", "degree_requirements.md", fixtures.degree_markdown),
        *(Passage(c.id, "course_catalog.md", c.passage()) for c in fixtures.catalog.values()),
    ]


class Index:
    def __init__(self, db: Database, embedder: Embedder, settings: Settings):
        self.db, self.embedder, self.settings = db, embedder, settings

    @property
    def signature(self) -> str:
        return f"{self.settings.embedding_model}:{self.settings.embedding_dimension}:retrieval-v1"

    def ingest(self, fixtures: Fixtures, *, reindex: bool = False) -> int:
        documents = passages(fixtures)
        with self.db.connection() as connection:
            connection.execute("SELECT pg_advisory_xact_lock(80929950)")
            config = connection.execute(
                "SELECT signature FROM embedding_configuration WHERE singleton = TRUE"
            ).fetchone()
            if config and config["signature"] != self.signature and not reindex:
                raise ValueError(
                    "Embedding configuration changed. Run advisor ingest --reindex explicitly."
                )
            if reindex:
                connection.execute("DELETE FROM document_chunks")
            hashes = {
                row["chunk_id"]: row["content_hash"]
                for row in connection.execute("SELECT chunk_id, content_hash FROM document_chunks")
            }
            changed = [doc for doc in documents if hashes.get(doc.id) != doc.digest]
            vectors = self.embedder.embed([doc.text for doc in changed], "RETRIEVAL_DOCUMENT")
            if len(vectors) != len(changed):
                raise ValueError("Embedding count does not match the documents.")
            for doc, vector in zip(changed, vectors, strict=True):
                if len(vector) != self.settings.embedding_dimension:
                    raise ValueError("Embedding dimension mismatch.")
                connection.execute(
                    """INSERT INTO document_chunks
                       (chunk_id, source, content, content_hash, embedding)
                       VALUES (%s, %s, %s, %s, %s)
                       ON CONFLICT (chunk_id) DO UPDATE SET source = EXCLUDED.source,
                       content = EXCLUDED.content, content_hash = EXCLUDED.content_hash,
                       embedding = EXCLUDED.embedding""",
                    (doc.id, doc.source, doc.text, doc.digest, np.asarray(vector)),
                )
            connection.execute(
                "DELETE FROM document_chunks WHERE NOT (chunk_id = ANY(%s))",
                ([doc.id for doc in documents],),
            )
            connection.execute(
                """INSERT INTO embedding_configuration (singleton, signature) VALUES (TRUE, %s)
                   ON CONFLICT (singleton) DO UPDATE SET signature = EXCLUDED.signature""",
                (self.signature,),
            )
        return len(changed)

    def search(self, query: str, limit: int = 5) -> list[Passage]:
        vector = self.embedder.embed([query], "RETRIEVAL_QUERY")[0]
        exact = re.findall(r"\b(?:CSI|MAT)\s+\d{3}\b", query.upper())
        with self.db.connection() as connection:
            config = connection.execute("SELECT signature FROM embedding_configuration").fetchone()
            if not config or config["signature"] != self.signature:
                raise ValueError(
                    "The document index needs ingestion with the current configuration."
                )
            rows = connection.execute(
                """SELECT chunk_id, source, content FROM document_chunks
                   WHERE source = 'course_catalog.md'
                   ORDER BY CASE WHEN chunk_id = ANY(%s) THEN 0 ELSE 1 END,
                   embedding <=> %s LIMIT %s""",
                (exact, np.asarray(vector), max(limit, len(set(exact)))),
            ).fetchall()
        return [Passage(row["chunk_id"], row["source"], row["content"]) for row in rows]
