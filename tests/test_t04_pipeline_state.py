"""Tests for T-04: thread-safe PipelineState."""

import sys
import threading
import time
from pathlib import Path

import pytest

# Project root on path so we can import main / config without installing
sys.path.insert(0, str(Path(__file__).parent.parent))

import config  # noqa: E402

# Speed up cooldown tests
config.COOLDOWN_SECONDS = 0.05

from state import PipelineState  # noqa: E402


# ---------------------------------------------------------------------------
# record_first_position
# ---------------------------------------------------------------------------

class TestRecordFirstPosition:
    def test_records_first_cy(self):
        state = PipelineState()
        state.record_first_position(1, 100)
        assert state._first_positions[1] == 100

    def test_ignores_subsequent_calls(self):
        state = PipelineState()
        state.record_first_position(1, 100)
        state.record_first_position(1, 200)
        assert state._first_positions[1] == 100

    def test_independent_tracks(self):
        state = PipelineState()
        state.record_first_position(1, 100)
        state.record_first_position(2, 300)
        assert state._first_positions[1] == 100
        assert state._first_positions[2] == 300


# ---------------------------------------------------------------------------
# should_count
# ---------------------------------------------------------------------------

class TestShouldCount:
    def test_first_call_returns_true(self):
        state = PipelineState()
        assert state.should_count(42) is True

    def test_second_call_within_cooldown_returns_false(self):
        state = PipelineState()
        state.should_count(42)
        assert state.should_count(42) is False

    def test_call_after_cooldown_returns_true(self):
        state = PipelineState()
        state.should_count(42)
        time.sleep(config.COOLDOWN_SECONDS + 0.02)
        assert state.should_count(42) is True

    def test_independent_tracks_do_not_share_cooldown(self):
        state = PipelineState()
        assert state.should_count(1) is True
        assert state.should_count(2) is True


# ---------------------------------------------------------------------------
# get_direction
# ---------------------------------------------------------------------------

class TestGetDirection:
    def test_no_first_position_returns_in(self):
        state = PipelineState()
        assert state.get_direction(1, 50) == "IN"

    def test_moved_down_returns_in(self):
        state = PipelineState()
        state.record_first_position(1, 100)
        assert state.get_direction(1, 150) == "IN"

    def test_moved_up_returns_out(self):
        state = PipelineState()
        state.record_first_position(1, 100)
        assert state.get_direction(1, 50) == "OUT"

    def test_same_position_returns_in(self):
        state = PipelineState()
        state.record_first_position(1, 100)
        assert state.get_direction(1, 100) == "IN"


# ---------------------------------------------------------------------------
# Concurrency
# ---------------------------------------------------------------------------

class TestConcurrency:
    def test_concurrent_should_count_exactly_one_true(self):
        """With N threads racing on the same track_id, exactly one wins."""
        state = PipelineState()
        results = []
        results_lock = threading.Lock()

        def worker():
            r = state.should_count(99)
            with results_lock:
                results.append(r)

        threads = [threading.Thread(target=worker) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 20
        assert results.count(True) == 1
        assert results.count(False) == 19

    def test_concurrent_record_first_position_stable(self):
        """Concurrent writers all write different values; exactly one is kept."""
        state = PipelineState()
        values = list(range(0, 200, 10))  # 20 distinct values

        def worker(cy):
            state.record_first_position(7, cy)

        threads = [threading.Thread(target=worker, args=(v,)) for v in values]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert 7 in state._first_positions
        assert state._first_positions[7] in values

    def test_concurrent_get_direction_consistent(self):
        """Reads while a writer runs never raise; direction stays valid."""
        state = PipelineState()
        state.record_first_position(5, 100)
        errors = []

        def reader():
            for _ in range(50):
                d = state.get_direction(5, 150)
                if d not in ("IN", "OUT"):
                    errors.append(d)

        def writer():
            for i in range(50):
                state.record_first_position(5, i)

        threads = [threading.Thread(target=reader) for _ in range(4)]
        threads.append(threading.Thread(target=writer))
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
