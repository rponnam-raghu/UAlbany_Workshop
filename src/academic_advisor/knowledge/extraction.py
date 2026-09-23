"""Local, bounded extraction. Uploads are data, never executable instructions."""

import hashlib
import re
from io import BytesIO
from pathlib import PurePosixPath
from zipfile import BadZipFile, ZipFile

from docx import Document as WordDocument
from docx.table import Table
from pypdf import PdfReader

from academic_advisor.domain.documents import Passage, Section, Upload

MAX_BYTES = 10 * 1024 * 1024
MAX_TEXT = 1_000_000
MEDIA = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
}


class UploadError(ValueError):
    """An individual file could not be extracted or indexed."""


def text_sections(text: str, *, markdown: bool) -> list[Section]:
    sections: list[Section] = []
    lines = text.splitlines()
    start, heading = 1, ""
    block: list[str] = []
    for number, line in enumerate(lines, 1):
        if markdown and re.match(r"^#{1,6}\s+", line):
            if block:
                sections.append(Section("\n".join(block), heading or f"Lines {start}–{number - 1}"))
            heading, start, block = line.lstrip("# ").strip(), number, []
        block.append(line)
    if block:
        sections.append(Section("\n".join(block), heading or f"Lines {start}–{len(lines)}"))
    return sections


def extract(filename: str, original: bytes) -> Upload:
    name = PurePosixPath(filename.replace("\\", "/")).name.strip()
    suffix = PurePosixPath(name).suffix.lower()
    if not name or len(name) > 200 or any(ord(c) < 32 for c in name):
        raise UploadError("Use a filename of 1–200 characters without control characters.")
    if suffix not in MEDIA:
        raise UploadError("Unsupported file. Upload PDF, TXT, Word .docx, or Markdown (.md/.markdown).")
    if not original:
        raise UploadError("This file is empty.")
    if len(original) > MAX_BYTES:
        raise UploadError("This file exceeds the 10 MB limit.")
    try:
        if suffix == ".pdf":
            if not original.startswith(b"%PDF-"):
                raise UploadError("The file contents are not a PDF.")
            reader = PdfReader(BytesIO(original))
            if reader.is_encrypted:
                raise UploadError("Encrypted PDFs are not supported. Upload an unencrypted copy.")
            if len(reader.pages) > 300:
                raise UploadError("This PDF exceeds the 300-page workshop limit.")
            sections = []
            total = 0
            for number, page in enumerate(reader.pages, 1):
                content = page.extract_text() or ""
                total += len(content)
                if total > MAX_TEXT:
                    raise UploadError("Extracted text exceeds the one-million-character workshop limit.")
                sections.append(Section(content, f"Page {number}", number))
            if not any(s.text.strip() for s in sections):
                raise UploadError("No extractable text in this PDF. Scanned PDFs need OCR, which this version does not include.")
        elif suffix == ".docx":
            with ZipFile(BytesIO(original)) as archive:
                if "word/document.xml" not in archive.namelist():
                    raise UploadError("The file contents are not a Word .docx document.")
                if sum(i.file_size for i in archive.infolist()) > 50 * 1024 * 1024:
                    raise UploadError("The expanded Word document exceeds the 50 MB workshop limit.")
            document = WordDocument(BytesIO(original))
            sections = []
            heading, paragraph_number, table_number = "Document", 0, 0
            for element in document.iter_inner_content():
                if isinstance(element, Table):
                    table_number += 1
                    rows = [" | ".join(c.text.strip() for c in row.cells) for row in element.rows]
                    sections.append(Section("\n".join(rows), f"{heading} · Table {table_number}"))
                else:
                    paragraph_number += 1
                    if element.style and element.style.name and element.style.name.startswith(("Heading", "Title")):
                        heading = element.text.strip() or heading
                    sections.append(Section(element.text, f"{heading} · Paragraph {paragraph_number}"))
        else:
            text = original.decode("utf-8-sig")
            if any(ord(c) < 32 and c not in "\n\r\t" for c in text):
                raise UploadError("This file contains binary data. TXT and Markdown must be UTF-8 text.")
            sections = text_sections(text, markdown=suffix in (".md", ".markdown"))
    except UploadError:
        raise
    except (UnicodeDecodeError, BadZipFile):
        raise UploadError("Unreadable file. Check the file format; TXT and Markdown must use UTF-8.") from None
    except Exception:
        raise UploadError("Unable to read this file. It may be damaged, encrypted, or in a different format.") from None
    cleaned = [Section(s.text.replace("\x00", "").strip(), s.location, s.page) for s in sections if s.text.strip()]
    if not cleaned:
        raise UploadError("This document has no extractable text.")
    if sum(len(s.text) for s in cleaned) > MAX_TEXT:
        raise UploadError("Extracted text exceeds the one-million-character workshop limit.")
    return Upload(name, original, hashlib.sha256(original).hexdigest(), MEDIA[suffix], cleaned)


def chunk(sections: list[Section], size: int = 1600, overlap: int = 200) -> list[Passage]:
    """Bounded passages never cross a source location (including PDF pages)."""
    if not 0 <= overlap < size:
        raise ValueError("Overlap must be smaller than the passage size.")
    result = []
    for section in sections:
        start = 0
        while start < len(section.text):
            end = min(start + size, len(section.text))
            if end < len(section.text):
                boundary = section.text.rfind(" ", start + size // 2, end)
                if boundary != -1:
                    end = boundary
            text = section.text[start:end].strip()
            if text:
                result.append(Passage(text, section.location, section.page))
            if end == len(section.text):
                break
            start = max(start + 1, end - overlap)
    return result
