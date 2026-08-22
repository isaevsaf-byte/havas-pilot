import sys
import os
import time
from collections import defaultdict
from datetime import datetime, timezone, timedelta, date
from zoneinfo import ZoneInfo

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

TASHKENT_TZ = ZoneInfo("Asia/Tashkent")
WORK_HOURS = list(range(8, 24))  # 08:00–23:59, store operating hours

for key in ("SUPABASE_URL", "SUPABASE_KEY"):
    if key in st.secrets:
        os.environ[key] = st.secrets[key]

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

st.set_page_config(page_title="Havas Analytics", layout="wide")

# --- Palette (validated: see dataviz skill references/palette.md) ---
COLOR_NEW = "#2a78d6"       # categorical slot 1 — blue
COLOR_REPEAT = "#eb6834"    # categorical slot 2 — orange
COLOR_IN = "#2a78d6"        # blue
COLOR_OUT = "#4a3aa7"       # categorical slot 7 — violet
COLOR_TREND = "#1baf7a"     # categorical slot 3 — aqua
STATUS_GOOD = "#0ca30c"
STATUS_WARNING = "#fab219"
STATUS_CRITICAL = "#d03b3b"
SURFACE = "#fcfcfb"
PAGE_BG = "#f9f9f7"
TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
TEXT_MUTED = "#898781"
GRIDLINE = "#e1e0d9"
BORDER = "rgba(11,11,11,0.10)"
FONT_STACK = "system-ui, -apple-system, 'Segoe UI', sans-serif"


def hex_to_rgba(hex_color: str, alpha: float) -> str:
    """Plotly's color validators don't accept 8-digit #RRGGBBAA (CSS-only) — use this for fills."""
    r, g, b = int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16)
    return f"rgba({r},{g},{b},{alpha})"


def style_fig(fig, height=None):
    """Apply the shared chart theme: surface, ink, gridlines, font."""
    fig.update_layout(
        plot_bgcolor=SURFACE,
        paper_bgcolor=SURFACE,
        font=dict(family=FONT_STACK, color=TEXT_SECONDARY, size=13),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=TEXT_SECONDARY)),
        margin=dict(t=16, b=10, l=10, r=10),
        hoverlabel=dict(bgcolor=SURFACE, font=dict(family=FONT_STACK, color=TEXT_PRIMARY)),
    )
    fig.update_xaxes(gridcolor=GRIDLINE, linecolor=GRIDLINE, tickfont=dict(color=TEXT_MUTED), title_font=dict(color=TEXT_SECONDARY))
    fig.update_yaxes(gridcolor=GRIDLINE, linecolor=GRIDLINE, tickfont=dict(color=TEXT_MUTED), title_font=dict(color=TEXT_SECONDARY))
    if height:
        fig.update_layout(height=height)
    return fig


def status_banner(icon: str, text: str, color: str):
    st.markdown(f"""
    <div style="display:flex;align-items:center;gap:10px;background:{color}14;
                border:1px solid {color}40;border-left:4px solid {color};
                border-radius:8px;padding:12px 16px;margin-bottom:12px">
        <span style="font-size:18px;line-height:1">{icon}</span>
        <span style="color:{TEXT_PRIMARY};font-weight:600;font-size:15px">{text}</span>
    </div>
    """, unsafe_allow_html=True)


def metric_card(label: str, value: str, delta: str = None, delta_positive: bool = True):
    # Custom HTML instead of st.metric: Streamlit's own metric widget
    # truncates its value/label text with "…" in narrow columns via JS
    # measurement, which no CSS override can undo. Single-line HTML (see
    # the note above the incidents block) to dodge the markdown code-block trap.
    delta_html = ""
    if delta is not None:
        color = STATUS_GOOD if delta_positive else STATUS_CRITICAL
        arrow = "↑" if delta_positive else "↓"
        delta_html = f'<div style="color:{color};font-size:13px;margin-top:4px">{arrow} {delta}</div>'
    st.markdown(
        f'<div style="background:{SURFACE};border:1px solid {BORDER};border-radius:12px;'
        f'padding:18px 20px;box-shadow:0 1px 2px rgba(11,11,11,0.04);height:100%">'
        f'<div style="color:{TEXT_MUTED};font-size:13px;overflow-wrap:break-word">{label}</div>'
        f'<div style="color:{TEXT_PRIMARY};font-size:1.9rem;font-weight:600;'
        f'font-variant-numeric:tabular-nums;overflow-wrap:break-word;line-height:1.2;margin-top:4px">{value}</div>'
        f'{delta_html}'
        f'</div>',
        unsafe_allow_html=True,
    )


