"""
Bot 6: TimePeriod Extractor (V5-C)
---------------------------------
Deterministic extraction of time periods.
NO LLMs.
PURE text -> structured signals.
"""

import re
from typing import List, Dict, Any


# --------------------------------------------------
# Deterministic time patterns
# --------------------------------------------------

TIME_PATTERNS = [
    # Fiscal years
    (r'\bFY\s?(\d{4})\b', lambda y: f"FY{y}", "ANNUAL"),
    (r'\bfiscal\s+year\s+(\d{4})\b', lambda y: f"FY{y}", "ANNUAL"),
    (r'\bFY\s?(\d{2})\b', lambda y: f"FY20{y}" if int(y) < 50 else f"FY19{y}", "ANNUAL"),

    # Quarters
    (r'\bQ([1-4])\s?FY\s?(\d{4})\b', lambda q, y: f"Q{q}FY{y}", "QUARTER"),
    (r'\bQ([1-4])\s+(\d{4})\b', lambda q, y: f"Q{q}CY{y}", "QUARTER"),
    (r'\bquarter\s+([1-4])\s+(?:of\s+)?(?:FY|fiscal\s+year)?\s*(\d{4})\b',
     lambda q, y: f"Q{q}FY{y}", "QUARTER"),

    # Half-years
    (r'\bH([1-2])\s?FY\s?(\d{4})\b', lambda h, y: f"H{h}FY{y}", "HALF"),
]

# Calendar years ONLY with financial context
CALENDAR_CONTEXT = (
    "year", "fy", "fiscal", "quarter", "results", "revenue", "income"
)


# --------------------------------------------------
# Extraction
# --------------------------------------------------

def extract_timeperiods(text: str) -> List[Dict[str, Any]]:
    """
    Extract unique, high-confidence time periods from text.
    """
    periods = []

    # ---- Pattern-based extraction ----
    for pattern, label_fn, ptype in TIME_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            groups = match.groups()
            label = label_fn(*groups)
            year = int(groups[-1])

            if year < 1990 or year > 2050:
                continue

            periods.append({
                "label": label,
                "year": year,
                "period_type": ptype,
            })

    # ---- Contextual calendar year extraction ----
    for match in re.finditer(r'\b(19\d{2}|20\d{2})\b', text):
        year = int(match.group(1))
        if year < 1990 or year > 2050:
            continue

        window = text[max(0, match.start() - 30): match.end() + 30].lower()
        if not any(k in window for k in CALENDAR_CONTEXT):
            continue

        periods.append({
            "label": f"CY{year}",
            "year": year,
            "period_type": "CALENDAR",
        })

    # ---- Deduplicate by label ----
    seen = set()
    unique = []
    for p in periods:
        if p["label"] not in seen:
            seen.add(p["label"])
            unique.append(p)

    # ---- Sort ----
    type_order = {"ANNUAL": 0, "HALF": 1, "QUARTER": 2, "CALENDAR": 3}
    unique.sort(key=lambda x: (x["year"], type_order.get(x["period_type"], 99)))

    return unique


# --------------------------------------------------
# Persistence (SEPARATE STEP)
# --------------------------------------------------

def persist_timeperiods(
    neo4j,
    sections: List[Dict[str, Any]],
    doc_id: str,
) -> Dict[str, int]:
    """
    Persist extracted TimePeriods and link to sections.
    """

    periods_created = 0
    links_created = 0

    with neo4j.driver.session() as session:
        for section in sections:
            section_id = section["section_id"]
            text = section.get("text", "")

            if not text:
                continue

            periods = extract_timeperiods(text)

            for p in periods:
                # GLOBAL TimePeriod node
                result = session.run("""
                    MERGE (t:TimePeriod {label: $label})
                    ON CREATE SET
                        t.year = $year,
                        t.period_type = $ptype,
                        t.scope = 'global'
                    RETURN t
                """, label=p["label"], year=p["year"], ptype=p["period_type"]).single()

                if result:
                    periods_created += 1

                link = session.run("""
                    MATCH (s:Section {doc_id: $doc_id, section_id: $section_id})
                    MATCH (t:TimePeriod {label: $label})
                    MERGE (s)-[r:APPLIES_TO]->(t)
                    RETURN r
                """, doc_id=doc_id, section_id=section_id, label=p["label"]).single()

                if link:
                    links_created += 1

    return {
        "periods_created": periods_created,
        "section_links": links_created,
    }
