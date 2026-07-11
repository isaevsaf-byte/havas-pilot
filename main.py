import queue
import threading
import time
from datetime import datetime, timezone

import cv2

import config
from detector import PersonDetector
from tracker import PersonTracker
from reid import ReIDChecker
from database import LocalDB, CloudDB

# --- State ---
first_positions = {}   # track_id -> cy at first sighting (direction reference)
last_counted = {}      # track_id -> unix time of last count (cooldown)
event_queue = queue.Queue()


def connect_camera():
    while True:
        cap = cv2.VideoCapture(config.CAMERA_URL)
        if cap.isOpened():
            return cap
        print("Камера недоступна, жду 10 секунд...")
        cap.release()
        time.sleep(config.CAMERA_RECONNECT_DELAY_SEC)


def should_count(track_id):
    now = time.time()
    last = last_counted.get(track_id)
    if last is not None and (now - last) < config.COOLDOWN_SECONDS:
        return False
    last_counted[track_id] = now
    return True


def get_direction(track_id, cy):
    # Compare against where the track first appeared, not the previous frame:
    # frame-to-frame bbox jitter flips direction, entry point does not.
    first = first_positions.get(track_id)
    if first is None or cy == first:
        return "IN"
    return "IN" if cy > first else "OUT"


def cloud_sender(cloud_db):
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
            print(f"[cloud_sender] ошибка отправки, вернул в очередь: {e}")
            event_queue.put((kind, payload))
            time.sleep(config.QUEUE_RETRY_DELAY_SEC)


def main():
    detector = PersonDetector()
    tracker = PersonTracker()
    local_db = LocalDB()
    cloud_db = CloudDB()
    reid = ReIDChecker(local_db)

    sender = threading.Thread(target=cloud_sender, args=(cloud_db,), daemon=True)
    sender.start()

    cap = connect_camera()
    frame_count = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Кадр не получен, переподключаюсь...")
            time.sleep(5)
            cap.release()
            cap = connect_camera()
            continue

        height, width = frame.shape[:2]
        line_y = int(height * config.LINE_POSITION)

        detections = detector.detect(frame)
        tracks = tracker.update(detections, frame)

        for track in tracks:
            bbox = track["bbox"]
            track_id = track["track_id"]
            x1, y1, x2, y2 = bbox
            cy = (y1 + y2) / 2

            # Remember where this track first appeared (direction reference)
            if track_id not in first_positions:
                first_positions[track_id] = cy

            color = (200, 200, 200)
            label = ""

            if abs(cy - line_y) < config.LINE_TOLERANCE_PX and should_count(track_id):
                crop = frame[y1:y2, x1:x2]
                result = reid.check(crop, track_id)
                if result is not None:
                    direction = get_direction(track_id, cy)
                    event_queue.put(("visit", {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "direction": direction,
                        "is_repeat": result["status"] == "repeat",
                        "visitor_id": result["visitor_id"],
                    }))
                    ts = datetime.now().strftime("%H:%M:%S")
                    short_id = result["visitor_id"][:8]
                    print(f"[{ts}] {direction} | {result['status']} | visitor_{short_id}")

                    color = (0, 255, 0) if result["status"] == "new" else (255, 0, 0)
                    label = f"{direction} | {result['status']}"

            if not config.HEADLESS:
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                if label:
                    cv2.putText(frame, label, (x1, y1 - 8),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 1)

        frame_count += 1
        if frame_count >= 750:
            event_queue.put(("heartbeat", {}))
            frame_count = 0

        if not config.HEADLESS:
            cv2.line(frame, (0, line_y), (width, line_y), (0, 255, 255), 2)
            cv2.imshow("Havas Pilot", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    cap.release()
    if not config.HEADLESS:
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
