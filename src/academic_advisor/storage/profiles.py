"""PostgreSQL profile storage with optimistic concurrency; no embeddings or LLM writes."""

from typing import Any
from uuid import UUID

from psycopg.types.json import Jsonb

from academic_advisor.domain.profiles import (
    ProfileConflict,
    ProfileData,
    ProfileUnavailable,
    StudentProfile,
)
from academic_advisor.storage.postgres import Database


def _profile(row: dict[str, Any]) -> StudentProfile:
    return StudentProfile.model_validate({**row["details"], "id": row["id"], "revision": row["revision"], "updated_at": row["updated_at"]})


class ProfileStore:
    def __init__(self, database: Database):
        self.database = database

    def list(self) -> list[StudentProfile]:
        with self.database.connection(vectors=False) as connection:
            return [_profile(row) for row in connection.execute("SELECT * FROM student_profiles ORDER BY details->>'name', id")]

    def get(self, profile_id: UUID) -> StudentProfile:
        with self.database.connection(vectors=False) as connection:
            row = connection.execute("SELECT * FROM student_profiles WHERE id = %s", (profile_id,)).fetchone()
        if row is None:
            raise ProfileUnavailable()
        return _profile(row)

    def update(self, profile_id: UUID, details: ProfileData, expected_revision: int) -> StudentProfile:
        with self.database.connection(vectors=False) as connection:
            row = connection.execute(
                """UPDATE student_profiles SET details = %s, revision = revision + 1,
                   updated_at = clock_timestamp() WHERE id = %s AND revision = %s RETURNING *""",
                (Jsonb(details.model_dump(mode="json")), profile_id, expected_revision),
            ).fetchone()
            if row is None:
                exists = connection.execute("SELECT 1 FROM student_profiles WHERE id = %s", (profile_id,)).fetchone()
                if exists is None:
                    raise ProfileUnavailable()
                raise ProfileConflict()
            return _profile(row)
