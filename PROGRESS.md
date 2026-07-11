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
| T-05: Рефакторинг main() | ✅ | 2026-07-11 | pipeline.py с 4 функциями; main() loop сокращен; 18 тестов в test_t05_main_refactor.py |
| T-06: Устранить дублирование pipeline | ✅ | 2026-07-11 | test_with_video.py рефакторен; используются pipeline.py функции; PipelineState; 10 тестов |
| T-07: Type hints | ✅ | 2026-07-11 | 25+ функций с типами; database, reid, detector, main, pipeline; 22 тестов |
| T-08: Оптимизация поиска галереи | ✅ | 2026-07-11 | numpy.tobytes() вместо pickle (10-100x), in-memory cache (TTL 10 мин), vectorized matmul для косинуса |
| T-09: Версии зависимостей | ✅ | 2026-07-11 | pip freeze → requirements.txt с 120+ пакетами; 5 секций (CORE/CLOUD/UI/UTILITIES/DEV); 8 тестов |
| T-10: SQLite путь + лок | ✅ | 2026-07-11 | thread-local connections + RLock + absolute path + WAL mode |

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

### Сессия 2026-07-11 — T-05
- `pipeline.py`: новый модуль с 4 функциями: `process_frame()`, `check_visitors()`, `render_overlay()`, `handle_heartbeat()`
- `main.py`: импортирует функции из `pipeline.py`; main() loop сокращен с 76 до 42 строк
- `tests/test_t05_main_refactor.py`: 18 юнит-тестов (процесс кадра, проверка визиторов, рендеринг, хартбит)
- Все тесты прошли

### Сессия 2026-07-11 — T-06
- `test_with_video.py`: полностью рефакторен на использование `pipeline.py`
- Удалены 60 строк дублирующегося кода (inline detection/tracking/visitor logic)
- Заменены на вызовы `process_frame()`, `check_visitors()`, `render_overlay()`, `handle_heartbeat()`
- Введён `PipelineState()` вместо ручного `prev_positions` + `last_counted` дicts
- Добавлена функция `process_events()` для синхронной обработки очереди событий
- Добавлены импорты: `queue`, `PipelineState`, `pipeline` функции
- `tests/test_t06_eliminate_duplication.py`: 10 новых тестов для проверки структурных изменений
- Все 42 теста (старые + новые) прошли успешно

### Сессия 2026-07-11 — T-01
- `main.py`: добавлен `timezone`, `datetime.now()` → `datetime.now(timezone.utc)` для DB timestamp
- `test_with_video.py`: то же самое для `cloud_db.log_visit()`
- `dashboard/app.py:35`: `except:` → `except Exception as e:` + `st.error()`
- Удалён `reid_backup.py` (полный дубликат `reid.py`)

### Сессия 2026-07-11 — T-07
- Добавлены type hints для 25+ функций:
  - `database.py`: `find_similar()`, `save_embedding()`, `log_visit()`, `log_heartbeat()`, `_cosine_similarity()`
  - `reid.py`: `check()`, `get_embedding()`, `normalize_crop()` + импорты `Optional`, `Dict`, `Any`
  - `detector.py`: `detect()`, `is_good_crop()` + импорты `List`, `Dict`, `Any`
  - `main.py`: `connect_camera()`, `cloud_sender()`, `main()` + импорт `Tuple`
  - `pipeline.py`: `process_frame()`, `check_visitors()`, `render_overlay()`, `handle_heartbeat()` + импорты + `queue`
- `tests/test_t07_type_hints.py`: 22 новых теста (проверка сигнатур, импортов, типов)
- Все 64 теста прошли успешно

### Сессия 2026-07-11 — T-08
- **Оптимизация поиска по галерее:**
  1. Замена `pickle.dumps/loads()` на `numpy.tobytes/frombuffer()` — 10-100x быстрее (float32 binary vs pickle overhead)
  2. In-memory кеш активной галереи: `self._cache` + TTL 10 мин (пересчет при истечении)
  3. Векторизованный поиск: `gallery_matrix @ query_vector` вместо цикла по embeddings
