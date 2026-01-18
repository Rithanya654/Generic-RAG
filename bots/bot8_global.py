"""
Bot 8: Financial Fact Extraction (V9-SAFE)
-----------------------------------------
Table-first financial fact extraction.

✔ Works with EXISTING Neo4jClient
✔ No unsupported parameters
✔ Year + Scope preserved in description
✔ No Bot 6 dependency
✔ Zero runtime TypeErrors
"""

import json
from typing import List, Dict, Any

from database.neo4j_client import Neo4jClient

# ==================================================
# Metric normalization (deterministic)
# ==================================================

CANONICAL_METRICS = {
    "asset": "Assets",
    "liabilit": "Liabilities",
    "equity": "Equity",
    "revenue": "Revenue",
    "profit": "Profit",
    "loss": "Profit",
    "cash": "CashFlow",
}


def classify_metric(label: str) -> str:
    label_l = label.lower()
    for k, v in CANONICAL_METRICS.items():
        if k in label_l:
            return v
    return "Other"


# ==================================================
# Column parser
# ==================================================

def parse_column(col: str):
    """
    Group_2024 → ("GROUP", "2024")
    Company_2023 → ("COMPANY", "2023")
    """
    if "_" not in col:
        return None, None

    scope, year = col.split("_", 1)
    if not year.isdigit():
        return None, None

    scope = scope.upper()
    if scope not in {"GROUP", "COMPANY"}:
        return None, None

    return scope, year


def normalize_number(value):
    if value in (None, "-", ""):
        return None
    try:
        return float(str(value).replace(",", ""))
    except Exception:
        return None


# ==================================================
# TABLE EXTRACTION (PRIMARY)
# ==================================================

def extract_facts_from_tables(
    section: Dict[str, Any],
    doc_id: str,
    neo4j: Neo4jClient,
) -> int:

    section_id = section["section_id"]
    tables = section.get("tables", [])
    created = 0

    for table in tables:
        if table.get("type") != "financial_statement":
            continue

        currency = table.get("currency", "UNKNOWN")
        columns = table.get("columns", [])
        rows = table.get("rows", [])

        # ---- parse column metadata ----
        col_meta = {}
        for col in columns:
            scope, year = parse_column(col)
            if scope and year:
                col_meta[col.lower()] = (scope, year)

        if not col_meta:
            continue

        for row in rows:
            label = row.get("item")
            if not label:
                continue

            metric = classify_metric(label)
            if metric == "Other":
                continue

            # Ensure metric entity exists
            neo4j.create_entity(
                name=metric,
                entity_type="FINANCIAL",
                description=f"Financial metric: {metric}",
                salience="CORE",
            )

            neo4j.link_entity_to_section(
                entity_name=metric,
                section_id=section_id,
                doc_id=doc_id,
            )

            for col_key, (scope, year) in col_meta.items():
                raw_val = row.get(col_key)
                value = normalize_number(raw_val)

                if value is None:
                    continue

                description = f"{metric} ({scope}) for year {year}"

                # ---- SAFE call (NO unsupported args) ----
                neo4j.create_financial_fact(
                    metric=metric,
                    value=value,
                    unit=currency,
                    confidence="HIGH",
                    section_id=section_id,
                    doc_id=doc_id,
                    description=description,
                )

                created += 1

    return created


# ==================================================
# SECTION ENTRY
# ==================================================

def extract_financial_facts_from_section(
    section: Dict[str, Any],
    doc_id: str,
    neo4j: Neo4jClient,
) -> Dict[str, int]:

    facts = extract_facts_from_tables(section, doc_id, neo4j)
    return {"facts_created": facts}


# ==================================================
# DOCUMENT ENTRY
# ==================================================

def extract_financial_facts_from_document(
    sections: List[Dict[str, Any]],
    doc_id: str,
    neo4j: Neo4jClient,
) -> Dict[str, int]:

    total = 0
    for section in sections:
        total += extract_financial_facts_from_section(
            section, doc_id, neo4j
        )["facts_created"]

    print(f"[Bot 8] Financial facts created: {total}")
    return {"facts_created": total}
