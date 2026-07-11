"""Tests for T-05: refactored main() functions."""

import sys
import queue
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

import pytest
import numpy as np
import cv2

# Project root on path
sys.path.insert(0, str(Path(__file__).parent.parent))

import config  # noqa: E402
from state import PipelineState  # noqa: E402
from pipeline import (  # noqa: E402
    process_frame,
    check_visitors,
    render_overlay,
    handle_heartbeat,
)


# ---------------------------------------------------------------------------
# process_frame
# ---------------------------------------------------------------------------

class TestProcessFrame:
    def test_calls_detector_and_tracker(self):
        """process_frame() calls detector.detect() and tracker.update()."""
        detector = Mock()
        tracker = Mock()

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        detections = [{"bbox": [10, 20, 30, 40]}]
        tracks = [{"track_id": 1, "bbox": [10, 20, 30, 40]}]

        detector.detect.return_value = detections
        tracker.update.return_value = tracks

        result = process_frame(frame, detector, tracker)

        detector.detect.assert_called_once_with(frame)
        tracker.update.assert_called_once_with(detections, frame)
        assert result == tracks

    def test_returns_tracker_output(self):
        """process_frame() returns exactly what tracker.update() returns."""
        detector = Mock()
        tracker = Mock()

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        expected_tracks = [
            {"track_id": 1, "bbox": [10, 20, 30, 40]},
            {"track_id": 2, "bbox": [50, 60, 70, 80]},
        ]

        detector.detect.return_value = []
        tracker.update.return_value = expected_tracks

        result = process_frame(frame, detector, tracker)

        assert result == expected_tracks
        assert len(result) == 2


# ---------------------------------------------------------------------------
# check_visitors
# ---------------------------------------------------------------------------

class TestCheckVisitors:
    def test_empty_tracks_returns_empty_results(self):
        """check_visitors() with no tracks returns empty list."""
        reid = Mock()
        state = PipelineState()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        event_queue = queue.Queue()

        result = check_visitors([], frame, reid, state, 240, event_queue)

        assert result == []

    def test_records_first_position_for_each_track(self):
        """check_visitors() records first position for each track."""
        reid = Mock()
        state = PipelineState()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        event_queue = queue.Queue()

        tracks = [
            {"track_id": 1, "bbox": [10, 100, 30, 200]},
            {"track_id": 2, "bbox": [50, 150, 70, 250]},
        ]

        reid.check.return_value = None

        check_visitors(tracks, frame, reid, state, 240, event_queue)

        # Check that first positions were recorded
        assert 1 in state._first_positions
        assert 2 in state._first_positions

    def test_returns_results_for_all_tracks(self):
        """check_visitors() returns result dict for each track."""
        reid = Mock()
        state = PipelineState()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        event_queue = queue.Queue()

        tracks = [
            {"track_id": 1, "bbox": [10, 100, 30, 200]},
            {"track_id": 2, "bbox": [50, 150, 70, 250]},
        ]

        reid.check.return_value = None

        result = check_visitors(tracks, frame, reid, state, 240, event_queue)

        assert len(result) == 2
        assert all("bbox" in r and "color" in r and "label" in r for r in result)

    def test_queues_visit_event_on_reid_match(self):
        """check_visitors() queues a 'visit' event when reid.check returns result."""
        reid = Mock()
        state = PipelineState()
        state.record_first_position(1, 100)  # So should_count returns True first call
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        event_queue = queue.Queue()

        tracks = [{"track_id": 1, "bbox": [10, 100, 30, 200]}]

        reid.check.return_value = {
            "status": "new",
            "visitor_id": "abc123def456",
        }

        check_visitors(tracks, frame, reid, state, 150, event_queue)

        assert not event_queue.empty()
        kind, payload = event_queue.get()
        assert kind == "visit"
        assert payload["direction"] in ("IN", "OUT")
        assert payload["visitor_id"] == "abc123def456"
        assert payload["is_repeat"] is False

    def test_no_event_when_reid_returns_none(self):
        """check_visitors() doesn't queue event when reid.check returns None."""
        reid = Mock()
        state = PipelineState()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        event_queue = queue.Queue()

        tracks = [{"track_id": 1, "bbox": [10, 100, 30, 200]}]

        reid.check.return_value = None

        check_visitors(tracks, frame, reid, state, 240, event_queue)

        assert event_queue.empty()

    def test_result_colors_by_status(self):
        """check_visitors() sets color based on reid status (new/repeat)."""
        reid = Mock()
        state = PipelineState()
        state.record_first_position(1, 100)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        event_queue = queue.Queue()

        tracks = [{"track_id": 1, "bbox": [10, 100, 30, 200]}]

        reid.check.return_value = {
            "status": "new",
            "visitor_id": "abc123def456",
        }

        result = check_visitors(tracks, frame, reid, state, 150, event_queue)

        assert result[0]["color"] == (0, 255, 0)  # Green for new

    def test_default_color_when_not_counted(self):
        """check_visitors() uses default color when track not at line."""
        reid = Mock()
        state = PipelineState()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        event_queue = queue.Queue()

        tracks = [{"track_id": 1, "bbox": [10, 100, 30, 200]}]

        reid.check.return_value = None

        result = check_visitors(tracks, frame, reid, state, 400, event_queue)

        assert result[0]["color"] == (200, 200, 200)  # Gray (default)
        assert result[0]["label"] == ""


