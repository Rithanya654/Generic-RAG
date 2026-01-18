# Hybrid GraphRAG Pipeline

A high-performance Knowledge Graph-based RAG system that combines the precision of Graph databases (Neo4j) with the semantic power of LLMs (OpenAI & Groq).

## 🤖 Pipeline Architecture (The Bots)

The pipeline is divided into 6 specialized "Bots", each handling a distinct stage of the indexing process:

### 1. Bot 1: Document Parser
- **Role**: Converts raw documents (PDF, Docx, TXT) into structured Markdown.
- **Technology**: Powered by **Docling**.
- **Optimization**: Added support for **Pre-extracted JSON** files to bypass heavy OCR/Parsing when data is already available in a structured element format.

### 2. Bot 2: Semantic Chunker
- **Role**: Splits document content into overlapping chunks based on token counts.
- **Feature**: Markdown-aware; detects headers and preserves section hierarchy in Neo4j for provenance.

### 3. Bot 3: Entity & relationship Extractor
- **Role**: Uses LLMs (OpenAI gpt-4o-mini or Groq Llama 3) to identify entities and their connections.
- **Optimization**: **Parallel Processing** implemented via `ThreadPoolExecutor`, allowing multiple chunks to be processed concurrently across API threads.

### 4. Bot 4: Entity Embedder
- **Role**: Generates vector embeddings for entities using OpenAI's `text-embedding-3-small`.
- **Optimization**: Uses **Batching** (Default: 50 entities per request) for better throughput and lower latency.

### 5. Bot 5: Community Detector
- **Role**: Runs the **Louvain Algorithm** to detect clusters of related entities in the graph.
- **Technology**: Client-side execution via **NetworkX**, making it compatible with all Neo4j versions (Aura/Community).

### 6. Bot 6: Community Summarizer
- **Role**: Generates high-level summaries for each detected community to enable global document understanding.
- **Optimization**: **Parallel Summarization** using `ThreadPoolExecutor` to handle multiple clusters simultaneously.

---

## 🚀 Performance Optimizations

### Parallel Execution
By moving from a sequential to a multithreaded architecture, the time required for Entity Extraction (Bot 3) and Community Summarization (Bot 6) has been significantly reduced, making it efficient even for large-scale documents.

### Structured JSON Ingestion
The system can now ingest pre-parsed JSON data (containing markdown elements and metadata), cutting down the initial processing time and allowing for better control over the source text.

---

## 🔍 Query Capabilities

- **Local Query**: Focuses on specific entities and their immediate neighborhood.
- **Global Query**: Uses community summaries to answer broad, thematic questions about the entire document.
- **Hybrid Query**: Combines vector similarity search with graph traversal for the most comprehensive results.

---

## 🛠️ Tech Stack
- **Database**: Neo4j (Graph)
- **LLMs**: OpenAI (Quality), Groq (Speed/Efficiency)
- **Parsing**: Docling
- **Graph Logic**: NetworkX, community-louvain
