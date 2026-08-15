import atexit
import faulthandler
import logging
import os
import queue
import subprocess
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Tuple

import cv2

import config
from logger import setup_logging
from state import PipelineState
from pipeline import process_frame, check_visitors, render_overlay
from detector import PersonDetector
from tracker import PersonTracker
from reid import ReIDChecker
from database import LocalDB, CloudDB

# A segfault/access violation inside OpenCV/FFmpeg's native code bypasses
# Python's exception machinery entirely — the try/except around main() below
# never sees it. faulthandler installs a low-level handler that can still
# dump a traceback for those before the process dies.
_fault_log_dir = Path(__file__).parent / "logs"
_fault_log_dir.mkdir(exist_ok=True)
_fault_file = open(_fault_log_dir / "fault.log", "a", encoding="utf-8")
faulthandler.enable(file=_fault_file)

setup_logging()
logger = logging.getLogger(__name__)

# --- State ---
event_queue = queue.Queue()

LOCK_FILE = Path(__file__).parent / "service.lock"
CRASH_LOG = Path(__file__).parent / "logs" / "crash.log"


def _pid_is_alive(pid: str) -> bool:
    # Filtered by image name too, not just PID — a bare PID match can be a
    # stale false positive once the OS recycles the number for an unrelated
    # process.
    result = subprocess.run(
        ["tasklist", "/FI", f"PID eq {pid}", "/FI", "IMAGENAME eq python.exe"],
        capture_output=True,
        text=True,
    )
    return pid in result.stdout


def _release_lock() -> None:
    try:
        LOCK_FILE.unlink()
    except FileNotFoundError:
        pass


def acquire_lock() -> None:
    # Guards against a second instance fighting an orphaned one for the
    # camera — the orphan holds the RTSP connection, the new instance just
    # loops failing to connect, and nothing about that looks unusual enough
    # to page anyone. Refusing to start is more honest than a silent stalemate.
    if LOCK_FILE.exists():
        old_pid = LOCK_FILE.read_text().strip()
        if old_pid and _pid_is_alive(old_pid):
            logger.error(
                "main.py уже запущен (PID %s), не подключаюсь к камере, выхожу", old_pid
            )
            raise SystemExit(1)
        logger.warning("Найден lock-файл от мёртвого PID %s, перезаписываю", old_pid)
    LOCK_FILE.write_text(str(os.getpid()))
    atexit.register(_release_lock)


def connect_camera(camera_ok: threading.Event) -> cv2.VideoCapture:
    # Bound how long a hung RTSP connect/read can block us — without this,
    # FFmpeg's own internal timeout decides (observed 30s to 8.5 minutes in
    # the wild), which is far too unpredictable for a reconnect loop.
    while True:
        cap = cv2.VideoCapture()
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, config.CAMERA_OPEN_TIMEOUT_MS)
        cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, config.CAMERA_READ_TIMEOUT_MS)
        cap.open(config.CAMERA_URL, cv2.CAP_FFMPEG)
        if cap.isOpened():
            camera_ok.set()
            return cap
        camera_ok.clear()
        logger.warning("Камера недоступна, жду %d секунд...", config.CAMERA_RECONNECT_DELAY_SEC)
        cap.release()
        time.sleep(config.CAMERA_RECONNECT_DELAY_SEC)


def heartbeat_sender(event_queue: queue.Queue, camera_ok: threading.Event) -> None:
    # Runs on its own timer, independent of the video loop — a camera that's
    # stuck reconnecting for hours must not also silence the heartbeat the
    # dashboard/monitor depends on to tell "service down" apart from
    # "service fine, camera's the problem" (see incidents.type).
    while True:
        status = "ok" if camera_ok.is_set() else "camera_down"
        event_queue.put(("heartbeat", {"status": status}))
        time.sleep(config.HEARTBEAT_INTERVAL_SEC)


def cloud_sender(cloud_db: CloudDB) -> None:
    # Network I/O lives here so a slow Supabase call never stalls
    # the video loop. Events wait in the queue until they are delivered.
    #
    # A failed event is requeued behind whatever arrived in the meantime
    # rather than retried in place — insertion order can shuffle, but a
    # permanently failing event (e.g. blocked by an RLS policy) can't
    # starve later events, including heartbeats the dashboard depends on
    # for its "система работает" status. Downstream consumers should sort
    # by the event's own timestamp, not by arrival order.
    while True:
        kind, payload = event_queue.get()
        try:
            if kind == "visit":
                cloud_db.log_visit(**payload)
            elif kind == "heartbeat":
                cloud_db.log_heartbeat(status=payload.get("status", "ok"))
        except Exception as e:
            logger.error("cloud_sender: ошибка отправки, вернул в очередь: %s", e)
            event_queue.put((kind, payload))
            time.sleep(config.QUEUE_RETRY_DELAY_SEC)


def main() -> None:
    acquire_lock()

    detector = PersonDetector()
    tracker = PersonTracker()
    local_db = LocalDB()
    cloud_db = CloudDB()
    reid = ReIDChecker(local_db)
    state = PipelineState()

    sender = threading.Thread(target=cloud_sender, args=(cloud_db,), daemon=True)
    sender.start()

    camera_ok = threading.Event()
    heartbeat = threading.Thread(target=heartbeat_sender, args=(event_queue, camera_ok), daemon=True)
    heartbeat.start()

    cap = connect_camera(camera_ok)

    while True:
        ret, frame = cap.read()
        if not ret:
            logger.warning("Кадр не получен, переподключаюсь...")
            camera_ok.clear()
            cap.release()
            cap = connect_camera(camera_ok)
            continue

        height, width = frame.shape[:2]
        line_y = int(height * config.LINE_POSITION)

        tracks = process_frame(frame, detector, tracker)
        tracks_with_results = check_visitors(tracks, frame, reid, state, line_y, event_queue)

        if not config.HEADLESS:
            render_overlay(frame, tracks_with_results, line_y)

        if not config.HEADLESS:
            cv2.imshow("Havas Pilot", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    cap.release()
    if not config.HEADLESS:
        cv2.destroyAllWindows()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        CRASH_LOG.parent.mkdir(exist_ok=True)
        with CRASH_LOG.open("a", encoding="utf-8") as f:
            f.write(f"\n=== {datetime.now().isoformat()} ===\n")
            traceback.print_exc(file=f)
        logger.exception("main.py упал с необработанным исключением")
        raise
