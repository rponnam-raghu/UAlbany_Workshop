"""Session-local editing of the chat instructions, with explicit application."""

import streamlit as st

from academic_advisor.agent.prompts import (
    DEFAULT_CHAT_INSTRUCTIONS,
    FIXED_RULES,
    validate_chat_instructions,
)


def _remember_draft() -> None:
    st.session_state.chat_prompt_draft = st.session_state.chat_prompt_editor


def _set_draft(value: str) -> None:
    st.session_state.chat_prompt_draft = value
    st.session_state.chat_prompt_editor = value
    st.session_state.pop("chat_prompt_error", None)
    st.session_state.pop("chat_prompt_notice", None)


def _activate(value: str) -> None:
    if value != st.session_state.chat_prompt_active:
        st.session_state.chat_prompt_active = value
        st.session_state.chat_prompt_revision += 1
    st.session_state.chat_prompt_notice = "Instructions applied to future answers in this session."


def _apply() -> None:
    value = st.session_state.chat_prompt_draft
    try:
        validate_chat_instructions(value)
    except ValueError as error:
        st.session_state.chat_prompt_error = str(error)
        st.session_state.pop("chat_prompt_notice", None)
        return
    st.session_state.pop("chat_prompt_error", None)
    _activate(value)


def _cancel() -> None:
    _set_draft(st.session_state.chat_prompt_active)


def _restore() -> None:
    _set_draft(DEFAULT_CHAT_INSTRUCTIONS)
    _activate(DEFAULT_CHAT_INSTRUCTIONS)


def prompt_editor() -> None:
    st.session_state.setdefault("chat_prompt_active", DEFAULT_CHAT_INSTRUCTIONS)
    st.session_state.setdefault("chat_prompt_revision", 0)
    # Keep the draft outside widget state so navigation cannot discard it.
    st.session_state.setdefault("chat_prompt_draft", st.session_state.chat_prompt_active)
    st.session_state.setdefault("chat_prompt_editor", st.session_state.chat_prompt_draft)
    with st.expander("Chat instructions"):
        st.caption(
            "These instructions apply to all students and general chat in this browser session. "
            "Apply changes to use them for future answers. New sessions start with defaults; "
            "refreshing or restarting the app may end your session."
        )
        st.text_area("Chat prompt", key="chat_prompt_editor", height=300, on_change=_remember_draft)
        if st.session_state.chat_prompt_draft != st.session_state.chat_prompt_active:
            st.caption("Unsaved draft — answers still use the currently active instructions below.")
            st.code(st.session_state.chat_prompt_active, language=None, wrap_lines=True)
        else:
            st.caption("The editor shows the currently active chat instructions.")
        apply, cancel, restore = st.columns(3)
        apply.button("Apply", on_click=_apply)
        cancel.button("Cancel edits", on_click=_cancel)
        restore.button("Restore defaults", on_click=_restore)
        if error := st.session_state.get("chat_prompt_error"):
            st.error(error)
        elif notice := st.session_state.get("chat_prompt_notice"):
            st.success(notice)
        st.markdown("**Fixed application rules (read-only)**")
        st.caption("These rules always accompany the chat prompt and take precedence over edits.")
        st.code(FIXED_RULES, language=None, wrap_lines=True)
