# Havas Pilot heartbeat monitor

Cloudflare Worker that polls the Supabase `heartbeat` table every 5 minutes
and alerts `@havas_pilot_monitor_bot` on Telegram when the service goes
silent for more than `THRESHOLD_MIN` (15 min), and again when it recovers.

Live at: https://havas-pilot-monitor.isaev-saf.workers.dev

This code is **not** auto-deployed from this repo — it's committed here
only so the source isn't stranded in a Cloudflare dashboard. To ship a
change:

```
cd monitor
npx wrangler deploy
```

State (`status`, `down_count`) lives in the `havas_pilot_monitor` KV
namespace, bound as `MONITOR_KV`. `TELEGRAM_BOT_TOKEN` is a Worker secret
(`npx wrangler secret put TELEGRAM_BOT_TOKEN`), not in this code.
