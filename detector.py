from ultralytics import YOLO
from typing import List, Dict, Any

import config


class PersonDetector:
    # Uses YOLOv8n to detect people in a video frame.
    # Returns bounding boxes and confidence scores for class 0 (person) only.

    def __init__(self):
        self.model = YOLO("yolov8n.pt")

    def detect(self, frame: Any) -> List[Dict[str, Any]]:
        results = self.model(frame, verbose=False)[0]
        detections = []
        for box in results.boxes:
            if int(box.cls[0]) != 0:
                continue
            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
            detections.append({
                "bbox": [x1, y1, x2, y2],
                "confidence": float(box.conf[0]),
            })
        return detections

    def is_good_crop(self, bbox: List[int]) -> bool:
        x1, y1, x2, y2 = bbox
        return (x2 - x1) > config.MIN_CROP_W and (y2 - y1) > config.MIN_CROP_H
