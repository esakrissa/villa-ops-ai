"""Text extraction: turn an uploaded file into heading-aware sections.

A ``Section`` is a run of text under one heading (and, for PDFs, on one page).
Chunks never cross a section boundary, so every chunk can cite where it came from.
"""

import io
import re
from dataclasses import dataclass

SUPPORTED_TYPES = {
    "pdf": "pdf",
    "docx": "docx",
    "md": "md",
    "markdown": "md",
    "txt": "txt",
}

HEADING_SEP = " \u203a "  # " › " between heading levels

_MD_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
# PDF heuristics: "3. Cancellation Policy", "2.1 Refunds" or a short ALL-CAPS line
_PDF_NUMBERED_HEADING = re.compile(r"^\d+(\.\d+)*\.?\s+[A-Z][^.!?]{1,70}$")
_PDF_CAPS_HEADING = re.compile(r"^[A-Z0-9][A-Z0-9 &/,'()-]{3,60}$")


class ExtractionError(ValueError):
    """The file couldn't be read or has no text."""


@dataclass
class Section:
    text: str
    heading: str | None = None  # "Privacy Policy › Data we collect"
    page: int | None = None


@dataclass
class Extracted:
    sections: list[Section]
    page_count: int | None = None

    @property
    def char_count(self) -> int:
        return sum(len(s.text) for s in self.sections)


def file_type_for(filename: str) -> str | None:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return SUPPORTED_TYPES.get(ext)


def extract(data: bytes, file_type: str) -> Extracted:
    if file_type == "pdf":
        result = _extract_pdf(data)
    elif file_type == "docx":
        result = _extract_docx(data)
    elif file_type in ("md", "txt"):
        result = Extracted(sections=extract_markdown(_decode(data)))
    else:
        raise ExtractionError(f"Unsupported file type: {file_type}")

    result.sections = [s for s in result.sections if s.text.strip()]
    if not result.sections:
        raise ExtractionError("No readable text found (scanned PDFs without a text layer aren't supported).")
    return result


def _decode(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ExtractionError("Couldn't decode the text file.")


class _HeadingTrail:
    """Tracks the heading hierarchy, e.g. ["Privacy Policy", "Data we collect"]."""

    def __init__(self) -> None:
        self.levels: list[tuple[int, str]] = []

    def push(self, level: int, title: str) -> None:
        self.levels = [(lvl, t) for lvl, t in self.levels if lvl < level]
        self.levels.append((level, title))

    @property
    def path(self) -> str | None:
        return HEADING_SEP.join(t for _, t in self.levels) or None


def extract_markdown(text: str) -> list[Section]:
    sections: list[Section] = []
    trail = _HeadingTrail()
    buf: list[str] = []
    in_code = False

    def flush() -> None:
        body = "\n".join(buf).strip()
        if body:
            sections.append(Section(text=body, heading=trail.path))
        buf.clear()

    for line in text.splitlines():
        if line.strip().startswith("```"):
            in_code = not in_code
        m = None if in_code else _MD_HEADING.match(line)
        if m:
            flush()
            trail.push(len(m.group(1)), m.group(2).strip())
        else:
            buf.append(line)
    flush()
    return sections


def _extract_pdf(data: bytes) -> Extracted:
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        pages = [(page.extract_text() or "") for page in reader.pages]
    except Exception as e:  # pypdf raises many types on malformed files
        raise ExtractionError(f"Couldn't read PDF: {e}") from e

    sections: list[Section] = []
    heading: str | None = None

    def flush(buf: list[str], heading: str | None, page: int) -> None:
        body = "\n".join(buf).strip()
        if body:
            sections.append(Section(text=body, heading=heading, page=page))
        buf.clear()

    for page_no, page_text in enumerate(pages, start=1):
        buf: list[str] = []
        for raw in page_text.splitlines():
            line = raw.strip()
            if line and len(line.split()) <= 10 and (
                _PDF_NUMBERED_HEADING.match(line) or (_PDF_CAPS_HEADING.match(line) and line.upper() == line)
            ):
                flush(buf, heading, page_no)
                heading = line.title() if line.isupper() else line
            else:
                buf.append(raw)
        flush(buf, heading, page_no)
    return Extracted(sections=sections, page_count=len(pages))


def _extract_docx(data: bytes) -> Extracted:
    try:
        from docx import Document

        doc = Document(io.BytesIO(data))
    except Exception as e:
        raise ExtractionError(f"Couldn't read DOCX: {e}") from e

    sections: list[Section] = []
    trail = _HeadingTrail()
    buf: list[str] = []

    def flush() -> None:
        body = "\n\n".join(buf).strip()
        if body:
            sections.append(Section(text=body, heading=trail.path))
        buf.clear()

    for para in doc.paragraphs:
        text = para.text.strip()
        style = (para.style.name if para.style is not None else "") or ""
        if style.startswith("Heading") or style == "Title":
            if text:
                flush()
                level = int(style.split()[-1]) if style.split()[-1].isdigit() else 1
                trail.push(level, text)
        elif text:
            buf.append(text)
    flush()

    # Tables (house rules, fee schedules) — one paragraph per row
    for table in doc.tables:
        rows = [" | ".join(c.text.strip() for c in row.cells if c.text.strip()) for row in table.rows]
        body = "\n".join(r for r in rows if r)
        if body:
            sections.append(Section(text=body, heading=trail.path))
    return Extracted(sections=sections)
