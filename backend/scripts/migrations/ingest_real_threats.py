"""
ingest_real_threats.py — ProjectXY Phase 3: AI Firewall Threat Vector Ingestion
================================================================================
Downloads REAL, open-source prompt injection and jailbreak datasets from HuggingFace,
converts them to vector embeddings using the local ``all-MiniLM-L6-v2`` model,
and persists them into PostgreSQL via the pgvector extension.

NO MOCK DATA — every vector in the database originates from a verified,
publicly available, real-world adversarial prompt corpus.

Datasets ingested:
  1. deepset/prompt-injections      — 662 real prompt injection examples
  2. rubend18/ChatGPT-Jailbreak-Prompts — 79 jailbreak attempts
  3. JasperLS/prompt-injection       — Multi-source injection catalogue

Usage:
    cd /home/bantu/Documents/ProjectXY/backend
    python ingest_real_threats.py
    python ingest_real_threats.py --dataset all --batch 64 --clear
"""
import argparse
import asyncio
import os
import sys
import time
from datetime import datetime, timezone
from typing import List, Optional

# ---------------------------------------------------------------------------
# Bootstrap: ensure we can import the app modules
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env.local"))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))  # fallback
load_dotenv(os.path.join(os.path.dirname(__file__), ".env.local"))
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))  # fallback

import asyncpg
import numpy as np
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres:changethis@localhost:5433/cyberintel")
DB_URL = DB_URL.replace("postgresql+asyncpg://", "postgresql://").replace("+asyncpg", "")

EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"   # 80 MB, 384-dim, <50 ms inference
EMBEDDING_DIM = 384

DATASETS = {
    "prompt-injections": {
        "hf_path": "deepset/prompt-injections",
        "split": "train",
        "text_col": "text",
        "label_col": "label",
        "category": "prompt_injection",
        "source": "deepset/prompt-injections@HuggingFace",
    },
    "jailbreak": {
        "hf_path": "rubend18/ChatGPT-Jailbreak-Prompts",
        "split": "train",
        "text_col": "Prompt",
        "label_col": None,  # unlabelled — treat all as threats
        "category": "jailbreak",
        "source": "rubend18/ChatGPT-Jailbreak-Prompts@HuggingFace",
    },
    "jasper-injection": {
        "hf_path": "JasperLS/prompt-injection",
        "split": "train",
        "text_col": "text",
        "label_col": "label",
        "category": "prompt_injection",
        "source": "JasperLS/prompt-injection@HuggingFace",
    },
}

# ---------------------------------------------------------------------------
# Database Setup
# ---------------------------------------------------------------------------

CREATE_EXTENSION_SQL = """
CREATE EXTENSION IF NOT EXISTS vector;
"""

CREATE_TABLE_SQL = f"""
CREATE TABLE IF NOT EXISTS threat_vectors (
    id          SERIAL PRIMARY KEY,
    text        TEXT NOT NULL,
    category    VARCHAR(64) NOT NULL,
    source      VARCHAR(128),
    severity    SMALLINT DEFAULT 3,          -- 1=low 2=medium 3=high 4=critical
    is_active   BOOLEAN DEFAULT TRUE,
    embedding   vector({EMBEDDING_DIM}),
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
"""