def breakdown_card(label: str, rows: list[tuple[str, str]]):
    """Same card shell as metric_card, but a short list of label/value rows
    instead of one big number — for a card whose content isn't a single stat."""
    if not rows:
        rows = [("—", "")]
    rows_html = "".join(
        f'<div style="display:flex;justify-content:space-between;gap:8px;'
        f'font-size:14px;color:{TEXT_PRIMARY};margin-top:6px">'
        f'<span>{k}</span><span style="font-weight:600;font-variant-numeric:tabular-nums">{v}</span></div>'
        for k, v in rows
    )
    st.markdown(
        f'<div style="background:{SURFACE};border:1px solid {BORDER};border-radius:12px;'
        f'padding:18px 20px;box-shadow:0 1px 2px rgba(11,11,11,0.04);height:100%">'
        f'<div style="color:{TEXT_MUTED};font-size:13px;overflow-wrap:break-word">{label}</div>'
        f'{rows_html}'
        f'</div>',
        unsafe_allow_html=True,
    )


st.markdown(f"""
<style>
html, body, [class*="css"] {{ font-family: {FONT_STACK}; }}
.stApp {{ background-color: {PAGE_BG}; }}
[data-testid="stHeader"] {{ background-color: transparent; }}

h1#havas-analytics {{ font-weight: 700; letter-spacing: -0.02em; margin-bottom: 0; }}
.havas-subtitle {{ color: {TEXT_MUTED}; font-size: 14px; margin-top: -6px; margin-bottom: 20px; }}

[data-testid="stExpander"] {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 10px;
}}

h3 {{ font-size: 16px !important; font-weight: 600 !important; color: {TEXT_PRIMARY}; }}

div[role="radiogroup"] {{ gap: 4px; }}
div[role="radiogroup"] label {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 6px 14px !important;
    margin-right: 0 !important;
    transition: background 0.15s;
}}
div[role="radiogroup"] label:hover {{ background: #f0efec; }}

hr {{ border-color: {GRIDLINE} !important; margin: 1.6rem 0 !important; }}
</style>
""", unsafe_allow_html=True)

st.markdown('<h1 id="havas-analytics">Havas Analytics</h1>', unsafe_allow_html=True)
st.markdown('<div class="havas-subtitle">Учёт посетителей · магазин Ташкент</div>', unsafe_allow_html=True)

if not config.SUPABASE_URL:
    st.warning("Настройте Supabase в config.py")
    st.stop()

from supabase import create_client

@st.cache_resource
def get_client():
    return create_client(config.SUPABASE_URL, config.SUPABASE_KEY)

client = get_client()


def fetch_heartbeat():
    try:
        result = client.table("heartbeat").select("*").eq("store", config.STORE_NAME).execute()
        if result.data and len(result.data) > 0:
            return result.data[0]
        return None
    except Exception as e:
        st.error(f"Ошибка получения heartbeat: {e}")
        return None


