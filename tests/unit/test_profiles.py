import pytest
from pydantic import ValidationError

from academic_advisor.domain.profiles import SAM_ID, AcademicTerm, CourseRecord, ProfileData


def test_normalizes_course_and_grade():
    assert CourseRecord(code=" csi213 ", grade="A−").model_dump() == {"code": "CSI 213", "grade": "A-"}
    assert CourseRecord(code="CSI 213", grade="").grade is None
    assert AcademicTerm.parse("fall 2026").year == 2026
    assert AcademicTerm.parse("") is None


@pytest.mark.parametrize("value", ["2026 Fall", "Fall 2200"])
def test_invalid_terms(value):
    with pytest.raises(ValueError):
        AcademicTerm.parse(value)


@pytest.mark.parametrize("grade", ["Z", "3.7", 5])
def test_invalid_grades(grade):
    with pytest.raises(ValidationError):
        CourseRecord(code="CSI 213", grade=grade)


def test_missing_optional_information_remains_unknown():
    profile = ProfileData(name="Avery", program="CS", status="applicant")
    assert profile.intake is None and profile.current_term is None
    assert profile.completed == profile.in_progress == ()


@pytest.mark.parametrize("changes", [
    {"name": " "},
    {"status": "registrar"},
    {"completed": [{"code": "CSI 213", "grade": "B"}, {"code": "csi213", "grade": "A"}]},
    {"completed": [{"code": "CSI 333"}], "in_progress": [{"code": "CSI 333"}]},
    {"in_progress": [{"code": "CSI 333", "grade": "A"}]},
])
def test_invalid_form_never_writes(profile_service, profile_store, changes):
    values = profile_service.get(SAM_ID).details().model_dump()
    values.update(changes)
    with pytest.raises(ValueError):
        profile_service.save(SAM_ID, values, 1)
    assert profile_store.saves == 0


def test_successful_save_preserves_old_snapshot_and_rejects_stale_save(profile_service):
    before = profile_service.get(SAM_ID)
    values = before.details().model_dump()
    values["goals"] = "AI and machine learning"
    saved = profile_service.save(SAM_ID, values, before.revision)
    assert saved.revision == 2 and saved.goals == values["goals"]
    assert before.goals == "Databases"
    with pytest.raises(ValueError, match="changed while you were editing"):
        profile_service.save(SAM_ID, values, before.revision)
