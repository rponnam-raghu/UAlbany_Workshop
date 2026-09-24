"""Fresh profile and knowledge snapshots with answer-specific evidence."""

import json
import re
from dataclasses import asdict
from typing import Protocol
from uuid import UUID

from google.genai import types

from academic_advisor.agent.prompts import DEFAULT_CHAT_INSTRUCTIONS, RESOLVE, compose_system
from academic_advisor.agent.runtime import ModelClient, run_turn
from academic_advisor.domain.documents import Answer, Message, SourceReference
from academic_advisor.domain.profiles import ProfileUnavailable, StudentProfile
from academic_advisor.tools.handlers import build_registry

CITATION = re.compile(r"\[S(\d+)\]")


class Knowledge(Protocol):
    def revision(self) -> int: ...
    def search(self, query: str) -> list[SourceReference]: ...


class Profiles(Protocol):
    def get(self, profile_id: UUID) -> StudentProfile: ...


class ChatService:
    def __init__(self, knowledge: Knowledge, client: ModelClient, max_calls: int = 8, *, profiles: Profiles | None = None):
        self.knowledge, self.client, self.max_calls = knowledge, client, max_calls
        self.profiles = profiles

    def _profile(self, profile_id: UUID | None) -> StudentProfile | None:
        if profile_id is None:
            return None
        if self.profiles is None:
            raise ProfileUnavailable()
        return self.profiles.get(profile_id)

    def ask(
        self, question: str, history: list[Message], profile_id: UUID | None = None,
        *, chat_instructions: str = DEFAULT_CHAT_INSTRUCTIONS, prompt_revision: int = 0,
    ) -> Answer:
        system = compose_system(chat_instructions)
        if not question.strip():
            raise ValueError("Enter a question to start chatting.")
        if len(question) > 8000:
            raise ValueError("Please keep a message under 8,000 characters.")
        for attempt in range(2):
            revision = self.knowledge.revision()
            profile = self._profile(profile_id)
            profile_revision = profile.revision if profile else None
            # Filter by owner before truncating; never accept another student's history.
            owned = [message for message in history if message.profile_id == profile_id]
            context = [
                {"role": m.role, "text": CITATION.sub("", m.text)[:4000]}
                for m in owned[-8:]
                if m.role == "user" or (
                    m.answer and m.answer.revision == revision
                    and m.answer.profile_id == profile_id
                    and m.answer.profile_revision == profile_revision
                    and m.answer.prompt_revision == prompt_revision
                )
            ]
            query = question
            if context or profile:
                # Retrieval needs academic topic context, not the student's name or grades.
                retrieval_profile = None if profile is None else {
                    "program": profile.program, "status": profile.status,
                    "intake": str(profile.intake) if profile.intake else None,
                    "current_term": str(profile.current_term) if profile.current_term else None,
                    "completed_courses": [course.code for course in profile.completed],
                    "in_progress_courses": [course.code for course in profile.in_progress],
                    "interests_or_goals": profile.goals,
                }
                rewrite = self.client.generate(RESOLVE, [types.Content(role="user", parts=[types.Part(text=json.dumps({"conversation": context, "student_context_for_retrieval": retrieval_profile, "latest_question": question}))])], [])
                resolved = " ".join(p.text for p in rewrite.parts or [] if p.text and not p.thought).strip()[:500]
                # Preserve explicit dates/terms in the actual question as well as the rewrite.
                if resolved and resolved != question:
                    query = f"{question}\n{resolved}"
            sources = self.knowledge.search(query)
            payload = json.dumps({
                "previous_conversation_for_topic_only": context,
                "current_student_profile": profile.model_dump(mode="json") if profile else None,
                "current_retrieved_passages": [asdict(s) for s in sources],
                "student_question": question,
            }, default=str)
            turn = run_turn(self.client, system, [], payload, build_registry(), self.max_calls)
            latest = self._profile(profile_id)
            if self.knowledge.revision() != revision or (latest.revision if latest else None) != profile_revision:
                if attempt == 0:
                    continue
                return Answer("The student profile or knowledge base changed while I was answering. Please ask again so I can use the latest information.", revision=revision, profile_snapshot=profile, prompt_revision=prompt_revision)
            cited = {f"S{n}" for n in CITATION.findall(turn.text)}
            available = {s.citation for s in sources}
            trace = [{"tool": "retrieve_knowledge", "arguments": {"query": query}, "result": {"status": "ok", "revision": revision, "passages": len(sources)}}] + turn.trace
            if profile:
                trace.append({"tool": "read_student_profile", "arguments": {"profile_id": str(profile.id)}, "result": {"status": "ok", "revision": profile.revision}})
            if cited - available:
                trace.append({"tool": "validate_citations", "arguments": {}, "result": {"status": "error", "message": "Unknown citation identifiers rejected."}})
                return Answer("I couldn't verify the sources for that answer. Please rephrase your question and try again.", trace=trace, revision=revision, profile_snapshot=profile, prompt_revision=prompt_revision)
            if profile is None and sources and not cited and not turn.text.startswith(("Stopped",)):
                turn.text += "\n\n_No supporting passage was cited for this response._"
            return Answer(turn.text, [s for s in sources if s.citation in cited], trace, revision, profile, prompt_revision)
        raise AssertionError("Unreachable")
