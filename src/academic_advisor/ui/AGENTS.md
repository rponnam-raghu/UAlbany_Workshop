# Streamlit presentation

- Keep three workflows: **Chat**, **Student Profile**, and **Knowledge Base**. Open to Chat with Sam selected on a new session, a compact profile summary, and prominent natural-language input.
- Keep histories separate by profile ID, including general chat. Clear pending questions and unsaved edit state when switching students; never fall back silently from an unavailable profile.
- Show profiles read-only first. Edit profile opens a prefilled form; Save validates and persists, Cancel discards changes. Retain the edit-start revision to reject stale saves.
- Accept freely typed questions and follow-ups. Keep example questions, source excerpts, and the tool trace in collapsed expanders rather than making presets the primary interaction.
- Render each historical answer with its own saved sources and trace, not the latest retrieval results. Knowledge changes must not erase the visible conversation.
- Keep parsing, embedding, SQL, chat orchestration, and date arithmetic in their services. UI code owns presentation, session state, and explicit user actions.
- Support multiple uploads, per-file extraction previews/errors, indexing progress, and a list of indexed documents. Add, replace, remove, and sample loading must be explicit actions.
- Start with an empty knowledge base. The optional sample-loading action must not run automatically during application startup or chat.
- Keep upload format choices and size limits aligned with extraction and `.streamlit/config.toml`. Explain Google Docs export to `.docx`/PDF rather than implying direct import.
- Render uploaded filenames and excerpts as data. Escape untrusted content before interpolating it into HTML.
- Use sanitized service errors. Keep implementation details under optional teaching expanders.
- Do not restore rungs, legacy Alex/Jordan transcript controls, approval actions, or a date-tool implementation toggle. The fictional student selector is a local demo control, not authentication.

For UI changes, verify real interactions through Streamlit AppTest or a browser as appropriate; the existing UI import/constant test alone does not establish workflow coverage. See [tests](../../../tests/AGENTS.md).
