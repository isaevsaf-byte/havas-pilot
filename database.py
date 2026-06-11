import sqlite3
import pickle
import numpy as np
from datetime import datetime, timezone, timedelta

import config


class LocalDB:
    # SQLite store for visitor embeddings.
    # Tracks unique visitors, visit counts, and first/last seen timestamps.

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

    def cleanup_old(self):
        # Embeddings older than GALLERY_TTL_DAYS can no longer match anyway
        # (visitor appearance changes) and slow down find_similar.
        cutoff = (datetime.now(timezone.utc) - timedelta(days=config.GALLERY_TTL_DAYS)).isoformat()
        self.conn.execute("DELETE FROM embeddings WHERE last_seen < ?", (cutoff,))
        self.conn.commit()

    def save_embedding(self, visitor_id, embedding):
        now = datetime.now(timezone.utc).isoformat()
        blob = pickle.dumps(embedding)
        self.conn.execute(
            """
            INSERT INTO embeddings (visitor_id, embedding, first_seen, last_seen)
            VALUES (?, ?, ?, ?)
            """,
            (visitor_id, blob, now, now),
        )
        self.conn.commit()

    def find_similar(self, embedding, threshold):
        cutoff = (datetime.now(timezone.utc) - timedelta(days=config.GALLERY_TTL_DAYS)).isoformat()
        rows = self.conn.execute(
            "SELECT visitor_id, embedding FROM embeddings WHERE last_seen >= ?",
            (cutoff,),
        ).fetchall()

        best_id, best_sim = None, 0.0
        for visitor_id, blob in rows:
            stored = pickle.loads(blob)
            sim = _cosine_similarity(embedding, stored)
            if sim > best_sim:
                best_sim = sim
                best_id = visitor_id

        if best_sim > threshold:
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
            return best_id, best_sim

        return None, 0.0


def _cosine_similarity(a, b):
    a, b = np.array(a, dtype=float), np.array(b, dtype=float)
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


class CloudDB:
    # Supabase client for logging visits and heartbeats.
    # Falls back to console output when SUPABASE_URL is not configured.

    def __init__(self):
        self.offline = not config.SUPABASE_URL
        if self.offline:
            print("[CloudDB] No SUPABASE_URL — running in offline mode")
            self.client = None
        else:
            from supabase import create_client
            self.client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)

    def log_visit(self, timestamp, direction, is_repeat, visitor_id):
        payload = {
            "timestamp": timestamp,
            "direction": direction,
            "is_repeat": is_repeat,
            "visitor_id": visitor_id,
            "store": config.STORE_NAME,
        }
        if self.offline:
            print(f"[CloudDB] visit: {payload}")
            return
        self.client.table("visits").insert(payload).execute()

    def log_heartbeat(self):
        now = datetime.now(timezone.utc).isoformat()
        payload = {"store": config.STORE_NAME, "last_seen": now}
        if self.offline:
            print(f"[CloudDB] heartbeat: {payload}")
            return
        self.client.table("heartbeat").upsert(payload, on_conflict="store").execute()