def fetch_incidents(limit=10):
    result = (
        client.table("incidents")
        .select("*")
        .eq("store", config.STORE_NAME)
        .order("started_at", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data or []


def fetch_visits(since_local=None, until_local=None):
    """Fetch visits between two Tashkent-local datetimes.

    Supabase stores timestamps in UTC, so the local bounds are converted
    to UTC only for the query — everything downstream works in Tashkent time.
    """
    q = (
        client.table("visits")
        .select("timestamp, direction, is_repeat, visitor_id")
        .eq("store", config.STORE_NAME)
        .order("timestamp", desc=True)
    )
    if since_local is not None:
        q = q.gte("timestamp", since_local.astimezone(timezone.utc).isoformat())
    if until_local is not None:
        q = q.lte("timestamp", until_local.astimezone(timezone.utc).isoformat())
    result = q.execute()
    if not result.data:
        return pd.DataFrame({
            "timestamp": pd.Series(dtype="datetime64[ns, UTC]"),
            "direction": pd.Series(dtype="object"),
            "is_repeat": pd.Series(dtype="bool"),
            "visitor_id": pd.Series(dtype="object"),
        })
    df = pd.DataFrame(result.data)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True).dt.tz_convert(TASHKENT_TZ)
    return df


def day_bounds(d: date):
    """Midnight-to-midnight bounds for a given local calendar date."""
    start = datetime.combine(d, datetime.min.time(), tzinfo=TASHKENT_TZ)
    end = start + timedelta(days=1) - timedelta(microseconds=1)
    return start, end


MAX_VISIT_MINUTES = 90  # sessions longer than this are treated as mismatched IN/OUT pairs, not real visits


def compute_dwell_times(df: pd.DataFrame) -> pd.DataFrame:
    """Pair each IN with the next OUT for the same visitor_id to get session durations.

    Sessions longer than MAX_VISIT_MINUTES are dropped as likely mismatched
    pairs (e.g. a missed detection leaving an IN or OUT unmatched).
    """
    sessions = []
    for visitor_id, group in df.sort_values("timestamp").groupby("visitor_id"):
        pending_in = None
        for _, row in group.iterrows():
            if row["direction"] == "IN":
                pending_in = row
            elif row["direction"] == "OUT" and pending_in is not None:
                duration_min = (row["timestamp"] - pending_in["timestamp"]).total_seconds() / 60
                if 0 < duration_min < MAX_VISIT_MINUTES:
                    sessions.append({
                        "visitor_id": visitor_id,
                        "is_repeat": bool(pending_in["is_repeat"]),
                        "duration_min": duration_min,
                    })
                pending_in = None
    return pd.DataFrame(sessions)


# --- Status bar ---
heartbeat = fetch_heartbeat()
if heartbeat is None:
    status_banner("⚪", "Нет данных от системы", TEXT_MUTED)
else:
    last_seen = pd.to_datetime(heartbeat["last_seen"], utc=True)
    age = datetime.now(timezone.utc) - last_seen
    last_seen_local = last_seen.tz_convert(TASHKENT_TZ)
    if age < timedelta(minutes=10):
        if heartbeat.get("status") == "camera_down":
            status_banner("🟡", "Сервис работает, но камера недоступна", STATUS_WARNING)
        else:
            status_banner("🟢", "Система работает", STATUS_GOOD)
    else:
        status_banner(
            "🔴",
            f"Система не отвечает — последний сигнал: {last_seen_local.strftime('%d.%m.%Y %H:%M')}",
            STATUS_CRITICAL,
        )

with st.expander("⚠️ Что делать, чтобы сервис не падал"):
    st.markdown("""
1. **Не выключайте и не закрывайте крышку ноутбука** в магазине — сервис остановится, пока кто-то физически не включит его обратно.
2. **Ноутбук всегда должен быть подключён к питанию и к интернету/VPN.** Если кабель выдернут или пропала сеть — подключите обратно.
3. **Не открывайте и не редактируйте файлы в папке `havas-pilot`** на ноутбуке без разработчиков — там боевая конфигурация.
4. Если статус выше показывает 🔴 дольше часа — в Telegram уже должен был прийти автоматический алерт. Если алерта не было, а статус красный — напишите разработчикам.
""")


def format_duration(minutes):
    if minutes is None:
        return "ещё длится"
    if minutes < 60:
        return f"{minutes} мин"
    hours, mins = divmod(minutes, 60)
    return f"{hours} ч {mins} мин"


TYPE_LABEL = {"camera": "📷 камера", "service": "🖥️ сервис/интернет"}
REPORT_WINDOW_DAYS = 7


def compute_incident_report(incidents, window_days=REPORT_WINDOW_DAYS):
    """Uptime % and downtime-by-type over a fixed trailing window.

    Incidents are clipped to the window — one that started before the
    window but ended inside it only counts its overlap, not its full span.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=window_days)
    window_total_min = window_days * 24 * 60
    by_type = defaultdict(lambda: {"count": 0, "minutes": 0.0})
    for inc in incidents:
        started = pd.to_datetime(inc["started_at"], utc=True).to_pydatetime()
        ended = pd.to_datetime(inc["ended_at"], utc=True).to_pydatetime() if inc.get("ended_at") else now
        if ended < cutoff:
            continue
        overlap_start = max(started, cutoff)
        minutes = (ended - overlap_start).total_seconds() / 60
        if minutes <= 0:
            continue
        t = inc.get("type") or "unknown"
        by_type[t]["count"] += 1
        by_type[t]["minutes"] += minutes
    total_down = sum(v["minutes"] for v in by_type.values())
    uptime_pct = 100 * (1 - total_down / window_total_min)
    return uptime_pct, total_down, by_type


incidents = fetch_incidents(limit=50)
if incidents:
    uptime_pct, total_down_min, by_type = compute_incident_report(incidents)
    r1, r2, r3 = st.columns(3)
    with r1:
        metric_card(f"Uptime ({REPORT_WINDOW_DAYS} дней)", f"{uptime_pct:.1f}%")
    with r2:
        metric_card("Простой всего", format_duration(round(total_down_min)) if total_down_min else "0 мин")
    with r3:
        rows = [
            (TYPE_LABEL.get(t, t), f'{format_duration(round(v["minutes"]))} ({v["count"]})')
            for t, v in sorted(by_type.items(), key=lambda kv: -kv[1]["minutes"])
        ]
        breakdown_card(f"Простой по причине ({REPORT_WINDOW_DAYS} дней)", rows)

    with st.expander(f"📉 История простоев ({len(incidents)})"):
        # Built as single-line HTML (no embedded newlines/indentation) —
        # Streamlit's markdown parser otherwise treats an indented line
        # after a blank line as a literal code block, not HTML.
        rows_html = []
        for inc in incidents:
            started = pd.to_datetime(inc["started_at"], utc=True).tz_convert(TASHKENT_TZ)
            duration = format_duration(inc.get("duration_min"))
            type_label = TYPE_LABEL.get(inc.get("type"), inc.get("type") or "неизвестно")
            ongoing = inc.get("ended_at") is None
            accent = STATUS_CRITICAL if ongoing else TEXT_MUTED
            status_text = "идёт сейчас" if ongoing else f"простой {duration}"
            rows_html.append(
                f'<div style="display:flex;align-items:center;justify-content:space-between;gap:12px;'
                f'padding:10px 14px;margin-bottom:6px;border-radius:8px;'
                f'background:{SURFACE};border-left:3px solid {accent}">'
                f'<span style="color:{TEXT_PRIMARY};font-weight:600;font-size:14px">{started.strftime("%d.%m.%Y %H:%M")}</span>'
                f'<span style="color:{TEXT_SECONDARY};font-size:13px">{status_text}</span>'
                f'<span style="background:{TEXT_MUTED}1a;color:{TEXT_SECONDARY};padding:3px 10px;'
                f'border-radius:12px;font-size:12px;font-weight:600;white-space:nowrap">{type_label}</span>'
                f'</div>'
            )
        st.markdown("".join(rows_html), unsafe_allow_html=True)

st.divider()

# --- Period selector (drives everything below except the 30-day heatmap/trend) ---
today_local = datetime.now(TASHKENT_TZ).date()

period_choice = st.radio(
    "Период", ["Сегодня", "Вчера", "Неделя", "Месяц", "Свой период"],
    horizontal=True,
)

if period_choice == "Сегодня":
    period_start, period_end = day_bounds(today_local)
    hourly_mode = True
elif period_choice == "Вчера":
    period_start, period_end = day_bounds(today_local - timedelta(days=1))
    hourly_mode = True
elif period_choice == "Неделя":
    period_start, _ = day_bounds(today_local - timedelta(days=6))
    period_end = datetime.now(TASHKENT_TZ)
    hourly_mode = False
elif period_choice == "Месяц":
    period_start, _ = day_bounds(today_local - timedelta(days=29))
    period_end = datetime.now(TASHKENT_TZ)
    hourly_mode = False
else:
    picked = st.date_input(
        "Диапазон дат",
        value=(today_local - timedelta(days=6), today_local),
        max_value=today_local,
    )
    if isinstance(picked, tuple) and len(picked) == 2:
        period_start, _ = day_bounds(picked[0])
        _, period_end = day_bounds(picked[1])
    else:
        period_start, period_end = day_bounds(today_local)
    hourly_mode = period_start.date() == period_end.date()

df_period = fetch_visits(period_start, period_end)
df_in = df_period[df_period["direction"] == "IN"]

# A fixed 30-day window, independent of the period selector, for the
# heatmap and retention trend — those need a stable amount of history.
df_30 = fetch_visits(datetime.now(TASHKENT_TZ) - timedelta(days=30), datetime.now(TASHKENT_TZ))

st.divider()

# --- KPI metrics ---
total_in = len(df_in)
new_count = int((~df_in["is_repeat"]).sum()) if total_in else 0
repeat_count = int(df_in["is_repeat"].sum()) if total_in else 0
new_pct = (new_count / total_in * 100) if total_in else 0
repeat_pct = (repeat_count / total_in * 100) if total_in else 0

dwell = compute_dwell_times(df_period)
avg_dwell = dwell["duration_min"].mean() if not dwell.empty else None
median_dwell = dwell["duration_min"].median() if not dwell.empty else None

# Compare against the immediately preceding period, using the SAME elapsed
# duration — not the full previous period. Otherwise "Сегодня" (a partial
# day, still in progress) gets compared against a complete "Вчера" and
# always looks artificially down.
now_local = datetime.now(TASHKENT_TZ)
effective_end = min(now_local, period_end)
elapsed = effective_end - period_start
nominal_length = period_end - period_start
prev_start = period_start - nominal_length
prev_end = prev_start + elapsed
df_prev_in = fetch_visits(prev_start, prev_end)
prev_total_in = len(df_prev_in[df_prev_in["direction"] == "IN"])
delta_pct = ((total_in - prev_total_in) / prev_total_in * 100) if prev_total_in else None

col1, col2, col3, col4 = st.columns(4)
with col1:
    metric_card(
        f"Входов ({period_choice.lower()})", str(total_in),
        delta=f"{delta_pct:+.0f}% vs пред. период (то же время)" if delta_pct is not None else None,
        delta_positive=delta_pct is not None and delta_pct >= 0,
    )
with col2:
    metric_card("Новые", f"{new_count} ({new_pct:.0f}%)")
with col3:
    metric_card("Повторные", f"{repeat_count} ({repeat_pct:.0f}%)")
with col4:
    metric_card(
        "Время в магазине (медиана / среднее)",
        f"{median_dwell:.0f} / {avg_dwell:.0f} мин" if avg_dwell else "—",
    )

st.divider()

# --- Charts row 1: time breakdown + new vs repeat ---
col_left, col_right = st.columns(2)

with col_left:
    if hourly_mode:
        st.subheader("Входы по часам (новые / повторные)")
        df_hourly = df_in.copy()
        df_hourly["hour"] = df_hourly["timestamp"].dt.hour
        df_hourly["Тип"] = df_hourly["is_repeat"].map({False: "Новые", True: "Повторные"})
        hourly = df_hourly.groupby(["hour", "Тип"]).size().reset_index(name="count")
        all_combos = pd.MultiIndex.from_product(
            [WORK_HOURS, ["Новые", "Повторные"]], names=["hour", "Тип"]
        ).to_frame(index=False)
        hourly = all_combos.merge(hourly, on=["hour", "Тип"], how="left").fillna(0)
        fig = px.bar(hourly, x="hour", y="count", color="Тип",
                     labels={"hour": "Час", "count": "Входов"},
                     color_discrete_map={"Новые": COLOR_NEW, "Повторные": COLOR_REPEAT})
        fig.update_xaxes(dtick=1)
        st.plotly_chart(style_fig(fig), width="stretch")
    else:
        st.subheader("Входы по дням (новые / повторные)")
        df_daily = df_in.copy()
        df_daily["date"] = df_daily["timestamp"].dt.date
        df_daily["Тип"] = df_daily["is_repeat"].map({False: "Новые", True: "Повторные"})
        daily = df_daily.groupby(["date", "Тип"]).size().reset_index(name="count")
        fig = px.bar(daily, x="date", y="count", color="Тип",
                     labels={"date": "Дата", "count": "Входов"},
                     color_discrete_map={"Новые": COLOR_NEW, "Повторные": COLOR_REPEAT})
        st.plotly_chart(style_fig(fig), width="stretch")
    if df_in.empty:
        st.info("Нет данных за этот период")

with col_right:
    st.subheader("Новые vs Повторные")
    if total_in:
        pie_data = df_in["is_repeat"].map({False: "Новые", True: "Повторные"}).value_counts().reset_index()
        pie_data.columns = ["Тип", "Количество"]
        fig_pie = px.pie(pie_data, names="Тип", values="Количество", hole=0.55,
                          color="Тип",
                          color_discrete_map={"Новые": COLOR_NEW, "Повторные": COLOR_REPEAT})
        fig_pie.update_traces(textinfo="percent+label", textfont_size=14, marker=dict(line=dict(color=SURFACE, width=2)))
        st.plotly_chart(style_fig(fig_pie), width="stretch")
    else:
        st.info("Нет данных за этот период")

# --- Charts row 2: dwell time comparison + retention trend ---
col_left2, col_right2 = st.columns(2)

with col_left2:
    st.subheader("Время в магазине: новые vs повторные")
    if not dwell.empty:
        dwell_avg = dwell.groupby("is_repeat")["duration_min"].mean().reset_index()
        dwell_avg["Тип"] = dwell_avg["is_repeat"].map({False: "Новые", True: "Повторные"})
        fig_dwell = px.bar(dwell_avg, x="Тип", y="duration_min",
                            labels={"duration_min": "Минут в среднем"},
                            color="Тип",
                            color_discrete_map={"Новые": COLOR_NEW, "Повторные": COLOR_REPEAT})
        st.plotly_chart(style_fig(fig_dwell), width="stretch")
    else:
        st.info("Недостаточно завершённых визитов (нужна пара IN+OUT) за этот период")

with col_right2:
    st.subheader("Доля повторных по неделям (30 дней)")
    if not df_30.empty:
        df_30_in = df_30[df_30["direction"] == "IN"].copy()
        df_30_in["week"] = df_30_in["timestamp"].dt.strftime("%Y-W%U")
        weekly = df_30_in.groupby("week")["is_repeat"].mean().reset_index()
        weekly["repeat_pct"] = weekly["is_repeat"] * 100
        if len(weekly) < 2:
            st.info("Пока только одна неделя данных — тренд появится, когда накопится история за несколько недель")
        else:
            fig_trend = px.line(weekly, x="week", y="repeat_pct",
                                 labels={"week": "Неделя", "repeat_pct": "% повторных"},
                                 markers=True,
                                 color_discrete_sequence=[COLOR_TREND])
            fig_trend.update_traces(line=dict(width=2), marker=dict(size=8))
            st.plotly_chart(style_fig(fig_trend), width="stretch")
    else:
        st.info("Нет данных за последние 30 дней")

st.divider()

# --- Heatmap: day of week x hour, fixed 30-day window ---
st.subheader("Тепловая карта загруженности (последние 30 дней)")
if not df_30.empty:
    df_hm = df_30[df_30["direction"] == "IN"].copy()
    df_hm["weekday"] = df_hm["timestamp"].dt.day_name()
    df_hm["hour"] = df_hm["timestamp"].dt.hour
    weekday_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    weekday_ru = {
        "Monday": "Пн", "Tuesday": "Вт", "Wednesday": "Ср", "Thursday": "Чт",
        "Friday": "Пт", "Saturday": "Сб", "Sunday": "Вс",
    }
    heat = df_hm.groupby(["weekday", "hour"]).size().reset_index(name="count")
    pivot = heat.pivot(index="weekday", columns="hour", values="count").reindex(
        index=weekday_order, columns=WORK_HOURS
    ).fillna(0)
    pivot.index = [weekday_ru[d] for d in pivot.index]
    pivot = pivot.loc[(pivot != 0).any(axis=1), :]  # drop days with zero visits across all hours
    pivot_display = pivot.replace(0, np.nan)  # blank cells instead of a solid color for zero
    # Sequential magnitude → one hue, light to dark (not a rainbow).
    sequential_scale = [(0.0, "#cde2fb"), (0.35, "#6da7ec"), (0.65, "#2a78d6"), (1.0, "#0d366b")]
    fig_heat = px.imshow(pivot_display, labels=dict(x="Час", y="День недели", color="Входов"),
                          color_continuous_scale=sequential_scale, range_color=(0, pivot.values.max()),
                          aspect="auto", text_auto=True)
    st.plotly_chart(style_fig(fig_heat, height=400), width="stretch")
else:
    st.info("Нет данных за последние 30 дней")

st.divider()

# --- Weekly pattern: total traffic per weekday, fixed 30-day window ---
st.subheader("Трафик по дням недели (последние 30 дней)")
if not df_30.empty:
    df_wd = df_30[df_30["direction"] == "IN"].copy()
    df_wd["weekday"] = df_wd["timestamp"].dt.day_name()
    weekday_totals = (
        df_wd.groupby("weekday").size()
        .reindex(weekday_order).fillna(0).reset_index(name="count")
    )
    weekday_totals["День"] = weekday_totals["weekday"].map(weekday_ru)
    fig_weekday = px.area(weekday_totals, x="День", y="count",
                           labels={"count": "Входов"},
                           markers=True, line_shape="spline",
                           color_discrete_sequence=[COLOR_NEW])
    fig_weekday.update_traces(fillcolor=hex_to_rgba(COLOR_NEW, 0.15), line=dict(width=2), marker=dict(size=7))
    st.plotly_chart(style_fig(fig_weekday), width="stretch")
else:
    st.info("Нет данных за последние 30 дней")

st.divider()

# --- Live feed + export ---
st.subheader(f"Живая лента ({period_choice.lower()})")
if not df_period.empty:
    table = df_period.copy()
    table["Дата"] = table["timestamp"].dt.strftime("%d.%m.%Y")
    table["Время"] = table["timestamp"].dt.strftime("%H:%M:%S")
    table["Тип"] = table["is_repeat"].map({False: "Новый", True: "Повторный"})

    dir_colors = {"IN": COLOR_IN, "OUT": COLOR_OUT}
    dir_labels = {"IN": "Вошёл", "OUT": "Вышел"}
    type_colors = {"Новый": COLOR_NEW, "Повторный": COLOR_REPEAT}

    # Single-line HTML per row (see note above the incidents block) — an
    # indented multi-line f-string here gets swallowed as a code block.
    rows_html = [f'<div style="background:{SURFACE};border:1px solid {BORDER};border-radius:10px;overflow:hidden">']
    for i, (_, row) in enumerate(table.head(15).iterrows()):
        d_color = dir_colors[row["direction"]]
        t_color = type_colors[row["Тип"]]
        border = f"border-bottom:1px solid {GRIDLINE};" if i < 14 else ""
        rows_html.append(
            f'<div style="display:flex;align-items:center;justify-content:space-between;'
            f'padding:10px 14px;{border}">'
            f'<span style="color:{TEXT_SECONDARY};font-size:14px">{row["Дата"]} {row["Время"]}</span>'
            f'<span style="background:{d_color}1a;color:{d_color};padding:3px 10px;'
            f'border-radius:12px;font-size:12px;font-weight:600">{dir_labels[row["direction"]]}</span>'
            f'<span style="background:{t_color}1a;color:{t_color};padding:3px 10px;'
            f'border-radius:12px;font-size:12px;font-weight:600">{row["Тип"]}</span>'
            f'</div>'
        )
    rows_html.append("</div>")
    st.markdown("".join(rows_html), unsafe_allow_html=True)

    csv_bytes = table[["Дата", "Время", "direction", "Тип", "visitor_id"]].to_csv(index=False).encode("utf-8")
    st.download_button(
        "Скачать CSV за период", data=csv_bytes,
        file_name=f"havas_visits_{period_choice}.csv", mime="text/csv",
    )
else:
    st.info("Событий за этот период пока нет")

# --- Auto-refresh ---
time.sleep(config.DASHBOARD_REFRESH_SEC)
st.rerun()
