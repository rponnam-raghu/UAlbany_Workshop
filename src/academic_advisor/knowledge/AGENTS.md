# Document ingestion

- `extraction.py` handles bytes, format validation, source locations, and chunking. `service.py` coordinates preview, indexing, replacement, deletion, and retrieval; leave SQL to storage.
- Support text-based PDF, UTF-8 TXT, Word `.docx`, and Markdown `.md`/`.markdown`, with a 10 MB limit per upload. Validate contents as well as suffixes.
- Report unsupported, empty, encrypted, or unreadable files individually. Explain when a PDF has no extractable text; OCR is outside this version.
- Preserve PDF page numbers, Word paragraph/table locations and headings, Markdown sections, and text line references. Extract Word paragraphs and tables in document order.
- Preserve bounded extraction, including page, extracted-character, and expanded-Word limits. Keep overlapping passages bounded and within their source section so citations remain usable.
- Preview must stay local: extracting a preview must not call Gemini or write to the database.
- Check content hashes before embedding identical uploads. Changed content with an existing filename requires an explicit replacement target.
- Finish extraction and all embedding batches before saving a replacement. Validate vector count, dimensions, finite values, and normalization; a failed replacement must leave the previous document usable.
- Keep the embedding model/dimension signature consistent across all indexed documents and search queries.
- Index only through explicit add/replace operations. Search must use all current uploaded knowledge rather than hardcoded course names or the legacy catalog filter.

Verify format locations, duplicate embedding avoidance, failure handling, and replacement behavior in [tests](../../../tests/AGENTS.md).
