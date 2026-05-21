checks = [
    ("config",   "config",   None),
    ("detector", "detector", "ultralytics"),
    ("tracker",  "tracker",  "supervision"),
    ("reid",     "reid",     "torchreid + torch"),
    ("database", "database", "supabase"),
]

all_ok = True
for name, module, install in checks:
    try:
        __import__(module)
        print(f"OK: {name}")
    except ImportError as e:
        hint = f"  → pip install {install}" if install else ""
        print(f"FAIL: {name} — {e}{hint}")
        all_ok = False

if all_ok:
    print("\nВсе импорты успешны.")
else:
    print("\nЕсть ошибки — установи недостающие библиотеки.")
