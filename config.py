import os

# === CAMERA ===
CAMERA_URL = os.getenv("CAMERA_URL", "rtsp://admin:admin@192.168.1.64:554/stream1")
CAMERA_RECONNECT_DELAY_SEC = 10  # seconds to wait before retrying a failed camera connection
QUEUE_RETRY_DELAY_SEC = 5        # seconds to wait before retrying a failed cloud event

# === DETECTION / TRACKING ===
LINE_POSITION = 0.5              # vertical position of counting line (0.0–1.0 of frame height)
LINE_TOLERANCE_PX = 20           # pixels around the line that trigger a count
HEARTBEAT_EVERY_N_FRAMES = 750   # send a heartbeat every N processed frames
MIN_CROP_W = 50                  # minimum bounding-box width (px) to accept a person crop
MIN_CROP_H = 100                 # minimum bounding-box height (px) to accept a person crop

# === REID ===
REID_THRESHOLD = 0.8             # cosine-similarity threshold: above → repeat visitor
COOLDOWN_SECONDS = 30            # seconds before the same track_id can be counted again
GALLERY_TTL_DAYS = 30            # days before an embedding is dropped from the gallery
CLAHE_CLIP_LIMIT = 2.0           # CLAHE clip limit for crop normalisation
CLAHE_TILE = (8, 8)              # CLAHE tile grid size for crop normalisation
EMBED_CROP_W = 128               # width to resize crop before embedding extraction
EMBED_CROP_H = 256               # height to resize crop before embedding extraction

# === DB ===
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

# === UI ===
HEADLESS = os.getenv("HEADLESS", "") == "1"
STORE_NAME = os.getenv("STORE_NAME", "havas_tashkent")
DASHBOARD_REFRESH_SEC = 30       # auto-refresh interval for the Streamlit dashboard
