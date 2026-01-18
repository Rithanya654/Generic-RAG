"""
TEST RUNNER — GraphRAG V4 (JSON INPUT)
------------------------------------
- Runs full pipeline on an already-parsed JSON file
- Interactive query loop
- Saves full terminal log on exit
"""

import json
import sys
import argparse
from pathlib import Path
from datetime import datetime
from contextlib import redirect_stdout, redirect_stderr

# --------------------------------------------------
# Pipeline imports (MATCH EXISTING BOTS EXACTLY)
# --------------------------------------------------

from bots.bot3_extractor import process_section_text
from bots.bot4_reference_extractor import (
    extract_cross_section_references,
    extract_tables_and_figures,
)
from bots.bot5_financial_normalizer import normalize_financial_entities
from bots.bot6_timeperiod_extractor import extract_timeperiods
from bots.bot8_financial_facts import extract_financial_facts_from_document

from database.neo4j_client import Neo4jClient
from query.global_query_v4 import global_query, format_global_results

# --------------------------------------------------
# Logging setup
# --------------------------------------------------

OUTPUT_DIR = Path("outputs")
OUTPUT_DIR.mkdir(exist_ok=True)
LOG_FILE = OUTPUT_DIR / "complete_log.txt"


def log_print(*args, **kwargs):
    print(*args, **kwargs)
    sys.stdout.flush()


# --------------------------------------------------
# Pipeline runner
# --------------------------------------------------

def run_pipeline_from_json(json_path: str, clear_existing: bool = False) -> str:
    log_print("=" * 70)
    log_print("GraphRAG V4 — TEST RUN (JSON INPUT)")
    log_print("=" * 70)

    with open(json_path, "r", encoding="utf-8") as f:
        parsed = json.load(f)

    sections = parsed.get("sections", [])
    if not sections:
        # Try nested structure
        document_structure = parsed.get("document_structure", {})
        sections = document_structure.get("sections", [])
    
    if not sections:
        raise ValueError("JSON must contain a 'sections' array (either at top level or under 'document_structure')")

    doc_id = Path(json_path).stem.replace(" ", "_")

    log_print(f"Document ID: {doc_id}")
    log_print(f"Sections detected: {len(sections)}")

    # Build section_id → text map
    section_text_map = {
        s["section_id"]: s.get("text", "")
        for s in sections
    }

    with Neo4jClient() as neo4j:
        assert neo4j.verify_connection()
        neo4j.setup_indexes()

        if clear_existing:
            log_print("Clearing existing graph")
            neo4j.clear_graph()

        # --------------------------------------------------
        # Create Section nodes
        # --------------------------------------------------

        log_print("Creating Section nodes")
        for s in sections:
            neo4j.create_section(
                section_id=s["section_id"],
                title=s.get("title", ""),
                level=s.get("level", 1),
                parent_id=s.get("parent_id"),
                doc_id=doc_id,
                page_start=s.get("page_start"),
                page_end=s.get("page_end"),
            )

        # --------------------------------------------------
        # Bot 3 — Entity & relationship extraction
        # --------------------------------------------------

        log_print("Running Bot 3 — Entity & Relationship Extraction")
        for section_id, text in section_text_map.items():
            process_section_text(
                section_text=text,
                section_id=section_id,
                neo4j=neo4j,
                doc_id=doc_id,
            )

        # --------------------------------------------------
        # Bot 4 — Reference / Table / Figure extraction
        # --------------------------------------------------

        log_print("Running Bot 4 — Reference Extraction")

        for section_id, text in section_text_map.items():
            refs = extract_cross_section_references(
                text=text,
                section_id=section_id,
                doc_id=doc_id,
            )

            tables, figures = extract_tables_and_figures(
                text=text,
                section_id=section_id,
                doc_id=doc_id,
            )

            for r in refs:
                neo4j.create_reference(
                    from_section_id=r["from_section_id"],
                    target_locator=r["target_locator"],
                    reference_type=r["reference_type"],
                    reason=r["reason"],
                    doc_id=doc_id,
                )

            for t in tables:
                neo4j.create_table(
                    table_id=t["table_id"],
                    caption="",
                    page=None,
                    section_id=section_id,
                    doc_id=doc_id,
                )

            for f in figures:
                neo4j.create_figure(
                    figure_id=f["figure_id"],
                    caption="",
                    page=None,
                    section_id=section_id,
                    doc_id=doc_id,
                )

        # --------------------------------------------------
        # Bot 5 — Financial normalization
        # --------------------------------------------------

        log_print("Running Bot 5 — Financial Normalization")
        normalize_financial_entities(neo4j, doc_id)

        # --------------------------------------------------
        # Bot 6 — Time period extraction
        # --------------------------------------------------

        log_print("Running Bot 6 — Time Period Extraction")

        sections_with_text = [
            {
                "section_id": sid,
                "text": text,
            }
            for sid, text in section_text_map.items()
        ]

        # Extract time periods from all section texts
        all_text = " ".join(section_text_map.values())
        time_periods = extract_timeperiods(all_text)
        
        # Store time periods in Neo4j
        for period in time_periods:
            neo4j.create_time_period(
                period_id=period.get("period_id"),
                period_type=period.get("period_type"),
                start_date=period.get("start_date"),
                end_date=period.get("end_date"),
                doc_id=doc_id
            )

        # --------------------------------------------------
        # Bot 8 — Financial facts
        # --------------------------------------------------

        log_print("Running Bot 8 — Financial Fact Extraction")

        extract_financial_facts_from_document(
            sections=sections_with_text,
            doc_id=doc_id,
            neo4j=neo4j,
        )

        stats = neo4j.get_graph_stats()

    log_print("=" * 70)
    log_print("PIPELINE COMPLETE")
    for k, v in stats.items():
        log_print(f"{k}: {v}")
    log_print("=" * 70)

    return doc_id


# --------------------------------------------------
# Interactive query loop
# --------------------------------------------------

def interactive_query_loop(doc_id: str):
    log_print("\nINTERACTIVE QUERY MODE")
    log_print("Type a question and press Enter.")
    log_print("Type 'end' to exit.\n")

    with Neo4jClient() as neo4j:
        while True:
            question = input("Question > ").strip()

            if question.lower() == "end":
                log_print("Ending session.")
                break

            if not question:
                continue

            result = global_query(question, neo4j, doc_id)
            answer = format_global_results(result)
            log_print("\n" + answer + "\n")


# --------------------------------------------------
# Main
# --------------------------------------------------

def main():
    parser = argparse.ArgumentParser("GraphRAG V4 Test Runner")
    parser.add_argument("--json", required=True, help="Parsed JSON file")
    parser.add_argument("--clear", action="store_true", help="Clear graph before run")

    args = parser.parse_args()

    with open(LOG_FILE, "a", encoding="utf-8") as log_file:
        log_file.write("\n" + "=" * 80 + "\n")
        log_file.write(f"RUN STARTED: {datetime.now()}\n")

        with redirect_stdout(log_file), redirect_stderr(log_file):
            doc_id = run_pipeline_from_json(args.json, args.clear)
            interactive_query_loop(doc_id)

        log_file.write(f"\nRUN ENDED: {datetime.now()}\n")
        log_file.write("=" * 80 + "\n")

    print(f"Full session log saved to: {LOG_FILE.resolve()}")


if __name__ == "__main__":
    main()