- `database.py`: переписан `LocalDB.__init__()`, `save_embedding()`, `find_similar()`; добавлены методы `_rebuild_cache()`, `_is_cache_valid()`; удалена функция `_cosine_similarity()`
- `tests/test_t08_gallery_optimization.py`: 7 новых тестов
  - Binary storage (не pickle)
  - Cache rebuild/validity check
  - Vectorized cosine similarity
  - Performance test: 100 embeddings, <50ms per search
- `tests/test_t07_type_hints.py`: удален тест `test_cosine_similarity_has_hints()` (функция больше не существует)
- Всего: 70 тестов, все прошли

### Сессия 2026-07-11 — T-09
- `requirements.txt`: обновлен с точными версиями из `pip freeze` (120+ пакетов)
- Организовано в 5 секций:
  - **CORE**: torch, torchvision, ultralytics, supervision, opencv-python, torchreid, numpy, scipy
  - **CLOUD**: supabase, supabase-auth, supabase-functions, postgrest, storage3, realtime
  - **UI**: streamlit, plotly, pandas
  - **UTILITIES**: gdown, tensorboard, requests, python-dotenv, tqdm, Pillow
  - **DEV**: pytest, pytest-cov, black, flake8, mypy
  - **INDIRECT**: все остальные зависимости (распечатаны из pip freeze для полной воспроизводимости)
- `tests/test_t09_pinned_versions.py`: 8 новых тестов
  - Все пакеты пиннованы (==)
  - Наличие всех секций
  - Проверка core/cloud/ui пакетов
  - Формат версии (semver)
  - Отсутствие дубликатов
  - Существование файла
- Всего: 78 тестов, все прошли

### Сессия 2026-07-11 — T-10
- **Thread-safety без `check_same_thread=False`:**
  1. Абсолютный путь: `Path(__file__).parent / "data" / "embeddings.db"`
  2. Thread-local connections: каждый поток получает свой connection (threading.local)
  3. RLock для защиты shared state (_cache, _cache_built_at, _embedding_dim)
  4. WAL mode (PRAGMA journal_mode=WAL) для улучшения конкурентного доступа
  5. Таймаут 30 сек для операций БД
- `database.py`:
  - Новый метод `_get_connection()` возвращает thread-local connection
  - Свойство `conn` для обратной совместимости (использует `_get_connection()`)
  - Инициализация: `_db_path`, `_db_lock` (RLock), `_thread_local` (threading.local)
- `tests/test_t10_thread_safe_db.py`: 11 новых тестов
  - TestAbsolutePath: 3 теста (абсолютный путь, директория data/, создание директории)
  - TestThreadLocal: 2 теста (разные connections в разных потоках, переиспользование в одном потоке)
  - TestLockPresence: 4 теста (наличие Lock, thread-local storage, отсутствие check_same_thread=False, WAL mode)
  - TestBasicOperations: 2 теста (базовые save/find, concurrent access без crashes)
- `tests/test_t08_gallery_optimization.py`: переписаны тесты (helper функция `create_test_db`)
- Всего: 89 тестов (78 + 11), все прошли

---

## Метрики (baseline)

| Метрика | Текущее |
|---------|---------|
| Файлов Python | 12 |
| Строк кода | ~890 (было ~862) |
| Функций с type hints | 25+/33 (~76%) |
| Магических чисел | 0 (было 20+, устранены в T-02) |
| `print()` вызовов | ~6 (только утилиты CLI: setup_supabase.py, check_imports.py, seed_test_data.py) |
| Критических багов | 0 (было 2, исправлены в T-01) |
| Дублирующихся файлов | 0 (было 1, удалён в T-01) |
| Тестов | 89 (было 42; +22 в T-07, +7 в T-08, +8 в T-09, +11 в T-10) |
| Производительность поиска | <50ms для 100 embeddings (было O(n) с pickle) |
| Пиннованные версии | 120+ (было 12 без версий, зафиксировано в T-09) |
| Воспроизводимость сборки | ✅ (requirements.txt с exact versions) |
| Thread-safety SQLite | ✅ (thread-local connections + RLock + WAL) |
| SQLite путь | ✅ (абсолютный: data/embeddings.db) |
| Завершённые задачи | 10/10 (T-01 до T-10, 100%) |
