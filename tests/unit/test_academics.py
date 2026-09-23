from datetime import date

import pytest

from academic_advisor.domain.models import Term
from academic_advisor.domain.rules import check_prerequisites, credits_remaining
from academic_advisor.workshop import exercises, solutions


def test_alex_exact_credits(fixtures):
    result = credits_remaining(fixtures.transcripts["alex"], fixtures.degree, fixtures.catalog)
    assert result["major_completed"] == 15
    assert result["major_remaining"] == 30
    assert result["overall_remaining"] == 105
    assert [c["remaining"] for c in result["categories"]] == [18, 4, 5, 3]
    assert not result["credit_requirements_met"]


def test_repeats_and_extra_electives(fixtures):
    transcript = fixtures.transcripts["alex"].model_copy(deep=True)
    transcript.completed += ["CSI 201", "CSI 410", "CSI 420", "CSI 430"]
    result = credits_remaining(transcript, fixtures.degree, fixtures.catalog)
    assert result["major_completed"] == 21
    assert result["overall_completed"] == 24
    assert result["categories"][0]["elective_slots_remaining"] == 0


def test_major_does_not_establish_graduation(fixtures):
    transcript = fixtures.transcripts["alex"].model_copy(deep=True)
    transcript.completed = [
        code
        for category in fixtures.degree.categories
        for code in category.required + category.elective_options[: category.elective_count]
    ]
    transcript.in_progress = []
    result = credits_remaining(transcript, fixtures.degree, fixtures.catalog)
    assert result["major_remaining"] == 0
    assert result["overall_remaining"] == 75
    assert not result["credit_requirements_met"]
    transcript.other_completed_credits = 75
    assert credits_remaining(transcript, fixtures.degree, fixtures.catalog)[
        "credit_requirements_met"
    ]


def test_prerequisites_count_completed_only(fixtures):
    result = check_prerequisites(
        "CSI 400", fixtures.transcripts["alex"], fixtures.catalog, Term.parse("Spring 2027")
    )
    assert result["missing_completed_prerequisites"] == ["CSI 310", "CSI 333"]
    assert result["in_progress_prerequisites"] == ["CSI 310"]
    assert not result["eligible_now"]
    assert result["conditional_earliest_term"] == "Spring 2028"
    assert not result["could_be_ready_by_target_if_plan_completed"]


def test_offerings_are_separate_from_prerequisites(fixtures):
    result = check_prerequisites(
        "CSI 333", fixtures.transcripts["alex"], fixtures.catalog, Term.parse("Spring 2027")
    )
    assert result["eligible_now"]
    assert not result["offered_in_target_term"]
    assert not result["can_register_based_on_completed_record"]


def test_capstone_requires_senior_credits(fixtures):
    student = fixtures.transcripts["alex"].model_copy(deep=True)
    student.completed += ["CSI 400"]
    result = check_prerequisites("CSI 499", student, fixtures.catalog, Term.parse("Spring 2027"))
    assert result["additional_completed_credits_needed"] == 72
    assert result["conditional_earliest_term"] is None
    student.other_completed_credits = 72
    assert check_prerequisites("CSI 499", student, fixtures.catalog, Term.parse("Spring 2027"))[
        "eligible_now"
    ]


@pytest.mark.parametrize("term", ["winter 2027", "2027-Spring", "Spring 1800", "Spring 2026"])
def test_bad_or_past_terms(term, fixtures):
    with pytest.raises(ValueError):
        check_prerequisites(
            "CSI 400", fixtures.transcripts["alex"], fixtures.catalog, Term.parse(term)
        )


@pytest.mark.parametrize(
    "target,expected",
    [
        ("2024-02-28", 0),
        ("2024-02-29", 1),
        ("2024-03-01", 2),
        ("2024-02-27", -1),
    ],
)
def test_dates(target, expected):
    assert solutions.days_until(target, today=date(2024, 2, 28))["days"] == expected


@pytest.mark.parametrize("target", ["2023-02-29", "2026-13-01", "tomorrow", "20261201", "2026-1-1"])
def test_invalid_dates(target):
    with pytest.raises(ValueError):
        solutions.days_until(target)


def test_student_stub_is_honest():
    assert exercises.days_until("2026-12-01")["status"] == "not_implemented"


def test_local_today_uses_new_york():
    result = solutions.days_until("2026-12-01")
    from datetime import datetime
    from zoneinfo import ZoneInfo

    assert result["today"] == datetime.now(ZoneInfo("America/New_York")).date().isoformat()


def test_timezone_boundary(monkeypatch):
    from datetime import UTC, datetime

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 9, 21, 2, 0, tzinfo=UTC).astimezone(tz)

    monkeypatch.setattr(solutions, "datetime", Clock)
    result = solutions.days_until("2026-09-21")
    assert result["today"] == "2026-09-20"
    assert result["days"] == 1
