import pytest

from academic_advisor.knowledge.service import DocumentService
from academic_advisor.storage.knowledge import KnowledgeStore

pytestmark = pytest.mark.integration


class FakeEmbeddings:
    def __init__(self, dimension: int):
        self.dimension = dimension
        self.calls: list[str] = []

    def embed(self, texts, task):
        self.calls.extend(texts)
        return [[1.0] + [0.0] * (self.dimension - 1) for _ in texts]


def test_upload_search_duplicate_and_removal(database):
    database, settings = database
    embedder = FakeEmbeddings(settings.embedding_dimension)
    store = KnowledgeStore(database, f"{settings.embedding_model}:{settings.embedding_dimension}")
    service = DocumentService(store, embedder, settings)
    upload = service.preview("guide.txt", b"The fictional deadline is November 15, 2026.")
    assert "Indexed" in service.add(upload)
    first_call_count = len(embedder.calls)
    assert "Already indexed" in service.add(upload)
    assert len(embedder.calls) == first_call_count
    assert service.search("deadline")[0].filename == "guide.txt"
    document = service.documents()[0]
    service.remove(document)
    assert service.documents() == []


def test_failed_replacement_preserves_previous_document(database):
    database, settings = database

    class BrokenEmbeddings(FakeEmbeddings):
        def embed(self, texts, task):
            raise RuntimeError("embedding service unavailable")

    working = FakeEmbeddings(settings.embedding_dimension)
    store = KnowledgeStore(database, f"{settings.embedding_model}:{settings.embedding_dimension}")
    service = DocumentService(store, working, settings)
    original = service.preview("guide.txt", b"Original deadline: November 15, 2026.")
    service.add(original)
    document = service.documents()[0]
    broken = DocumentService(store, BrokenEmbeddings(settings.embedding_dimension), settings)
    replacement = broken.preview("guide.txt", b"Updated deadline: December 1, 2026.")
    with pytest.raises(RuntimeError):
        broken.add(replacement, replace=document)
    assert service.documents()[0].content_hash == original.content_hash


def test_supported_sample_formats_index_together(database):
    database, settings = database
    embedder = FakeEmbeddings(settings.embedding_dimension)
    store = KnowledgeStore(database, f"{settings.embedding_model}:{settings.embedding_dimension}")
    service = DocumentService(store, embedder, settings)
    sample_dir = settings.sample_dir
    filenames = ["intake_guide.pdf", "campus_services.txt", "advising_faq.docx", "course_catalog.md"]
    for filename in filenames:
        path = sample_dir / filename
        upload = service.preview(filename, path.read_bytes())
        service.add(upload)
    assert {document.filename for document in service.documents()} == set(filenames)
    assert all(service.search(filename) for filename in filenames)
