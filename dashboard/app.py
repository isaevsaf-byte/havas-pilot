import sys
import os
import time
from datetime import datetime, timezone, timedelta, date
from zoneinfo import ZoneInfo

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

TASHKENT_TZ = ZoneInfo("Asia/Tashkent")
WORK_HOURS = list(range(8, 22))  # 08:00–21:59, store operating hours

for key in ("SUPABASE_URL", "SUPABASE_KEY"):
    if key in st.secrets:
        os.environ[key] = st.secrets[key]

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

st.set_page_config(page_title="Havas Analytics", layout="wide")
st.title("Havas Analytics")

st.markdown("""
<style>
[data-testid="stMetric"] {
    background-color: rgba(128, 128, 128, 0.06);
    border: 1px solid rgba(128, 128, 128, 0.15);
    padding: 16px 18px;
    border-radius: 12px;
}
[data-testid="stMetricLabel"] { font-size: 13px; opacity: 0.75; }
</style>
""", unsafe_allow_html=True)

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
    st.warning("⚪ Нет данных от системы")
else:
    last_seen = pd.to_datetime(heartbeat["last_seen"], utc=True)
    age = datetime.now(timezone.utc) - last_seen
    last_seen_local = last_seen.tz_convert(TASHKENT_TZ)
    if age < timedelta(minutes=10):
        st.success("🟢 Система работает")
    else:
        st.error(f"🔴 Система не отвечает — последний сигнал: {last_seen_local.strftime('%d.%m.%Y %H:%M')}")

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

# Compare against the immediately preceding period of equal length
# (e.g. "Неделя" compares to the week before it) to show a trend arrow.
period_length = period_end - period_start
prev_start = period_start - period_length
prev_end = period_start - timedelta(microseconds=1)
df_prev_in = fetch_visits(prev_start, prev_end)
prev_total_in = len(df_prev_in[df_prev_in["direction"] == "IN"])
delta_pct = ((total_in - prev_total_in) / prev_total_in * 100) if prev_total_in else None

col1, col2, col3, col4 = st.columns(4)
col1.metric(
    f"Входов ({period_choice.lower()})", total_in,
    delta=f"{delta_pct:+.0f}% vs пред. период" if delta_pct is not None else None,
)
col2.metric("Новые", f"{new_count} ({new_pct:.0f}%)")
col3.metric("Повторные", f"{repeat_count} ({repeat_pct:.0f}%)")
col4.metric(
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
                     color_discrete_map={"Новые": "#1f77b4", "Повторные": "#ff7f0e"})
        fig.update_xaxes(dtick=1)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.subheader("Входы по дням (новые / повторные)")
        df_daily = df_in.copy()
        df_daily["date"] = df_daily["timestamp"].dt.date
        df_daily["Тип"] = df_daily["is_repeat"].map({False: "Новые", True: "Повторные"})
        daily = df_daily.groupby(["date", "Тип"]).size().reset_index(name="count")
        fig = px.bar(daily, x="date", y="count", color="Тип",
                     labels={"date": "Дата", "count": "Входов"},
                     color_discrete_map={"Новые": "#1f77b4", "Повторные": "#ff7f0e"})
        st.plotly_chart(fig, use_container_width=True)
    if df_in.empty:
        st.info("Нет данных за этот период")

with col_right:
    st.subheader("Новые vs Повторные")
    if total_in:
        pie_data = df_in["is_repeat"].map({False: "Новые", True: "Повторные"}).value_counts().reset_index()
        pie_data.columns = ["Тип", "Количество"]
        fig_pie = px.pie(pie_data, names="Тип", values="Количество", hole=0.55,
                          color="Тип",
                          color_discrete_map={"Новые": "#1f77b4", "Повторные": "#ff7f0e"})
        fig_pie.update_traces(textinfo="percent+label", textfont_size=14)
        st.plotly_chart(fig_pie, use_container_width=True)
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
                            color_discrete_map={"Новые": "#1f77b4", "Повторные": "#ff7f0e"})
        st.plotly_chart(fig_dwell, use_container_width=True)
    else:
        st.info("Недостаточно завершённых визитов (нужна пара IN+OUT) за этот период")

with col_right2:
    st.subheader("Доля повторных по неделям (30 дней)")
    if not df_30.empty:
        df_30_in = df_30[df_30["direction"] == "IN"].copy()
        df_30_in["week"] = df_30_in["timestamp"].dt.strftime("%Y-W%U")
        weekly = df_30_in.groupby("week")["is_repeat"].mean().reset_index()
        weekly["repeat_pct"] = weekly["is_repeat"] * 100
        fig_trend = px.line(weekly, x="week", y="repeat_pct",
                             labels={"week": "Неделя", "repeat_pct": "% повторных"},
                             markers=True,
                             color_discrete_sequence=["#2ca02c"])
        st.plotly_chart(fig_trend, use_container_width=True)
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
    pivot_display = pivot.replace(0, np.nan)  # blank cells instead of solid green for zero
    smooth_scale = [(0.0, "#2ca02c"), (0.5, "#ffeb3b"), (1.0, "#d32f2f")]
    fig_heat = px.imshow(pivot_display, labels=dict(x="Час", y="День недели", color="Входов"),
                          color_continuous_scale=smooth_scale, range_color=(0, pivot.values.max()),
                          aspect="auto", text_auto=True)
    fig_heat.update_layout(height=400, plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig_heat, use_container_width=True)
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

    dir_colors = {"IN": "#2ca02c", "OUT": "#d62728"}
    dir_labels = {"IN": "Вошёл", "OUT": "Вышел"}
    type_colors = {"Новый": "#1f77b4", "Повторный": "#ff7f0e"}

    rows_html = []
    for _, row in table.head(15).iterrows():
        d_color = dir_colors[row["direction"]]
        t_color = type_colors[row["Тип"]]
        rows_html.append(f"""
        <div style="display:flex;align-items:center;justify-content:space-between;
                    padding:10px 4px;border-bottom:1px solid rgba(128,128,128,0.15)">
            <span style="opacity:0.7;font-size:14px">{row['Дата']} {row['Время']}</span>
            <span style="background:{d_color}22;color:{d_color};padding:3px 10px;
                        border-radius:12px;font-size:12px;font-weight:600">{dir_labels[row['direction']]}</span>
            <span style="background:{t_color}22;color:{t_color};padding:3px 10px;
                        border-radius:12px;font-size:12px;font-weight:600">{row['Тип']}</span>
        </div>
        """)
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
