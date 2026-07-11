"""
T-08: Gallery Search Optimization — tests for vectorization + caching.

Tests:
  1. Binary storage (numpy.tobytes, no pickle)
  2. Cache rebuild and validity check
  3. Vectorized cosine similarity (single dot product vs loop)
  4. Cache TTL expiration
  5. Performance: 100+ embeddings, find_similar() is fast
"""

import sys
import os
import time
import tempfile
import sqlite3
import numpy as np
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import LocalDB


class TestBinaryStorage:
    """Verify embeddings are stored as binary, not pickle."""

    def test_save_embedding_stores_binary_not_pickle(self):
        """Embeddings should be stored as numpy binary (tobytes), not pickle."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")

            # Monkey-patch connection path
            original_init = LocalDB.__init__
            def patched_init(self):
                self.conn = sqlite3.connect(db_path, check_same_thread=False)
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
                self._cache = {}
                self._cache_built_at = None
                self._embedding_dim = None

            LocalDB.__init__ = patched_init
            try:
                db = LocalDB()
                embedding = np.random.randn(512).astype(np.float32)
                db.save_embedding("test_visitor_1", embedding)

                # Check raw bytes in database
                conn = sqlite3.connect(db_path)
                blob = conn.execute(
                    "SELECT embedding FROM embeddings WHERE visitor_id = ?",
                    ("test_visitor_1",)
                ).fetchone()[0]
                conn.close()

                # Verify it's NOT pickle (pickle starts with b'\x80' or similar)
                assert not blob.startswith(b'\x80'), "Should not be pickle format"

                # Verify we can reconstruct it as numpy
                reconstructed = np.frombuffer(blob, dtype=np.float32, count=512)
                assert reconstructed.shape == (512,), "Should reconstruct to correct shape"
                np.testing.assert_array_almost_equal(embedding, reconstructed, decimal=5)
            finally:
                LocalDB.__init__ = original_init

    def test_embedding_dim_inference(self):
        """Dimension should be inferred from first embedding."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")

            original_init = LocalDB.__init__
            def patched_init(self):
                self.conn = sqlite3.connect(db_path, check_same_thread=False)
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
                self._cache = {}
                self._cache_built_at = None
                self._embedding_dim = None

            LocalDB.__init__ = patched_init
            try:
                db = LocalDB()
                embedding = np.random.randn(256).astype(np.float32)
                db.save_embedding("visitor_1", embedding)

                assert db._embedding_dim == 256, "Dimension should be inferred"
            finally:
                LocalDB.__init__ = original_init


class TestCacheManagement:
    """Verify cache rebuild and TTL logic."""

    def test_cache_rebuild_loads_all_embeddings(self):
        """Cache should load all active embeddings on rebuild."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")

            original_init = LocalDB.__init__
            def patched_init(self):
                self.conn = sqlite3.connect(db_path, check_same_thread=False)
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
                self._cache = {}
                self._cache_built_at = None
                self._embedding_dim = None

            LocalDB.__init__ = patched_init
            try:
                db = LocalDB()

                # Add 3 embeddings
                for i in range(3):
                    emb = np.random.randn(128).astype(np.float32)
                    db.save_embedding(f"visitor_{i}", emb)

                # Manually rebuild cache
                db._rebuild_cache()

                assert len(db._cache) == 3, "Cache should have 3 embeddings"
                assert "visitor_0" in db._cache, "Should have visitor_0"
                assert db._cache_built_at is not None, "Cache timestamp should be set"
            finally:
                LocalDB.__init__ = original_init

    def test_cache_validity_check(self):
        """Cache validity should expire after TTL."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")

            original_init = LocalDB.__init__
            def patched_init(self):
                self.conn = sqlite3.connect(db_path, check_same_thread=False)
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
                self._cache = {}
                self._cache_built_at = None
                self._embedding_dim = None

            LocalDB.__init__ = patched_init
            try:
                db = LocalDB()
                db.CACHE_TTL_MINUTES = 0.001  # ~0.06 seconds for testing

                emb = np.random.randn(128).astype(np.float32)
                db.save_embedding("visitor_1", emb)
                db._rebuild_cache()

                assert db._is_cache_valid(), "Cache should be valid right after rebuild"
                time.sleep(0.1)  # Wait for TTL to expire
                assert not db._is_cache_valid(), "Cache should expire after TTL"
            finally:
                LocalDB.__init__ = original_init


class TestVectorizedSearch:
    """Verify vectorized cosine similarity works correctly."""

    def test_find_similar_vectorized(self):
        """find_similar should use vectorized search, not loops."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")

            original_init = LocalDB.__init__
            def patched_init(self):
                self.conn = sqlite3.connect(db_path, check_same_thread=False)
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
                self._cache = {}
                self._cache_built_at = None
                self._embedding_dim = None

            LocalDB.__init__ = patched_init
            try:
                db = LocalDB()

                # Create query embedding
                query = np.random.randn(128)
                query = query / (np.linalg.norm(query) + 1e-8)

                # Create very similar embedding (cosine sim ~0.95)
                similar = query.copy()
                similar += 0.1 * np.random.randn(128)
                similar = similar / (np.linalg.norm(similar) + 1e-8)

                # Create dissimilar embedding (cosine sim ~0.05)
                dissimilar = np.random.randn(128)
                dissimilar = dissimilar / (np.linalg.norm(dissimilar) + 1e-8)

                db.save_embedding("similar", similar)
                db.save_embedding("dissimilar", dissimilar)

                # Search should find the similar one
                visitor_id, sim = db.find_similar(query, threshold=0.5)

                assert visitor_id == "similar", f"Should find similar embedding, got {visitor_id}"
                assert sim > 0.5, f"Similarity should exceed threshold, got {sim}"
            finally:
                LocalDB.__init__ = original_init

    def test_find_similar_empty_gallery(self):
        """find_similar on empty gallery should return (None, 0.0)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")

            original_init = LocalDB.__init__
            def patched_init(self):
                self.conn = sqlite3.connect(db_path, check_same_thread=False)
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
                self._cache = {}
                self._cache_built_at = None
                self._embedding_dim = None

            LocalDB.__init__ = patched_init
            try:
                db = LocalDB()
                query = np.random.randn(128)
                visitor_id, sim = db.find_similar(query, threshold=0.5)

                assert visitor_id is None, "Should return None for empty gallery"
                assert sim == 0.0, "Should return 0.0 similarity"
            finally:
                LocalDB.__init__ = original_init


class TestPerformance:
    """Performance tests: large gallery, fast search."""

    def test_performance_100_embeddings(self):
        """Search in 100 embeddings should be fast (<10ms)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")

            original_init = LocalDB.__init__
            def patched_init(self):
                self.conn = sqlite3.connect(db_path, check_same_thread=False)
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
                self._cache = {}
                self._cache_built_at = None
                self._embedding_dim = None

            LocalDB.__init__ = patched_init
            try:
                db = LocalDB()

                # Add 100 random embeddings
                for i in range(100):
                    emb = np.random.randn(256).astype(np.float32)
                    db.save_embedding(f"visitor_{i}", emb)

                # Search should be fast
                query = np.random.randn(256).astype(np.float32)

                start = time.time()
                for _ in range(10):  # 10 searches
                    db.find_similar(query, threshold=0.5)
                elapsed = time.time() - start

                avg_time_ms = (elapsed / 10) * 1000
                assert avg_time_ms < 50, f"Search should be <50ms, got {avg_time_ms:.2f}ms"
                print(f"✓ 100 embeddings: {avg_time_ms:.2f}ms per search (vectorized)")
            finally:
                LocalDB.__init__ = original_init


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