# ---------------------------------------------------------------------------
# render_overlay
# ---------------------------------------------------------------------------

class TestRenderOverlay:
    def test_renders_without_error(self):
        """render_overlay() runs without raising exceptions."""
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        tracks_with_results = [
            {
                "bbox": [10, 20, 30, 40],
                "color": (0, 255, 0),
                "label": "IN | new",
            }
        ]

        render_overlay(frame, tracks_with_results, 240)

    def test_modifies_frame_in_place(self):
        """render_overlay() modifies the frame (draws on it)."""
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        original_sum = frame.sum()

        tracks_with_results = [
            {
                "bbox": [10, 20, 100, 100],
                "color": (255, 255, 255),
                "label": "IN | new",
            }
        ]

        render_overlay(frame, tracks_with_results, 240)

        # Frame should have changed (pixels were drawn)
        assert frame.sum() > original_sum

    def test_draws_line_y(self):
        """render_overlay() draws the counting line."""
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        original_sum = frame.sum()

        render_overlay(frame, [], 240)

        # Frame should have changed (line was drawn)
        assert frame.sum() > original_sum

    def test_handles_empty_tracks(self):
        """render_overlay() handles empty track list."""
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        render_overlay(frame, [], 240)

    def test_skips_label_when_empty(self):
        """render_overlay() skips putText when label is empty."""
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        tracks_with_results = [
            {
                "bbox": [10, 20, 100, 100],
                "color": (255, 255, 255),
                "label": "",
            }
        ]

        # Should not raise even though label is empty
        render_overlay(frame, tracks_with_results, 240)


# ---------------------------------------------------------------------------
# handle_heartbeat
# ---------------------------------------------------------------------------

class TestHandleHeartbeat:
    def test_returns_same_count_when_below_threshold(self):
        """handle_heartbeat() returns frame_count unchanged if below threshold."""
        event_queue = queue.Queue()
        count = 50

        result = handle_heartbeat(count, event_queue)

        assert result == 50
        assert event_queue.empty()

    def test_queues_heartbeat_at_threshold(self):
        """handle_heartbeat() queues heartbeat when frame_count >= threshold."""
        event_queue = queue.Queue()
        count = config.HEARTBEAT_EVERY_N_FRAMES

        result = handle_heartbeat(count, event_queue)

        assert not event_queue.empty()
        kind, payload = event_queue.get()
        assert kind == "heartbeat"
        assert payload == {}

    def test_resets_count_to_zero_at_threshold(self):
        """handle_heartbeat() returns 0 when threshold reached."""
        event_queue = queue.Queue()
        count = config.HEARTBEAT_EVERY_N_FRAMES

        result = handle_heartbeat(count, event_queue)

        assert result == 0

    def test_queues_heartbeat_above_threshold(self):
        """handle_heartbeat() queues heartbeat when frame_count > threshold."""
        event_queue = queue.Queue()
        count = config.HEARTBEAT_EVERY_N_FRAMES + 10

        result = handle_heartbeat(count, event_queue)

        assert not event_queue.empty()
        kind, payload = event_queue.get()
        assert kind == "heartbeat"
        assert result == 0
