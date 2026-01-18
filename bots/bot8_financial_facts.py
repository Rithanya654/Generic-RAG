"""
Bot 8: Financial Fact Extraction (FINAL — Neo4j-SAFE)
----------------------------------------------------
Table-first, deterministic financial fact extraction.

✔ Uses table columns for year
✔ No dependency on Bot 6
✔ Matches Neo4jClient.create_financial_fact EXACTLY
✔ Query-ready
"""

import json
from typing import List, Dict, Any

from openai import OpenAI
from groq import Groq

from database.neo4j_client import Neo4jClient
from config.settings import (
    OPENAI_API_KEY,
    OPENAI_LLM_MODEL,
    GROQ_API_KEY,
    GROQ_LLM_MODEL,
)

# ==================================================
# LLM (rare fallback only)
# ==================================================

openai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None


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
# Helpers
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

    if scope.upper() not in {"GROUP", "COMPANY"}:
        return None, None

    return scope.upper(), year


def normalize_number(value):
    if value in (None, "", "-"):
        return None
    try:
        return float(str(value).replace(",", ""))
    except Exception:
        return None


def infer_scale(currency: str) -> str:
    """
    Rs.'000 → THOUSANDS
    """
    if not currency:
        return "UNIT"

    c = currency.lower()
    if "000" in c:
        return "THOUSANDS"
    if "million" in c:
        return "MILLIONS"
    if "billion" in c:
        return "BILLIONS"

    return "UNIT"


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

        currency = table.get("currency", "")
        scale = infer_scale(currency)

        columns = table.get("columns", [])
        rows = table.get("rows", [])

        # Parse columns → scope + year
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

            base_metric = classify_metric(label)
            if base_metric == "Other":
                continue

            # Ensure entity exists
            neo4j.create_entity(
                name=base_metric,
                entity_type="FINANCIAL",
                description=f"Financial metric: {base_metric}",
                salience="CORE",
            )

            neo4j.link_entity_to_section(
                entity_name=base_metric,
                section_id=section_id,
                doc_id=doc_id,
            )

            for col_key, (scope, year) in col_meta.items():
                raw_val = row.get(col_key)
                value = normalize_number(raw_val)
                if value is None:
                    continue

                # 👇 EXACT Neo4jClient signature
                neo4j.create_financial_fact(
                    metric=base_metric,
                    value=value,
                    unit=currency,
                    scale=scale,
                    period_type="YEAR",
                    period_value=year,
                    confidence="HIGH",
                    doc_id=doc_id,
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
