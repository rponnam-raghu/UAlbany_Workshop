# PostgreSQL storage

- `postgres.py` owns connections and migration execution. `knowledge.py` owns document storage and `profiles.py` owns fictional student records; keep SQL out of presentation and services.
- Store profiles as validated structured JSON with revision/timestamp metadata. Save with a revision predicate and return the new snapshot; stale saves and deleted records must be distinguished.
- Use parameterized SQL and short transaction scopes. Perform provider calls and embedding work before opening the document-save transaction.
- Persist original upload bytes, document metadata/content hashes, and linked passages with embeddings. Originals are needed for document management and must survive application restarts.
- Preserve atomic replacement: recheck the target hash and filename conflicts under the existing lock, then replace metadata and passages together while retaining the document identity.
- Handle duplicate uploads and concurrent changes inside the transaction, even if the service already performed a preflight check.
- Increment the knowledge revision on effective changes. Keep passage deletion linked to document deletion and cascade deletion to every embedding index.
- Search shared `knowledge_passages` joined to `knowledge_embeddings` filtered by the active provider/model/dimension signature. Preserve document diversity when selecting results; do not revive the fixed-fixture catalog-only search.
- Keep database errors sanitized and rollback behavior intact. Do not expose connection strings through user-facing exceptions.
- `fixtures.py` and `transcripts.py` support the legacy demonstration, not the current chatbot.

Schema changes belong in [migrations](../../../migrations/AGENTS.md). Exercise transactional behavior using the isolated database setup in [tests](../../../tests/AGENTS.md).
