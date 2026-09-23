"""Session-scoped transcript copies; original fixtures are never writable here."""

import os
import re
import tempfile
from pathlib import Path

from academic_advisor.domain.models import Course, StudentId, Transcript


class TranscriptStore:
    def __init__(self, root: Path, session_id: str, original: Transcript):
        if not re.fullmatch(r"[a-f0-9]{32}", session_id):
            raise ValueError("Invalid session identifier.")
        self.original = original.model_copy(deep=True)
        self.directory = root / session_id
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / f"{original.student_id}.json"
        if not self.path.exists():
            self.reset()

    def read(self, student_id: StudentId | str) -> Transcript:
        if student_id != self.original.student_id:
            raise ValueError("Only the selected student's transcript is available.")
        return Transcript.model_validate_json(self.path.read_text())

    def _write(self, transcript: Transcript) -> None:
        fd, temporary = tempfile.mkstemp(dir=self.directory, suffix=".json")
        try:
            with os.fdopen(fd, "w") as handle:
                handle.write(transcript.model_dump_json(indent=2) + "\n")
            os.replace(temporary, self.path)
        finally:
            Path(temporary).unlink(missing_ok=True)

    def reset(self) -> None:
        self._write(self.original)

    def mark_complete(self, course: str, student_id: str, catalog: dict[str, Course]) -> bool:
        transcript = self.read(student_id)
        if course not in catalog:
            raise ValueError(f"Unknown course: {course}")
        if course in transcript.completed:
            return False
        transcript.completed.append(course)
        transcript.in_progress = [c for c in transcript.in_progress if c != course]
        self._write(transcript)
        return True
