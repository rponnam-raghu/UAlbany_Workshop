"""Explicit tool loop with preserved native model messages and bounded execution."""

import json
from dataclasses import dataclass
from typing import Any, Protocol

from google.genai import types

from academic_advisor.agent.gemini import ProviderError
from academic_advisor.tools.registry import Registry


class ModelClient(Protocol):
    def generate(
        self, system: str, history: list[types.Content], schemas: list[dict[str, Any]]
    ) -> types.Content: ...


@dataclass
class Turn:
    text: str
    history: list[types.Content]
    trace: list[dict[str, Any]]


def run_turn(
    client: ModelClient,
    system: str,
    history: list[types.Content],
    user_input: str,
    registry: Registry,
    max_calls: int = 24,
) -> Turn:
    messages = [*history, types.Content(role="user", parts=[types.Part(text=user_input)])]
    trace: list[dict[str, Any]] = []
    calls_used = 0
    seen: dict[str, dict[str, Any]] = {}
    for _ in range(12):
        try:
            content = client.generate(system, messages, registry.schemas())
        except ProviderError as error:
            return Turn(f"Gemini request failed: {error}", messages, trace)
        messages.append(content)  # Preserve thought signatures; never reconstruct model parts.
        calls = [part.function_call for part in content.parts or [] if part.function_call]
        if not calls:
            text = "\n".join(
                part.text for part in content.parts or [] if part.text and not part.thought
            )
            return Turn(text or "No answer returned. Please try again.", messages, trace)
        responses = []
        for call in calls:
            name, arguments = call.name or "", dict(call.args or {})
            fingerprint = json.dumps([name, arguments], sort_keys=True)
            key = f"{call.id}:{fingerprint}" if call.id else f"{len(messages)}:{fingerprint}"
            if key in seen:
                result = seen[key]
            elif calls_used >= max_calls:
                result = {
                    "status": "error",
                    "message": "Tool call budget reached. Stop and summarize.",
                }
            else:
                result = registry.dispatch(name, arguments)
                calls_used += 1
                seen[key] = result
            trace.append({"tool": name, "arguments": arguments, "result": result})
            responses.append(
                types.Part(
                    function_response=types.FunctionResponse(name=name, id=call.id, response=result)
                )
            )
        messages.append(types.Content(role="user", parts=responses))
        if calls_used >= max_calls:
            return Turn(
                "Stopped at the tool-call limit. Review the trace before continuing.",
                messages,
                trace,
            )
    return Turn(
        "Stopped after repeated tool requests. Review the trace before continuing.", messages, trace
    )
