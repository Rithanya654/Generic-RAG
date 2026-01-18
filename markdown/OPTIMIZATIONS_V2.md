IMPLEMENTATION_PLAN.md
Structured & Cost-Optimized GraphRAG Pipeline
0. Objective

Upgrade the existing concept-level GraphRAG pipeline into a structure-aware, cost-efficient, section-grounded system that:

Preserves global semantic recall

Reduces graph explosion

Enables section-level reasoning

Minimizes LLM token usage

Remains incrementally deployable

This plan assumes the current pipeline is correct and recall-heavy.

1. Current Baseline (Assumed)

The system currently has:

Bot 1: Docling-based document parsing

Bot 2: Token-based overlapping chunking

Bot 3: LLM-based entity + relationship extraction (MERGE on name)

Bot 4: Entity embeddings + Neo4j vector index

Bot 5: Community detection (Louvain / Leiden) on entity graph

Bot 6: Community summarization

Provenance stored as source_chunk (int)

Known issues:

No explicit section nodes

Chunking ignores document structure

Graph is recall-heavy and dense

Summarization cost is high

2. High-Level Upgrade Strategy
Core idea

Introduce lightweight structural anchoring (Sections), then move summarization and reasoning “up” from entities to sections and communities.

We do not aim for sentence-level or argument graphs.

3. Phase 1 — Structural Anchoring (Highest Priority)
3.1 Introduce Section Nodes

Create a new node type:

(:Section {
  section_id: str,        // stable ID
  title: str,
  level: int,             // heading depth (H1=1, H2=2)
  page_start: int,
  page_end: int
})


Constraints:

Only create sections at semantic boundaries (H1/H2)

Do NOT create paragraph-level nodes

Expected count: ~8–20 per 10-page document

3.2 Section Hierarchy

Create hierarchy edges:

(:Section)-[:PART_OF]->(:Section)


Used to represent:

Chapter → Section → Subsection

3.3 Replace source_chunk with Section Provenance

Deprecate:

Entity.source_chunk
Relationship.source_chunk


Replace with:

(:Section)-[:MENTIONS]->(:Entity)
(:Section)-[:ASSERTS]->(:Relationship)


This enables:

true provenance

section-level reasoning

section-based summarization

4. Phase 2 — Structure-Aware Chunking
4.1 Modify Bot 2 (Chunker)

Current:

Sliding token windows

New behavior:

Use Docling’s structural output

Chunk within section boundaries

Ensure:

No chunk spans multiple sections

Chunks reference section_id

Chunk metadata:

{
  "chunk_id": "...",
  "section_id": "...",
  "text": "..."
}

4.2 Global Anchor Injection

Ensure every chunk explicitly references the primary document entity
(e.g., the company name) to avoid orphan subgraphs.

5. Phase 3 — Extraction Prompt Upgrade (Bot 3)
5.1 Extend Extraction Schema

Update JSON schema to include:

{
  "entity": {
    "name": "...",
    "type": "...",
    "salience": "CORE | IMPORTANT | SUPPORTING"
  },
  "relationship": {
    "type": "...",
    "source": "...",
    "target": "...",
    "section_id": "..."
  }
}

5.2 Prompt Instructions

Add explicit instructions:

Infer section relevance

Distinguish definition vs mention

Avoid re-extracting generic entities unless salient

Prefer specific relations over generic ones

6. Phase 4 — Entity Salience Enforcement
6.1 Salience Levels
Salience	Meaning
CORE	Central concepts (company, strategy, structure)
IMPORTANT	Executives, risks, regions
SUPPORTING	Banks, auditors, metrics

Store on Entity.salience.

6.2 Salience-Based Rules
Operation	Allowed for
Summarization	CORE, IMPORTANT
Embeddings	CORE, IMPORTANT
Graph storage	All
Community seeding	CORE

This prevents low-value nodes from driving cost.

7. Phase 5 — Graph Pruning & Relationship Control
7.1 Relationship Collapsing Rules

Before or after write:

Drop generic relations if a specific one exists

Deduplicate repeated relations across sections

Example:

RELATED_TO + LOCATED_IN → keep LOCATED_IN

7.2 Frequency Thresholding (Optional)

Remove relationships:

With low semantic weight

Appearing only once

Between SUPPORTING entities

8. Phase 6 — Section-First Summarization (Major Cost Reduction)
8.1 Replace Entity Summaries

❌ Do NOT summarize entities
✅ Summarize Sections

Create:

(:Section)-[:HAS_SUMMARY]->(:SectionSummary)


Section summaries are:

Short

Bounded

Stable

8.2 Community Over Sections

Run community detection over:

Section ↔ Section


(using shared CORE entities as edges)

Summarize:

Global community (C0)

Major thematic communities (C1)

Skip deep levels unless needed.

9. Phase 7 — Lazy / On-Demand Summarization
Rule

