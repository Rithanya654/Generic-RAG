"""
Bot 4: Reference Extraction (Deterministic)
------------------------------------------
- Extract cross-section references, tables, figures
- NO LLMs
- NO database writes
- PURE text -> structured signals
"""

import re
from typing import List, Dict, Any, Tuple


# -----------------------------
# Cross-section references
# -----------------------------

def extract_cross_section_references(
    text: str,
    section_id: str,
    doc_id: str,
) -> List[Dict[str, Any]]:
    """
    Extract high-confidence cross-section references using regex + heuristics.
    """

    references: List[Dict[str, Any]] = []

    patterns = [
        (r'\bpage\s+(\d+)\b', "PAGE"),
        (r'\bsection\s+(\d+(?:\.\d+)*)\b', "SECTION"),
        (r'\bappendix\s+([A-Z])\b', "APPENDIX"),
        (r'\btable\s+(\d+(?:\.\d+)*)\b', "TABLE"),
        (r'\bfigure\s+(\d+(?:\.\d+)*)\b', "FIGURE"),
        (r'\bfig\.\s*(\d+(?:\.\d+)*)\b', "FIGURE"),
    ]

    for pattern, ref_type in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            start, end = match.start(), match.end()
            locator = match.group(1)

            window = text[max(0, start - 60): min(len(text), end + 60)].lower()
            if not any(k in window for k in (
                "see", "refer", "defined", "detailed", "explained", "shown"
            )):
                continue

            references.append({
                "reference_id": f"{doc_id}:{section_id}:{ref_type}:{locator}",
                "reference_type": ref_type,
                "target_locator": locator,
                "from_section_id": section_id,
                "doc_id": doc_id,
                "reason": _infer_reference_reason(window),
            })

    return _deduplicate_references(references)


def _infer_reference_reason(context: str) -> str:
    if "defined" in context:
        return "DEFINED_IN"
    if any(k in context for k in ("detailed", "explained", "described")):
        return "DETAILED_IN"
    return "REFERENCED_IN"


def _deduplicate_references(
    references: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    seen = set()
    unique = []

    for ref in references:
        key = ref["reference_id"]
        if key not in seen:
            seen.add(key)
            unique.append(ref)

    return unique


# -----------------------------
# Tables & figures (mentions only)
# -----------------------------

def extract_tables_and_figures(
    text: str,
    section_id: str,
    doc_id: str,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Detect table and figure mentions only.
    """

    tables = []
    figures = []

    for match in re.finditer(r'\btable\s+(\d+(?:\.\d+)*)\b', text, re.IGNORECASE):
        table_id = match.group(1)
        tables.append({
            "table_id": f"{doc_id}:table:{table_id}",
            "label": table_id,
            "section_id": section_id,
            "doc_id": doc_id,
        })

    for match in re.finditer(
        r'\b(?:fig(?:ure)?\.?)\s*(\d+(?:\.\d+)*)\b',
        text,
        re.IGNORECASE
    ):
        fig_id = match.group(1)
        figures.append({
            "figure_id": f"{doc_id}:figure:{fig_id}",
            "label": fig_id,
            "section_id": section_id,
            "doc_id": doc_id,
        })

    return (
        _deduplicate_by_key(tables, "table_id"),
        _deduplicate_by_key(figures, "figure_id"),
    )


def _deduplicate_by_key(
    items: List[Dict[str, Any]],
    key: str
) -> List[Dict[str, Any]]:
    seen = set()
    result = []

    for item in items:
        if item[key] not in seen:
            seen.add(item[key])
            result.append(item)

    return result
