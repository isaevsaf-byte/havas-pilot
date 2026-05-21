import os
import random
from datetime import datetime, timezone, timedelta

import config
from supabase import create_client

# Uses service_role key to bypass RLS for seeding
# Set SUPABASE_SERVICE_KEY in config.py or as env variable
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", config.SUPABASE_KEY)
client = create_client(config.SUPABASE_URL, SERVICE_KEY)

PEAK_HOURS = list(range(12, 15)) + list(range(18, 21))
NORMAL_HOURS = [h for h in range(9, 22) if h not in PEAK_HOURS]

def random_hour():
    # 60% chance of peak hour
    if random.random() < 0.6:
        return random.choice(PEAK_HOURS)
    return random.choice(NORMAL_HOURS)

rows = []
today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

for day_offset in range(29, -1, -1):
    day = today - timedelta(days=day_offset)
    count = random.randint(50, 150)

    for _ in range(count):
        hour = random_hour()
        minute = random.randint(0, 59)
        second = random.randint(0, 59)
        ts = day.replace(hour=hour, minute=minute, second=second)
        is_repeat = random.random() < 0.30
        rows.append({
            "timestamp": ts.isoformat(),
            "direction": "IN",
            "is_repeat": is_repeat,
            "visitor_id": f"seed-{random.randint(100000, 999999)}",
            "store": config.STORE_NAME,
        })

# Insert in batches of 500
BATCH = 500
inserted = 0
for i in range(0, len(rows), BATCH):
    batch = rows[i:i + BATCH]
    client.table("visits").insert(batch).execute()
    inserted += len(batch)
    print(f"  вставлено {inserted}/{len(rows)}...")

print(f"\nГотово. Всего добавлено записей: {inserted}")
