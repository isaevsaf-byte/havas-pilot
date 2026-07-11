# Havas-Pilot — Plan улучшений кода

> Аудит: 2026-07-11 | Стек: YOLOv8 + ByteTrack + torchreid + SQLite + Supabase + Streamlit
> Найдено: ~50 проблем. Здесь — 10 задач ~1 час каждая, отсортированы по impact.

---

## [x] T-01 — Критические баги (timezone + bare except + дубликат) `~30 мин`
**Impact: 🔴 Critical | Сложность: Low**

Три независимых фикса в одной задаче — все быстрые, все опасные если не починить.

**1. Timezone bug (молчаливая порча данных)**
- `main.py:111` — `datetime.now().isoformat()` создаёт naive datetime
- `test_with_video.py:93` — та же проблема
- База данных везде использует `timezone.utc`, сравнения ломаются
- **Фикс:** `datetime.now(timezone.utc).isoformat()`

**2. Bare `except:` в дашборде**
- `dashboard/app.py:35` — ловит `KeyboardInterrupt`, `SystemExit`, скрывает ошибки
- **Фикс:** `except Exception as e:` + логировать ошибку

**3. Удалить `reid_backup.py`**
- Полная копия `reid.py`, никаких отличий
- Вводит в заблуждение, не нужен

---

## [x] T-02 — Централизация конфигурации `~1 час`
**Impact: 🟠 High | Сложность: Low-Medium**

20+ магических чисел разбросаны по коду. `config.py` содержит только 9 переменных.

**Найденные хардкоды:**
| Файл | Строка | Значение | Имя переменной |
|------|--------|----------|----------------|
| `main.py` | 105 | `20` | `LINE_TOLERANCE_PX` |
| `main.py` | 130 | `750` | `HEARTBEAT_EVERY_N_FRAMES` |
| `main.py` | 27 | `10` | `CAMERA_RECONNECT_DELAY_SEC` |
| `main.py` | 61 | `5` | `QUEUE_RETRY_DELAY_SEC` |
| `detector.py` | 26 | `50, 100` | `MIN_CROP_W`, `MIN_CROP_H` |
| `reid.py` | 38 | `128, 256` | `EMBED_CROP_W`, `EMBED_CROP_H` |
| `reid.py` | 27 | `2.0, (8,8)` | `CLAHE_CLIP_LIMIT`, `CLAHE_TILE` |
| `dashboard/app.py` | 161 | `30` | `DASHBOARD_REFRESH_SEC` |

**Цель:** все константы в `config.py` с секциями `# === CAMERA ===`, `# === REID ===`, `# === DB ===`, `# === UI ===`

---

## [x] T-03 — Заменить `print()` на `logging` `~45 мин`
**Impact: 🟠 High | Сложность: Low**

Код использует `print()` в 5 файлах (~20 вызовов). В проде невозможно дебажить.

**Что нужно:**
- Настроить `logging` в одном месте (`config.py` или `logger.py`)
- Формат: `%(asctime)s [%(levelname)s] %(name)s: %(message)s`
- Заменить `print()` на `logger.info()` / `logger.warning()` / `logger.error()`
- Ротация логов через `RotatingFileHandler` (10 MB, 3 файла)
- В `main.py` и `database.py` — именованные логгеры (`logging.getLogger(__name__)`)

---

## [x] T-04 — Thread safety для глобальных словарей `~1 час`
**Impact: 🟠 High | Сложность: Medium**

`main.py` использует глобальные `dict` из двух контекстов без блокировок.

**Проблемы:**
- `first_positions` (dict) — пишет основной цикл, читает `should_count()`
- `last_counted` (dict) — гонка между кадрами при высоком FPS
- `event_queue` — thread-safe сам по себе, но логика вокруг него — нет

**Рекомендуемое решение:**
```python
_state_lock = threading.Lock()

with _state_lock:
    first_positions[track_id] = cy
```

Или инкапсулировать состояние в `class PipelineState` с методами-аксессорами.

---

## [x] T-05 — Рефакторинг `main()` — разбить на функции `~1 час`
**Impact: 🟡 Medium | Сложность: Medium**

`main()` в `main.py` — 78 строк, 4 разных ответственности. `main()` в `test_with_video.py` — 88 строк аналогичного кода.

**Предлагаемое разбиение:**
```
main()
├── process_frame(frame, detector, tracker) → List[Detection]
├── check_visitors(detections, reid, db, event_queue) → None
├── render_overlay(frame, detections, stats) → frame
└── handle_heartbeat(frame_count, store_name, event_queue) → None
```

Каждая функция — 15-25 строк, легко тестируется отдельно.

---

## [x] T-06 — Устранить дублирование `main.py` / `test_with_video.py` `~1 час`
**Impact: 🟡 Medium | Сложность: Medium**

**Выполнено:** Оба файла теперь используют общие функции из `pipeline.py`.

- `test_with_video.py` рефакторен: удалены ~60 строк дублирующегося кода
- Используются `process_frame()`, `check_visitors()`, `render_overlay()`, `handle_heartbeat()` из `pipeline.py`
- Введён `PipelineState()` вместо ручного управления `prev_positions` и `last_counted`
- Добавлена функция `process_events()` для обработки очереди событий (работает синхронно в test_with_video)
- Тесты: 10 новых тестов в `test_t06_eliminate_duplication.py`, все 42 теста проходят

---

## [x] T-07 — Добавить type hints в ключевые модули `~1 час`
**Impact: 🟡 Medium | Сложность: Low**

**Выполнено:** Добавлены type hints для 25+ функций в приоритетных модулях.

