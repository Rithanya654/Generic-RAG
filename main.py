"""
GraphRAG Pipeline V4 - Pure Graph Implementation
NO embeddings. NO vectors. Graph-only reasoning.
"""

import argparse
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent))

from bots.bot1_parser import parse_document_with_structure
from bots.bot2_chunker import (
    build_chunks_from_sections,
    build_chunks_without_sections
)
from bots.bot3_extractor import process_section_text
from bots.bot4_reference_extractor import extract_and_persist_references
from bots.bot5_financial_normalizer import normalize_financial_entities
from bots.bot6_timeperiod_extractor import extract_and_persist_timeperiods
from bots.bot8_financial_facts import extract_financial_facts_from_document
from database.neo4j_client import Neo4jClient
from query.global_query_v4 import (
    global_query, 
    format_global_results,
    query_financial_concept_over_time,
    compare_financial_concepts,
    query_financial_facts
)


# --------------------------------------------------
# Indexing Pipeline
# --------------------------------------------------

def run_indexing_pipeline_v4(
    document_path: str,
    clear_existing: bool = False,
    max_pages: int = None,
) -> dict:

    print("=" * 60)
    print("🚀 GraphRAG V4 — Pure Graph Pipeline")
    print("=" * 60)

    # ------------------------------
    # Bot 1 — Parse document
    # ------------------------------
    parsed = parse_document_with_structure(document_path, max_pages=max_pages)
    text = parsed["text"]
    sections = parsed.get("sections", [])

    doc_id = Path(document_path).stem.replace(" ", "_")

    print(f"📄 Parsed document: {doc_id}")
    print(f"   Sections detected: {len(sections)}")

    # ------------------------------
    # Bot 2 — Chunk by section
    # ------------------------------
    if sections:
        chunks = build_chunks_from_sections(text, sections, doc_id)
    else:
        chunks = build_chunks_without_sections(text, doc_id)

    print(f"✂️  Created {len(chunks)} chunks")

    # ------------------------------
    # Neo4j setup
    # ------------------------------
    with Neo4jClient() as neo4j:
        if not neo4j.verify_connection():
            raise RuntimeError("Neo4j connection failed")

        neo4j.setup_indexes()

        if clear_existing:
            print("⚠️ Clearing existing graph")
            neo4j.clear_graph()

        # ------------------------------
        # CREATE SECTION NODES (MANDATORY)
        # ------------------------------
        print("📐 Creating Section nodes")
        for s in sections:
            neo4j.create_section(
                section_id=s["section_id"],
                title=s.get("title", ""),
                level=s.get("level", 1),
                parent_id=s.get("parent_id"),
                doc_id=doc_id,
                page_start=s.get("page_start"),
                page_end=s.get("page_end"),
                synthetic=s.get("synthetic", False),
            )

        # ------------------------------
        # Bot 3 — Semantic extraction
        # ------------------------------
        print("🧠 Extracting entities & relationships")

        total_entities = 0
        total_relationships = 0

        for chunk in chunks:
            result = process_section_text(
                section_text=chunk["text"],
                section_id=chunk["section_id"],
                neo4j=neo4j,
                doc_id=doc_id,
            )
            total_entities += result["entities"]
            total_relationships += result["relationships"]

        # ------------------------------
        # Bot 4 — Reference extraction
        # ------------------------------
        print("🔗 Extracting cross-section references")
        
        # Prepare sections with text for reference extraction
        sections_with_text = []
        for chunk in chunks:
            section_id = chunk["section_id"]
            section_text = chunk["text"]
            
            # Find the section metadata
            section_meta = next((s for s in sections if s["section_id"] == section_id), None)
            if section_meta:
                sections_with_text.append({
                    "section_id": section_id,
                    "text": section_text,
                    **section_meta
                })
        
        reference_result = extract_and_persist_references(neo4j, sections_with_text, doc_id)

        # ------------------------------
        # Bot 5 — Financial normalization
        # ------------------------------
        print("💰 Normalizing financial entities")
        financial_result = normalize_financial_entities(neo4j, doc_id)

        # ------------------------------
        # Bot 6 — TimePeriod extraction
        # ------------------------------
        print("📅 Extracting time periods")
        
        # Prepare sections with text for TimePeriod extraction
        sections_with_text = []
        for chunk in chunks:
            section_id = chunk["section_id"]
            section_text = chunk["text"]
            
            # Find the section metadata
            section_meta = next((s for s in sections if s["section_id"] == section_id), None)
            if section_meta:
                sections_with_text.append({
                    "section_id": section_id,
                    "text": section_text,
                    **section_meta
                })
        
        timeperiod_result = extract_and_persist_timeperiods(neo4j, sections_with_text, doc_id)

        # ------------------------------
        # Bot 8 — Financial Fact extraction
        # ------------------------------
        print("📊 Extracting financial facts")
        
        # Prepare sections with text for FinancialFact extraction
        sections_with_text = []
        for chunk in chunks:
            section_id = chunk["section_id"]
            section_text = chunk["text"]
            
            # Find section metadata
            section_meta = next((s for s in sections if s["section_id"] == section_id), None)
            if section_meta:
                sections_with_text.append({
                    "section_id": section_id,
                    "text": section_text,
                    **section_meta
                })
        
        facts_result = extract_financial_facts_from_document(sections_with_text, doc_id, neo4j)

        # ------------------------------
        # Final stats
        # ------------------------------
        stats = neo4j.get_graph_stats()

    print("=" * 60)
    print("✅ Indexing complete")
    print(f"   Sections: {stats['sections']}")
    print(f"   Entities: {stats['entities']}")
    print(f"   Relationships: {stats['relationships']}")
    print(f"   Financial Concepts: {stats['financial_concepts']}")
    print(f"   Time Periods: {stats['timeperiods']}")
    print(f"   Financial Facts: {stats['financial_facts']}")
    print("=" * 60)

    return stats


