"""
Bot 6: Community & Section Summarization (V5-ON-DEMAND)
------------------------------------------------------
LLM-only summarization.
- NO graph inference
- NO structure mutation
- NEVER auto-run
- OpenAI PRIMARY, Groq FALLBACK
"""

from typing import List, Dict, Any
from database.neo4j_client import Neo4jClient
from config.settings import (
    OPENAI_API_KEY,
    OPENAI_LLM_MODEL,
    GROQ_API_KEY,
    GROQ_LLM_MODEL,
    MAX_COMPLETION_TOKENS,
)

from openai import OpenAI
from groq import Groq


# ==================================================
# Lazy LLM invocation (OpenAI first)
# ==================================================

def chat_completion(messages, temperature=0.2, max_tokens=250):
    """
    OpenAI PRIMARY, Groq FALLBACK.
    LLM client is created ONLY when called.
    """

    # ---- OpenAI first ----
    if OPENAI_API_KEY:
        try:
            client = OpenAI(api_key=OPENAI_API_KEY)
            response = client.chat.completions.create(
                model=OPENAI_LLM_MODEL,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"⚠️ OpenAI failed, falling back to Groq: {e}")

    # ---- Groq fallback ----
    if GROQ_API_KEY:
        client = Groq(api_key=GROQ_API_KEY)
        response = client.chat.completions.create(
            model=GROQ_LLM_MODEL,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content.strip()

    raise RuntimeError("❌ No LLM provider available")


# ==================================================
# Community Summarization (ON-DEMAND)
# ==================================================

def summarize_communities(
    neo4j: Neo4jClient,
    doc_id: str = "doc-1"
) -> Dict[str, Any]:
    """
    Generate summaries ONLY when explicitly requested.
    """

    results = []

    with neo4j.driver.session() as session:
        communities = session.run("""
            MATCH (c:Community {doc_id: $doc_id})
            RETURN c.community_id AS cid, c.size AS size
            ORDER BY c.size DESC
        """, doc_id=doc_id)

        for c in communities:
            cid = c["cid"]

            sections = session.run("""
                MATCH (c:Community {community_id: $cid})-[:CONTAINS]->(s:Section)
                RETURN s.title AS title
                ORDER BY s.section_id
            """, cid=cid)

            titles = [r["title"] for r in sections]
            if not titles:
                continue

            prompt = f"""
Summarize the common theme of these document sections.

Sections:
{chr(10).join(f"- {t}" for t in titles)}

Write 2–3 precise sentences capturing the shared topic.
Avoid vague language.
"""

            summary = chat_completion(
                messages=[
                    {"role": "system", "content": "You summarize corporate documents precisely."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=MAX_COMPLETION_TOKENS,
            )

            session.run("""
                MERGE (cs:CommunitySummary {community_id: $cid, doc_id: $doc_id})
                SET cs.summary = $summary,
                    cs.updated_at = datetime()
                MERGE (c:Community {community_id: $cid, doc_id: $doc_id})
                    -[:HAS_SUMMARY]->(cs)
            """, cid=cid, doc_id=doc_id, summary=summary)

            results.append({
                "community_id": cid,
                "sections": len(titles),
                "summary": summary
            })

    return {"communities": results}


# ==================================================
# Section Summarization (ON-DEMAND)
# ==================================================

def summarize_sections(
    neo4j: Neo4jClient,
    section_ids: List[str],
    doc_id: str = "doc-1"
) -> Dict[str, str]:
    """
    Lazy section summarization.
    Called ONLY when user explicitly asks.
    """

    summaries = {}

    with neo4j.driver.session() as session:
        for sid in section_ids:
            existing = session.run("""
                MATCH (s:Section {doc_id: $doc_id, section_id: $sid})
                OPTIONAL MATCH (s)-[:HAS_SUMMARY]->(ss:SectionSummary)
                RETURN ss.summary AS summary, s.title AS title
            """, sid=sid, doc_id=doc_id).single()

            if existing and existing["summary"]:
                summaries[sid] = existing["summary"]
                continue

            entities = session.run("""
                MATCH (s:Section {section_id: $sid, doc_id: $doc_id})
                      -[:MENTIONS]->(e:Entity)
                RETURN e.name AS name
                ORDER BY e.salience DESC
                LIMIT 8
            """, sid=sid, doc_id=doc_id)

            entity_names = [r["name"] for r in entities]

            prompt = f"""
Summarize the following document section.

Title: {existing['title']}
Key entities: {', '.join(entity_names)}

Write 2–3 precise sentences describing what this section covers.
"""

            summary = chat_completion(
                messages=[
                    {"role": "system", "content": "You summarize corporate documents accurately."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=MAX_COMPLETION_TOKENS,
            )

            session.run("""
                MERGE (ss:SectionSummary {section_id: $sid, doc_id: $doc_id})
                SET ss.summary = $summary,
                    ss.updated_at = datetime()
                MERGE (s:Section {section_id: $sid, doc_id: $doc_id})
                    -[:HAS_SUMMARY]->(ss)
            """, sid=sid, doc_id=doc_id, summary=summary)

            summaries[sid] = summary

    return summaries
