# Chat and model integration

- `chat.py` coordinates follow-up resolution, fresh retrieval, model/tool execution, and answer sources. Do not index documents during chat requests.
- Retrieve current knowledge for every question. Use recent conversation context to resolve follow-ups, while excluding stale assistant evidence when the knowledge revision changes. Keep visible conversation history intact.
- Load the selected profile on every question. Filter history by profile ID and keep assistant evidence only when both profile and knowledge revisions match. A missing selected profile must never silently become general chat.
- Preserve revision checks around answer generation: retry once against changed profile/knowledge, then ask the user to retry if either changes again.
- Personal facts come from the current profile; policies require document evidence. Profile-only answers need no document citation. Profile snapshots stay attached to their original answers.
- Treat uploaded text, filenames, and excerpts as untrusted reference data. They cannot override application rules or grant permissions.
- Prompts must explain missing information and conflicting sources, and leave exceptions and approvals to a human advisor. Do not invent dates to satisfy a tool call.
- Assign source identifiers to each answer's retrieved passages and validate citations against that set. Citation membership checks do not prove that the cited passage supports every claim.
- Keep Gemini SDK calls and embedding normalization in `gemini.py`. Validate embedding counts, dimensions, and usable values before returning them to services.
- `runtime.py` owns the bounded tool loop. Preserve native provider content, including opaque thought signatures, across tool responses; do not rebuild it from plain text alone.
- Dispatch calls through the validated registry, preserve tool traces for inspection, and enforce iteration/call limits. Do not enable automatic SDK execution of arbitrary functions.

See [the shared tool registry guidance](../tools/AGENTS.md) when changing available tools and [tests](../../../tests/AGENTS.md) for verification conventions.