Never summarize at indexing time unless required.

Summaries should be generated:

When a query requests them

When a section/community is accessed

Cache results.

This is the largest token-saving optimization.

10. Phase 8 — Query-Time Optimization
10.1 Graph-First Answering

For factoid queries:

Attempt direct Cypher answer

Call LLM only if explanation or aggregation is needed

10.2 Scoped Context Injection

When calling LLM:

Inject only:

relevant Section summaries

related CORE entities

Never inject full graph context

11. Metrics & Validation Targets
Expected Healthy Ranges (10-page doc)
Metric	Target
Sections	8–20
Entities	40–80
Relationships	100–250
Summaries	≤5
Communities	2–5

Track:

tokens per query

summaries per query

entities per section

12. Explicit Non-Goals (For This Phase)

Do NOT implement yet:

Sentence-level nodes

Argument graphs

Temporal versioning

Contradiction detection

Full legal reasoning graphs

These are Phase-3 features.

13. Implementation Order (Critical)

Section nodes + hierarchy

Replace chunk provenance with section provenance

Section-aware chunking

Salience tagging

Section-level summarization

Lazy summarization

Query-time pruning

Do not change everything at once.

14. One-Line System Description (Use This)

“We evolved a recall-heavy GraphRAG into a structure-aware system by anchoring entities to document sections, enforcing salience, and shifting summarization from entities to sections and communities, significantly reducing graph size and token cost.”



Phase 9+ — Explicit References, Tables, and Advanced Enhancements
16. Phase 9 — Explicit Cross-Section Reference Layer (Targeted Upgrade)
16.1 Problem Addressed

The current system supports semantic linking via shared entities but does not explicitly model:

“See page X”

“Defined in section Y”

“As shown in Fig 2.3”

“Detailed in Appendix A”

These are document navigation and citation constructs, not just concepts.

16.2 Reference Extraction (Minimal & Safe)
Add a lightweight Reference extraction pass after entity extraction.

This is NOT full NLP citation parsing — only high-confidence patterns.

Patterns to detect

page \d+

section [\d\.]+

appendix [A-Z]

fig(ure)? \d+(\.\d+)?

table \d+(\.\d+)?

“detailed in”, “defined in”, “see”

Reference object schema
{
  "reference_type": "PAGE | SECTION | TABLE | FIGURE | APPENDIX",
  "from_section_id": "...",
  "target_locator": "104 | 2.3 | Appendix A",
  "context_entity": "Risk Management Policy"
}


Rules:

Only extract references within the same document

Skip weak language (“may be discussed later”)

16.3 Section-to-Section Reference Edges

Resolve page / section numbers to actual Section nodes.

Create edges:

(:Section)-[:REFERS_TO {reason}]->(:Section)


Where reason ∈ {DEFINED_IN, DETAILED_IN, REFERENCED_IN}

This enables:

section navigation

traceable provenance

legal / policy reasoning

16.4 Figure & Table Nodes (Lightweight Only)
Node schema
(:Table {
  id: "Fig_2_3",
  page: 200,
  caption: "...",
  section_id: "..."
})

Edges
(:Section)-[:REFERS_TO]->(:Table)
(:Table)-[:DEFINES]->(:Entity)


Rules:

Do NOT create cell-level nodes

Table content remains text-embedded

Only parse table content if queried

17. Phase 10 — Section-Centric Community Graph (Refinement)
17.1 Shift Communities from Entities → Sections

Current:

Communities over entity–entity edges

Upgrade:

Communities over Section–Section graph

Shared CORE entities

Explicit REFERS_TO edges

(:Section)-[:RELATED_SECTION {weight}]->(:Section)


Community detection now reflects document structure, not concept soup.

17.2 Community Summarization Scope

Summarize:

Global (C0)

Major themes (C1)

Do NOT summarize:

Every section

Every sub-community

18. Phase 11 — Query-Aware Graph Traversal
18.1 Query Type Classification

Classify queries into:

Type	Example
Factoid	“Where is X defined?”
Sectional	“Which section explains Y?”
Navigational	“Show related sections”
Analytical	“Summarize policy structure”

Routing rules:

Factoid → Graph only

Sectional → Section graph

Analytical → Section summaries + LLM

18.2 Reference-Aware Query Resolution

Example:

“Where is this rule defined?”

Execution:

Find entity

Traverse DEFINED_IN / REFERS_TO

Return section + page

Call LLM only if explanation is required

19. Phase 12 — Cost & Noise Control Enhancements
19.1 Reference Salience Rules

Do NOT extract references for:

SUPPORTING entities

boilerplate sections

generic phrases

Only extract for:

CORE / IMPORTANT entities

governance, policy, standards sections

19.2 Adaptive Extraction Depth

Use heuristics:

Early pages → deeper extraction

Repetitive sections → shallow extraction

Appendices → reference-only extraction

