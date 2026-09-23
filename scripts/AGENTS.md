# Sample artifact generation

- `build_artifacts.py` generates and overwrites two files: `data/samples/intake_guide.pdf` and `data/samples/advising_faq.docx`.
- Regenerate only when intentionally changing those artifacts. Upload deduplication uses byte hashes, so regenerated files can be treated as changed content even when they look similar.
- The generator uses `python-docx` and `reportlab`. `reportlab` is not an application dependency; use an artifact-generation environment that provides it rather than adding it to the deployed app merely to run this script.
- Keep documents clearly fictional, readable, and text-extractable. Retain the Word table and meaningful PDF page content used to demonstrate source references.
- After changing generated document layout, render and inspect every output page as well as checking extracted text and source locations.
- Keep corresponding text/Markdown facts synchronized deliberately: this script does not generate all sample formats.
- Coordinate sample facts with [data guidance](../data/AGENTS.md) and the [workshop walkthrough in README.md](../README.md). Do not generate alternate-deadline artifacts. Never embed keys or personal information into generated assets.
