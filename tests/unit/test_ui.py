import json

import pytest
from google.genai import types
from streamlit.testing.v1 import AppTest

from academic_advisor.agent.prompts import (
    DEFAULT_CHAT_INSTRUCTIONS,
    FIXED_RULES,
    RESOLVE,
    compose_system,
)
from academic_advisor.domain.profiles import SAM_ID
from academic_advisor.ui import app
from academic_advisor.ui.app import SUPPORTED, chat_screen, knowledge_screen
from academic_advisor.ui.profiles import profile_screen


def test_three_screen_surface_and_upload_formats():
    assert SUPPORTED == ["pdf", "txt", "docx", "md", "markdown"]
    assert callable(chat_screen)
    assert callable(knowledge_screen)
    assert callable(profile_screen)


class EmptyKnowledge:
    def check_signature(self):
        pass

    def documents(self):
        return []

    def revision(self):
        return 0


class UIModel:
    def __init__(self):
        self.answers = []
        self.systems = []

    def generate(self, system, history, schemas):
        self.systems.append(system)
        payload = json.loads(history[-1].parts[0].text)
        if system == RESOLVE:
            text = payload["latest_question"]
        else:
            self.answers.append(payload)
            student = payload["current_student_profile"]
            text = f"Saved goals for {student['name']}: {student['goals']}" if student else "General response"
        return types.Content(role="model", parts=[types.Part(text=text)])


@pytest.fixture
def screen(monkeypatch, profile_service):
    model = UIModel()
    monkeypatch.setattr(app, "_services", lambda settings: EmptyKnowledge())
    monkeypatch.setattr(app, "_profile_service", lambda settings: profile_service)
    monkeypatch.setattr(app, "_client", lambda settings: model)
    at = AppTest.from_string("from academic_advisor.ui.app import main\nmain()\n", default_timeout=30).run()
    assert not at.exception
    return at, model


def button(at, label):
    return next(item for item in at.button if item.label == label)


def field(at, label):
    return next(item for item in at.text_input if item.label == label)


def text(at):
    return "\n".join(item.value for item in at.markdown)


def test_profile_view_save_cancel_and_validation(screen, profile_store):
    at, _ = screen
    assert at.sidebar.selectbox[0].value == str(SAM_ID)
    at.radio[0].set_value("Student Profile").run()
    assert len(at.dataframe) == 2
    button(at, "Edit profile").click().run()
    field(at, "Name").set_value("Discard this edit")
    button(at, "Cancel").click().run()
    assert profile_store.saves == 0
    assert "Discard this edit" not in text(at)
    button(at, "Edit profile").click().run()
    field(at, "Name").set_value("")
    button(at, "Save").click().run()
    assert at.error and profile_store.saves == 0
    field(at, "Name").set_value("Sam updated")
    button(at, "Save").click().run()
    assert not at.exception and at.success
    assert profile_store.get(SAM_ID).name == "Sam updated"
    assert profile_store.get(SAM_ID).revision == 2


def test_stale_edit_is_not_overwritten(screen, profile_store):
    at, _ = screen
    at.radio[0].set_value("Student Profile").run()
    button(at, "Edit profile").click().run()
    before = profile_store.get(SAM_ID)
    profile_store.records[SAM_ID] = before.model_copy(update={"name": "External update", "revision": 2})
    field(at, "Name").set_value("Stale form value")
    button(at, "Save").click().run()
    assert "changed while you were editing" in at.error[0].value
    assert profile_store.get(SAM_ID).name == "External update"


def test_switching_students_separates_history_and_pending_messages(screen, profile_store):
    at, model = screen
    at.chat_input[0].set_value("What are my goals?").run()
    assert "Saved goals for Sam" in text(at)
    assert any(expander.label == "Student profile used" for expander in at.expander)
    other = next(p.id for p in profile_store.list() if p.id != SAM_ID)
    at.session_state["pending_question"] = (str(SAM_ID), "OLD PENDING MESSAGE")
    at.sidebar.selectbox[0].set_value(str(other)).run()
    assert len(model.answers) == 1
    assert "Saved goals for Sam" not in text(at)
    at.chat_input[0].set_value("What are my goals?").run()
    assert model.answers[-1]["current_student_profile"]["name"] == "Maya"
    assert model.answers[-1]["previous_conversation_for_topic_only"] == []
    at.sidebar.selectbox[0].set_value(str(SAM_ID)).run()
    assert "Saved goals for Sam" in text(at) and "Saved goals for Maya" not in text(at)
    at.sidebar.selectbox[0].set_value("general").run()
    at.chat_input[0].set_value("Hello").run()
    assert model.answers[-1]["current_student_profile"] is None
    assert model.answers[-1]["previous_conversation_for_topic_only"] == []
    assert not at.exception


def test_switch_during_edit_discards_unsaved_form(screen, profile_store):
    at, _ = screen
    at.radio[0].set_value("Student Profile").run()
    button(at, "Edit profile").click().run()
    field(at, "Name").set_value("UNSAVED")
    other = next(p.id for p in profile_store.list() if p.id != SAM_ID)
    at.sidebar.selectbox[0].set_value(str(other)).run()
    assert not at.text_input and "UNSAVED" not in text(at)
    assert profile_store.saves == 0


