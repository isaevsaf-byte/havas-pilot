"""
T-10: SQLite Thread Safety — tests for absolute path + Lock + thread-local connections.

Tests:
  1. Database uses absolute path (not relative)
  2. Path is created in data/ directory relative to database.py
  3. Thread-safe with Lock for race conditions
  4. Thread-local connections (no check_same_thread=False needed)
  5. WAL mode for concurrent access
"""

import sys
import os
import tempfile
import threading
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import LocalDB


class TestAbsolutePath:
    """Verify database uses absolute path in data/ directory."""

    def test_db_path_is_absolute(self):
        """Database path should be absolute, not relative."""
        db = LocalDB()

        # Verify the db_path is absolute
        assert db._db_path.is_absolute(), f"Path should be absolute, got {db._db_path}"

    def test_db_path_is_in_data_directory(self):
        """Database should be in data/ subdirectory."""
        db = LocalDB()

        # Check that the parent directory is named "data"
        assert db._db_path.parent.name == "data", f"Path should be in data/ dir, got {db._db_path}"

    def test_data_directory_is_created(self):
        """data/ directory should be created if it doesn't exist."""
        # The directory should exist after LocalDB initialization
        data_dir = Path(__file__).parent.parent / "data"
        assert data_dir.exists(), "data/ directory should be created"
        assert data_dir.is_dir(), "data/ should be a directory"


class TestThreadLocal:
    """Verify thread-local connections are used."""

    def test_connections_per_thread(self):
        """Each thread should get its own connection."""
        db = LocalDB()

        connections = {}
        lock = threading.Lock()

        def get_connection_id():
            conn = db._get_connection()
            conn_id = id(conn)
            with lock:
                connections[threading.current_thread().name] = conn_id

        # Create multiple threads and get connection IDs
        threads = []
        for i in range(3):
            t = threading.Thread(target=get_connection_id, name=f"Thread-{i}")
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # All connection IDs should be unique (different threads get different connections)
        conn_ids = list(connections.values())
        assert len(conn_ids) == len(set(conn_ids)), "Each thread should get a unique connection"

    def test_same_thread_reuses_connection(self):
        """Same thread should reuse the same connection."""
        db = LocalDB()

        conn1 = db._get_connection()
        conn2 = db._get_connection()

        assert id(conn1) == id(conn2), "Same thread should reuse same connection"


class TestLockPresence:
    """Verify Lock is present and used correctly."""

    def test_db_has_lock(self):
        """LocalDB should have _db_lock attribute."""
        db = LocalDB()
        assert hasattr(db, "_db_lock"), "LocalDB should have _db_lock"
        # Check that it's an RLock by checking its type name
        assert type(db._db_lock).__name__ == 'RLock', f"_db_lock should be an RLock, got {type(db._db_lock).__name__}"

    def test_db_has_thread_local_storage(self):
        """LocalDB should have thread-local storage."""
        db = LocalDB()
        assert hasattr(db, "_thread_local"), "LocalDB should have _thread_local"
        assert isinstance(db._thread_local, threading.local), "_thread_local should be threading.local"

    def test_no_check_same_thread_false(self):
        """Database should NOT use check_same_thread=False."""
        # Read database.py source to verify
        db_file = Path(__file__).parent.parent / "database.py"
        content = db_file.read_text()

        assert "check_same_thread=False" not in content, \
            "check_same_thread=False should be removed"

    def test_uses_wal_mode(self):
        """Database should enable WAL mode for concurrency."""
        # Read database.py source to verify
        db_file = Path(__file__).parent.parent / "database.py"
        content = db_file.read_text()

        assert "journal_mode=WAL" in content or "WAL" in content, \
            "Database should enable WAL mode for concurrent access"


class TestBasicOperations:
    """Verify basic database operations work."""

    def test_save_and_find_embedding(self):
        """Basic save and find operations should work."""
        db = LocalDB()

        # Save an embedding
        query = np.random.randn(128).astype(np.float32)
        query_norm = query / (np.linalg.norm(query) + 1e-8)

        db.save_embedding("visitor_1", query_norm)

        # Create a very similar embedding
        similar = query_norm.copy()
        similar += 0.01 * np.random.randn(128)
        similar = similar / (np.linalg.norm(similar) + 1e-8)

        # Search should find it
        visitor_id, sim = db.find_similar(similar, threshold=0.5)

        assert visitor_id == "visitor_1", f"Should find visitor_1, got {visitor_id}"
        assert sim > 0.5, f"Similarity should exceed threshold, got {sim}"

    def test_concurrent_operations_dont_crash(self):
        """Concurrent operations should complete without errors."""
        db = LocalDB()

        errors = []
        lock = threading.Lock()

        def save_embeddings():
            try:
                for i in range(5):
                    emb = np.random.randn(128).astype(np.float32)
                    visitor_id = f"visitor_save_{threading.current_thread().name}_{i}"
                    db.save_embedding(visitor_id, emb)
            except Exception as e:
                with lock:
                    errors.append(str(e))

        def search_embeddings():
            try:
                for _ in range(5):
                    query = np.random.randn(128).astype(np.float32)
                    db.find_similar(query, threshold=0.5)
            except Exception as e:
                with lock:
                    errors.append(str(e))

        # Start multiple threads with different operations
        threads = []
        for i in range(2):
            t = threading.Thread(target=save_embeddings, name=f"Saver-{i}")
            threads.append(t)
            t.start()

        for i in range(2):
            t = threading.Thread(target=search_embeddings, name=f"Searcher-{i}")
            threads.append(t)
            t.start()

        # Wait for all threads
        for t in threads:
            t.join()

        # No errors should occur
        assert len(errors) == 0, f"Concurrent operations should not error: {errors}"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
