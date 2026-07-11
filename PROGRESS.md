# Havas-Pilot — Progress Tracker

> Начат: 2026-07-11 | Последнее обновление: 2026-07-11

---

## Статусы

| Символ | Значение |
|--------|----------|
| ⬜ | Не начато |
| 🔄 | В процессе |
| ✅ | Готово |
| ❌ | Заблокировано / отменено |

---

## Задачи

| Задача | Статус | Сессия | Заметки |
|--------|--------|--------|---------|
| T-01: Критические баги (timezone, except, дубликат) | ✅ | 2026-07-11 | timezone.utc в main.py+test_with_video.py; except Exception в app.py; удалён reid_backup.py |
| T-02: Централизация конфига | ✅ | 2026-07-11 | 9 констант добавлены в config.py (4 секции); заменены хардкоды в main.py, detector.py, reid.py, dashboard/app.py |
| T-03: print() → logging | ✅ | 2026-07-11 | logger.py создан (RotatingFileHandler 10MB×3); 14 print() заменены в main.py, database.py, test_with_video.py |
| T-04: Thread safety | ✅ | 2026-07-11 | PipelineState в state.py (Lock на _first_positions + _last_counted); 14 тестов |
| T-05: Рефакторинг main() | ⬜ | — | |
| T-06: Устранить дублирование pipeline | ⬜ | — | |
| T-07: Type hints | ⬜ | — | |
| T-08: Оптимизация поиска галереи | ⬜ | — | |
| T-09: Версии зависимостей | ⬜ | — | |
| T-10: SQLite путь + лок | ⬜ | — | |

---

## Лог сессий

### Сессия 2026-07-11 — Аудит
- Просмотрено 12 Python-файлов, ~862 строки кода
- Найдено ~50 проблем, сформирован PLAN.md с 10 задачами
- Код не менялся — только аудит

### Сессия 2026-07-11 — T-02
- `config.py`: расширен с 9 до 18 переменных, добавлены секции CAMERA / DETECTION / REID / DB / UI
- Новые константы: `CAMERA_RECONNECT_DELAY_SEC`, `QUEUE_RETRY_DELAY_SEC`, `LINE_TOLERANCE_PX`, `HEARTBEAT_EVERY_N_FRAMES`, `MIN_CROP_W`, `MIN_CROP_H`, `CLAHE_CLIP_LIMIT`, `CLAHE_TILE`, `EMBED_CROP_W`, `EMBED_CROP_H`, `DASHBOARD_REFRESH_SEC`
- `main.py`: заменены 5 хардкодов (10, 5, 5, 20, 750) — включая `time.sleep` в frame-reconnect
- `detector.py`: заменены 2 хардкода (50, 100); добавлен `import config`
- `reid.py`: заменены 3 хардкода (2.0, (8,8), 128/256)
- `dashboard/app.py`: заменён 1 хардкод (30)
- `test_with_video.py`: заменён хардкод 40 → `config.LINE_TOLERANCE_PX`

### Сессия 2026-07-11 — T-03
- `logger.py`: новый модуль — `setup_logging()` с консольным + `RotatingFileHandler` (10 MB × 3 файла), формат `%(asctime)s [%(levelname)s] %(name)s: %(message)s`
- `main.py`: 4 `print()` → `logger.warning/error/info`; удалена лишняя переменная `ts`; добавлены `import logging`, `from logger import setup_logging`
- `database.py`: 3 `print()` → `logger.warning/info/debug`; добавлены `import logging`, `logger = logging.getLogger(__name__)`
- `test_with_video.py`: 7 `print()` → `logger.*`; добавлены `import logging`, `from logger import setup_logging`

### Сессия 2026-07-11 — T-04
- `state.py`: новый модуль — `PipelineState` с `threading.Lock`; методы `record_first_position`, `should_count`, `get_direction`
- `main.py`: удалены глобальные `first_positions`, `last_counted` и standalone-функции; `state = PipelineState()` в `main()`; импорт из `state.py`
- `tests/test_t04_pipeline_state.py`: 14 тестов — unit (3 класса) + конкурентные (3 теста), все прошли

### Сессия 2026-07-11 — T-01
- `main.py`: добавлен `timezone`, `datetime.now()` → `datetime.now(timezone.utc)` для DB timestamp
- `test_with_video.py`: то же самое для `cloud_db.log_visit()`
- `dashboard/app.py:35`: `except:` → `except Exception as e:` + `st.error()`
- Удалён `reid_backup.py` (полный дубликат `reid.py`)

---

## Метрики (baseline)

| Метрика | Текущее |
|---------|---------|
| Файлов Python | 12 |
| Строк кода | ~862 |
| Функций без type hints | 33/33 |
| Магических чисел | 0 (было 20+, устранены в T-02) |
| `print()` вызовов | ~6 (только утилиты CLI: setup_supabase.py, check_imports.py, seed_test_data.py) |
| Критических багов | 0 (было 2, исправлены) |
| Дублирующихся файлов | 0 (было 1, удалён) |
