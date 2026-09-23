"""Seed, persistence, concurrency, and upgrade checks against isolated PostgreSQL."""

from uuid import UUID, uuid4

import pytest

from academic_advisor.domain.profiles import SAM_ID, ProfileConflict, ProfileUnavailable
from academic_advisor.profiles.service import ProfileService
from academic_advisor.storage.knowledge import KnowledgeStore
from academic_advisor.storage.postgres import Database
from academic_advisor.storage.profiles import ProfileStore

pytestmark = pytest.mark.integration


def test_seeded_profiles_have_expected_academic_records(database):
    db, _ = database
    profiles = {p.name: p for p in ProfileStore(db).list()}
    assert set(profiles) == {"Avery", "Sam", "Maya"}
    assert profiles["Sam"].id == SAM_ID
    assert str(profiles["Avery"].intake) == "Spring 2027"
    assert profiles["Avery"].status == "applicant"
    assert not profiles["Avery"].completed and not profiles["Avery"].in_progress
    assert {c.code: c.grade for c in profiles["Sam"].completed} == {"CSI 201": "A", "CSI 213": "B+", "MAT 112": "B", "MAT 214": "B+"}
    assert [c.code for c in profiles["Sam"].in_progress] == ["CSI 333"]
    assert {c.code: c.grade for c in profiles["Maya"].completed} == {"CSI 201": "A", "CSI 213": "A-", "CSI 310": "B+", "CSI 333": "B", "MAT 112": "A", "MAT 214": "A-"}
    assert [c.code for c in profiles["Maya"].in_progress] == ["CSI 445"]
    assert all(str(p.current_term) == "Fall 2026" and p.revision == 1 for p in profiles.values())


def test_updates_persist_and_repeated_migrations_do_not_reset_or_reseed(database):
    db, settings = database
    service = ProfileService(ProfileStore(db))
    original = service.get(SAM_ID)
    values = original.details().model_dump()
    values["goals"] = "Edited workshop goals"
    values["completed"][0]["grade"] = "B"
    updated = service.save(SAM_ID, values, original.revision)
    assert updated.revision == 2 and updated.updated_at >= original.updated_at
    with pytest.raises(ProfileConflict):
        service.save(SAM_ID, values, original.revision)
    with db.connection(vectors=False) as connection:
        connection.execute("DELETE FROM student_profiles WHERE id = %s", (UUID("10000000-0000-4000-8000-000000000001"),))
    restarted = Database(settings)
    restarted.migrate()
    restarted.migrate()
    persisted = ProfileStore(restarted)
    assert len(persisted.list()) == 2
    assert persisted.get(SAM_ID) == updated
    with pytest.raises(ProfileUnavailable):
        persisted.get(UUID("10000000-0000-4000-8000-000000000001"))
    with pytest.raises(ProfileUnavailable):
        persisted.update(uuid4(), original.details(), 1)


@pytest.mark.parametrize("database", ["legacy"], indirect=True)
def test_upgrade_preserves_existing_knowledge(database):
    db, _ = database
    document_id = uuid4()
    with db.connection(vectors=False) as connection:
        connection.execute("INSERT INTO knowledge_documents(id, filename, content_hash, media_type, original, size_bytes, passage_count) VALUES (%s, 'existing.txt', 'original-hash', 'text/plain', %s, 8, 0)", (document_id, b"existing"))
        connection.execute("UPDATE knowledge_state SET revision = 7, embedding_signature = 'existing:model'")
    db.migrate()
    assert len(ProfileStore(db).list()) == 3
    assert KnowledgeStore(db, "existing:model").revision() == 7
    with db.connection(vectors=False) as connection:
        saved = connection.execute("SELECT original FROM knowledge_documents WHERE id = %s", (document_id,)).fetchone()
        assert bytes(saved["original"]) == b"existing"
        assert connection.execute("SELECT embedding_signature FROM knowledge_state").fetchone()["embedding_signature"] == "existing:model"