CREATE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS threat_vectors_embedding_idx
    ON threat_vectors
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
"""


async def setup_database(conn: asyncpg.Connection, clear: bool = False):
    """Install pgvector extension and create the threat_vectors table."""
    print("[DB] Installing pgvector extension...")
    await conn.execute(CREATE_EXTENSION_SQL)
    
    if clear:
        print("[DB] Clearing existing threat_vectors table...")
        await conn.execute("DROP TABLE IF EXISTS threat_vectors CASCADE;")

    print("[DB] Creating threat_vectors table...")
    await conn.execute(CREATE_TABLE_SQL)
    print("[DB] Creating IVFFlat cosine similarity index...")
    await conn.execute(CREATE_INDEX_SQL)
    print("[DB] Database setup complete.\n")


# ---------------------------------------------------------------------------
# Embedding Engine
# ---------------------------------------------------------------------------

class EmbeddingEngine:
    """Local SentenceTransformer wrapper with batch inference."""

    def __init__(self, model_name: str = EMBEDDING_MODEL_NAME):
        print(f"[EMBED] Loading model '{model_name}' (first run downloads ~80MB)...")
        self.model = SentenceTransformer(model_name)
        print(f"[EMBED] Model ready. Embedding dimension: {self.model.get_sentence_embedding_dimension()}\n")

    def encode_batch(self, texts: List[str], batch_size: int = 64) -> np.ndarray:
        """Encode texts into normalised L2 unit vectors."""
        return self.model.encode(
            texts,
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
            convert_to_numpy=True,
        )


# ---------------------------------------------------------------------------
# Dataset Loader
# ---------------------------------------------------------------------------

def load_threats_from_hf(dataset_key: str) -> List[dict]:
    """Load a HuggingFace dataset and return a list of threat dicts."""
    cfg = DATASETS[dataset_key]
    print(f"[HF] Downloading '{cfg['hf_path']}' split='{cfg['split']}'...")
    
    try:
        from datasets import load_dataset
        ds = load_dataset(cfg["hf_path"], split=cfg["split"], trust_remote_code=True)
    except Exception as exc:
        print(f"[HF][WARN] Could not load '{cfg['hf_path']}': {exc}")
        return []

    threats = []
    for row in ds:
        text = row.get(cfg["text_col"], "").strip()
        if not text or len(text) < 10:
            continue

        # Determine if this is a genuine threat (label=1 or unlabelled)
        label = row.get(cfg["label_col"], 1) if cfg["label_col"] else 1
        if label == 0:  # Benign sample — skip
            continue

        # Estimate severity from text length and aggressiveness heuristic
        severity = 3  # default HIGH
        aggressive_kws = ["ignore all", "bypass", "jailbreak", "system prompt", "DAN", "STAN",
                          "evil", "developer mode", "pretend", "disregard", "override"]
        if any(kw.lower() in text.lower() for kw in aggressive_kws):
            severity = 4  # CRITICAL

        threats.append({
            "text": text,
            "category": cfg["category"],
            "source": cfg["source"],
            "severity": severity,
        })

    print(f"[HF] Loaded {len(threats)} real threat samples from '{cfg['hf_path']}'.\n")
    return threats


# ---------------------------------------------------------------------------
# Ingestion Writer
# ---------------------------------------------------------------------------

async def ingest_threats(
    conn: asyncpg.Connection,
    threats: List[dict],
    engine: EmbeddingEngine,
    batch_size: int = 64,
):
    """Embed and insert threat vectors into PostgreSQL."""
    if not threats:
        print("[INGEST] No threats to ingest.")
        return

    texts = [t["text"] for t in threats]
    print(f"[INGEST] Encoding {len(texts)} threat texts into {EMBEDDING_DIM}-dim vectors...")

    # Batch encode
    start = time.perf_counter()
    embeddings = engine.encode_batch(texts, batch_size=batch_size)
    elapsed = time.perf_counter() - start
    print(f"[INGEST] Embedding complete in {elapsed:.2f}s ({len(texts)/elapsed:.0f} samples/sec).\n")

    # Batch insert using asyncpg executemany
    records = [
        (
            t["text"],
            t["category"],
            t["source"],
            t["severity"],
            # Convert the list to a string like "[0.1, 0.2, ...]"
            # This string format is automatically parsed as a vector by pgvector
            str(embedding.tolist()) 
        )
        for t, embedding in zip(threats, embeddings)
    ]

    print(f"[INGEST] Writing {len(records)} vectors to PostgreSQL...")
    inserted = 0
    for i in tqdm(range(0, len(records), batch_size), desc="Inserting batches"):
        batch = records[i : i + batch_size]
        await conn.executemany(
            """
            INSERT INTO threat_vectors (text, category, source, severity, embedding)
            VALUES ($1, $2, $3, $4, $5::vector)
            ON CONFLICT DO NOTHING
            """,
            batch,
        )
        inserted += len(batch)

    print(f"\n[INGEST] Successfully persisted {inserted} threat vectors.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main(dataset_keys: List[str], batch_size: int, clear: bool):
    conn = await asyncpg.connect(DB_URL, timeout=10)
    print(f"[DB] Connected to PostgreSQL at {DB_URL.split('@')[-1]}")

    await setup_database(conn, clear=clear)

    engine = EmbeddingEngine()

    total_ingested = 0
    for key in dataset_keys:
        threats = load_threats_from_hf(key)
        await ingest_threats(conn, threats, engine, batch_size=batch_size)
        total_ingested += len(threats)

    await conn.close()

    print(f"\n{'='*60}")
    print(f"  INGESTION COMPLETE: {total_ingested} real threat vectors")
    print(f"  Stored in: PostgreSQL > threat_vectors (pgvector)")
    print(f"  Model used: {EMBEDDING_MODEL_NAME} ({EMBEDDING_DIM}-dim)")
    print(f"  Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest real prompt injection vectors into pgvector.")
    parser.add_argument("--dataset", default="all", help="Dataset key or 'all'")
    parser.add_argument("--batch", type=int, default=64, help="Embedding batch size")
    parser.add_argument("--clear", action="store_true", help="Drop and recreate threat_vectors table")
    args = parser.parse_args()

    keys = list(DATASETS.keys()) if args.dataset == "all" else [args.dataset]
    asyncio.run(main(keys, args.batch, args.clear))
