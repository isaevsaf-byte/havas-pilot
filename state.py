"""Thread-safe pipeline state (T-04)."""

import threading
import time

import config


class PipelineState:
    """Thread-safe container for per-track mutable state.

    Both the main video loop and any future worker threads can call these
    methods safely: every read-modify-write is protected by a single lock.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._first_positions: dict = {}  # track_id -> cy at first sighting
        self._last_counted: dict = {}     # track_id -> unix time of last count

    def record_first_position(self, track_id, cy) -> None:
        """Store first-seen y-centre for track_id (ignored on subsequent calls)."""
        with self._lock:
            if track_id not in self._first_positions:
                self._first_positions[track_id] = cy

    def should_count(self, track_id) -> bool:
        """Return True and start cooldown, or False if still in cooldown."""
        now = time.time()
        with self._lock:
            last = self._last_counted.get(track_id)
            if last is not None and (now - last) < config.COOLDOWN_SECONDS:
                return False
            self._last_counted[track_id] = now
            return True

    def get_direction(self, track_id, cy) -> str:
        """Return 'IN' or 'OUT' based on first-seen vs current y-centre."""
        # Compare against where the track first appeared, not the previous frame:
        # frame-to-frame bbox jitter flips direction, entry point does not.
        with self._lock:
            first = self._first_positions.get(track_id)
        if first is None or cy == first:
            return "IN"
        return "IN" if cy > first else "OUT"
