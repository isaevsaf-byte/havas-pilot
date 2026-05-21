import sys
import config


def check():
    if not config.SUPABASE_URL or not config.SUPABASE_KEY:
        print("ОШИБКА: SUPABASE_URL или SUPABASE_KEY не заполнены в config.py")
        sys.exit(1)

    try:
        from supabase import create_client
    except ImportError:
        print("ОШИБКА: библиотека supabase не установлена → pip install supabase")
        sys.exit(1)

    print(f"Подключаюсь к {config.SUPABASE_URL} ...")
    try:
        client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
    except Exception as e:
        print(f"ОШИБКА: не удалось создать клиент Supabase — {e}")
        sys.exit(1)

    for table in ("visits", "heartbeat"):
        try:
            result = client.table(table).select("*").limit(1).execute()
            print(f"  ✓ таблица '{table}' доступна")
        except Exception as e:
            msg = str(e)
            if "does not exist" in msg or "42P01" in msg:
                print(f"  ✗ таблица '{table}' не найдена — выполни SQL из setup_supabase.md")
            else:
                print(f"  ✗ таблица '{table}' — ошибка: {msg}")
            sys.exit(1)

    print("\nSupabase готов")


if __name__ == "__main__":
    check()
