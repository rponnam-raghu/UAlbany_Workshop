"""One registry owns schema validation, read/write classification, and dispatch."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    arguments: type[BaseModel]
    handler: Callable[[Any], dict[str, Any]]
    writes: bool = False

    def schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters_json_schema": self.arguments.model_json_schema(),
        }


class Registry:
    def __init__(self, tools: list[Tool], protected: bool):
        self.tools = {tool.name: tool for tool in tools}
        if len(self.tools) != len(tools):
            raise ValueError("Tool names must be unique.")
        self.protected = protected

    def schemas(self) -> list[dict[str, Any]]:
        return [tool.schema() for tool in self.tools.values()]

    def dispatch(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        tool = self.tools.get(name)
        if tool is None:
            return {"status": "error", "message": "This tool is not available in the student helpdesk."}
        # Check before argument validation or handler execution. Model arguments cannot override it.
        if tool.writes and self.protected:
            return {
                "status": "confirmation_required",
                "message": "Transcript changes require an external registrar. No change was made.",
            }
        try:
            validated = tool.arguments.model_validate(arguments)
            return tool.handler(validated)
        except ValidationError:
            return {"status": "error", "message": "Invalid tool arguments. Follow the tool schema."}
        except ValueError as error:
            return {"status": "error", "message": str(error)}
        except OSError:
            return {
                "status": "error",
                "message": "Transcript storage is unavailable. No success confirmed.",
            }
