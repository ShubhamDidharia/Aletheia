# Deploying Aletheia

Frontend on **Vercel**, backend + Redis on **Render** (a Railway config is
included too), Supabase for auth and long-term memory.

---

## 0. Before you start

| Service | What you need | Notes |
|---|---|---|
| [Google AI Studio](https://aistudio.google.com/apikey) | `GEMINI_API_KEY` | **Free tier is ~20 requests/day per model.** A mission costs 4 calls (planner, analyst, auditor, visualizer) plus 1 for the contradiction sweep and 1 for the embedding. Enable billing before real use. |
| [Tavily](https://app.tavily.com) | `TAVILY_API_KEY` | 1000 free credits/month; 1 credit per sub-task. |
| [Supabase](https://supabase.com) | project URL, anon key, service-role key | Auth + persistence. |
| Redis | provisioned by `render.yaml` | Or Redis Cloud / Upstash. |

---

## 1. Supabase

1. Create a project.
2. **SQL Editor** → run [`backend/supabase_schema.sql`](backend/supabase_schema.sql).
   It enables `pgvector`, creates `missions` / `sources` / `reports`, the
   `match_reports` search function, and RLS policies.
3. **Authentication → Providers → Google**: enable it, paste your Google OAuth
   client ID and secret.
4. **Authentication → URL Configuration**:
   - Site URL: `https://<your-app>.vercel.app`
   - Redirect URLs: `https://<your-app>.vercel.app/auth/callback`
     (add `http://localhost:3000/auth/callback` for local work)
5. **Project Settings → API**: copy the project URL, the `anon` key, and the
   `service_role` key.

> The `service_role` key bypasses Row Level Security. It belongs in the backend
> only — never in `NEXT_PUBLIC_*`, never in the browser.

---

## 2. Backend on Render

Push the repo, then **New → Blueprint** and point it at this repository.
[`render.yaml`](render.yaml) provisions the web service and a Redis instance,
and wires `REDIS_URL` between them automatically.

Set these in the dashboard after the first deploy:

```
GEMINI_API_KEY, TAVILY_API_KEY,
SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY,
CORS_ORIGINS = https://<your-app>.vercel.app
```

Verify:

```bash
curl https://<your-api>.onrender.com/health
```

Expect `{"status":"ok","redis":"ok","missing_keys":[]}`.

### Why one worker

`startCommand` pins `--workers 1` deliberately. LangGraph's `MemorySaver` keeps
interrupt state **in process**, so a mission paused on a decision gate must
return to the same worker to resume. Redis carries the thought stream, the
checkpoint and the replay log across reconnects, but not the graph's own
interrupt state.

To scale horizontally you need a Redis-backed LangGraph checkpointer, at which
point workers become interchangeable. Until then, more workers means resumes
that land on the wrong process and hang.

### Playwright (optional)

The scraper fallback needs a browser in the image:

```bash
pip install -r requirements.txt && playwright install --with-deps chromium
```

That adds several hundred MB. Without it the app runs fine and simply skips
pages Tavily can't read — the startup log says which mode you're in.

---

## 3. Frontend on Vercel

Import the repo and set **Root Directory** to `frontend`. Environment
variables:

```
NEXT_PUBLIC_SUPABASE_URL       = https://<project>.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY  = <anon key>
NEXT_PUBLIC_WS_URL             = wss://<your-api>.onrender.com/ws/research
NEXT_PUBLIC_API_URL            = https://<your-api>.onrender.com
```

**`wss://`, not `ws://`.** A page served over HTTPS refuses to open an insecure
WebSocket, and the failure looks like "the backend is down" rather than a mixed
content error.

---

## 4. Post-deploy checks

1. `GET /health` → `redis: ok`, `missing_keys: []`.
2. Visit the app signed out → redirected to `/login`.
3. Sign in with Google → lands on `/dashboard`.
4. Run a mission → the thought stream should be live, not a single burst at the
   end. If everything arrives at once, `NEXT_PUBLIC_WS_URL` is wrong and the
   client never opened the socket.
5. Answer a decision gate → the agent should continue. If it hangs, you are
   almost certainly running more than one worker.
6. Backend logs should say `Supabase: missions will be persisted with
   embeddings.` — otherwise the service-role key is missing.

---

## 5. Known limits

- **A backend restart loses an in-flight mission.** LangGraph state is in
  process; page refreshes are covered by Redis replay, process restarts are not.
- **Single worker** (see above).
- **Gemini free tier** will not survive real traffic — roughly 3 missions/day.
- **Mission history is per browser** (`localStorage`). Missions *are* persisted
  to Supabase, but the sidebar does not yet read them back.

---

## Railway instead of Render

[`railway.json`](railway.json) is included. Add a Redis plugin, set the same
env vars, and point `REDIS_URL` at the plugin's connection string. Everything
else is identical.
