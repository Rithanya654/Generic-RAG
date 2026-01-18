"""
PHASE 2 + PHASE 3 RUNNER
-----------------------
Phase 2: Financial Fact Extraction (Bot 8 only)
Phase 3: Interactive Query Loop (LLM → Cypher → Answer)

SAFE MODE:
- Bot 3 already ran
- Graph already populated
- NO graph clearing
"""

import json
from database.neo4j_client import Neo4jClient
from bots.bot8_financial_facts import extract_financial_facts_from_document

from openai import OpenAI
from groq import Groq
from config.settings import (
    OPENAI_API_KEY,
    OPENAI_LLM_MODEL,
    GROQ_API_KEY,
    GROQ_LLM_MODEL,
)

# --------------------------------------------------
# CONFIG
# --------------------------------------------------

JSON_PATH = "integrated_output_with_tables.json"
SECTION_ID = "sec_009"
DOC_ID = "doc_probe_sec_009"   # MUST MATCH BOT 3 RUN

# --------------------------------------------------
# LLM (QUERY ONLY)
# --------------------------------------------------

openai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None


def llm_to_cypher(question: str) -> str:
    """
    Converts user question → Cypher.
    VERY SMALL prompt to control cost.
    """

    prompt = f"""
You generate Cypher queries for a Neo4j financial graph.

Graph model:
- (:Section)
- (:Entity {{name}})
- (:FinancialFact {{metric, value, unit, scope}})
- (Entity)-[:HAS_FACT]->(FinancialFact)
- (Section)-[:STATES]->(FinancialFact)

RULES:
- Return ONLY Cypher
- No explanations
- Read-only queries only

Question:
{question}
"""

    messages = [
        {"role": "system", "content": "You translate questions into Cypher. Output only Cypher."},
        {"role": "user", "content": prompt},
    ]

    if openai_client:
        response = openai_client.chat.completions.create(
            model=OPENAI_LLM_MODEL,
            messages=messages,
            temperature=0,
            max_tokens=150,
        )
    elif groq_client:
        response = groq_client.chat.completions.create(
            model=GROQ_LLM_MODEL,
            messages=messages,
            temperature=0,
            max_tokens=150,
        )
    else:
        raise RuntimeError("No LLM available")

    return response.choices[0].message.content.strip()


# --------------------------------------------------
# LOAD SECTION
# --------------------------------------------------

def load_section(json_path: str, section_id: str) -> dict:
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    for s in data["document_structure"]["sections"]:
        if s["section_id"] == section_id:
            return s

    raise ValueError(f"Section {section_id} not found")


# --------------------------------------------------
# MAIN
# --------------------------------------------------

def main():
    print("=" * 70)
    print("PHASE 2 + PHASE 3 RUNNER")
    print("=" * 70)

    section = load_section(JSON_PATH, SECTION_ID)

    section_for_bot8 = {
        "section_id": section["section_id"],
        "text": section.get("text", ""),
        "tables": section.get("tables", []),
    }

    with Neo4jClient() as neo4j:
        assert neo4j.verify_connection()

        # -------------------------------
        # PHASE 2 — BOT 8
        # -------------------------------
        print("\n[PHASE 2] Financial Fact Extraction (Bot 8)")
        res = extract_financial_facts_from_document(
            sections=[section_for_bot8],
            doc_id=DOC_ID,
            neo4j=neo4j,
        )
        print(f"Financial facts created: {res['facts_created']}")

        # -------------------------------
        # PHASE 3 — QUERY LOOP
        # -------------------------------
        print("\n[PHASE 3] Interactive Query Mode")
        print("Type a question, or 'exit' to quit\n")

        while True:
            question = input(">> ").strip()
            if question.lower() in {"exit", "quit"}:
                break

            try:
                cypher = llm_to_cypher(question)
                print("\nCypher:")
                print(cypher)

                result = neo4j.run_query(cypher)

                print("\nResult:")
                if not result:
                    print("(no records)")
                else:
                    for row in result:
                        print(row)

            except Exception as e:
                print(f"Error: {e}")

    print("\nDONE.")


if __name__ == "__main__":
    main()
