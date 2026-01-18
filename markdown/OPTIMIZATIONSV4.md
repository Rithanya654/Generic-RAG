Section-Accurate, Quota-Safe, Large-Document GraphRAG
0. Objective (V4)

Upgrade the pipeline so that it:

Detects document sections accurately (even in messy PDFs)

Never collapses entire documents into one section

Does not depend on LLM “intelligence” for structure

Survives partial failures (API quota, retries)

Scales to large annual reports (100+ pages)

Uses LLMs only where they are strong (semantics), not where they are weak (layout)

1. Critical Insight (Why V3 Failed)
❌ Wrong assumption

“The LLM will figure out structure from text.”

✅ Reality

LLMs are semantic, not layout-aware.

They:

do NOT reliably infer headings

do NOT understand pagination

do NOT see visual hierarchy

do NOT know when a section starts/ends unless told

Section detection must be deterministic and layout-driven, not LLM-driven.

V4 fixes this decisively.

2. Architectural Separation of Responsibilities (NEW)
Layer	Responsibility	Tool
Layout & Structure	Sections, pages, tables	Docling (deterministic)
Chunking	Size & overlap	Deterministic
Semantics	Entities & relations	LLM
References	Regex + heuristics	Deterministic
Reasoning	Summaries & synthesis	LLM

LLMs never decide structure.

3. Phase 0 — Hardening & Failure Safety (MANDATORY)
3.1 Chunk Checkpointing (Carryover)

Each chunk must have:

(:Chunk {
  chunk_id,
  section_id,
  status: "PENDING | PROCESSED | FAILED",
  retry_count
})


Rules:

Never reprocess PROCESSED chunks

Allow resume after crash or quota exhaustion

This is REQUIRED for large docs

3.2 Neo4j Correctness Rule (CRITICAL)

🚫 Never link nodes to relationships

This is illegal in Neo4j:

(sec)-[:ASSERTS]->(r)


✅ Correct pattern:

Store provenance on relationship properties

MERGE (s)-[r:REL_TYPE]->(t)
ON CREATE SET
  r.section_id = $section_id,
  r.doc_id = $doc_id

4. Phase 1 — Deterministic Section Detection (CORE FIX)
4.1 Section Detection MUST NOT Use LLM

Sections must be created before chunking and LLM calls.

Sources of truth (in priority order):

Docling heading hierarchy (H1, H2)

Numbered headings (1., 2.3, IV.)

Typography heuristics:

ALL CAPS lines

Bold + large font

Page-range fallback

4.2 Section Creation Rules (STRICT)

Create Section nodes only when:

Heading depth ≤ 2

OR page-range fallback triggers

(:Section {
  section_id,
  title,
  level,        // 1 or 2
  page_start,
  page_end,
  synthetic     // true if fallback
})

4.3 Fallback Rule (NON-NEGOTIABLE)

If total detected sections < 6:

➡ Create synthetic sections every 2–4 pages

Example:

Pages 1–3 → Section

Pages 4–6 → Section

This guarantees:

No single-section documents

Stable section counts for large reports

5. Phase 2 — Section-Bound Chunking (FIX)
5.1 Chunk ONLY Within Sections

Rules:

No chunk spans multiple sections

Each chunk has exactly one section_id

Chunk size adapts to section size

Chunk metadata:

{
  "chunk_id": "...",
  "section_id": "...",
  "page_range": "...",
  "text": "..."
}

6. Phase 3 — LLM Extraction (Why It Looked “Dumb”)
6.1 Why entities were missing

Entities were NOT missing because the LLM is weak.

They were missing because:

All chunks failed at a Neo4j Cypher error

No entities were ever committed

LLM output was discarded on failure

Once Neo4j errors are fixed:
➡ LLM extraction will work normally.

6.2 LLM Responsibilities (RESTRICTED)

LLM may:

Extract entities

Extract relationships

Assign salience

LLM must NOT:

Decide section boundaries

Decide page ranges

Create structure

6.3 Extraction Prompt Fix (MANDATORY)

All prompts using regex must be raw strings:

EXTRACTION_PROMPT = r"""
Detect references like page \d+, section \d+\.\d+
"""


Failure to do this silently breaks reference extraction.

7. Phase 4 — Salience & Cost Control (UNCHANGED)

Salience levels:

CORE

IMPORTANT

SUPPORTING

Rules:

Only CORE & IMPORTANT get embeddings

Only CORE & IMPORTANT get summarized

SUPPORTING stored but ignored for cost

8. Phase 5 — Explicit Cross-Section References (FIXED)
8.1 Deterministic Reference Extraction

Use regex + context rules (NOT LLM):

Detect:

see section X

as defined in section Y

refer to table Z

appendix A

Create:

(:Section)-[:REFERS_TO {reason}]->(:Section)

9. Phase 6 — Tables & Figures (REQUIRED FOR ANNUAL REPORTS)
9.1 Table / Figure Nodes
(:Table {
  table_id,
  caption,
  page,
  section_id
})


Edges:

(:Section)-[:REFERS_TO]->(:Table)
(:Table)-[:DEFINES]->(:Entity)


Rules:

No cell-level nodes

No numeric reasoning

Text-level only

10. Phase 7 — Embeddings Are OPTIONAL (CRITICAL)
10.1 Free-API Safe Mode

If embedding quota fails:

Skip embeddings

Skip vector indexes

GLOBAL queries must still work

Never fail indexing due to embeddings.

11. Phase 8 — Communities (Section-Centric)

Communities must be built over:

Sections

REFERS_TO edges

Shared CORE entities

Entity-only communities are deprecated.

12. Phase 9 — Verification Script Alignment

Remove all checks for:

(:Entity)-[:MENTIONED_IN]->(:Chunk)


Replace with:

MATCH (s:Section)-[:MENTIONS]->(:Entity)

13. Expected Healthy Metrics (Annual Reports)
Pages	Sections	Chunks
10–15	8–15	30–60
25	12–20	60–120
70	25–40	200–350
200	60–100	600–1200

These numbers are normal.

14. Implementation Order (FINAL, DO NOT CHANGE)

Deterministic section detection

Synthetic section fallback

Section-bound chunking

Fix Neo4j relationship writes

LLM extraction

Reference extraction

Table / figure modeling

Optional embeddings

Section-centric communities

Lazy summarization

15. One-Line Description (V4)

“We evolved GraphRAG into a deterministic, section-accurate system by separating layout from semantics, enforcing structural guarantees, and making the pipeline robust to partial failures and large corporate documents.”

