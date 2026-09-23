"""Edit this module during the workshop; it is mounted by compose.dev.yaml."""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from academic_advisor.storage.fixtures import Fixtures
    from academic_advisor.storage.transcripts import TranscriptStore
    from academic_advisor.tools.registry import Tool


def days_until(date_str: str) -> dict[str, Any]:
    """Exercise: validate YYYY-MM-DD and compute signed days in America/New_York."""
    # Return status, today, date, days, and timezone. See README.md, section 6.
    return {
        "status": "not_implemented",
        "message": "Student exercise: implement days_until; do not invent a date or day count.",
    }


def custom_tools(fixtures: "Fixtures", store: "TranscriptStore") -> list["Tool"]:
    """End challenge: return a Tool with typed arguments and an explicit writes flag."""
    return []
