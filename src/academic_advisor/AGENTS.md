# Python package

## Responsibilities

- Keep the UI and CLI as entry points that assemble services. Document ingestion belongs in `knowledge`, conversation coordination in `agent`, and SQL in `storage`.
- Put shared document and answer contracts in `domain/documents.py` and fictional profile contracts in `domain/profiles.py`. Keep domain models independent of Streamlit and provider SDKs.
- Centralize environment configuration in `config.py`. Preserve secret-aware types and the embedding model/dimension configuration shared by ingestion and retrieval.
- Keep provider exceptions sanitized at service boundaries so presentation code can show useful errors without exposing credentials or raw provider responses.
- The current CLI commands are `init-db`, `list-documents`, `load-samples`, and `smoke`. Keep CLI help and documentation consistent with `cli.py`; a retrieval smoke check alone does not verify a live chat conversation.

## Current and legacy paths

- The active application uses `ChatService`, `DocumentService`, and `KnowledgeStore` for uploaded knowledge, and `ProfileService`/`ProfileStore` for selected fictional students. It must not depend on the legacy fixed catalog or Alex/Jordan transcript storage.
- `domain/models.py`, `domain/rules.py`, `storage/fixtures.py`, `storage/transcripts.py`, and `retrieval/index.py` retain the earlier course/transcript demonstration. Some tests still exercise them.
- Do not reconnect legacy transcript writes or the old fixed-fixture index to the active chatbot. Do not remove legacy modules as an incidental cleanup without checking their callers and tests.

## Component guidance

- [Agent and chat](agent/AGENTS.md)
- [Document ingestion](knowledge/AGENTS.md)
- [Student profile service](profiles/AGENTS.md)
- [Database storage](storage/AGENTS.md)
- [Tool registration](tools/AGENTS.md)
- [Streamlit UI](ui/AGENTS.md)
- [Student exercises and solutions](workshop/AGENTS.md)
