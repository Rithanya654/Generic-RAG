"""
Bot 1: Document Parser using Docling
Extracts text + structural layout (sections, tables) deterministically.
NO graph writes. NO LLMs.
"""

from pathlib import Path
from pypdf import PdfReader, PdfWriter
import tempfile
import os
import json
from typing import List, Dict, Any

from docling.document_converter import DocumentConverter

# --------------------------------------------------
# Init
# --------------------------------------------------

converter = DocumentConverter()

REAL_SECTION_THRESHOLD = 3  # do NOT destroy real structure below this


# --------------------------------------------------
# Public API
# --------------------------------------------------

def parse_document_with_structure(file_path: str, max_pages: int = None) -> dict:
    """
    Parse a document and extract:
    - markdown text
    - section hierarchy with page boundaries
    - table metadata with section grounding
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    if file_path.suffix.lower() == ".json":
        return parse_json_document_with_structure(str(file_path))

    result = converter.convert(str(file_path))

    text_content = result.document.export_to_markdown()
    sections = extract_sections_from_docling(result.document)
    tables = extract_tables_from_docling(result.document)

    # ---- FALLBACK ONLY IF NO REAL HEADINGS ----
    has_real_headings = any(not s.get("synthetic") for s in sections)

    if not has_real_headings and hasattr(result.document, "pages"):
        sections = build_synthetic_sections(result.document)

    # ---- ASSIGN TABLE → SECTION ----
    assign_tables_to_sections(tables, sections)

    return {
        "text": text_content,
        "sections": sections,
        "tables": tables,
    }


# --------------------------------------------------
# Section Extraction
# --------------------------------------------------

def extract_sections_from_docling(document) -> List[Dict[str, Any]]:
    """
    Extract H1 / H2 headings with page boundaries.
    Conservative: NEVER destroys real headings.
    """
    sections = []

    if hasattr(document, "pages"):
        for page_idx, page in enumerate(document.pages):
            if hasattr(page, "body") and hasattr(page.body, "elements"):
                for el in page.body.elements:
                    if getattr(el, "label", None) in ("heading1", "heading2"):
                        level = 1 if el.label == "heading1" else 2
                        title = el.text.strip() if getattr(el, "text", None) else "Untitled"

                        sections.append(
                            {
                                "section_id": f"section_{len(sections) + 1}",
                                "title": title,
                                "level": level,
                                "page_start": page_idx + 1,
                                "page_end": page_idx + 1,
                                "synthetic": False,
                                "source": "docling_heading",
                            }
                        )

    # ---- SET PARENTS + PAGE RANGES ----
    for i, sec in enumerate(sections):
        if sec["level"] == 2:
            for j in range(i - 1, -1, -1):
                if sections[j]["level"] == 1:
                    sec["parent_id"] = sections[j]["section_id"]
                    break

        if i < len(sections) - 1:
            sec["page_end"] = sections[i + 1]["page_start"] - 1

    return sections


# --------------------------------------------------
# Synthetic Sections (Fallback ONLY)
# --------------------------------------------------

def build_synthetic_sections(document) -> List[Dict[str, Any]]:
    """
    Page-based fallback when NO real structure exists.
    """
    total_pages = len(document.pages) if hasattr(document, "pages") else 1
    pages_per_section = max(2, total_pages // 6)

    sections = []
    for start in range(1, total_pages + 1, pages_per_section):
        end = min(start + pages_per_section - 1, total_pages)

        sections.append(
            {
                "section_id": f"section_{len(sections) + 1}",
                "title": f"Pages {start}-{end}",
                "level": 1,
                "page_start": start,
                "page_end": end,
                "synthetic": True,
                "source": "page_fallback",
            }
        )

    return sections


# --------------------------------------------------
# Tables
# --------------------------------------------------

def extract_tables_from_docling(document) -> List[Dict[str, Any]]:
    """
    Extract lightweight table metadata (NO cell parsing).
    """
    tables = []

    if hasattr(document, "pages"):
        for page_idx, page in enumerate(document.pages):
            if hasattr(page, "body") and hasattr(page.body, "elements"):
                for el in page.body.elements:
                    if getattr(el, "label", None) == "table":
                        tables.append(
                            {
                                "table_id": f"table_{len(tables) + 1}",
                                "caption": el.text.strip() if getattr(el, "text", None) else "",
                                "page": page_idx + 1,
                                "section_id": None,
                            }
                        )

    return tables


def assign_tables_to_sections(tables, sections):
    """
    Deterministically assign tables to their containing section.
    """
    for t in tables:
        for s in sections:
            if s["page_start"] <= t["page"] <= s["page_end"]:
                t["section_id"] = s["section_id"]
                break


# --------------------------------------------------
# JSON Input
# --------------------------------------------------

def parse_json_document_with_structure(file_path: str) -> dict:
    """
    Parse pre-extracted JSON consistently.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    markdown = []
    sections = []
    current_page = 0

    if "pages" in data:
        for i, page in enumerate(data["pages"]):
            current_page = i + 1

            for el in page.get("elements", []):
                if "content" in el and "markdown" in el["content"]:
                    markdown.append(el["content"]["markdown"])

                if el.get("type") == "heading" and el.get("level") in (1, 2):
                    sections.append(
                        {
                            "section_id": f"section_{len(sections) + 1}",
                            "title": el["content"]["text"].strip(),
                            "level": el["level"],
                            "page_start": current_page,
                            "page_end": current_page,
                            "synthetic": False,
                            "source": "json_heading",
                        }
                    )

    for i, s in enumerate(sections):
        if i < len(sections) - 1:
            s["page_end"] = sections[i + 1]["page_start"] - 1
        else:
            s["page_end"] = current_page

    return {
        "text": "\n\n".join(markdown),
        "sections": sections,
        "tables": [],
    }


# --------------------------------------------------
# PDF Page Limit Helper (unchanged)
# --------------------------------------------------

def parse_document_with_limit(file_path: str, max_pages: int = None) -> str:
    file_path = Path(file_path)

    if file_path.suffix.lower() == ".pdf" and max_pages:
        fd, tmp = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)

        reader = PdfReader(str(file_path))
        writer = PdfWriter()

        for i in range(min(max_pages, len(reader.pages))):
            writer.add_page(reader.pages[i])

        with open(tmp, "wb") as f:
            writer.write(f)

        try:
            return parse_document(tmp)
        finally:
            os.remove(tmp)

    return parse_document(str(file_path))


def parse_document(file_path: str) -> str:
    result = converter.convert(str(file_path))
    return result.document.export_to_markdown()
