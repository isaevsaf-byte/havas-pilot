import os

CAMERA_URL = "rtsp://admin:admin@192.168.1.64:554/stream1"
LINE_POSITION = 0.5
REID_THRESHOLD = 0.8
COOLDOWN_SECONDS = 30
STORE_NAME = os.getenv("STORE_NAME", "havas_tashkent")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
