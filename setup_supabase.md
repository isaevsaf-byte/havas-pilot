# Настройка Supabase

## 1. Создай аккаунт

Зайди на [supabase.com](https://supabase.com) и зарегистрируйся.

## 2. Создай новый проект

Нажми **New Project** и заполни:
- **Name:** havas-pilot
- **Database Password:** придумай и запомни пароль
- **Region:** выбери ближайший (например, EU Central)

Подожди 1–2 минуты пока проект создаётся.

## 3. Скопируй ключи

Перейди: **Settings → API**

Скопируй и вставь в `config.py`:
- **Project URL** → `SUPABASE_URL`
- **anon public** (под Project API Keys) → `SUPABASE_KEY`

## 4. Создай таблицы

Открой **SQL Editor** в левом меню и выполни:

```sql
CREATE TABLE visits (
  id          BIGSERIAL PRIMARY KEY,
  timestamp   TIMESTAMPTZ NOT NULL,
  direction   TEXT        NOT NULL,
  is_repeat   BOOLEAN     NOT NULL,
  visitor_id  TEXT        NOT NULL,
  store       TEXT        NOT NULL
);

CREATE TABLE heartbeat (
  store      TEXT PRIMARY KEY,
  last_seen  TIMESTAMPTZ NOT NULL
);

CREATE INDEX idx_visits_timestamp ON visits(timestamp DESC);
CREATE INDEX idx_visits_store     ON visits(store);
```

## 5. Проверь подключение

```bash
python3 setup_supabase.py
```

Должно вывести: **Supabase готов**
