"""Types shared by extraction, storage, retrieval, and presentation."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from academic_advisor.domain.profiles import StudentProfile


@dataclass(frozen=True)
class Section:
    text: str
    location: str
    page: int | None = None


@dataclass(frozen=True)
class Upload:
    filename: str
    original: bytes
    content_hash: str
    media_type: str
    sections: list[Section]


@dataclass(frozen=True)
class Passage:
    text: str
    location: str
    page: int | None = None


@dataclass(frozen=True)
class Document:
    id: UUID
    filename: str
    content_hash: str
    media_type: str
    size_bytes: int
    passage_count: int
    indexed_at: datetime


@dataclass(frozen=True)
class SourceReference:
    citation: str
    document_id: UUID
    filename: str
    content_hash: str
    location: str
    text: str
    page: int | None = None


@dataclass
class Answer:
    text: str
    sources: list[SourceReference] = field(default_factory=list)
    trace: list[dict[str, Any]] = field(default_factory=list)
    revision: int = 0
    profile_snapshot: StudentProfile | None = None
    prompt_revision: int = 0

    @property
    def profile_id(self) -> UUID | None:
        return self.profile_snapshot.id if self.profile_snapshot else None

    @property
    def profile_revision(self) -> int | None:
        return self.profile_snapshot.revision if self.profile_snapshot else None


@dataclass
class Message:
    role: Literal["user", "assistant"]
    text: str
    answer: Answer | None = None
    profile_id: UUID | None = None
