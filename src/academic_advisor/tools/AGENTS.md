# Tool registration and permissions

- `handlers.build_registry()` is the active tool allowlist. The current chatbot exposes only `days_until`, using the instructor solution by default.
- Tool names, descriptions, and argument schemas are the model's interface. Describe when to use each tool and the exact input format rather than relying on UI examples.
- Validate arguments before execution and reject unknown tools and extra arguments. Never turn model-provided names or arguments into executable code or arbitrary filesystem access.
- Keep the registry's write-permission guard ahead of argument execution. Its generic write support is retained infrastructure, not authorization to expose transcript writes in this chatbot.
- Use an explicit user-supplied or retrieved deadline for `days_until`; do not infer an unsupported date merely to call the tool.
- Preserve structured results and traces so students can inspect how a model-selected call contributed to an answer.
- Register student extensions through this one documented registry entry and keep them within the application's advising permissions.

The date-tool starter and solution live in [workshop](../workshop/AGENTS.md); keep the wiring instructions there and in the student exercise consistent with the actual import in `handlers.py`.
