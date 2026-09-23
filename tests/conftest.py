from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from academic_advisor.domain.profiles import (
    SAM_ID,
    ProfileConflict,
    ProfileUnavailable,
    StudentProfile,
)
from academic_advisor.profiles.service import ProfileService
from academic_advisor.storage.fixtures import load_fixtures
from academic_advisor.storage.transcripts import TranscriptStore


@pytest.fixture
def fixtures():
    return load_fixtures(Path(__file__).resolve().parents[1] / "data/fixtures")


@pytest.fixture
def store(tmp_path, fixtures):
    return TranscriptStore(tmp_path, uuid4().hex, fixtures.transcripts["alex"])


class MemoryProfiles:
    def __init__(self, records):
        self.records = {profile.id: profile for profile in records}
        self.reads = []
        self.saves = 0

    def list(self):
        return list(self.records.values())

    def get(self, profile_id):
        self.reads.append(profile_id)
        if profile_id not in self.records:
            raise ProfileUnavailable()
        return self.records[profile_id].model_copy(deep=True)

    def update(self, profile_id, details, expected_revision):
        original = self.get(profile_id)
        if original.revision != expected_revision:
            raise ProfileConflict()
        updated = StudentProfile(**details.model_dump(), id=profile_id, revision=original.revision + 1, updated_at=datetime.now(UTC))
        self.records[profile_id] = updated
        self.saves += 1
        return updated


@pytest.fixture
def profile_store():
    common = {"program": "B.S. in Computer Science", "status": "enrolled", "current_term": {"season": "Fall", "year": 2026}, "revision": 1, "updated_at": datetime(2026, 9, 23, tzinfo=UTC)}
    sam = StudentProfile(**common, id=SAM_ID, name="Sam", intake={"season": "Fall", "year": 2025}, completed=[{"code": "CSI 213", "grade": "B+"}], in_progress=[{"code": "CSI 333"}], goals="Databases")
    maya = StudentProfile(**common, id=UUID("10000000-0000-4000-8000-000000000003"), name="Maya", intake={"season": "Fall", "year": 2024}, completed=[{"code": "CSI 310", "grade": "B+"}, {"code": "CSI 333", "grade": "B"}], goals="Software engineering")
    return MemoryProfiles([sam, maya])


@pytest.fixture
def profile_service(profile_store):
    return ProfileService(profile_store)