# --------------------------------------------------
# Query Mode
# --------------------------------------------------

def run_graph_query(question: str) -> str:
    with Neo4jClient() as neo4j:
        if not neo4j.verify_connection():
            return "Neo4j connection failed"
        result = global_query(question, neo4j)
        return format_global_results(result)


def run_temporal_financial_query(concept: str) -> str:
    """Query a financial concept across all time periods."""
    with Neo4jClient() as neo4j:
        if not neo4j.verify_connection():
            return "Neo4j connection failed"
        
        result = query_financial_concept_over_time(neo4j, concept)
        
        lines = [
            f"📊 Financial Concept: {result['concept']}",
            "=" * 50,
        ]
        
        for period in result['periods']:
            lines.append(f"\n📅 {period['time_period']} ({period['period_type']})")
            lines.append(f"   Entities: {period['entity_count']}")
            lines.append(f"   Mentions: {', '.join(period['entities'][:5])}")
        
        return "\n".join(lines)


def run_comparison_query(concepts: str) -> str:
    """Compare multiple financial concepts."""
    concept_list = [c.strip() for c in concepts.split(',')]
    
    with Neo4jClient() as neo4j:
        if not neo4j.verify_connection():
            return "Neo4j connection failed"
        
        comparison = compare_financial_concepts(neo4j, concept_list)
        
        lines = [
            f"📊 Financial Comparison: {', '.join(concept_list)}",
            "=" * 50,
        ]
        
        for concept, data in comparison.items():
            lines.append(f"\n💰 {concept}")
            if data['periods']:
                for period in data['periods']:
                    lines.append(f"   {period['time_period']}: {period['entity_count']} entities")
            else:
                lines.append("   No data found")
        
        return "\n".join(lines)


def run_financial_facts_query(metric: str = None) -> str:
    """Query financial facts with optional metric filter."""
    with Neo4jClient() as neo4j:
        if not neo4j.verify_connection():
            return "Neo4j connection failed"
        
        result = query_financial_facts(neo4j, metric)
        
        lines = [
            f"📊 Financial Facts ({result['metric_filter']})",
            "=" * 50,
        ]
        
        for fact in result['facts'][:20]:  # Limit to top 20
            lines.append(f"\n💰 {fact['metric']}: {fact['value']:,} {fact['unit']}")
            lines.append(f"   Scale: {fact['scale']}")
            lines.append(f"   Period: {fact['period_value']} ({fact['period_type']})")
            lines.append(f"   Confidence: {fact['confidence']}")
            if fact['section']:
                lines.append(f"   Section: {fact['section']}")
            if fact['entities']:
                lines.append(f"   Entities: {', '.join(fact['entities'][:3])}")
        
        if result['total_facts'] > 20:
            lines.append(f"\n... and {result['total_facts'] - 20} more facts")
        
        return "\n".join(lines)


# --------------------------------------------------
# CLI
# --------------------------------------------------

def main():
    parser = argparse.ArgumentParser("GraphRAG V4 — Pure Graph")

    parser.add_argument("--index", type=str)
    parser.add_argument("--clear", action="store_true")
    parser.add_argument("--pages", type=int)
    parser.add_argument("--query-graph", type=str)
    parser.add_argument("--query-financial", type=str, help="Query financial concept over time (e.g., Revenue)")
    parser.add_argument("--compare", type=str, help="Compare financial concepts (comma-separated, e.g., Revenue,Profit)")
    parser.add_argument("--query-facts", type=str, nargs="?", const=None, help="Query financial facts (optional: filter by metric)")

    args = parser.parse_args()

    if args.index:
        run_indexing_pipeline_v4(
            args.index,
            clear_existing=args.clear,
            max_pages=args.pages,
        )
    elif args.query_graph:
        print(run_graph_query(args.query_graph))
    elif args.query_financial:
        print(run_temporal_financial_query(args.query_financial))
    elif args.compare:
        print(run_comparison_query(args.compare))
    elif args.query_facts is not None:
        print(run_financial_facts_query(args.query_facts))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
