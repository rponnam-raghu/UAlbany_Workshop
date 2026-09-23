"""Instructor reference implementation, selectable explicitly in the UI."""

import re
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo


def days_until(date_str: str, *, today: date | None = None) -> dict[str, Any]:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_str):
        raise ValueError("Use an ISO calendar date: YYYY-MM-DD.")
    try:
        deadline = date.fromisoformat(date_str)
    except ValueError:
        raise ValueError("That calendar date does not exist.") from None
    current = today if today is not None else datetime.now(ZoneInfo("America/New_York")).date()
    return {
        "status": "ok",
        "today": current.isoformat(),
        "date": deadline.isoformat(),
        "days": (deadline - current).days,
        "timezone": "America/New_York",
    }
