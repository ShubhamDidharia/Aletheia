# Aletheia — Strategic Intelligence Agent

An agent that *investigates* rather than summarises. Give it a research goal; it
breaks the goal into search tasks, gathers and validates sources, pauses to ask
you about genuine ambiguities, and streams every step to the UI in real time.

Implemented through **Commit 6 (Human-in-the-loop)** of the build plan.

---

## Prerequisites & API keys

| Key | Required | Where to get it | Used for |
|---|---|---|---|
| `GEMINI_API_KEY` | **yes** | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) — free tier | Planner agent, Analyst (contradiction detection) |
| `TAVILY_API_KEY` | **yes** | [app.tavily.com](https://app.tavily.com) — 1000 free credits/month | Web search |
| `REDIS_URL` | recommended | local Docker, or [Upstash](https://upstash.com) free tier | Thought stream, checkpoints, search cache |
| `NEXT_PUBLIC_SUPABASE_URL` / `..._ANON_KEY` | for auth | [supabase.com](https://supabase.com) | Google sign-in, route protection |

Without a reachable `REDIS_URL` the backend still runs, but in **degraded mode**:
state lives in process memory, is lost on restart, and cannot be shared across
workers. `GET /health` reports which mode you're in.

---

## Setup

```bash
docker compose up -d
```

**Backend**

```bash
cd backend && python -m venv venv && venv/Scripts/activate && pip install -r requirements.txt
```

Copy `.env.example` to `.env`, fill in the keys, then:

```bash
cd backend && uvicorn main:app --reload
```

**Frontend**

```bash
cd frontend && npm install && npm run dev
```

Open http://localhost:3000.

---

## Verifying it works

```bash
curl http://localhost:8000/health
```

Returns `{"status":"ok","redis":"ok","missing_keys":[]}` when fully configured.

Drive a full mission over the WebSocket, answer every decision gate, and assert
the protocol behaves — including a simulated page refresh mid-pause:

```bash
cd backend && python test_ws.py "Compare Apple and Microsoft 2026 ESG carbon targets"
```

---

## Architecture

```
Next.js ──WebSocket──> FastAPI ──> LangGraph ──> Gemini (plan / analyse)
                          │                  └──> Tavily (search)
                          └──> Redis (pub/sub thought stream + checkpoints + cache)
```

### The agent graph

| Node | Does |
|---|---|
| `plan_node` | Gemini breaks the goal into 3–4 searchable sub-tasks and judges whether the scope is too broad |
| `research_node` | Runs **exactly one** sub-task, validates results with Pydantic, streams `SOURCE_FOUND` |
| `analyze_node` | Detects stale sources and asks Gemini for genuine contradictions |
| `gate_node` | Handles **one** ambiguity gate: `interrupt()`, then applies the decision |
| `finalize_node` | Emits `COMPLETE` |

**Why gates are their own node.** LangGraph re-executes a node from the top when
it resumes from `interrupt()`. An interrupt inside the research loop re-runs
every Tavily call in that node and re-emits every `SOURCE_FOUND`, once per user
decision. Keeping `research_node` to one sub-task and confining `interrupt()` to
a side-effect-free `gate_node` makes re-execution free.

### Ambiguity junctions

The agent pauses at most once per junction per mission, and each decision has a
real effect on what it does next:

| Gate | Fires when | Choosing… |
|---|---|---|
| **scope** | the planner judges the query has no region, timeframe or named entities | *Narrow* re-plans against the narrowed query |
| **recency** | ≥2 sources are >3 years old **and** some are current | *Stick to recent* drops them and re-syncs the library |
| **conflict** | Gemini finds two sources that factually contradict each other | *Tie-breaker* appends a new search task and runs it |

### Message protocol

`STATUS_UPDATE`, `LOG`, `SOURCE_FOUND`, `SOURCES_SYNC`, `AWAITING_INPUT`,
`COMPLETE`, `ERROR` — defined and validated in `backend/schemas/messages.py`.
Every outgoing event is validated against these models, so the backend cannot
silently drift from what the frontend expects.

### Resuming after a refresh

Events are appended to a capped Redis list per session. On reconnect the backend
replays that history, then re-asks any pending decision gate — so a page refresh
mid-mission restores the whole thought stream instead of a blank feed. The
session id is persisted in `sessionStorage`, which is what makes the id stable
across the reload.

---

## Not yet built (commits 7–10)

Auditor and Visualizer agents, `ResponseDispatcher` with DataTable/SWOT/chart
rendering, Playwright scraper, Supabase persistence of missions and reports,
pgvector embeddings, mission history sidebar, deployment config.
