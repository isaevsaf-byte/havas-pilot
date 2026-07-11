import logging
import queue
import threading
import time
from typing import Tuple

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

# --- State ---
event_queue = queue.Queue()


def connect_camera() -> cv2.VideoCapture:
    while True:
        cap = cv2.VideoCapture(config.CAMERA_URL)
        if cap.isOpened():
            return cap
        logger.warning("Камера недоступна, жду %d секунд...", config.CAMERA_RECONNECT_DELAY_SEC)
        cap.release()
        time.sleep(config.CAMERA_RECONNECT_DELAY_SEC)


def cloud_sender(cloud_db: CloudDB) -> None:
    # Network I/O lives here so a slow Supabase call never stalls
    # the video loop. Events wait in the queue until they are delivered.
    while True:
        kind, payload = event_queue.get()
        try:
            if kind == "visit":
                cloud_db.log_visit(**payload)
            elif kind == "heartbeat":
                cloud_db.log_heartbeat()
        except Exception as e:
            logger.error("cloud_sender: ошибка отправки, вернул в очередь: %s", e)
            event_queue.put((kind, payload))
            time.sleep(config.QUEUE_RETRY_DELAY_SEC)


def main() -> None:
    detector = PersonDetector()
    tracker = PersonTracker()
    local_db = LocalDB()
    cloud_db = CloudDB()
    reid = ReIDChecker(local_db)
    state = PipelineState()

    sender = threading.Thread(target=cloud_sender, args=(cloud_db,), daemon=True)
    sender.start()

    cap = connect_camera()
    frame_count = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            logger.warning("Кадр не получен, переподключаюсь...")
            time.sleep(config.CAMERA_RECONNECT_DELAY_SEC)
            cap.release()
            cap = connect_camera()
            continue

        height, width = frame.shape[:2]
        line_y = int(height * config.LINE_POSITION)

        tracks = process_frame(frame, detector, tracker)
        tracks_with_results = check_visitors(tracks, frame, reid, state, line_y, event_queue)

        if not config.HEADLESS:
            render_overlay(frame, tracks_with_results, line_y)

        frame_count += 1
        frame_count = handle_heartbeat(frame_count, event_queue)

        if not config.HEADLESS:
            cv2.imshow("Havas Pilot", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    cap.release()
    if not config.HEADLESS:
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
