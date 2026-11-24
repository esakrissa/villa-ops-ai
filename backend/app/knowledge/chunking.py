"""Heading-aware chunking with overlap.

Strategy (simple, explainable, good enough for policy/handbook documents):
1. Never cross a section boundary (heading or PDF page), so citations stay exact.
2. Pack whole paragraphs up to ``target_tokens``; split oversized paragraphs by
   sentence, and oversized sentences by words.
3. Carry the last ~``overlap_tokens`` of sentences into the next chunk of the
   same section, so an answer that straddles a boundary is still retrievable.

Token counts are estimated (≈4 characters per token) — close enough for
sizing chunks, and it avoids shipping a tokenizer for a hosted embedding model.
"""

import re
from dataclasses import dataclass

from app.knowledge.extract import Section

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])")
_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n")


@dataclass
class Chunk:
    text: str
    heading: str | None
    page: int | None
    token_count: int


def estimate_tokens(text: str) -> int:
    return max(1, round(len(text) / 4))


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_SPLIT.split(text) if s.strip()]


def _split_long(unit: str, max_tokens: int) -> list[str]:
    """Split a unit that's too long on its own: by sentence, then by words."""
    if estimate_tokens(unit) <= max_tokens:
        return [unit]
    pieces: list[str] = []
    for sentence in _sentences(unit):
        if estimate_tokens(sentence) <= max_tokens:
            pieces.append(sentence)
            continue
        words, cur = sentence.split(), []
        for w in words:
            cur.append(w)
            if estimate_tokens(" ".join(cur)) >= max_tokens:
                pieces.append(" ".join(cur))
                cur = []
        if cur:
            pieces.append(" ".join(cur))
    return pieces


def _overlap_tail(text: str, overlap_tokens: int) -> str:
    """Last few whole sentences of ``text`` totalling ≤ overlap_tokens."""
    if overlap_tokens <= 0:
        return ""
    tail: list[str] = []
    for sentence in reversed(_sentences(text)):
        if estimate_tokens(" ".join([sentence, *tail])) > overlap_tokens:
            break
        tail.insert(0, sentence)
    return " ".join(tail)


def chunk_section(section: Section, target_tokens: int = 350, overlap_tokens: int = 50) -> list[Chunk]:
    paragraphs = [p.strip() for p in _PARAGRAPH_SPLIT.split(section.text) if p.strip()]
    units: list[str] = []
    for p in paragraphs:
        units.extend(_split_long(p, target_tokens))

    chunks: list[Chunk] = []
    current: list[str] = []
    carry = ""

    def emit() -> None:
        nonlocal carry
        body = "\n\n".join(current).strip()
        if not body:
            return
        text = f"{carry} {body}".strip() if carry else body
        chunks.append(Chunk(text=text, heading=section.heading, page=section.page, token_count=estimate_tokens(text)))
        carry = _overlap_tail(body, overlap_tokens)

    for unit in units:
        candidate = "\n\n".join([*current, unit])
        if current and estimate_tokens(candidate) + estimate_tokens(carry) > target_tokens:
            emit()
            current = [unit]
        else:
            current.append(unit)
    emit()
    return chunks


def chunk_sections(sections: list[Section], target_tokens: int = 350, overlap_tokens: int = 50) -> list[Chunk]:
    chunks: list[Chunk] = []
    for section in sections:
        chunks.extend(chunk_section(section, target_tokens, overlap_tokens))
    return chunks


def embedding_text(chunk_text: str, doc_name: str, heading: str | None) -> str:
    """Text actually embedded: a short header gives the chunk its context.

    A chunk saying "Guests may cancel up to 14 days before arrival" embeds much
    better as "Document: Booking Policy · Section: Cancellations\\n\\n…".
    """
    header = f"Document: {doc_name}"
    if heading:
        header += f" · Section: {heading}"
    return f"{header}\n\n{chunk_text}"
