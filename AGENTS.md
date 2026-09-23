# Repository guidance

## Project-wide constraints

- Build the educational workshop **Intro to AI Agents and Building Chatbots with LLMs** for students with basic Python familiarity.
- The product is a fictional student helpdesk: users upload shared knowledge and ask natural-language questions. It advises; human advisors handle exceptions and approvals. Do not present its answers as official UAlbany advice.
- Keep the existing Python 3.12, uv, Streamlit, Gemini, and PostgreSQL/pgvector foundation. Docker Compose runs the application and database as two services.
- Fictional student profiles are stored in PostgreSQL and edited through the UI. Real personal transcripts, authentication, public hosting, direct Google Docs imports, legacy `.doc` files, and OCR are outside the current version.

## Working conventions

- Use `uv` and the checked-in lockfile. Keep `pyproject.toml` and `uv.lock` synchronized when changing dependencies.
- Keep secrets in environment configuration. Never copy `.env` values, API keys, or database credentials into code, documentation, logs, or test output.
- Preserve uploaded knowledge and the persistent database volume. Do not reset workshop data to simplify a change or test.
- Keep changes scoped to the request. Preserve unrelated work and distinguish current behavior from planned behavior in documentation.
- Run verification appropriate to the change and report what was actually checked. Application test commands and database-test isolation are documented in [tests/AGENTS.md](tests/AGENTS.md).

## Where guidance lives

- [Python package](src/academic_advisor/AGENTS.md): architecture and shared contracts; its subfolders contain component-specific instructions.
- [Data](data/AGENTS.md), [migrations](migrations/AGENTS.md), and [scripts](scripts/AGENTS.md): fixtures, persistence changes, and artifact generation.
- Use [README.md](README.md) as the single application and workshop guide, including setup, the sequential session, troubleshooting, and checks; keep those details there rather than duplicating them here.
