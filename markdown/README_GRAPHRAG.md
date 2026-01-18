# GraphRAG: Beyond Traditional Vector Search

This project implements a **Hybrid GraphRAG** pipeline, which offers significant advantages over "normal" (Vector-only) RAG systems.

## 🚀 Why GraphRAG is Better than Normal RAG

### 1. Global Document Understanding
*   **Normal RAG**: Searches for specific "top-k" chunks that are semantically similar to your query. It often misses the bigger picture or connections that span the whole document.
*   **GraphRAG**: Builds a Knowledge Graph (KG) of the entire document. It detects "communities" (clusters) of related entities, allowing it to summarize high-level themes across the whole document (Global Query).

### 2. Capturing Intricate Sectional Links
You asked if this captures links between different sections. **Yes, it does, and it logs them into the graph:**
- **Shared Entities**: If Section A and Section B both mention "Medine Ltd", they are implicitly linked through that entity node.
- **Bot 4 & Neo4j Logic**: Our pipeline explicitly builds `RELATED_SECTION` links based on shared entities. If two sections share more than a threshold of entities, the graph logs a direct relationship between them.
- **Hierarchical Provenance**: Each `Entity` is linked to the `Chunk` it was mentioned in (`MENTIONED_IN`), and each `Chunk` is linked to its parent `Section`. This creates a path: `Entity -> Chunk -> Section`.

### 3. Multi-Hop Reasoning
- **Normal RAG**: Can't easily answer "How is Person X related to Project Y?" if they are mentioned 10 pages apart.
- **GraphRAG**: Traverses the graph. It can find: `Person X -> works_for -> Organization Z -> owner_of -> Project Y`. This multi-hop path is explicitly stored in Neo4j.

## 🛠️ How it Works (and Logs)

| Phase | What it Captures | Logged to Graph? |
| :--- | :--- | :--- |
| **Parsing** | Document structure (Headers, Levels, Text) | ✅ Yes (Section nodes) |
| **Chunking** | Contextual text segments | ✅ Yes (Chunk nodes) |
| **Extraction** | Entities and their direct Relationships | ✅ Yes (Entity & Rel nodes) |
| **Provenance** | Which entity was found in which chunk/section | ✅ Yes (`MENTIONED_IN`, `IN_SECTION`) |
| **Linking** | Cross-section connections via shared entities | ✅ Yes (`RELATED_SECTION`) |
| **Communities** | Thematic grouping of entities | ✅ Yes (Community nodes) |

## 💨 Performance Optimizations
We use **Parallel Processing** (`ThreadPoolExecutor`) to:
1.  Extract entities from multiple chunks simultaneously.
2.  Summarize multiple thematic communities at once.
This overcomes the latency of sequential LLM API calls, making it viable for large, complex documents.
