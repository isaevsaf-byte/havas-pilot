import numpy as np
import supervision as sv


class PersonTracker:
    # Assigns and maintains track IDs across frames using ByteTrack.
    # Wraps supervision's ByteTrack to stay compatible with detector.py output format.

    def __init__(self):
        self.tracker = sv.ByteTrack()

    def update(self, detections, frame):
        if not detections:
            return []

        xyxy = np.array([d["bbox"] for d in detections], dtype=float)
        confidence = np.array([d["confidence"] for d in detections], dtype=float)
        class_id = np.zeros(len(detections), dtype=int)

        sv_detections = sv.Detections(
            xyxy=xyxy,
            confidence=confidence,
            class_id=class_id,
        )

        tracked = self.tracker.update_with_detections(sv_detections)

        result = []
        for i in range(len(tracked)):
            x1, y1, x2, y2 = map(int, tracked.xyxy[i])
            result.append({
                "bbox": [x1, y1, x2, y2],
                "confidence": float(tracked.confidence[i]),
                "track_id": int(tracked.tracker_id[i]),
            })
        return result
