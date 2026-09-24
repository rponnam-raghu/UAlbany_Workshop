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


def test_provider_indexes_are_independent_and_replacement_invalidates(database):
    db, settings = database
    gemini = KnowledgeStore(db, settings.signature("gemini"))
    openai = KnowledgeStore(db, settings.signature("openai"))
    g = DocumentService(gemini, FakeEmbeddings(768), settings)
    o = DocumentService(openai, FakeEmbeddings(768), settings.for_provider("openai"))
    upload = g.preview("guide.txt", b"Original shared document.")
    g.add(upload)
    document = g.documents()[0]
    assert not gemini.missing_documents()
    assert openai.missing_documents()[0].id == document.id
    with pytest.raises(ValueError, match="Index existing"):
        o.search("guide")
    o.index_document(document)
    assert not openai.missing_documents()
    assert o.search("guide")[0].document_id == document.id
    assert g.search("guide")[0].document_id == document.id
    g.add(g.preview("guide.txt", b"Changed shared document."), replace=document)
    assert openai.missing_documents()
    with pytest.raises(ValueError, match="changed"):
        o.index_document(document)
    assert g.search("guide")[0].text == "Changed shared document."
    o.index_document(g.documents()[0])
    g.remove(g.documents()[0])
    with db.connection() as connection:
        assert connection.execute("SELECT count(*) AS n FROM knowledge_embeddings").fetchone()["n"] == 0


@pytest.mark.parametrize("database", ["legacy"], indirect=True)
def test_upgrade_preserves_original_and_gemini_vectors(database):
    from uuid import uuid4

    import numpy as np

    db, settings = database
    doc, passage = uuid4(), uuid4()
    vector = np.array([1.0] + [0.0] * 767)
    with db.connection() as conn:
        conn.execute("INSERT INTO knowledge_documents(id,filename,content_hash,media_type,original,size_bytes,passage_count) VALUES (%s,'old.txt','old-hash','text/plain',%s,3,1)", (doc, b"old"))
        conn.execute("INSERT INTO knowledge_passages(id,document_id,ordinal,content,location,embedding) VALUES (%s,%s,0,'old','Line 1',%s)", (passage, doc, vector))
        conn.execute("UPDATE knowledge_state SET revision=9, embedding_signature=%s", (f"{settings.embedding_model}:768",))
    db.migrate()
    store = KnowledgeStore(db, settings.signature("gemini"))
    assert store.original(doc) == b"old"
    assert store.revision() == 9
    assert not store.missing_documents()
    assert store.search(vector.tolist())[0].document_id == doc
    assert KnowledgeStore(db, settings.signature("openai")).missing_documents()
    db.migrate()
    assert store.documents()[0].id == doc


def test_embedding_spaces_with_different_dimensions(database):
    db, settings = database
    gstore = KnowledgeStore(db, settings.signature("gemini"))
    osettings = settings.model_copy(update={"openai_embedding_dimension": 1536}).for_provider("openai")
    ostore = KnowledgeStore(db, osettings.signature("openai"))
    g = DocumentService(gstore, FakeEmbeddings(768), settings)
    o = DocumentService(ostore, FakeEmbeddings(1536), osettings)
    g.add(g.preview("guide.txt", b"A shared guide."))
    o.index_document(g.documents()[0])
    assert g.search("guide") and o.search("guide")


def test_failed_alternate_index_preserves_working_provider(database):
    db, settings = database
    original_store = KnowledgeStore(db, settings.signature("gemini"))
    original = DocumentService(original_store, FakeEmbeddings(768), settings)
    original.add(original.preview("guide.txt", b"Original evidence."))
    document = original.documents()[0]
    revision = original.revision()

    class InvalidEmbeddings:
        def embed(self, texts, task):
            return [[float("nan")] * 768 for _ in texts]

    alternate_store = KnowledgeStore(db, settings.signature("openai"))
    alternate = DocumentService(alternate_store, InvalidEmbeddings(), settings.for_provider("openai"))
    with pytest.raises(ValueError, match="invalid embeddings"):
        alternate.index_document(document)
    assert alternate_store.missing_documents()[0].id == document.id
    assert original.revision() == revision
    assert original_store.original(document.id) == b"Original evidence."
    assert original.search("evidence")[0].text == "Original evidence."
