# Date-tool exercise

- Keep the student starter in `exercises.py` separate from the working instructor implementation in `solutions.py`. Do not fill in the starter when changing the production default.
- The active application imports `solutions.days_until` through `tools/handlers.py`. Students connect their implementation by changing that documented import; there is no UI toggle for this.
- Keep `days_until` strict about `YYYY-MM-DD` input and invalid calendar dates. Use the configured implementation's America/New_York calendar date, with an injectable `today` for deterministic tests.
- Preserve the structured result contract, including status, input date, today's date, signed day count, and timezone. Same-day results are zero and past dates are negative.
- Leave selecting a supported deadline to chat and retrieval; the date tool only performs date validation and arithmetic.
- The retained `custom_tools` starter references the older fixture/transcript exercise. It is not the active registration hook; new chatbot extensions belong in `tools/handlers.py`.
- Keep the [README date-tool activity and instructor solution](../../../README.md#6-add-a-date-tool) aligned with code and registry wiring.
