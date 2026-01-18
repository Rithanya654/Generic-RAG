"""
Bot 3: Entity & Relationship Extractor (STABLE)
----------------------------------------------
LLM-based semantic extraction ONLY.

GUARANTEES:
- Never crashes pipeline
- Never breaks JSON parsing
- Never hallucinates structure
- Returns empty safely on failure
"""

import json
from typing import List, Dict, Any

from openai import OpenAI
from groq import Groq

from config.settings import (
    OPENAI_API_KEY,
    OPENAI_LLM_MODEL,
    GROQ_API_KEY,
    GROQ_LLM_MODEL,
    MAX_COMPLETION_TOKENS,
    LLM_TEMPERATURE,
)

from database.neo4j_client import Neo4jClient


# ==================================================
# LLM Clients
# ==================================================

openai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None


def chat_completion(messages):
    """OpenAI primary, Groq fallback"""
    if openai_client:
        try:
            return openai_client.chat.completions.create(
                model=OPENAI_LLM_MODEL,
                messages=messages,
                temperature=LLM_TEMPERATURE,
                max_tokens=MAX_COMPLETION_TOKENS,
                response_format={"type": "json_object"},
            )
        except Exception as e:
            print(f"[Bot3] OpenAI failed → Groq fallback: {e}")

    if groq_client:
        return groq_client.chat.completions.create(
            model=GROQ_LLM_MODEL,
            messages=messages,
            temperature=LLM_TEMPERATURE,
            max_tokens=MAX_COMPLETION_TOKENS,
            response_format={"type": "json_object"},
        )

    raise RuntimeError("No LLM provider available")


# ==================================================
# Prompt (STRICT JSON CONTRACT)
# ==================================================

EXTRACTION_PROMPT = """
You are a knowledge graph extraction engine.

RULES (MANDATORY):
- Output MUST be valid JSON
- Output MUST contain ONLY these keys:
  - entities
  - relationships
- No markdown
- No comments
- No trailing text

STRICT CONSTRAINTS:
- Use ONLY the provided section text
- Do NOT invent facts, numbers, tables, or references
- Do NOT infer values not explicitly stated
- Prefer precision over coverage

FAIL-SAFE RULE:
- If you cannot produce COMPLETE and VALID JSON, return EXACTLY:
  { "entities": [], "relationships": [] }
- Do NOT return partial JSON
- Do NOT explain errors


ENTITY SCHEMA:
{
  "name": string,
  "type": "PERSON" | "ORGANIZATION" | "FINANCIAL" | "GOVERNANCE" | "RISK" | "CONCEPT" | "EVENT" | "OTHER",
  "description": string,
  "salience": "CORE" | "IMPORTANT" | "SUPPORTING"
}

RELATIONSHIP SCHEMA:
{
  "source": string,
  "target": string,
  "type": "DEFINES" | "DETAILS" | "REFERS_TO" | "ASSOCIATED_WITH",
  "description": string
}

LIMITS:
- Max 25 entities
- Max 30 relationships

TEXT:
"""


# ==================================================
# Helpers
# ==================================================

ALLOWED_REL_TYPES = {
    "DEFINES",
    "DETAILS",
    "REFERS_TO",
    "ASSOCIATED_WITH",
}


def _safe_list(v):
    return v if isinstance(v, list) else []


def normalize_name(name: str) -> str:
    return " ".join(name.strip().split()) if name else ""


# ==================================================
# Extraction
# ==================================================

def extract_entities_and_relationships(
    text: str,
    section_id: str,
    is_empty: bool = False,
) -> Dict[str, Any]:

    if is_empty or not text.strip():
        return {"entities": [], "relationships": []}

    try:
        response = chat_completion(
            [
                {
                    "role": "system",
                    "content": "Return valid JSON only.",
                },
                {
                    "role": "user",
                    "content": EXTRACTION_PROMPT
                    + f"\n[SECTION: {section_id}]\n"
                    + text,
                },
            ]
        )

        content = response.choices[0].message.content

        # ---- ABSOLUTE JSON PARSE ----
        raw = json.loads(content)

        return {
            "entities": _safe_list(raw.get("entities"))[:25],
            "relationships": _safe_list(raw.get("relationships"))[:30],
        }

    except Exception as e:
        print(f"[Bot3] Extraction failed safely for {section_id}: {e}")
        return {"entities": [], "relationships": []}


# ==================================================
# Persistence
# ==================================================

def persist_extraction(
    extraction: Dict[str, Any],
    section_id: str,
    neo4j: Neo4jClient,
    doc_id: str,
) -> Dict[str, int]:

    entities_written = 0
    relationships_written = 0

        # ---- ENSURE SECTION NODE EXISTS ----
    neo4j.create_section(
        section_id=section_id,
        title=section_id,      # title optional here
        level=1,               # safe default
        doc_id=doc_id,
    )


    # ---- Entities ----
    for e in extraction["entities"]:
        name = normalize_name(e.get("name"))
        if not name:
            continue

        salience = e.get("salience", "SUPPORTING")
        if salience not in {"CORE", "IMPORTANT", "SUPPORTING"}:
            salience = "SUPPORTING"

        created = neo4j.create_entity(
            name=name,
            entity_type=e.get("type", "OTHER"),
            description=e.get("description", ""),
            salience=salience,
        )

        neo4j.link_entity_to_section(
            entity_name=name,
            section_id=section_id,
            doc_id=doc_id,
        )

        if created:
            entities_written += 1

    # ---- Relationships ----
    for r in extraction["relationships"]:
        rel_type = r.get("type", "").upper()
        if rel_type not in ALLOWED_REL_TYPES:
            continue

        src = normalize_name(r.get("source"))
        tgt = normalize_name(r.get("target"))

        if not src or not tgt or src == tgt:
            continue

        created = neo4j.create_relationship(
            source_name=src,
            target_name=tgt,
            rel_type=rel_type,
            description=r.get("description", ""),
        )

        if created:
            relationships_written += 1

    return {
        "entities": entities_written,
        "relationships": relationships_written,
    }


# ==================================================
# Entry Point
# ==================================================

def process_section_text(
    section_text: str,
    section_id: str,
    neo4j: Neo4jClient,
    doc_id: str,
    is_empty: bool = False,
) -> Dict[str, int]:

    extraction = extract_entities_and_relationships(
        section_text,
        section_id,
        is_empty=is_empty,
    )

    return persist_extraction(extraction, section_id, neo4j, doc_id)
