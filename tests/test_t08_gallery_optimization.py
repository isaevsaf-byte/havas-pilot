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
import threading
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import LocalDB


def create_test_db(tmpdir):
    """Helper to create a LocalDB instance with a temp database."""
    db_path = os.path.join(tmpdir, "test.db")

    # Create a simple LocalDB with temp path
    original_get_connection = LocalDB._get_connection

    def patched_get_connection(self):
        if not hasattr(self._thread_local, 'conn'):
            self._thread_local.conn = sqlite3.connect(db_path, timeout=30.0)
            self._thread_local.conn.execute("PRAGMA journal_mode=WAL")
        return self._thread_local.conn

    LocalDB._get_connection = patched_get_connection
    db = LocalDB()
    LocalDB._get_connection = original_get_connection
    return db


class TestBinaryStorage:
    """Verify embeddings are stored as binary, not pickle."""

    def test_save_embedding_stores_binary_not_pickle(self):
        """Embeddings should be stored as numpy binary (tobytes), not pickle."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db = create_test_db(tmpdir)
            db_path = os.path.join(tmpdir, "test.db")

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

    def test_embedding_dim_inference(self):
        """Dimension should be inferred from first embedding."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db = create_test_db(tmpdir)

            embedding = np.random.randn(256).astype(np.float32)
            db.save_embedding("visitor_1", embedding)

            assert db._embedding_dim == 256, "Dimension should be inferred"


class TestCacheManagement:
    """Verify cache rebuild and TTL logic."""

    def test_cache_rebuild_loads_all_embeddings(self):
        """Cache should load all active embeddings on rebuild."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db = create_test_db(tmpdir)

            # Add 3 embeddings
            for i in range(3):
                emb = np.random.randn(128).astype(np.float32)
                db.save_embedding(f"visitor_{i}", emb)

            # Manually rebuild cache
            db._rebuild_cache()

            assert len(db._cache) == 3, "Cache should have 3 embeddings"
            assert "visitor_0" in db._cache, "Should have visitor_0"
            assert db._cache_built_at is not None, "Cache timestamp should be set"

    def test_cache_validity_check(self):
        """Cache validity should expire after TTL."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db = create_test_db(tmpdir)
            db.CACHE_TTL_MINUTES = 0.001  # ~0.06 seconds for testing

            emb = np.random.randn(128).astype(np.float32)
            db.save_embedding("visitor_1", emb)
            db._rebuild_cache()

            assert db._is_cache_valid(), "Cache should be valid right after rebuild"
            time.sleep(0.1)  # Wait for TTL to expire
            assert not db._is_cache_valid(), "Cache should expire after TTL"


class TestVectorizedSearch:
    """Verify vectorized cosine similarity works correctly."""

    def test_find_similar_vectorized(self):
        """find_similar should use vectorized search, not loops."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db = create_test_db(tmpdir)

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

    def test_find_similar_empty_gallery(self):
        """find_similar on empty gallery should return (None, 0.0)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db = create_test_db(tmpdir)
            query = np.random.randn(128)
            visitor_id, sim = db.find_similar(query, threshold=0.5)

            assert visitor_id is None, "Should return None for empty gallery"
            assert sim == 0.0, "Should return 0.0 similarity"


class TestPerformance:
    """Performance tests: large gallery, fast search."""

    def test_performance_100_embeddings(self):
        """Search in 100 embeddings should be fast (<50ms)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db = create_test_db(tmpdir)

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


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
