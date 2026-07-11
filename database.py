import logging
import sqlite3
import numpy as np
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple, Dict, List

import config

logger = logging.getLogger(__name__)


class LocalDB:
    # SQLite store for visitor embeddings.
    # Tracks unique visitors, visit counts, and first/last seen timestamps.
    # Optimized with numpy binary storage and in-memory cache.

    CACHE_TTL_MINUTES = 10  # Rebuild cache every 10 minutes to pick up new embeddings

    def __init__(self):
        self.conn = sqlite3.connect("havas_embeddings.db", check_same_thread=False)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS embeddings (
                id          INTEGER PRIMARY KEY,
                visitor_id  TEXT UNIQUE,
                embedding   BLOB,
                first_seen  TEXT,
                last_seen   TEXT,
                visit_count INTEGER DEFAULT 1
            )
        """)
        self.conn.commit()
        self.cleanup_old()

        # Cache for active gallery embeddings
        self._cache: Dict[str, np.ndarray] = {}  # visitor_id -> embedding
        self._cache_built_at: Optional[datetime] = None
        self._embedding_dim: Optional[int] = None

    def cleanup_old(self) -> None:
        # Embeddings older than GALLERY_TTL_DAYS can no longer match anyway
        # (visitor appearance changes) and slow down find_similar.
        cutoff = (datetime.now(timezone.utc) - timedelta(days=config.GALLERY_TTL_DAYS)).isoformat()
        self.conn.execute("DELETE FROM embeddings WHERE last_seen < ?", (cutoff,))
        self.conn.commit()
        # Invalidate cache after cleanup
        self._cache_built_at = None

    def save_embedding(self, visitor_id: str, embedding: np.ndarray) -> None:
        now = datetime.now(timezone.utc).isoformat()
        # Store as binary (numpy) instead of pickle — 10-100x faster
        blob = embedding.astype(np.float32).tobytes()
        self._embedding_dim = embedding.shape[0] if embedding.ndim == 1 else embedding.shape[-1]

        self.conn.execute(
            """
            INSERT INTO embeddings (visitor_id, embedding, first_seen, last_seen)
            VALUES (?, ?, ?, ?)
            """,
            (visitor_id, blob, now, now),
        )
        self.conn.commit()
        # Invalidate cache — new embedding added
        self._cache_built_at = None

    def _rebuild_cache(self) -> None:
        # Load all active embeddings into memory for vectorized search
        cutoff = (datetime.now(timezone.utc) - timedelta(days=config.GALLERY_TTL_DAYS)).isoformat()
        rows = self.conn.execute(
            "SELECT visitor_id, embedding FROM embeddings WHERE last_seen >= ?",
            (cutoff,),
        ).fetchall()

        self._cache.clear()
        for visitor_id, blob in rows:
            if self._embedding_dim is None:
                # Infer dimension from first blob
                self._embedding_dim = len(blob) // 4  # float32 = 4 bytes
            embedding = np.frombuffer(blob, dtype=np.float32, count=self._embedding_dim)
            self._cache[visitor_id] = embedding

        self._cache_built_at = datetime.now(timezone.utc)
        logger.debug(f"Built cache with {len(self._cache)} embeddings (dim={self._embedding_dim})")

    def _is_cache_valid(self) -> bool:
        if self._cache_built_at is None:
            return False
        age = datetime.now(timezone.utc) - self._cache_built_at
        return age.total_seconds() < self.CACHE_TTL_MINUTES * 60

    def find_similar(self, embedding: np.ndarray, threshold: float) -> Tuple[Optional[str], float]:
        # Ensure cache is built and valid
        if not self._is_cache_valid():
            self._rebuild_cache()

        if not self._cache:
            return None, 0.0

        embedding = embedding.astype(np.float32)

        # Vectorized search: build matrix and use dot product
        visitor_ids = list(self._cache.keys())
        gallery_matrix = np.array([self._cache[vid] for vid in visitor_ids])  # (n_visitors, D)

        # Cosine similarity = (A @ B) / (||A|| * ||B||)
        # Normalize embeddings once
        embedding_norm = embedding / (np.linalg.norm(embedding) + 1e-8)
        gallery_norms = gallery_matrix / (np.linalg.norm(gallery_matrix, axis=1, keepdims=True) + 1e-8)

        # Vectorized dot product
        similarities = gallery_norms @ embedding_norm  # (n_visitors,)
        best_idx = int(np.argmax(similarities))
        best_sim = float(similarities[best_idx])

        if best_sim > threshold:
            best_id = visitor_ids[best_idx]
            now = datetime.now(timezone.utc).isoformat()
            self.conn.execute(
                """
                UPDATE embeddings
                SET last_seen = ?, visit_count = visit_count + 1
                WHERE visitor_id = ?
                """,
                (now, best_id),
            )
            self.conn.commit()
            # Invalidate cache — visitor updated
            self._cache_built_at = None
            return best_id, best_sim

        return None, 0.0


class CloudDB:
    # Supabase client for logging visits and heartbeats.
    # Falls back to console output when SUPABASE_URL is not configured.

    def __init__(self):
        self.offline = not config.SUPABASE_URL
        if self.offline:
            logger.warning("No SUPABASE_URL — running in offline mode")
            self.client = None
        else:
            from supabase import create_client
            self.client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)

    def log_visit(self, timestamp: str, direction: str, is_repeat: bool, visitor_id: str) -> None:
        payload = {
            "timestamp": timestamp,
            "direction": direction,
            "is_repeat": is_repeat,
            "visitor_id": visitor_id,
            "store": config.STORE_NAME,
        }
        if self.offline:
            logger.info("visit (offline): %s", payload)
            return
        self.client.table("visits").insert(payload).execute()

    def log_heartbeat(self) -> None:
        now = datetime.now(timezone.utc).isoformat()
        payload = {"store": config.STORE_NAME, "last_seen": now}
        if self.offline:
            logger.debug("heartbeat (offline): %s", payload)
            return
        self.client.table("heartbeat").upsert(payload, on_conflict="store").execute()
