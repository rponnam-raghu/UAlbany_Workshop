"""Load the four teaching fixtures and validate their shared academic rules."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from academic_advisor.domain.models import Course, Degree, StudentId, Transcript


def read_document(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text()
    parts = text.split("---", 2)
    if len(parts) != 3 or parts[0].strip():
        raise ValueError(f"{path.name} needs YAML front matter.")
    metadata = yaml.safe_load(parts[1])
    if not isinstance(metadata, dict):
        raise ValueError(f"{path.name} metadata must be an object.")
    return metadata, parts[2].strip()


@dataclass(frozen=True)
class Fixtures:
    degree: Degree
    catalog: dict[str, Course]
    transcripts: dict[StudentId, Transcript]
    degree_markdown: str
    catalog_markdown: str


def load_fixtures(directory: Path) -> Fixtures:
    degree_data, degree_md = read_document(directory / "degree_requirements.md")
    catalog_data, catalog_md = read_document(directory / "course_catalog.md")
    degree = Degree.model_validate(degree_data)
    courses = [Course.model_validate(c) for c in catalog_data["courses"]]
    catalog = {c.id: c for c in courses}
    if len(catalog) != len(courses):
        raise ValueError("Duplicate course IDs in catalog.")
    assigned: set[str] = set()
    for category in degree.categories:
        codes = category.required + category.elective_options
        if len(codes) != len(set(codes)) or assigned.intersection(codes):
            raise ValueError("A course must belong to exactly one requirement group.")
        assigned.update(codes)
        elective_values = {catalog[c].credits for c in category.elective_options}
        if len(elective_values) > 1 or category.elective_count > len(category.elective_options):
            raise ValueError("Electives must have equal credits and enough choices.")
        total = sum(catalog[c].credits for c in category.required)
        total += category.elective_count * next(iter(elective_values), 0)
        if total != category.credits:
            raise ValueError(f"Credit mismatch for {category.name}.")
    for course in courses:
        if not course.offered or any(c not in catalog for c in course.prerequisites):
            raise ValueError(f"Invalid catalog prerequisites or offerings: {course.id}")

    def visit(code: str, ancestors: frozenset[str]) -> None:
        if code in ancestors:
            raise ValueError("Catalog contains a prerequisite cycle.")
        for prereq in catalog[code].prerequisites:
            visit(prereq, ancestors | {code})

    for code in catalog:
        visit(code, frozenset())
    transcripts: dict[StudentId, Transcript] = {}
    for student in ("alex", "jordan"):
        transcript = Transcript.model_validate_json(
            (directory / f"transcript_{student}.json").read_text()
        )
        if transcript.student_id != student:
            raise ValueError("Transcript identifier does not match its fixture.")
        if any(c not in catalog for c in transcript.completed + transcript.in_progress):
            raise ValueError("Transcript references an unknown course.")
        transcripts[transcript.student_id] = transcript
    return Fixtures(degree, catalog, transcripts, degree_md, catalog_md)
