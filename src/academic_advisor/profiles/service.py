"""Explicit profile reads and validated form saves, independent of Streamlit."""

from typing import Any, Protocol
from uuid import UUID

from pydantic import ValidationError

from academic_advisor.domain.profiles import ProfileData, StudentProfile


class ProfileRepository(Protocol):
    def list(self) -> list[StudentProfile]: ...
    def get(self, profile_id: UUID) -> StudentProfile: ...
    def update(self, profile_id: UUID, details: ProfileData, expected_revision: int) -> StudentProfile: ...


class ProfileService:
    def __init__(self, store: ProfileRepository):
        self.store = store

    def list(self) -> list[StudentProfile]:
        return self.store.list()

    def get(self, profile_id: UUID) -> StudentProfile:
        return self.store.get(profile_id)

    def save(self, profile_id: UUID, values: dict[str, Any], expected_revision: int) -> StudentProfile:
        try:
            details = ProfileData.model_validate(values)
        except ValidationError as error:
            messages = [f"{'.'.join(str(part) for part in item['loc']) or 'Profile'}: {item['msg']}" for item in error.errors(include_input=False)]
            raise ValueError("Please check the profile. " + "; ".join(messages)) from None
        return self.store.update(profile_id, details, expected_revision)
