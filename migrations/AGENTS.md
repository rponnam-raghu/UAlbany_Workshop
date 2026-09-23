# Database migrations

- Add schema changes as new, sequentially numbered SQL files. Do not rewrite an already applied migration: the runner records filenames in `schema_migrations`, not content checksums.
- Keep migrations compatible with the transactional runner and its advisory lock in `storage/postgres.py`. Do not add operations that require running outside a transaction without deliberately updating the runner.
- `001_documents.sql` creates the retained legacy index and vector infrastructure. `002_knowledge_base.sql` introduces active uploaded-document storage. Do not treat old fixed-fixture rows as active chat knowledge.
- `003_student_profiles.sql` creates and seeds fictional profiles once. Do not reseed through startup code or replay the migration to reset edits.
- Preserve original upload bytes, document identity, unique filename/hash constraints, passage links/order, embedding compatibility, and knowledge revision state across upgrades.
- Use foreign-key cascading behavior for linked passages and maintain the store's atomic replacement contract. Coordinate schema and SQL changes with [storage guidance](../src/academic_advisor/storage/AGENTS.md).
- Validate both a fresh database and an upgrade from the previous schema when changing migrations. Use the isolated test database described in [tests](../tests/AGENTS.md), not a destructive reset of the workshop instance.
