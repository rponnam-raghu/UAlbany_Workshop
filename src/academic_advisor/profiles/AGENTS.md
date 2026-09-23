# Fictional student profiles

- Keep typed immutable records in `domain/profiles.py`, validation and explicit saves in this service, SQL in `storage/profiles.py`, and forms in `ui/profiles.py`.
- Profile data is separate from document embeddings. The chat service receives only the selected student's current record.
- Seed fictional examples only through the migration ledger; startup must never overwrite edits or restore deleted profiles.
- Require an expected revision on every save and reject stale edits. Preserve unknown terms/grades rather than fabricating values.
- Profile changes are explicit UI actions. Do not register a model-callable profile writer or restore transcript-write tools.
- Keep intake and current term distinct. Completed course records can contain failing or unknown grades; do not turn them into unconditional eligibility or GPA calculations.
