"""The chatbot's complete allowlist: read-only tools with validated arguments."""
from pydantic import BaseModel, ConfigDict, Field

from academic_advisor.tools.registry import Registry, Tool
from academic_advisor.workshop.solutions import days_until


class DateArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")
    date_str: str = Field(description="The deadline from the retrieved document, as YYYY-MM-DD.")

def build_registry() -> Registry:
    return Registry([
        Tool(
            "days_until",
            "Calculate calendar days from today in America/New_York to a deadline. Use whenever a user asks how many days remain or how long until a date. Obtain the date from current retrieved sources or an explicit user-provided date; never guess it. Negative days mean the date has passed.",
            DateArguments,
            lambda args: days_until(args.date_str),
        ),
    ], protected=True)
