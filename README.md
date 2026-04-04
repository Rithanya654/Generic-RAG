# Generic-RAG: Graph-Based Document Intelligence

A production-ready Knowledge Graph-based RAG system that converts documents to structured markdown, automatically constructs an entity-relationship graph via LLM extraction, and answers complex questions through graph traversal with LLM reasoning.

## Overview

Generic-RAG processes documents in three core stages:

1. PDF-to-Markdown Parsing (Docling): Converts raw documents into structured markdown while preserving document hierarchy
2. Intelligent Chunking & Graph Construction: Splits documents into section-aware chunks and uses LLMs to extract entities and relationships, building a Neo4j knowledge graph
3. Graph-Traversal Retrieval: Answers complex queries by traversing the graph to gather relevant chunks from multiple document sections, providing LLM with rich context for reasoning and trend analysis

This approach excels with long documents and complex queries that require correlating information across distant sections—particularly valuable for corporate documents like financial reports, lease agreements, contracts, and regulatory filings where traditional vector RAG fails.

## Key Advantages

### Long Document Processing
- Cross-Section Retrieval: Gathers relevant chunks from multiple sections in a single query
- Hierarchical Context: Preserves document structure for accurate reasoning
- Trend Detection: LLM can form trends and patterns by correlating data from different document sections

### Graph-Based Intelligence
- Deterministic Retrieval: Exact entity-relationship matching vs. similarity-based vector search
- Complete Provenance: Every retrieved chunk traces back to source section and page
- Multi-Hop Reasoning: Traverse multiple relationships to answer complex questions

### Superior for Corporate Documents
- Lease Agreements: Extract obligations, dates, and linked clauses across document sections
- Financial Reports: Correlate metrics, footnotes, and explanations from separate sections
- Contracts: Navigate linked terms, conditions, and cross-references
- Regulatory Documents: Track requirements across distributed sections

## Technology Choices & Rationale

### Document Parsing (Docling)
We evaluated multiple parsing solutions before settling on Docling:
- Tried LlamaIndex for document parsing but found limitations with complex table structures
- Tested Camelot specifically for table extraction but struggled with nested tables and table continuity across pages
- Chose Docling because it excels at handling nested tables, preserves table structure across page boundaries, and maintains document hierarchy while converting to clean markdown

### Entity & Relationship Extraction
Achieved proper graph structure through extensive LLM prompting:
- Iteratively refined prompts to ensure accurate entity identification across document contexts
- Developed relationship inference prompts that capture semantic connections between entities
- Fine-tuned extraction prompts to handle domain-specific terminology and implicit relationships

### Intent Classification Layer
Implemented an LLM-based document intent classifier:
- Analyzes input document type (financial report, contract, lease, regulatory filing, etc.)
- Adapts entity extraction and relationship formation based on document intent
- Customizes graph schema construction to match document structure and domain requirements
- Ensures context-appropriate processing for diverse corporate document types

## Architecture

### Core Pipeline Components

#### Bot 1: Document Parser (Docling)
- Input: PDF, DOCX, TXT
- Output: Structured Markdown with hierarchy
- Features: Document structure preservation, section detection, page boundary tracking, robust table handling

#### Bot 2: Semantic Chunker
- Input: Structured Markdown
- Output: Section-aware chunks with metadata
- Features: Token-aware chunking, header-aware splitting, context continuity, section metadata

#### Bot 3: Entity & Relationship Extractor + Graph Builder
- Input: Document chunks
- Output: Neo4j Knowledge Graph
- Features: LLM-powered extraction with extensive prompting, relationship inference, parallel processing, source linking, intent-based graph customization

## Neo4j Schema

Node Types:
- Document {doc_id, title, source_file, document_type}
- Section {section_id, title, level, page_start, page_end}
- Chunk {chunk_id, text, section_id, page_num}
- Entity {name, type, description}

Relationship Types:
- Document CONTAINS Section
- Section CONTAINS Chunk
- Chunk MENTIONS Entity
- Entity RELATED_TO Entity

## Usage

### Document Indexing
python main.py --index "document.pdf"
python main.py --index "document.pdf" --clear
python main.py --index "document.pdf" --pages 20

### Querying Documents
python main.py --query "What are the key obligations mentioned across the document?"
python main.py --query "How are revenue and expenses related?"
python main.py

## Performance Characteristics

### Strengths
- Long Document Handling: Efficient processing of 100+ page documents
- Cross-Section Intelligence: Naturally retrieves information from multiple document sections
- Complex Reasoning: LLM context includes diverse, relevant chunks for trend analysis
- Exact Provenance: Complete source tracking for every retrieved fact
- Deterministic Results: Same query yields same results

### Best For
- Corporate documents (contracts, agreements, leases)
- Financial reports (annual reports, 10-Ks, earnings documents)
- Regulatory filings and compliance documents
- Long-form technical documentation
- Complex multi-section policy documents

## Configuration

Environment Variables:
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password
OPENAI_API_KEY=your_openai_key
GROQ_API_KEY=your_groq_key
USE_GROQ=false
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
MAX_PAGES=None

## When to Use Generic-RAG

Use Generic-RAG when:
- Documents are long (50+ pages) with information spread across sections
- You need to correlate data from multiple document locations
- Document structure is important
- Exact fact provenance is critical
- Working with corporate, legal, or financial documents

Don't use when:
- You need semantic similarity search across diverse documents
- Working with single-page or very short documents
- Latency requirements demand sub-second response times

---

Generic-RAG combines the precision of graph databases with LLM reasoning to answer complex questions across long, structured documents where traditional vector RAG falls short.
