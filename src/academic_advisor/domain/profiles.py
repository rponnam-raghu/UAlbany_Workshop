"""Validated, immutable fictional student records, separate from knowledge documents."""

import re
from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SAM_ID = UUID("10000000-0000-4000-8000-000000000002")
GRADES = ("A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D+", "D", "D-", "F", "P", "NP", "I", "W")


class ProfileModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class AcademicTerm(ProfileModel):
    season: Literal["Spring", "Summer", "Fall", "Winter"]
    year: int = Field(ge=2000, le=2100)

    def __str__(self) -> str:
        return f"{self.season} {self.year}"

    @classmethod
    def parse(cls, text: str) -> Self | None:
        if not text.strip():
            return None
        match = re.fullmatch(r"(Spring|Summer|Fall|Winter) (\d{4})", text.strip(), re.I)
        if not match:
            raise ValueError("Enter a term such as Fall 2026, or leave it blank if unknown.")
        return cls.model_validate({"season": match[1].title(), "year": int(match[2])})


class CourseRecord(ProfileModel):
    code: str = Field(min_length=3, max_length=30)
    grade: str | None = None

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        match = re.fullmatch(r"([A-Za-z]{2,8})\s*(\d{2,4}[A-Za-z]?)", value.strip())
        if not match:
            raise ValueError("Use a course code such as CSI 201.")
        return f"{match[1].upper()} {match[2].upper()}"

    @field_validator("grade", mode="before")
    @classmethod
    def normalize_grade(cls, value: object) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("A grade must be text, or blank if unknown.")
        if not value.strip():
            return None
        grade = value.strip().upper().replace("−", "-")
        if grade not in GRADES:
            raise ValueError("Use a letter grade, P, NP, I, W, or leave the grade blank.")
        return grade


class ProfileData(ProfileModel):
    name: str = Field(min_length=1, max_length=100)
    program: str = Field(min_length=1, max_length=200)
    intake: AcademicTerm | None = None
    current_term: AcademicTerm | None = None
    status: Literal["applicant", "enrolled"]
    completed: tuple[CourseRecord, ...] = Field(default_factory=tuple, max_length=200)
    in_progress: tuple[CourseRecord, ...] = Field(default_factory=tuple, max_length=50)
    goals: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def validate_courses(self) -> Self:
        codes = [record.code for record in (*self.completed, *self.in_progress)]
        if len(codes) != len(set(codes)):
            raise ValueError("List each course once, as completed or in progress.")
        if any(record.grade is not None for record in self.in_progress):
            raise ValueError("In-progress courses cannot have final grades.")
        return self


class StudentProfile(ProfileData):
    id: UUID
    revision: int = Field(ge=1)
    updated_at: datetime

    def details(self) -> ProfileData:
        return ProfileData.model_validate(self.model_dump(exclude={"id", "revision", "updated_at"}))


class ProfileUnavailable(ValueError):
    def __init__(self) -> None:
        super().__init__("The selected student profile is unavailable. Please select another student.")


class ProfileConflict(ValueError):
    def __init__(self) -> None:
        super().__init__("This profile changed while you were editing. Cancel and reopen Edit profile to use the latest record.")
