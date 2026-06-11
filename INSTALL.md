# Установка на ноутбук магазина — пошагово

Время: ~1 час (большая часть — скачивание библиотек).
Нужен интернет на ноуте.

---

## Шаг 0. Что взять с собой

- Ключи Supabase (URL и publishable key) — записаны ниже в шаге 5
- RTSP-адрес камеры — спросить у установщиков: **IP камеры, логин, пароль**.
  Адрес выглядит так: `rtsp://логин:пароль@IP:554/stream1`

---

## Шаг 1. Установить Python

1. Открой [python.org/downloads](https://www.python.org/downloads/)
2. Скачай **Python 3.12** (не самый новый — стабильнее)
3. При установке на Windows — **обязательно поставь галочку
   "Add Python to PATH"** на первом экране установщика
4. Проверка: открой терминал и набери
   ```
   python3 --version
   ```
   (на Windows: `python --version`). Должна показаться версия.

**Как открыть терминал:**
- Mac: Command+Space → набери "Terminal" → Enter
- Windows: Win → набери "PowerShell" → Enter

---

## Шаг 2. Установить Git

- Mac: набери в терминале `git --version` — если нет, macOS сам предложит установить
- Windows: скачай с [git-scm.com](https://git-scm.com), ставь со всеми настройками по умолчанию

---

## Шаг 3. Скачать проект

В терминале:

```bash
cd ~
git clone https://github.com/isaevsaf-byte/havas-pilot.git
cd havas-pilot
```

Репозиторий приватный — попросит логин GitHub. Пароль = Personal Access Token
(создать заранее: github.com → Settings → Developer settings → Tokens).

---

## Шаг 4. Установить библиотеки

```bash
pip3 install -r requirements.txt
```

(Windows: `pip install -r requirements.txt`)

Это займёт 10–20 минут — torch весит ~2 ГБ. Дождись конца без ошибок.

---

## Шаг 5. Прописать ключи

**Mac** — добавь в конец файла `~/.zshrc` (открыть: `nano ~/.zshrc`):

```bash
export SUPABASE_URL="https://kxyyvnxklbczuofzaoow.supabase.co"
export SUPABASE_KEY="sb_publishable_79gUEoh_qoocFxnwied-Tw_IE3uU00j"
export CAMERA_URL="rtsp://логин:пароль@IP_КАМЕРЫ:554/stream1"
```

Сохрани (Ctrl+O, Enter, Ctrl+X), затем: `source ~/.zshrc`

**Windows** — в PowerShell (один раз, сохранится навсегда):

```powershell
[Environment]::SetEnvironmentVariable("SUPABASE_URL", "https://kxyyvnxklbczuofzaoow.supabase.co", "User")
[Environment]::SetEnvironmentVariable("SUPABASE_KEY", "sb_publishable_79gUEoh_qoocFxnwied-Tw_IE3uU00j", "User")
[Environment]::SetEnvironmentVariable("CAMERA_URL", "rtsp://логин:пароль@IP_КАМЕРЫ:554/stream1", "User")
```

После этого закрой и заново открой терминал.

---

## Шаг 6. Проверка по цепочке

Каждый шаг должен пройти, прежде чем идти дальше.

**6.1. Библиотеки встали:**
```bash
python3 check_imports.py
```
Ожидаем: `OK` по всем пяти строкам.

**6.2. База доступна:**
```bash
python3 setup_supabase.py
```
Ожидаем: `Supabase готов`.

**6.3. Пайплайн работает (тест на видеофайле, камера не нужна):**
```bash
python3 test_with_video.py
```
Ожидаем: в конце статистика с "Всего событий: 1" (или больше).
При первом запуске скачаются веса моделей — нужен интернет.

**6.4. Камера отвечает:**
```bash
python3 -c "import cv2, os; cap = cv2.VideoCapture(os.environ['CAMERA_URL']); print('КАМЕРА OK' if cap.read()[0] else 'КАМЕРА НЕ ОТВЕЧАЕТ')"
```
Если "НЕ ОТВЕЧАЕТ" — проверь: ноут в той же Wi-Fi/сети что камера?
IP, логин, пароль правильные? Спроси установщиков.

---

## Шаг 7. Боевой запуск

**Первый запуск — с окном**, чтобы глазами проверить:

```bash
python3 main.py
```

Должно открыться окно с видео. Проверь:
- [ ] люди обводятся рамками
- [ ] жёлтая линия проходит там, где люди реально пересекают вход
  (если нет — поменяй `LINE_POSITION` в config.py: 0.3 = выше, 0.7 = ниже)
- [ ] при пересечении линии в терминале печатается `[время] IN | new | visitor_...`
- [ ] зайди-выйди сам 2 раза — второй раз должен быть `repeat`

Выход — клавиша `q`.

**Постоянная работа — без окна:**

```bash
HEADLESS=1 python3 main.py
```

(Windows PowerShell: `$env:HEADLESS="1"; python main.py`)

---

## Шаг 8. Проверить дашборд

Открой дашборд в браузере (Streamlit Cloud) — через 5–10 минут работы
системы должен гореть статус 🟢 и появляться события.

---

## Если что-то сломалось

| Симптом | Лечение |
|---|---|
| `No module named ...` | `pip3 install <имя модуля>` |
| Веса не скачиваются (SSL ошибка) | Mac: запусти `/Applications/Python 3.12/Install Certificates.command` |
| Камера недоступна | Ноут и камера в одной сети? `ping IP_КАМЕРЫ` |
| `RLS policy` ошибка из Supabase | Политики уже настроены; проверь что ключ = publishable |
| Окно не открывается | Запускай с `HEADLESS=1` |

---

## Перед уходом из магазина

- [ ] `main.py` работает в режиме HEADLESS
- [ ] В дашборде статус 🟢 и события идут
- [ ] Ноут не уходит в сон: настрой "никогда не засыпать" при питании от сети
      (Mac: System Settings → Battery; Windows: Параметры → Питание)
- [ ] Ноут подключён к розетке
- [ ] Wi-Fi автоподключение включено
