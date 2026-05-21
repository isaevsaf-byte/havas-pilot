import time
from datetime import datetime

import cv2

import config
from detector import PersonDetector
from tracker import PersonTracker
from reid import ReIDChecker
from database import LocalDB, CloudDB

# --- State ---
prev_positions = {}
last_counted = {}
frame_count = 0


def connect_camera():
    while True:
        cap = cv2.VideoCapture(config.CAMERA_URL)
        if cap.isOpened():
            return cap
        print("Камера недоступна, жду 10 секунд...")
        cap.release()
        time.sleep(10)


def should_count(track_id):
    now = time.time()
    last = last_counted.get(track_id)
    if last is not None and (now - last) < config.COOLDOWN_SECONDS:
        return False
    last_counted[track_id] = now
    return True


def get_direction(track_id, bbox, frame_height):
    x1, y1, x2, y2 = bbox
    cy = (y1 + y2) / 2
    prev = prev_positions.get(track_id)
    prev_positions[track_id] = cy
    if prev is None:
        return "IN"
    return "IN" if cy > prev else "OUT"


def main():
    global frame_count

    detector = PersonDetector()
    tracker = PersonTracker()
    local_db = LocalDB()
    cloud_db = CloudDB()
    reid = ReIDChecker(local_db)

    cap = connect_camera()
    line_color = (0, 255, 255)

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

            color = (200, 200, 200)
            label = ""

            if abs(cy - line_y) < 20 and should_count(track_id):
                crop = frame[y1:y2, x1:x2]
                result = reid.check(crop, track_id)
                if result is not None:
                    direction = get_direction(track_id, bbox, height)
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

                    color = (0, 255, 0) if result["status"] == "new" else (255, 0, 0)
                    label = f"{direction} | {result['status']}"
            else:
                get_direction(track_id, bbox, height)

            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            if label:
                cv2.putText(frame, label, (x1, y1 - 8),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 1)

        cv2.line(frame, (0, line_y), (width, line_y), line_color, 2)

        frame_count += 1
        if frame_count >= 750:
            cloud_db.log_heartbeat()
            frame_count = 0

        cv2.imshow("Havas Pilot", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
