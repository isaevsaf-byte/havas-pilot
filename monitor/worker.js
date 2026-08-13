const SUPABASE_URL = "https://kxyyvnxklbczuofzaoow.supabase.co";
const SUPABASE_KEY = "sb_publishable_79gUEoh_qoocFxnwied-Tw_IE3uU00j";
const CHAT_ID = "90364962";
const THRESHOLD_MIN = 15;      // alert if no heartbeat for longer than this
const REMINDER_EVERY = 4;      // with a 5-min cron, resend "still down" every ~20 min

export default {
  async scheduled(event, env, ctx) {
    ctx.waitUntil(checkHeartbeat(env));
  },
  async fetch(request, env, ctx) {
    // Manual trigger for testing: GET this worker's URL.
    await checkHeartbeat(env);
    return new Response("checked\n");
  },
};

async function checkHeartbeat(env) {
  const res = await fetch(`${SUPABASE_URL}/rest/v1/heartbeat?select=*`, {
    headers: {
      apikey: SUPABASE_KEY,
      Authorization: `Bearer ${SUPABASE_KEY}`,
    },
  });
  const data = await res.json();
  const row = data && data[0];
  if (!row) {
    console.log("No heartbeat row found");
    return;
  }

  const lastSeen = new Date(row.last_seen);
  const ageMin = (Date.now() - lastSeen.getTime()) / 60000;
  const prevStatus = (await env.MONITOR_KV.get("status")) || "up";

  if (ageMin > THRESHOLD_MIN) {
    if (prevStatus === "up") {
      await sendTelegram(
        env,
        `🔴 Havas Pilot: сервис не отвечает уже ${Math.round(ageMin)} мин (последний сигнал: ${row.last_seen})`
      );
      await env.MONITOR_KV.put("status", "down");
      await env.MONITOR_KV.put("down_count", "0");
    } else {
      const count = parseInt((await env.MONITOR_KV.get("down_count")) || "0", 10) + 1;
      await env.MONITOR_KV.put("down_count", String(count));
      if (count % REMINDER_EVERY === 0) {
        await sendTelegram(
          env,
          `🔴 Havas Pilot: всё ещё не отвечает (простой ~${Math.round(ageMin)} мин)`
        );
      }
    }
  } else if (prevStatus === "down") {
    await sendTelegram(
      env,
      `✅ Havas Pilot: сервис снова отвечает (простой ~${Math.round(ageMin)} мин с последнего сигнала)`
    );
    await env.MONITOR_KV.put("status", "up");
    await env.MONITOR_KV.put("down_count", "0");
  }
}

async function sendTelegram(env, text) {
  await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: `chat_id=${CHAT_ID}&text=${encodeURIComponent(text)}`,
  });
}
