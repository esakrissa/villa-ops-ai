"""Unit tests for knowledge-base text extraction and chunking (no DB, no network)."""

import io

import pytest

from app.knowledge.chunking import chunk_section, chunk_sections, embedding_text, estimate_tokens
from app.knowledge.extract import ExtractionError, Section, extract, extract_markdown, file_type_for


class TestFileType:
    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("Policy.PDF", "pdf"),
            ("rules.md", "md"),
            ("notes.markdown", "md"),
            ("handbook.docx", "docx"),
            ("faq.txt", "txt"),
            ("image.png", None),
            ("no-extension", None),
        ],
    )
    def test_file_type_for(self, name: str, expected: str | None) -> None:
        assert file_type_for(name) == expected


class TestMarkdownExtraction:
    def test_heading_trail(self) -> None:
        sections = extract_markdown(
            "# Privacy Policy\nIntro text.\n\n## Data we collect\n### Booking data\nName and email.\n\n## Retention\nFive years."
        )
        assert [s.heading for s in sections] == [
            "Privacy Policy",
            "Privacy Policy \u203a Data we collect \u203a Booking data",
            "Privacy Policy \u203a Retention",
        ]
        assert sections[1].text == "Name and email."

    def test_heading_inside_code_block_is_ignored(self) -> None:
        sections = extract_markdown("# Doc\n```\n# not a heading\n```\nAfter.")
        assert len(sections) == 1
        assert "# not a heading" in sections[0].text

    def test_text_without_headings(self) -> None:
        sections = extract_markdown("Just some text.\n\nAnother paragraph.")
        assert len(sections) == 1
        assert sections[0].heading is None

    def test_extract_txt_decodes_bom(self) -> None:
        result = extract("﻿Hello policy".encode(), "txt")
        assert result.sections[0].text == "Hello policy"
        assert result.char_count == len("Hello policy")

    def test_empty_file_raises(self) -> None:
        with pytest.raises(ExtractionError):
            extract(b"   \n\n ", "md")

    def test_unsupported_type_raises(self) -> None:
        with pytest.raises(ExtractionError):
            extract(b"data", "xlsx")


class TestDocxExtraction:
    def test_headings_paragraphs_and_tables(self) -> None:
        from docx import Document

        doc = Document()
        doc.add_heading("House Rules", level=1)
        doc.add_paragraph("Be kind to staff.")
        doc.add_heading("Pool", level=2)
        doc.add_paragraph("No glass near the pool.")
        table = doc.add_table(rows=1, cols=2)
        table.rows[0].cells[0].text = "Late check-out"
        table.rows[0].cells[1].text = "50% of one night"
        buf = io.BytesIO()
        doc.save(buf)

        result = extract(buf.getvalue(), "docx")
        headings = [s.heading for s in result.sections]
        assert "House Rules" in headings
        assert "House Rules \u203a Pool" in headings
        assert any("Late check-out | 50% of one night" in s.text for s in result.sections)

    def test_corrupt_docx_raises(self) -> None:
        with pytest.raises(ExtractionError):
            extract(b"not a zip file", "docx")


class TestPdfExtraction:
    def test_corrupt_pdf_raises(self) -> None:
        with pytest.raises(ExtractionError):
            extract(b"%PDF-garbage", "pdf")


class TestChunking:
    def _long_section(self, paragraphs: int = 12) -> Section:
        para = " ".join(f"Sentence number {i} explains a villa rule in some detail." for i in range(8))
        return Section(text="\n\n".join(para for _ in range(paragraphs)), heading="Rules", page=2)

    def test_small_section_is_one_chunk(self) -> None:
        chunks = chunk_section(Section(text="Short rule.", heading="Pool", page=1))
        assert len(chunks) == 1
        assert chunks[0].heading == "Pool"
        assert chunks[0].page == 1

    def test_chunks_respect_target_size(self) -> None:
        target, overlap = 200, 40
        chunks = chunk_section(self._long_section(), target, overlap)
        assert len(chunks) > 1
        for c in chunks:
            # body ≤ target, plus at most the carried overlap
            assert c.token_count <= target + overlap + 5
            assert c.heading == "Rules"
            assert c.page == 2

    def test_overlap_carries_previous_sentences(self) -> None:
        chunks = chunk_section(self._long_section(), 200, 40)
        first_tail = chunks[0].text.rstrip().split(". ")[-1].rstrip(".")
        assert first_tail in chunks[1].text

    def test_no_overlap(self) -> None:
        chunks = chunk_section(self._long_section(), 200, 0)
        assert len(chunks) > 1
        assert all(c.token_count <= 205 for c in chunks)

    def test_giant_sentence_is_split_by_words(self) -> None:
        section = Section(text=" ".join(["word"] * 2000))
        chunks = chunk_section(section, 100, 0)
        assert len(chunks) > 5
        assert all(c.token_count <= 110 for c in chunks)

    def test_chunks_never_cross_sections(self) -> None:
        chunks = chunk_sections([Section(text="A rule.", heading="One"), Section(text="B rule.", heading="Two")])
        assert [(c.heading, c.text) for c in chunks] == [("One", "A rule."), ("Two", "B rule.")]

    def test_estimate_tokens(self) -> None:
        assert estimate_tokens("") == 1
        assert estimate_tokens("a" * 400) == 100

    def test_embedding_text_header(self) -> None:
        text = embedding_text("Refunds take 5 days.", "Booking Policy.md", "Cancellations")
        assert text.startswith("Document: Booking Policy.md · Section: Cancellations\n\n")
        assert text.endswith("Refunds take 5 days.")
        assert embedding_text("x", "Doc", None) == "Document: Doc\n\nx"
