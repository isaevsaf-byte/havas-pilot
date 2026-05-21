import sys
import os
import time
from datetime import datetime, timezone, timedelta

import streamlit as st
import pandas as pd
import plotly.express as px

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

st.set_page_config(page_title="Havas Analytics", layout="wide")
st.title("Havas Analytics")

if not config.SUPABASE_URL:
    st.warning("Настройте Supabase в config.py")
    st.stop()

from supabase import create_client

@st.cache_resource
def get_client():
    return create_client(config.SUPABASE_URL, config.SUPABASE_KEY)

client = get_client()


def fetch_heartbeat():
    row = (
        client.table("heartbeat")
        .select("last_seen")
        .eq("store", config.STORE_NAME)
        .maybe_single()
        .execute()
    )
    return row.data


def fetch_visits(days=None):
    q = (
        client.table("visits")
        .select("timestamp, direction, is_repeat, visitor_id")
        .eq("store", config.STORE_NAME)
        .order("timestamp", desc=True)
    )
    if days is not None:
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        q = q.gte("timestamp", since)
    result = q.execute()
    if not result.data:
        return pd.DataFrame(columns=["timestamp", "direction", "is_repeat", "visitor_id"])
    df = pd.DataFrame(result.data)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    return df


# --- Status bar ---
heartbeat = fetch_heartbeat()
if heartbeat:
    last_seen = pd.to_datetime(heartbeat["last_seen"], utc=True)
    age = datetime.now(timezone.utc) - last_seen
    if age < timedelta(minutes=10):
        st.success("🟢 Система работает")
    else:
        st.error(f"🔴 Система не отвечает — последний сигнал: {last_seen.strftime('%d.%m.%Y %H:%M')}")
else:
    st.error("🔴 Нет данных о статусе системы")

st.divider()

# --- KPI metrics ---
df_all = fetch_visits()
df_30 = fetch_visits(days=30)

today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
if not df_all.empty:
    df_today = df_all[
        (df_all["direction"] == "IN") &
        (df_all["timestamp"].dt.date == pd.Timestamp(today_str).date())
    ]
    df_7d = df_all[
        (df_all["direction"] == "IN") &
        (df_all["timestamp"] >= datetime.now(timezone.utc) - timedelta(days=7))
    ]
    total_in = df_all[df_all["direction"] == "IN"]
else:
    df_today = df_7d = total_in = pd.DataFrame()

col1, col2, col3 = st.columns(3)
col1.metric("Сегодня (входов)", len(df_today))
col2.metric("За 7 дней", len(df_7d))
col3.metric("Всего за всё время", len(total_in))

st.divider()

# --- Charts ---
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("Входы по часам сегодня")
    if not df_all.empty:
        df_today_in = df_all[
            (df_all["direction"] == "IN") &
            (df_all["timestamp"].dt.date == pd.Timestamp(today_str).date())
        ].copy()
        df_today_in["hour"] = df_today_in["timestamp"].dt.hour
        hourly = df_today_in.groupby("hour").size().reset_index(name="count")
        all_hours = pd.DataFrame({"hour": range(24)})
        hourly = all_hours.merge(hourly, on="hour", how="left").fillna(0)
        fig = px.bar(hourly, x="hour", y="count",
                     labels={"hour": "Час", "count": "Входов"},
                     color_discrete_sequence=["#1f77b4"])
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Нет данных за сегодня")

with col_right:
    st.subheader("Входы по дням за 30 дней")
    if not df_30.empty:
        df_30_in = df_30[df_30["direction"] == "IN"].copy()
        df_30_in["date"] = df_30_in["timestamp"].dt.date
        daily = df_30_in.groupby("date").size().reset_index(name="count")
        fig2 = px.line(daily, x="date", y="count",
                       labels={"date": "Дата", "count": "Входов"},
                       markers=True,
                       color_discrete_sequence=["#2ca02c"])
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("Нет данных за последние 30 дней")

# --- Pie chart ---
st.subheader("Новые vs Повторные (30 дней)")
if not df_30.empty:
    df_30_in = df_30[df_30["direction"] == "IN"]
    pie_data = df_30_in["is_repeat"].map({False: "Новые", True: "Повторные"}).value_counts().reset_index()
    pie_data.columns = ["Тип", "Количество"]
    fig3 = px.pie(pie_data, names="Тип", values="Количество",
                  color_discrete_sequence=["#1f77b4", "#ff7f0e"])
    st.plotly_chart(fig3, use_container_width=True)
else:
    st.info("Нет данных за последние 30 дней")

st.divider()

# --- Last 20 events table ---
st.subheader("Последние 20 событий")
if not df_all.empty:
    recent = df_all.head(20).copy()
    recent["Время"] = recent["timestamp"].dt.strftime("%d.%m.%Y %H:%M:%S")
    recent["Направление"] = recent["direction"]
    recent["Тип"] = recent["is_repeat"].map({False: "Новый", True: "Повторный"})
    st.dataframe(
        recent[["Время", "Направление", "Тип"]],
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info("Событий пока нет")

# --- Auto-refresh every 30 seconds ---
time.sleep(30)
st.rerun()
