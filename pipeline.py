"""Pipeline functions for frame processing and visitor tracking.

This module contains reusable functions that process video frames and
track visitors, isolated from I/O and initialization logic.
"""

import logging
import queue
from datetime import datetime, timezone
from typing import List, Dict, Any

import cv2
import numpy as np

import config

logger = logging.getLogger(__name__)


def process_frame(frame: np.ndarray, detector: Any, tracker: Any) -> List[Dict[str, Any]]:
    """Detect and track persons in frame.

    Args:
        frame: Input frame (numpy array)
        detector: PersonDetector instance
        tracker: PersonTracker instance

    Returns:
        List of tracked persons with keys: bbox, track_id
    """
    detections = detector.detect(frame)
    tracks = tracker.update(detections, frame)
    return tracks


def check_visitors(
    tracks: List[Dict[str, Any]],
    frame: np.ndarray,
    reid: Any,
    state: Any,
    line_y: float,
    event_queue: queue.Queue
) -> List[Dict[str, Any]]:
    """Check if tracked persons are new/repeat visitors.

    Args:
        tracks: List of tracked persons
        frame: Input frame for crops
        reid: ReIDChecker instance
        state: PipelineState instance
        line_y: Y-coordinate of the counting line
        event_queue: Queue for events

    Returns:
        List of dicts with track info and reid results for rendering
    """
    results = []

    for track in tracks:
        bbox = track["bbox"]
        track_id = track["track_id"]
        x1, y1, x2, y2 = bbox
        cy = (y1 + y2) / 2

        state.record_first_position(track_id, cy)

        color = (200, 200, 200)
        label = ""
        reid_result = None

        if abs(cy - line_y) < config.LINE_TOLERANCE_PX and state.should_count(track_id):
            crop = frame[y1:y2, x1:x2]
            reid_result = reid.check(crop, track_id)

            if reid_result is not None:
                direction = state.get_direction(track_id, cy)
                event_queue.put(("visit", {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "direction": direction,
                    "is_repeat": reid_result["status"] == "repeat",
                    "visitor_id": reid_result["visitor_id"],
                }))
                short_id = reid_result["visitor_id"][:8]
                logger.info("%s | %s | visitor_%s", direction, reid_result["status"], short_id)
                color = (0, 255, 0) if reid_result["status"] == "new" else (255, 0, 0)
                label = f"{direction} | {reid_result['status']}"

        results.append({
            "bbox": bbox,
            "color": color,
            "label": label,
        })

    return results


def render_overlay(frame: np.ndarray, tracks_with_results: List[Dict[str, Any]], line_y: float) -> None:
    """Draw bounding boxes, labels, and counting line on frame.

    Args:
        frame: Input frame (modified in place)
        tracks_with_results: List of dicts with bbox, color, label
        line_y: Y-coordinate of the counting line
    """
    height, width = frame.shape[:2]

    for result in tracks_with_results:
        x1, y1, x2, y2 = result["bbox"]
        color = result["color"]
        label = result["label"]

        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        if label:
            cv2.putText(frame, label, (x1, y1 - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 1)

    cv2.line(frame, (0, line_y), (width, line_y), (0, 255, 255), 2)


def handle_heartbeat(frame_count: int, event_queue: queue.Queue) -> int:
    """Check if it's time to send heartbeat and reset counter.

    Args:
        frame_count: Current frame count
        event_queue: Queue for events

    Returns:
        Reset frame_count (0) or original value
    """
    if frame_count >= config.HEARTBEAT_EVERY_N_FRAMES:
        event_queue.put(("heartbeat", {}))
        return 0
    return frame_count
