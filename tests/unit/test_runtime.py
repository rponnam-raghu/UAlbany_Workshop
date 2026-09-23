from datetime import date

from academic_advisor.workshop.solutions import days_until


def test_date_tool_is_deterministic_when_today_is_supplied():
    result = days_until("2026-12-01", today=date(2026, 11, 15))
    assert result == {
        "status": "ok",
        "today": "2026-11-15",
        "date": "2026-12-01",
        "days": 16,
        "timezone": "America/New_York",
    }
