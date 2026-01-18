"""
Global Query V5 – Graph-Orchestrated, Lazy LLM
----------------------------------------------
DEFAULT: Graph-only reasoning
OPTIONAL: Lazy LLM calls (summaries, explanations) ONLY if query demands
NO embeddings. NO vector search.
"""

from typing import Dict, Any, List
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
# Intent Detection (cheap, deterministic)
# ==================================================

def detect_query_intent(query: str) -> str:
    q = query.lower()

    if any(k in q for k in [
        "summarize", "summary", "overview", "explain", "high level",
        "what is this about"
    ]):
        return "SUMMARY"

    if any(k in q for k in [
        "compare", "trend", "over time"
    ]):
        return "TEMPORAL"

    return "GRAPH_ONLY"


# ==================================================
# Lazy LLM Invocation (OpenAI → Groq)
# ==================================================

def chat_completion(messages, temperature=0.1):
    if OPENAI_API_KEY:
        try:
            client = OpenAI(api_key=OPENAI_API_KEY)
            return client.chat.completions.create(
                model=OPENAI_LLM_MODEL,
                messages=messages,
                temperature=temperature,
                max_tokens=MAX_COMPLETION_TOKENS,
            ).choices[0].message.content.strip()
        except Exception as e:
            print(f"⚠️ OpenAI failed, falling back to Groq: {e}")

    if GROQ_API_KEY:
        client = Groq(api_key=GROQ_API_KEY)
        return client.chat.completions.create(
            model=GROQ_LLM_MODEL,
            messages=messages,
            temperature=temperature,
            max_tokens=MAX_COMPLETION_TOKENS,
        ).choices[0].message.content.strip()

    raise RuntimeError("No LLM provider available")


# ==================================================
# Graph Context Fetch
# ==================================================

def fetch_graph_context(
    neo4j: Neo4jClient,
    doc_id: str,
    limit: int = 80,
) -> List[Dict[str, Any]]:

    with neo4j.driver.session() as session:
        result = session.run(
            """
            MATCH (s:Section {doc_id:$doc})-[:MENTIONS]->(e:Entity)
            WHERE e.salience IN ['CORE','IMPORTANT']
            OPTIONAL MATCH (e)-[:NORMALIZED_TO]->(fc:FinancialConcept)
            OPTIONAL MATCH (s)-[:APPLIES_TO]->(t:TimePeriod)
            RETURN
                s.section_id      AS section_id,
                s.title           AS section_title,
                s.page_start      AS page_start,
                e.name            AS entity,
                e.type            AS type,
                e.description     AS description,
                e.salience        AS salience,
                fc.name           AS financial_concept,
                t.label           AS time_period
            ORDER BY e.salience DESC
            LIMIT $limit
            """,
            doc=doc_id,
            limit=limit,
        )

        return [dict(r) for r in result]


# ==================================================
# Core Query Orchestrator
# ==================================================

def global_query_v5(
    question: str,
    neo4j: Neo4jClient,
    doc_id: str = "doc-1",
) -> Dict[str, Any]:

    intent = detect_query_intent(question)
    print(f"[Query Intent] {intent} | {question}")

    # --------------------------------------------------
    # GRAPH CONTEXT (always)
    # --------------------------------------------------

    rows = fetch_graph_context(neo4j, doc_id)

    if not rows:
        return {
            "query": question,
            "answer": "No relevant information found in the document graph.",
            "references": [],
        }

    # Compact structured context
    context_lines = []
    references = []

    for r in rows:
        context_lines.append(
            f"- {r['entity']} ({r['type']}, {r['salience']})"
            + (f" → {r['financial_concept']}" if r["financial_concept"] else "")
            + (f": {r['description']}" if r["description"] else "")
        )

        references.append({
            "section": r["section_title"],
            "page": r.get("page_start"),
        })

    context = "\n".join(context_lines[:120])

    # --------------------------------------------------
    # GRAPH-ONLY ANSWERING (DEFAULT)
    # --------------------------------------------------

    prompt = f"""
You are answering using a DOCUMENT KNOWLEDGE GRAPH.

STRICT RULES:
- Answer SHARP and CONCISE (no fluff)
- Use ONLY the provided graph context
- Prefer CORE entities
- Do NOT hallucinate
- If unsure, say so clearly

GRAPH CONTEXT:
{context}

QUESTION:
{question}

ANSWER (2–5 sentences max):
"""

    answer = chat_completion(
        messages=[
            {"role": "system", "content": "You answer strictly from graph data."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.1,
    )

    # --------------------------------------------------
    # LAZY SUMMARY EXTENSION (Bot 9)
    # --------------------------------------------------

    if intent == "SUMMARY":
        from bots.bot9_summarization import summarize_communities

        summary = summarize_communities(neo4j, doc_id)

        answer += "\n\n📌 COMMUNITY OVERVIEW:\n"
        for c in summary.get("communities", []):
            answer += f"- {c['summary']}\n"

    # --------------------------------------------------
    # FINAL OUTPUT
    # --------------------------------------------------

    return {
        "query": question,
        "answer": answer.strip(),
        "references": list({
            (r["section"], r["page"]) for r in references if r["section"]
        }),
    }


# ==================================================
# Formatter
# ==================================================

def format_global_results_v5(result: Dict[str, Any]) -> str:
    lines = [
        f"🌍 QUERY: {result['query']}",
        "=" * 60,
        "💡 ANSWER:",
        result["answer"],
        "",
        "📚 REFERENCES:",
    ]

    for sec, page in result.get("references", []):
        page_str = f"Page {page}" if page else "Page N/A"
        lines.append(f"- {sec} ({page_str})")

    return "\n".join(lines)


# Backward compatibility
global_query = global_query_v5
format_global_results = format_global_results_v5
