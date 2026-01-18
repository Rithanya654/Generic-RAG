Robust, Quota-Safe, Structure-Aware GraphRAG Pipeline
0. Objective (V3)

Stabilize and harden the GraphRAG pipeline so that it:

Works correctly even under API quota limits

Produces multiple real sections, not one giant section

Anchors entities & relationships at the section level

Explicitly models cross-section references

Captures tables and figure citations

Avoids re-processing and graph corruption on partial runs

Is safe for annual reports (10–100 pages)

1. New Problems Observed (Why V3 Exists)

From recent verification:

Only one Section node created for entire document

Partial chunk processing due to API quota exhaustion

Missing Section → Entity provenance

Missing reference edges (REFERS_TO, DEFINED_IN, etc.)

Table / figure queries failing (expected but now required)

Verification script still checking deprecated chunk logic

V3 addresses all of these explicitly.

2. Phase 0 — Quota-Safe Indexing Foundation (NEW)
2.1 Chunk Processing Checkpointing (MANDATORY)

Each chunk must have a durable processing state.

Create / use a Chunk node:

(:Chunk {
  chunk_id,
  section_id,
  status: "PENDING | PROCESSED | FAILED",
  error: optional,
  retry_count: int
})


Rules:

Mark chunk as PROCESSED only after successful write

Never reprocess PROCESSED chunks

Allow retry for FAILED chunks up to N times

This guarantees:

Safe resume after quota failures

No duplicated entities or relationships

No lost progress

2.2 Idempotent Writes Everywhere

All writes must be idempotent:

MERGE entities by canonical name

MERGE relationships by (source, type, target, section_id)

MERGE sections by section_id

Never use CREATE without a guard.

3. Phase 1 — Correct Section Detection (CRITICAL FIX)
3.1 Fix the “Single Section” Problem

Root cause:

Docling content not mapped to headings

Fallback logic collapsed entire doc

Required behavior:

Extract H1 + H2 only

Ignore paragraph-level markers

If no headings exist:

Create synthetic sections by page ranges (e.g., every 3–5 pages)

Section schema (final):
(:Section {
  section_id,
  title,
  level,        // 1 or 2
  page_start,
  page_end,
  synthetic: boolean
})


Target counts:

10–15 sections for ~25 pages

25–40 sections for ~70 pages

3.2 Section Hierarchy

Create:

(:Section)-[:PART_OF]->(:Section)


Only between H2 → H1.

4. Phase 2 — Section-Aware Chunking (FIX)
4.1 Chunk Within Sections Only

Rules:

No chunk may span multiple sections

Every chunk must have section_id

Chunk size may shrink if section is small

Chunk metadata:

{
  "chunk_id": "...",
  "section_id": "...",
  "page_range": "10–12",
  "text": "..."
}

5. Phase 3 — Section-Anchored Extraction (FIX)
5.1 Remove Chunk Provenance

Deprecate completely:

Entity.source_chunk

(:Entity)-[:MENTIONED_IN]->(:Chunk)

5.2 Add Section Provenance

Mandatory edges:

(:Section)-[:MENTIONS]->(:Entity)
(:Section)-[:ASSERTS]->(:Relationship)


Each extracted object must be anchored to exactly one section.

6. Phase 4 — Salience Enforcement (Cost Control)
6.1 Salience Levels
CORE        → company, programs, strategy, governance
IMPORTANT   → risks, executives, regions
SUPPORTING  → auditors, banks, vendors


Store on Entity.salience.

6.2 Salience Rules
Operation	CORE	IMPORTANT	SUPPORTING
Store	✅	✅	✅
Embed	✅	✅	❌
Summarize	✅	✅	❌
Reference extraction	✅	✅	❌
7. Phase 5 — Explicit Cross-Section Reference Layer (FIX)
7.1 Reference Extraction (Post-Extraction Pass)

Run after entity extraction, per section.

Detect only high-confidence patterns:

page \d+

section [\d\.]+

appendix [A-Z]

figure \d+(\.\d+)?

table \d+(\.\d+)?

“see”, “defined in”, “detailed in”

Reference object:

{
  "reference_type": "PAGE | SECTION | TABLE | FIGURE | APPENDIX",
  "from_section_id": "...",
  "target_locator": "...",
  "reason": "DEFINED_IN | DETAILED_IN | REFERENCED_IN"
}

7.2 Resolve References to Sections

Resolve locator → actual Section.

Create:

(:Section)-[:REFERS_TO {reason}]->(:Section)


These edges must exist before cross-section queries are run.

8. Phase 6 — Table & Figure Modeling (REQUIRED NOW)
8.1 Table / Figure Nodes
(:Table {
  table_id,
  caption,
  page,
  section_id
})

8.2 Edges
(:Section)-[:REFERS_TO]->(:Table)
(:Table)-[:DEFINES]->(:Entity)


Rules:

No cell-level nodes

Table content stored as text blob

Parse table only when referenced or queried

9. Phase 7 — Section-First Summarization (FIX)
9.1 Do NOT Summarize Entities

❌ Entity summaries
✅ Section summaries

(:Section)-[:HAS_SUMMARY]->(:SectionSummary)

9.2 Lazy Summarization (MANDATORY)

Summaries are generated:

On first access

Cached

Never at indexing time

This is your biggest token saver.

10. Phase 8 — Section-Centric Communities
10.1 Build Communities Over Sections

Edges used:

REFERS_TO

Shared CORE entities

(:Section)-[:RELATED_SECTION {weight}]->(:Section)


Run Leiden/Louvain here.

11. Phase 9 — Verification Script Alignment (FIX)
Replace deprecated checks:

❌ Entity → Chunk
✅ Section → Entity

Required verification queries:

MATCH (s:Section) RETURN count(s)
MATCH (s:Section)-[:MENTIONS]->(:Entity) RETURN count(*)
MATCH (s1:Section)-[:REFERS_TO]->(s2:Section) RETURN count(*)
MATCH (s:Section)-[:REFERS_TO]->(:Table) RETURN count(*)

12. Expected Healthy Metrics (25 pages)
Metric	Target
Sections	10–15
Chunks	60–120
Entities	50–100
Relationships	150–300
REFERS_TO edges	> 5
Tables	2–10
Summaries	≤ 5
13. Explicit Non-Goals (UNCHANGED)

Do NOT implement:

sentence-level nodes

token graphs

full citation parsing

legal reasoning logic

contradiction resolution

14. Final Implementation Order (DO NOT CHANGE)

Chunk checkpointing & idempotency

Fix section detection (multiple sections)

Section-aware chunking

Replace chunk provenance

Salience enforcement

Reference extraction

Table / figure nodes

Lazy summarization

Section communities

Verification updates

15. One-Line Description (V3)

“We hardened a structure-aware GraphRAG pipeline with quota-safe indexing, section-level anchoring, explicit cross-section references, and table citation modeling, enabling reliable annual-report reasoning under real API constraints.”

16. Final Truth (Important)

Your recent errors were not architectural failures.

They were caused by:

partial indexing due to quota

section splitting not yet fixed

verification ahead of implementation

V3 fixes all of that.