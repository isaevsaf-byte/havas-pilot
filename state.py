"""Thread-safe pipeline state (T-04)."""

import threading
import time
from typing import Optional

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

    def is_in_cooldown(self, track_id) -> bool:
        """Return True if track_id was already counted within the cooldown window."""
        now = time.time()
        with self._lock:
            last = self._last_counted.get(track_id)
            return last is not None and (now - last) < config.COOLDOWN_SECONDS

    def mark_counted(self, track_id) -> None:
        """Start (or restart) the cooldown window for track_id."""
        with self._lock:
            self._last_counted[track_id] = time.time()

    def should_count(self, track_id) -> bool:
        """Return True and start cooldown, or False if still in cooldown.

        Kept for backward compatibility with existing callers/tests.
        check_visitors() uses is_in_cooldown()/mark_counted() directly so
        the cooldown only starts once a visit is actually recorded, not
        merely attempted (a failed ReID crop used to burn the cooldown
        with no event logged).
        """
        if self.is_in_cooldown(track_id):
            return False
        self.mark_counted(track_id)
        return True

    def get_direction(self, track_id, cy) -> Optional[str]:
        """Return 'IN' or 'OUT' based on first-seen vs current y-centre, or
        None when direction can't be determined.

        Compare against where the track first appeared, not the previous
        frame: frame-to-frame bbox jitter flips direction, entry point does
        not. cy == first (including a brand-new track_id, since
        record_first_position and get_direction are called with the same cy
        in the same frame) means this track was first seen right at the
        counting line — most often the tracker losing and re-acquiring an
        ID mid-crossing, where occlusion/frame noise is worst. Guessing
        "IN" here used to silently bias every fragmented track toward IN;
        returning None lets the caller skip logging an event it can't back.
        """
        with self._lock:
            first = self._first_positions.get(track_id)
        if first is None or cy == first:
            return None
        return "IN" if cy > first else "OUT"
