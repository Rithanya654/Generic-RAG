"""
SECTION PROBE — SAFE ONE-SECTION RUNNER
-------------------------------------
Runs Bots:
- Bot 3: Entity & Relationship Extraction (LLM)
- Bot 6: Time Period Extraction (Regex)
- Bot 8: Financial Fact Extraction (Tables + minimal LLM)

SAFE MODE:
- One section only
- Text sanitized
- Tables isolated
- Minimal token usage
"""

import json
from pathlib import Path

from database.neo4j_client import Neo4jClient

from bots.bot3_extractor import process_section_text
from bots.bot6_timeperiod_extractor import extract_timeperiods
from bots.bot8_financial_facts import extract_financial_facts_from_document


# --------------------------------------------------
# CONFIG
# --------------------------------------------------

JSON_PATH = "integrated_output_with_tables.json"
SECTION_ID = "sec_009"
DOC_ID = "doc_probe_sec_009"   # keep UNIQUE for probe
CLEAR_GRAPH = True


# --------------------------------------------------
# Utilities
# --------------------------------------------------

def sanitize_text(text: str) -> str:
    """
    Prevents LLM JSON / parsing failures.
    """
    return (
        text
        .replace("\t", " ")
        .replace("’", "'")
        .replace("Rs.'000", "Rs 000")
        .strip()
    )


def load_section(json_path: str, section_id: str) -> dict:
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    sections = data["document_structure"]["sections"]

    for s in sections:
        if s["section_id"] == section_id:
            return s

    raise ValueError(f"Section {section_id} not found")


# --------------------------------------------------
# MAIN PROBE
# --------------------------------------------------

def main():
    print("=" * 70)
    print("SECTION PROBE START")
    print("=" * 70)

    section = load_section(JSON_PATH, SECTION_ID)

    # ---- Sanitize text ----
    clean_text = sanitize_text(section.get("text", ""))

    if not clean_text:
        raise RuntimeError("Section text is empty after sanitization")

    print(f"Loaded section: {section['title']}")
    print(f"Text length: {len(clean_text)} characters")

    # ---- Prepare minimal section objects ----
    section_for_bot3 = {
        "section_id": section["section_id"],
        "text": clean_text,
    }

    section_for_bot6 = {
        "section_id": section["section_id"],
        "text": clean_text,
    }

    section_for_bot8 = {
        "section_id": section["section_id"],
        "text": clean_text,
        "tables": section.get("tables", []),
    }

    with Neo4jClient() as neo4j:
        assert neo4j.verify_connection()

        if CLEAR_GRAPH:
            print("Clearing graph (probe mode)")
            neo4j.clear_graph()

        neo4j.setup_indexes()
    
        neo4j.create_section(
            section_id=section["section_id"],
            title=section["title"],
            level=section["level"],   
            page_start=section.get("page_start"),
            page_end=section.get("page_end"),
            doc_id=DOC_ID,
        )


        # --------------------------------------------------
        # Bot 3 — Entity & Relationship Extraction
        # --------------------------------------------------
        print("\n[Bot 3] Entity & Relationship Extraction")

        result = process_section_text(
            section_text=section_for_bot3["text"],
            section_id=section_for_bot3["section_id"],
            neo4j=neo4j,
            doc_id=DOC_ID,
        )

        print(f"Entities created: {result['entities']}")
        print(f"Relationships created: {result['relationships']}")

        # --------------------------------------------------
        # Bot 6 — Time Period Extraction (regex only)
        # --------------------------------------------------
        print("\n[Bot 6] Time Period Extraction")

        # Extract time periods from section text
        time_periods = extract_timeperiods(clean_text)
        
        # Store time periods in Neo4j
        for period in time_periods:
            neo4j.create_time_period(
                period_id=period.get("period_id"),
                period_type=period.get("period_type"),
                start_date=period.get("start_date"),
                end_date=period.get("end_date"),
                doc_id=DOC_ID
            )

        print("Time periods extracted")

        # --------------------------------------------------
        # Bot 8 — Financial Fact Extraction (tables)
        # --------------------------------------------------
        print("\n[Bot 8] Financial Fact Extraction")

        facts_result = extract_financial_facts_from_document(
            sections=[section_for_bot8],
            doc_id=DOC_ID,
            neo4j=neo4j,
        )

        print(f"Financial facts created: {facts_result['facts_created']}")

        # --------------------------------------------------
        # Final stats
        # --------------------------------------------------
        stats = neo4j.get_graph_stats()

    print("\n" + "=" * 70)
    print("PROBE COMPLETE")
    for k, v in stats.items():
        print(f"{k}: {v}")
    print("=" * 70)


if __name__ == "__main__":
    main()
