"""Validated fictional catalog, requirement, and transcript types."""

import re
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

Semester = Literal["Spring", "Fall"]
StudentId = Literal["alex", "jordan"]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Term(Model):
    year: int = Field(ge=2000, le=2100)
    semester: Semester

    @classmethod
    def parse(cls, value: str) -> Self:
        match = re.fullmatch(r"(Spring|Fall) (\d{4})", value)
        if not match:
            raise ValueError("Use a term such as Spring 2027 or Fall 2027.")
        return cls(year=int(match[2]), semester="Spring" if match[1] == "Spring" else "Fall")

    @property
    def index(self) -> int:
        return self.year * 2 + (self.semester == "Fall")

    def next(self) -> "Term":
        if self.semester == "Spring":
            return Term(year=self.year, semester="Fall")
        return Term(year=self.year + 1, semester="Spring")

    def __str__(self) -> str:
        return f"{self.semester} {self.year}"


class Course(Model):
    id: str
    title: str
    credits: int = Field(gt=0)
    prerequisites: list[str] = Field(default_factory=list)
    offered: list[Semester] = ["Spring", "Fall"]
    minimum_credits: int = Field(default=0, ge=0)

    def passage(self) -> str:
        prereqs = ", ".join(self.prerequisites) or "None"
        return (
            f"{self.id} — {self.title}. Credits: {self.credits}. Prerequisites: {prereqs}. "
            f"Minimum completed overall credits: {self.minimum_credits}. "
            f"Offered: {', '.join(self.offered)}."
        )


class Category(Model):
    name: str
    credits: int = Field(gt=0)
    required: list[str]
    elective_options: list[str] = Field(default_factory=list)
    elective_count: int = Field(default=0, ge=0)


class Degree(Model):
    name: str
    major_credits: int
    overall_credits: int
    categories: list[Category]

    @model_validator(mode="after")
    def check_totals(self) -> Self:
        if sum(item.credits for item in self.categories) != self.major_credits:
            raise ValueError("Category credits must sum to the major total.")
        return self


class Transcript(Model):
    student_id: StudentId
    name: str
    current_term: Term
    completed: list[str]
    in_progress: list[str]
    other_completed_credits: int = Field(default=0, ge=0)
    advisor_notes: str = ""

    @model_validator(mode="after")
    def check_statuses(self) -> Self:
        if set(self.completed) & set(self.in_progress):
            raise ValueError("A course cannot be both completed and in progress.")
        return self
