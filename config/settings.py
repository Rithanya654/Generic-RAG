"""
GraphRAG Pipeline Configuration
--------------------------------
Policy:
- OpenAI is ALWAYS the primary LLM provider
- Groq is used ONLY as a fallback if OpenAI fails
- Embeddings only at ingestion
- Graph-first, cost-safe defaults
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# Neo4j Configuration
# ============================================================
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

if not all([NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD]):
    raise EnvironmentError("❌ Neo4j credentials are not fully configured")


# ============================================================
# LLM Provider Policy (IMPORTANT)
# ============================================================
# OpenAI is PRIMARY
# Groq is FALLBACK only
PRIMARY_LLM_PROVIDER = "openai"
FALLBACK_LLM_PROVIDER = "groq"


# ============================================================
# OpenAI Configuration (PRIMARY)
# ============================================================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_LLM_MODEL = os.getenv(
    "OPENAI_LLM_MODEL",
    "gpt-4o-mini"
)

OPENAI_EMBEDDING_MODEL = os.getenv(
    "OPENAI_EMBEDDING_MODEL",
    "text-embedding-3-small"
)

if not OPENAI_API_KEY:
    print("⚠️ OPENAI_API_KEY not set — will rely on fallback only")


# ============================================================
# Groq Configuration (FALLBACK ONLY)
# ============================================================
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_LLM_MODEL = os.getenv(
    "GROQ_LLM_MODEL",
    "llama-3.1-70b-versatile"
)

if not GROQ_API_KEY:
    print("⚠️ GROQ_API_KEY not set — no fallback available")


# ============================================================
# LLM Safety & Cost Controls
# ============================================================
LLM_TEMPERATURE = 0.0
MAX_COMPLETION_TOKENS = 900
MAX_RETRIES = 3
REQUEST_TIMEOUT = 30  # seconds


# ============================================================
# Chunking Configuration
# ============================================================
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", 600))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", 100))
MAX_CHUNK_SIZE = 800

if CHUNK_SIZE > MAX_CHUNK_SIZE:
    raise ValueError(
        f"❌ CHUNK_SIZE ({CHUNK_SIZE}) exceeds MAX_CHUNK_SIZE ({MAX_CHUNK_SIZE})"
    )


# ============================================================
# Embedding Policy
# ============================================================
EMBEDDINGS_ENABLED = True
EMBEDDINGS_INGESTION_ONLY = True
STORE_NODE_EMBEDDINGS = True
STORE_CHUNK_EMBEDDINGS = True


# ========
