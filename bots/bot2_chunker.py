"""
Bot 2: Section-Aware Chunker
Responsibility:
- Normalize text
- Split text into token-bounded chunks
- STRICTLY respect section boundaries from Bot 1
NO heading detection
NO graph logic
NO references
"""

import re
import tiktoken
from typing import List, Dict, Any

from config.settings import (
    CHUNK_SIZE,
    CHUNK_OVERLAP,
    MAX_CHUNK_SIZE,
)

# --------------------------------------------------
# Encoder (singleton)
# --------------------------------------------------

_ENCODER = None

def get_encoder():
    global _ENCODER
    if _ENCODER is None:
        try:
            _ENCODER = tiktoken.get_encoding("cl100k_base")
        except Exception:
            _ENCODER = tiktoken.get_encoding("p50k_base")
    return _ENCODER


# --------------------------------------------------
# Text Normalization
# --------------------------------------------------

def normalize_text(text: str) -> str:
    """
    Normalize whitespace without altering semantics.
    """
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    lines = [line.rstrip() for line in text.splitlines()]
    return "\n".join(lines).strip()


# --------------------------------------------------
# Token Utilities
# --------------------------------------------------

def count_tokens(text: str) -> int:
    return len(get_encoder().encode(text))


def chunk_by_tokens(
    text: str,
    chunk_size: int,
    overlap: int,
) -> List[str]:
    """
    Token-based chunking with strict safety caps.
    """
    encoder = get_encoder()
    tokens = encoder.encode(text)

    if len(tokens) <= chunk_size:
        return [text]

    chunks = []
    start = 0

    while start < len(tokens):
        end = min(start + chunk_size, len(tokens))
        chunk_tokens = tokens[start:end]

        # HARD SAFETY CHECK
        if len(chunk_tokens) > MAX_CHUNK_SIZE:
            raise ValueError("Chunk exceeds MAX_CHUNK_SIZE safety limit")

        chunks.append(encoder.decode(chunk_tokens))

        if end == len(tokens):
            break

        start = max(end - overlap, start + 1)

    return chunks


# --------------------------------------------------
# Section-Aware Chunking
# --------------------------------------------------

def build_chunks_from_sections(
    full_text: str,
    sections: List[Dict[str, Any]],
    doc_id: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> List[Dict[str, Any]]:
    """
    Chunk text STRICTLY within section boundaries.
    """
    normalized = normalize_text(full_text)
    chunks: List[Dict[str, Any]] = []

    for section in sections:
        section_text = extract_text_for_section(
            normalized,
            section,
        )

        # Explicit empty-section marker
        if not section_text.strip():
            chunks.append(_make_chunk(
                text="",
                section=section,
                doc_id=doc_id,
                chunk_in_section=1,
                global_index=len(chunks),
                is_empty=True,
            ))
            continue

        section_chunks = chunk_by_tokens(
            section_text,
            chunk_size=chunk_size,
            overlap=overlap,
        )

        for idx, chunk_text in enumerate(section_chunks, start=1):
            chunks.append(_make_chunk(
                text=chunk_text,
                section=section,
                doc_id=doc_id,
                chunk_in_section=idx,
                global_index=len(chunks),
                is_empty=False,
            ))

    return chunks


def extract_text_for_section(
    full_text: str,
    section: Dict[str, Any],
) -> str:
    """
    Placeholder for true section slicing.
    For now: assumes Bot 1 already scoped text per section.
    """
    return section.get("text", "")


# --------------------------------------------------
# Chunk Object
# --------------------------------------------------

def _make_chunk(
    text: str,
    section: Dict[str, Any],
    doc_id: str,
    chunk_in_section: int,
    global_index: int,
    is_empty: bool,
) -> Dict[str, Any]:
    chunk_id = f"{doc_id}:{section['section_id']}:{chunk_in_section}"

    return {
        "chunk_id": chunk_id,
        "chunk_index": global_index,
        "doc_id": doc_id,
        "section_id": section["section_id"],
        "section_title": section.get("title"),
        "section_level": section.get("level"),
        "parent_section_id": section.get("parent_id"),
        "page_start": section.get("page_start"),
        "page_end": section.get("page_end"),
        "text": text,
        "token_count": count_tokens(text),
        "is_empty": is_empty,
    }


# --------------------------------------------------
# Fallback (No Sections)
# --------------------------------------------------

def build_chunks_without_sections(
    text: str,
    doc_id: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> List[Dict[str, Any]]:
    normalized = normalize_text(text)
    chunks = []

    chunk_texts = chunk_by_tokens(normalized, chunk_size, overlap)

    for idx, ctext in enumerate(chunk_texts, start=1):
        chunks.append({
            "chunk_id": f"{doc_id}:section_0:{idx}",
            "chunk_index": idx - 1,
            "doc_id": doc_id,
            "section_id": "section_0",
            "section_title": "Document",
            "section_level": 0,
            "parent_section_id": None,
            "page_start": 1,
            "page_end": None,
            "text": ctext,
            "token_count": count_tokens(ctext),
            "is_empty": False,
        })

    return chunks