def test_deleted_selection_does_not_silently_switch_students(screen, profile_store):
    at, _ = screen
    del profile_store.records[SAM_ID]
    at.run()
    assert at.sidebar.selectbox[0].value == str(SAM_ID)
    assert "unavailable" in at.error[0].value
    assert not at.chat_input


def test_saved_edit_refreshes_answers_without_rewriting_history(screen, profile_store):
    at, model = screen
    at.chat_input[0].set_value("What are my goals?").run()
    original = at.session_state["chat_histories"][str(SAM_ID)][-1].answer
    at.radio[0].set_value("Student Profile").run()
    button(at, "Edit profile").click().run()
    at.text_area[0].set_value("Machine learning")
    button(at, "Save").click().run()
    at.radio[0].set_value("Chat").run()
    assert "Saved goals for Sam: Databases" in text(at)
    at.chat_input[0].set_value("What are my goals now?").run()
    assert model.answers[-1]["current_student_profile"]["goals"] == "Machine learning"
    assert all(item["role"] == "user" for item in model.answers[-1]["previous_conversation_for_topic_only"])
    assert original.profile_snapshot.goals == "Databases"
    assert profile_store.get(SAM_ID).revision == 2


def prompt_field(at):
    return next(item for item in at.text_area if item.label == "Chat prompt")


def test_prompt_draft_apply_cancel_restore_and_history(screen):
    at, model = screen
    assert prompt_field(at).value == DEFAULT_CHAT_INSTRUCTIONS
    assert any(item.value == FIXED_RULES.strip() for item in at.code)
    at.chat_input[0].set_value("What are my goals?").run()
    original = at.session_state["chat_histories"][str(SAM_ID)][-1].answer
    custom = "Explain in three short bullets, then ask a helpful question."
    prompt_field(at).set_value(custom).run()
    assert any("Unsaved draft" in item.value for item in at.caption)
    assert any(item.value == DEFAULT_CHAT_INSTRUCTIONS.strip() for item in at.code)
    at.chat_input[0].set_value("And my courses?").run()
    assert model.systems[-1] == compose_system()
    button(at, "Cancel edits").click().run()
    assert prompt_field(at).value == DEFAULT_CHAT_INSTRUCTIONS
    prompt_field(at).set_value(custom).run()
    button(at, "Apply").click().run()
    assert at.session_state["chat_prompt_revision"] == 1
    button(at, "Apply").click().run()
    assert at.session_state["chat_prompt_revision"] == 1
    at.chat_input[0].set_value("What should I do next?").run()
    assert model.systems[-1] == compose_system(custom)
    assert all(item["role"] == "user" for item in model.answers[-1]["previous_conversation_for_topic_only"])
    assert "Saved goals for Sam" in text(at)
    assert original.prompt_revision == 0
    assert at.session_state["chat_histories"][str(SAM_ID)][-1].answer.prompt_revision == 1
    button(at, "Restore defaults").click().run()
    assert prompt_field(at).value == DEFAULT_CHAT_INSTRUCTIONS
    assert at.session_state["chat_prompt_revision"] == 2
    at.chat_input[0].set_value("My goals again?").run()
    assert model.systems[-1] == compose_system()
    assert all(item["role"] == "user" for item in model.answers[-1]["previous_conversation_for_topic_only"])
    assert not at.exception


@pytest.mark.parametrize("invalid", ["   ", "x" * 12_001])
def test_invalid_prompt_keeps_active_instructions(screen, invalid):
    at, model = screen
    prompt_field(at).set_value(invalid).run()
    button(at, "Apply").click().run()
    assert at.error
    assert at.session_state["chat_prompt_revision"] == 0
    at.chat_input[0].set_value("My goals?").run()
    assert model.systems[-1] == compose_system()
    button(at, "Cancel edits").click().run()
    assert not at.error
    assert prompt_field(at).value == DEFAULT_CHAT_INSTRUCTIONS


def test_prompt_navigation_and_new_session_isolation(screen, profile_store):
    at, model = screen
    custom = "Use brief numbered steps."
    prompt_field(at).set_value(custom).run()
    button(at, "Apply").click().run()
    prompt_field(at).set_value("Unapplied draft").run()
    at.radio[0].set_value("Student Profile").run()
    at.radio[0].set_value("Knowledge Base").run()
    at.radio[0].set_value("Chat").run()
    assert prompt_field(at).value == "Unapplied draft"
    other = next(p.id for p in profile_store.list() if p.id != SAM_ID)
    at.sidebar.selectbox[0].set_value(str(other)).run()
    assert prompt_field(at).value == "Unapplied draft"
    at.chat_input[0].set_value("My goals?").run()
    assert model.systems[-1] == compose_system(custom)
    at.sidebar.selectbox[0].set_value("general").run()
    at.chat_input[0].set_value("Hello").run()
    assert model.systems[-1] == compose_system(custom)
    fresh = AppTest.from_string("from academic_advisor.ui.app import main\nmain()\n", default_timeout=30).run()
    assert prompt_field(fresh).value == DEFAULT_CHAT_INSTRUCTIONS
    assert fresh.session_state["chat_prompt_revision"] == 0
    assert at.session_state["chat_prompt_active"] == custom
    assert not at.exception and not fresh.exception
