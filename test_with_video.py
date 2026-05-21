import os
import subprocess
import time
from datetime import datetime
from collections import defaultdict

import cv2

import config
from detector import PersonDetector
from tracker import PersonTracker
from reid import ReIDChecker
from database import LocalDB, CloudDB

VIDEO_URL = "https://raw.githubusercontent.com/intel-iot-devkit/sample-videos/master/person-bicycle-car-detection.mp4"
VIDEO_PATH = "test_video.mp4"


def download_video():
    if os.path.exists(VIDEO_PATH):
        print(f"Видео уже есть: {VIDEO_PATH}")
        return
    print(f"Скачиваю {VIDEO_URL} ...")
    subprocess.run(["curl", "-L", VIDEO_URL, "-o", VIDEO_PATH], check=True)
    print(f"Сохранено: {VIDEO_PATH}")


def main():
    download_video()

    # Override camera source
    config.CAMERA_URL = VIDEO_PATH

    detector = PersonDetector()
    tracker = PersonTracker()
    local_db = LocalDB()
    cloud_db = CloudDB()
    # Lower crop quality threshold for test video (people are small in frame)
    from detector import PersonDetector as _PD
    _PD.is_good_crop = lambda self, bbox: (bbox[2]-bbox[0]) > 30 and (bbox[3]-bbox[1]) > 50

    reid = ReIDChecker(local_db)

    prev_positions = {}
    last_counted = {}

    stats = defaultdict(int)

    cap = cv2.VideoCapture(VIDEO_PATH)
    if not cap.isOpened():
        print("Не удалось открыть видео.")
        return

    frame_count = 0
    print("Обрабатываю видео...\n")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        height, width = frame.shape[:2]
        line_y = int(height * config.LINE_POSITION)

        detections = detector.detect(frame)
        tracks = tracker.update(detections, frame)

        for track in tracks:
            bbox = track["bbox"]
            track_id = track["track_id"]
            x1, y1, x2, y2 = bbox
            cy = (y1 + y2) / 2

            # Direction tracking (always update)
            prev_cy = prev_positions.get(track_id)
            prev_positions[track_id] = cy
            direction = "IN" if (prev_cy is None or cy > prev_cy) else "OUT"

            if abs(cy - line_y) < 40:
                now = time.time()
                last = last_counted.get(track_id)
                if last is not None and (now - last) < config.COOLDOWN_SECONDS:
                    continue
                last_counted[track_id] = now

                crop = frame[y1:y2, x1:x2]
                result = reid.check(crop, track_id)
                if result is None:
                    continue

                is_repeat = result["status"] == "repeat"
                cloud_db.log_visit(
                    timestamp=datetime.now().isoformat(),
                    direction=direction,
                    is_repeat=is_repeat,
                    visitor_id=result["visitor_id"],
                )

                ts = datetime.now().strftime("%H:%M:%S")
                short_id = result["visitor_id"][:8]
                print(f"[{ts}] {direction} | {result['status']} | visitor_{short_id}")

                stats["total"] += 1
                stats[result["status"]] += 1
                stats[direction] += 1

        frame_count += 1

    cap.release()

    print("\n--- Итоговая статистика ---")
    print(f"Всего событий:  {stats['total']}")
    print(f"Новых визитов:  {stats['new']}")
    print(f"Повторных:      {stats['repeat']}")
    print(f"IN:             {stats['IN']}")
    print(f"OUT:            {stats['OUT']}")


if __name__ == "__main__":
    main()
