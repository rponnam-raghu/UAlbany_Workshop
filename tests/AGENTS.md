# Verification

Run from the repository root after `uv sync --locked`:

```sh
PYTHONPATH=src uv run --no-sync ruff check src tests streamlit_app.py
PYTHONPATH=src uv run --no-sync mypy src
PYTHONPATH=src uv run --no-sync pytest -q
```

- Use checks appropriate to the change. Pure guidance edits need link/scope checks, not a Docker rebuild or provider calls.
- Keep unit tests deterministic with fake model/embedding adapters and injected dates. Live Gemini calls must be intentional and clearly distinguished from offline coverage.
- Database integration tests skip without `TEST_DATABASE_URL`. `integration/conftest.py` creates and drops a uniquely named test database; the configured role needs that privilege. Never substitute truncating or dropping the workshop database.
- With the development Compose stack running, the bundled database can provide integration-test connectivity:

```sh
docker compose -f compose.yaml -f compose.dev.yaml exec -T -e TEST_DATABASE_URL=postgresql://advisor:workshop@db:5432/advisor app uv run --no-sync pytest -q
```

- Prioritize observable contracts: extraction locations across formats, duplicate uploads avoiding embedding work, atomic replacement failures, removal/revision behavior, grounded follow-ups, citation identifiers, and the read-only tool allowlist.
- Verify UI workflows with AppTest or browser interaction when changing them. Importing the UI and checking upload constants is not end-to-end coverage.
- Cover profile isolation, stale form saves, startup seed persistence, Save/Cancel, unknown fields, and snapshot freshness alongside document evidence. Fake-model tests inspect payloads; live rehearsal evaluates actual wording and guidance.
- Retained academic-rule tests still depend on `data/fixtures`; do not delete those fixtures solely because the active UI no longer displays transcripts.
- Report skipped integration/live checks explicitly and do not describe a fake-provider test as proof of a live Gemini answer.
