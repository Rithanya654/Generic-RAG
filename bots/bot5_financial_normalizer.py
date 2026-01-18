"""
Bot 5: Financial Normalizer (V5-B)
---------------------------------
Deterministic mapping of extracted entities
to canonical FinancialConcept nodes.
NO LLMs.
"""

import json
import re
from pathlib import Path
from typing import Dict, Any
from database.neo4j_client import Neo4jClient


CONCEPT_PATH = Path("config/financial_concepts.json")


# --------------------------------------------------
# Registry
# --------------------------------------------------

def load_financial_concepts() -> Dict[str, Dict[str, Any]]:
    with open(CONCEPT_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _normalize_key(text: str) -> str:
    """
    Normalize entity text for alias matching.
    """
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text


# --------------------------------------------------
# Normalization
# --------------------------------------------------

def normalize_financial_entities(
    neo4j: Neo4jClient,
    doc_id: str = "doc-1"
) -> Dict[str, Any]:
    """
    Normalize Entity nodes to global FinancialConcept nodes.
    """

    concepts = load_financial_concepts()

    # Build alias → canonical concept map
    alias_map = {}
    for concept, meta in concepts.items():
        for alias in meta.get("aliases", []):
            alias_map[_normalize_key(alias)] = concept

    concepts_created = 0
    links_created = 0

    with neo4j.driver.session() as session:

        entities = session.run("""
            MATCH (e:Entity {doc_id: $doc_id})
            RETURN e.name AS name
        """, doc_id=doc_id)

        for record in entities:
            entity_name = record["name"]
            key = _normalize_key(entity_name)

            canonical = alias_map.get(key)
            if not canonical:
                continue

            category = concepts[canonical].get("category", "OTHER")

            # Create or match FinancialConcept (GLOBAL)
            result = session.run("""
                MERGE (fc:FinancialConcept {name: $name})
                ON CREATE SET
                    fc.category = $category,
                    fc.source = 'financial_concepts.json'
                RETURN fc
            """, name=canonical, category=category).single()

            if result and result["fc"].get("source") == "financial_concepts.json":
                concepts_created += 1

            # Link Entity → FinancialConcept (idempotent)
            link = session.run("""
                MATCH (e:Entity {doc_id: $doc_id, name: $entity_name})
                MATCH (fc:FinancialConcept {name: $concept_name})
                MERGE (e)-[r:NORMALIZED_TO]->(fc)
                RETURN r
            """, doc_id=doc_id, entity_name=entity_name, concept_name=canonical).single()

            if link:
                links_created += 1

    print("✅ Financial normalization complete")
    print(f"   New concepts created: {concepts_created}")
    print(f"   Entity links created: {links_created}")

    return {
        "concepts_created": concepts_created,
        "entity_links": links_created,
    }


if __name__ == "__main__":
    with Neo4jClient() as neo4j:
        normalize_financial_entities(neo4j)
