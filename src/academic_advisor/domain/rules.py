"""Deterministic degree audits and prerequisite timing."""

from typing import Any

from academic_advisor.domain.models import Course, Degree, Term, Transcript


def overall_credits(transcript: Transcript, catalog: dict[str, Course]) -> int:
    return (
        sum(catalog[c].credits for c in set(transcript.completed))
        + transcript.other_completed_credits
    )


def credits_remaining(
    transcript: Transcript, degree: Degree, catalog: dict[str, Course]
) -> dict[str, Any]:
    completed = set(transcript.completed)
    categories: list[dict[str, Any]] = []
    for category in degree.categories:
        electives = sorted(completed & set(category.elective_options))[: category.elective_count]
        counted = (completed & set(category.required)) | set(electives)
        earned = sum(catalog[c].credits for c in counted)
        categories.append(
            {
                "category": category.name,
                "required": category.credits,
                "completed": earned,
                "remaining": max(0, category.credits - earned),
                "missing_courses": [c for c in category.required if c not in completed],
                "elective_slots_remaining": max(0, category.elective_count - len(electives)),
                "elective_options": category.elective_options,
            }
        )
    major_earned = sum(c["completed"] for c in categories)
    overall = overall_credits(transcript, catalog)
    major_complete = major_earned == degree.major_credits
    return {
        "student_id": transcript.student_id,
        "categories": categories,
        "major_required": degree.major_credits,
        "major_completed": major_earned,
        "major_remaining": degree.major_credits - major_earned,
        "overall_completed": overall,
        "overall_required": degree.overall_credits,
        "overall_remaining": max(0, degree.overall_credits - overall),
        "in_progress_excluded": transcript.in_progress,
        "credit_requirements_met": major_complete and overall >= degree.overall_credits,
        "approval": "Advisory calculation only; the registrar determines graduation eligibility.",
        "source": "degree_requirements.md + course_catalog.md + selected transcript",
    }


def earliest_term(
    course_id: str,
    transcript: Transcript,
    catalog: dict[str, Course],
    visiting: frozenset[str] = frozenset(),
) -> Term | None:
    """Unlimited course load, no summer, no assumed future credit threshold accrual."""
    if course_id in visiting:
        raise ValueError("Catalog prerequisite cycle detected.")
    course = catalog[course_id]
    if overall_credits(transcript, catalog) < course.minimum_credits:
        return None
    earliest = transcript.current_term.next()
    for prerequisite in course.prerequisites:
        if prerequisite in transcript.completed or prerequisite in transcript.in_progress:
            continue
        prerequisite_term = earliest_term(prerequisite, transcript, catalog, visiting | {course_id})
        if prerequisite_term is None:
            return None
        after_completion = prerequisite_term.next()
        if after_completion.index > earliest.index:
            earliest = after_completion
    for _ in range(4):
        if earliest.semester in course.offered:
            return earliest
        earliest = earliest.next()
    return None


def check_prerequisites(
    course_id: str,
    transcript: Transcript,
    catalog: dict[str, Course],
    target_term: Term,
) -> dict[str, Any]:
    if course_id not in catalog:
        raise ValueError(f"Unknown course: {course_id}")
    if target_term.index <= transcript.current_term.index:
        raise ValueError("Select a term after the transcript's current term.")
    course = catalog[course_id]
    missing = [c for c in course.prerequisites if c not in transcript.completed]
    in_progress = [c for c in missing if c in transcript.in_progress]
    credits_short = max(0, course.minimum_credits - overall_credits(transcript, catalog))
    earliest = earliest_term(course_id, transcript, catalog)
    return {
        "course": course_id,
        "target_term": str(target_term),
        "eligible_now": not missing and not credits_short,
        "offered_in_target_term": target_term.semester in course.offered,
        "can_register_based_on_completed_record": (
            not missing and not credits_short and target_term.semester in course.offered
        ),
        "missing_completed_prerequisites": missing,
        "in_progress_prerequisites": in_progress,
        "additional_completed_credits_needed": credits_short,
        "offered": course.offered,
        "conditional_earliest_term": str(earliest) if earliest else None,
        "could_be_ready_by_target_if_plan_completed": (
            earliest is not None
            and earliest.index <= target_term.index
            and target_term.semester in course.offered
        ),
        "planning_assumptions": (
            "Pass all in-progress courses at the end of the current term; take missing "
            "prerequisites in their next available terms; no course-load or timetable limits. "
            "Future credits for senior standing are not assumed."
        ),
        "source": f"course_catalog.md#{course_id} + selected transcript",
    }