**Типы добавлены:**
- `database.py` (5 функций): `find_similar`, `save_embedding`, `log_visit`, `log_heartbeat`, `_cosine_similarity`
- `reid.py` (3 метода): `check`, `get_embedding`, `normalize_crop`
- `detector.py` (2 метода): `detect`, `is_good_crop`
- `main.py` (3 функции): `connect_camera`, `cloud_sender`, `main`
- `pipeline.py` (4 функции): `process_frame`, `check_visitors`, `render_overlay`, `handle_heartbeat`

**Импорты добавлены:** `Optional`, `Tuple`, `List`, `Dict`, `Any`, `queue`

**Тесты:** 22 новых тестов в `test_t07_type_hints.py` + все 42 старых теста прошли.
Всего: 64 теста успешно.

---

## [x] T-08 — Оптимизация поиска по галерее (vectorize + кеш) `~1 час`
**Impact: 🟡 Medium | Сложность: Medium**

**Выполнено:** Оптимизирована `find_similar()` в `database.py` (3 улучшения).

**Реализованные оптимизации:**
1. **Замена pickle на numpy.tobytes()** — 10-100x быстрее
   - `save_embedding()`: `embedding.tobytes()` вместо `pickle.dumps()`
   - `find_similar()`: `np.frombuffer()` вместо `pickle.loads()`
   - Удалена функция `_cosine_similarity()` (заменена на векторизацию)

2. **In-memory кеш активной галереи** с TTL
   - `self._cache: dict[str, np.ndarray]` — хранит active embeddings
   - `self._cache_built_at: datetime | None` — время создания
   - `CACHE_TTL_MINUTES = 10` — пересчет кеша каждые 10 минут

3. **Векторизованный поиск** матричным умножением
   - Собрать все embeddings в матрицу (n_visitors, D)
   - Нормализация: `gallery @ query / (||gallery|| * ||query||)`
   - Одно `.argmax()` вместо цикла for

**Тесты:** 7 новых тестов в `test_t08_gallery_optimization.py`:
- Binary storage (не pickle)
- Cache rebuild и TTL
- Vectorized search (находит похожие)
- Performance: 100 embeddings — <50ms per search
- Всего: 70 тестов, все прошли

---

## [x] T-09 — Зафиксировать версии зависимостей `~30 мин`
**Impact: 🟡 Medium | Сложность: Low**

**Выполнено:** Все 120+ пакетов зафиксированы с точными версиями.

**Реализовано:**
1. Запущен `pip freeze` для получения всех установленных версий
2. `requirements.txt` обновлён с точными версиями (==) для каждого пакета
3. Организовано в 5 секций:
   - `CORE` — ML/Vision модели (torch, ultralytics, supervision, opencv, torchreid, numpy, scipy)
   - `CLOUD` — Supabase backend (supabase, postgrest, storage3, realtime, supabase-auth/functions)
   - `UI` — Streamlit dashboard (streamlit, plotly, pandas)
   - `UTILITIES` — Поддержка и логирование (gdown, tensorboard, requests, python-dotenv, tqdm, Pillow)
   - `DEV` — Тестирование и качество (pytest, pytest-cov, black, flake8, mypy)
   - `INDIRECT` — Косвенные зависимости (все остальные пакеты, распечатаны из pip freeze)

4. Добавлены 8 тестов в `test_t09_pinned_versions.py`:
   - Проверка что все пакеты пиннованы (==)
   - Проверка наличия всех секций
   - Проверка присутствия core/cloud/ui пакетов
   - Верификация формата версии (semver)
   - Проверка отсутствия дубликатов
   - Проверка существования файла

**Результат:** 78 тестов прошли успешно (70 старых + 8 новых).

---

## [ ] T-10 — Абсолютный путь к SQLite + убрать `check_same_thread=False` `~45 мин`
**Impact: 🟡 Medium | Сложность: Medium**

**Проблема 1:** `database.py:14`
```python
self.conn = sqlite3.connect("havas_embeddings.db", check_same_thread=False)
```
Относительный путь — файл создаётся в `cwd`, который может быть разным.

**Проблема 2:** `check_same_thread=False` + многопоточность — потенциальная порча данных.

**Фикс:**
```python
db_path = Path(__file__).parent / "data" / "embeddings.db"
db_path.parent.mkdir(exist_ok=True)
self._db_lock = threading.Lock()
self.conn = sqlite3.connect(str(db_path))

# При каждом запросе:
with self._db_lock:
    self.conn.execute(...)
```

---

## Сводная таблица

| # | Задача | Impact | Сложность | ~Время |
|---|--------|--------|-----------|--------|
| T-01 | Критические баги (timezone, except, дубликат) | 🔴 Critical | Low | 30 мин |
| T-02 | Централизация конфига | 🟠 High | Low | 1 час |
| T-03 | print() → logging | 🟠 High | Low | 45 мин |
| T-04 | Thread safety | 🟠 High | Medium | 1 час |
| T-05 | Рефакторинг main() | 🟡 Medium | Medium | 1 час |
| T-06 | Устранить дублирование pipeline | 🟡 Medium | Medium | 1 час |
| T-07 | Type hints | 🟡 Medium | Low | 1 час |
| T-08 | Оптимизация поиска галереи | 🟡 Medium | Medium | 1 час |
| T-09 | Версии зависимостей | 🟡 Medium | Low | 30 мин |
| T-10 | SQLite путь + лок | 🟡 Medium | Medium | 45 мин |

**Рекомендуемый порядок работы:** T-01 → T-09 → T-02 → T-03 → T-07 → T-10 → T-04 → T-08 → T-05 → T-06
