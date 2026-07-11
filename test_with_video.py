import logging
import os
import queue
import subprocess
from collections import defaultdict

import cv2

import config
from logger import setup_logging
from state import PipelineState
from pipeline import process_frame, check_visitors, render_overlay, handle_heartbeat
from detector import PersonDetector
from tracker import PersonTracker
from reid import ReIDChecker
from database import LocalDB, CloudDB

setup_logging()
logger = logging.getLogger(__name__)

VIDEO_URL = "https://raw.githubusercontent.com/intel-iot-devkit/sample-videos/master/person-bicycle-car-detection.mp4"
VIDEO_PATH = "test_video.mp4"


def download_video():
    if os.path.exists(VIDEO_PATH):
        logger.info("Видео уже есть: %s", VIDEO_PATH)
        return
    logger.info("Скачиваю %s ...", VIDEO_URL)
    subprocess.run(["curl", "-L", VIDEO_URL, "-o", VIDEO_PATH], check=True)
    logger.info("Сохранено: %s", VIDEO_PATH)


def process_events(event_queue, cloud_db, stats):
    """Process queued events and update stats.

    Args:
        event_queue: Queue with (kind, payload) tuples
        cloud_db: CloudDB instance
        stats: Stats dict to update
    """
    while not event_queue.empty():
        try:
            kind, payload = event_queue.get_nowait()
            if kind == "visit":
                cloud_db.log_visit(**payload)
                visitor_id = payload["visitor_id"]
                direction = payload["direction"]
                is_repeat = payload["is_repeat"]
                status = "repeat" if is_repeat else "new"
                stats["total"] += 1
                stats[status] += 1
                stats[direction] += 1
            elif kind == "heartbeat":
                cloud_db.log_heartbeat()
        except queue.Empty:
            break


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
    state = PipelineState()
    event_queue = queue.Queue()
    stats = defaultdict(int)

    cap = cv2.VideoCapture(VIDEO_PATH)
    if not cap.isOpened():
        logger.error("Не удалось открыть видео: %s", VIDEO_PATH)
        return

    frame_count = 0
    logger.info("Обрабатываю видео...")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        height, width = frame.shape[:2]
        line_y = int(height * config.LINE_POSITION)

        tracks = process_frame(frame, detector, tracker)
        tracks_with_results = check_visitors(tracks, frame, reid, state, line_y, event_queue)
        render_overlay(frame, tracks_with_results, line_y)

        frame_count += 1
        frame_count = handle_heartbeat(frame_count, event_queue)

        # Process events immediately (no separate cloud_sender thread in test)
        process_events(event_queue, cloud_db, stats)

    cap.release()

    logger.info(
        "Итоговая статистика: всего=%d, новых=%d, повторных=%d, IN=%d, OUT=%d",
        stats["total"], stats["new"], stats["repeat"], stats["IN"], stats["OUT"],
    )


if __name__ == "__main__":
    main()
