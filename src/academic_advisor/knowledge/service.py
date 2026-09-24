"""Single owner of preview, indexing, deduplication, and document lifecycle."""
from collections.abc import Callable
from typing import Literal, Protocol

import numpy as np

from academic_advisor.config import Settings
from academic_advisor.domain.documents import Document, Passage, SourceReference, Upload
from academic_advisor.knowledge.extraction import chunk, extract
from academic_advisor.storage.knowledge import KnowledgeStore


class Embedder(Protocol):
    def embed(self, texts: list[str], task: Literal["RETRIEVAL_DOCUMENT", "RETRIEVAL_QUERY"]) -> list[list[float]]: ...

class DocumentService:
    def __init__(self, store: KnowledgeStore, embedder: Embedder, settings: Settings):
        self.store, self.embedder, self.settings = store, embedder, settings

    @staticmethod
    def preview(filename: str, content: bytes) -> Upload:
        return extract(filename, content)

    def documents(self) -> list[Document]:
        return self.store.documents()

    def revision(self) -> int:
        return self.store.revision()

    def add(self, upload: Upload, *, replace: Document | None = None, progress: Callable[[float], None] | None = None) -> str:
        self.store.check_signature()
        current = self.documents()
        duplicate = next((d for d in current if d.content_hash == upload.content_hash), None)
        if duplicate:
            if replace and duplicate.id != replace.id:
                raise ValueError("Another document already contains this content. No replacement was made.")
            if any(d.id == duplicate.id for d in self.store.missing_documents()):
                self.index_document(duplicate, progress=progress)
                return "Indexed existing document for this provider."
            return "Already indexed; no embedding work needed."
        if any(d.filename == upload.filename and (not replace or d.id != replace.id) for d in current):
            raise ValueError("This filename exists with different content. Use Replace on that document.")
        passages = chunk(upload.sections)
        vectors = self._embed(upload.filename, passages, progress)
        saved = self.store.save(upload, passages, vectors, replace=replace)
        if not saved:
            # A concurrent upload may have saved the same document in another space.
            for document in self.store.missing_documents():
                if document.content_hash == upload.content_hash:
                    self.index_document(document, progress=progress)
                    return "Indexed existing document for this provider."
        return f"Indexed {len(passages)} passages." if saved else "Already indexed; no change needed."

    def _embed(self, filename: str, passages: list[Passage], progress: Callable[[float], None] | None = None) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(passages), 32):
            batch = passages[start:start + 32]
            embedded = self.embedder.embed([f"{filename}\n{p.location}\n{p.text}" for p in batch], "RETRIEVAL_DOCUMENT")
            if len(embedded) != len(batch) or any(len(v) != self.settings.embedding_dimension or not np.isfinite(v).all() or not np.linalg.norm(v) for v in embedded):
                raise ValueError("Incomplete or invalid embeddings. The previous document has been preserved.")
            vectors.extend(embedded)
            if progress:
                progress(len(vectors) / len(passages))
        return vectors

    def index_document(self, document: Document, *, progress: Callable[[float], None] | None = None) -> None:
        if not any(d.id == document.id for d in self.store.missing_documents()):
            # Still reject a stale caller snapshot, even when an index already exists.
            self.store.passages(document)
            return
        passages = self.store.passages(document)
        vectors = self._embed(document.filename, passages, progress)
        self.store.index_existing(document, vectors)

    def remove(self, document: Document) -> None:
        self.store.remove(document)

    def search(self, query: str) -> list[SourceReference]:
        self.store.check_signature()
        if not self.documents():
            return []
        self.store.require_complete()
        return self.store.search(self.embedder.embed([query], "RETRIEVAL_QUERY")[0])
