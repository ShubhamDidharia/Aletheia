# Aletheia — Strategic Intelligence Agent

An agent that *investigates* rather than summarises. Give it a research goal; it
breaks the goal into search tasks, gathers and validates sources, pauses to ask
you about genuine ambiguities, and streams every step to the UI in real time.

Implemented through **Commit 7 (Auditor + Visualizer + structured output)** of
the build plan.

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

Regression test for the decision-gate race (answering the instant the question
arrives). Uses a stub graph, so it costs no Gemini or Tavily quota:

```bash
cd backend && python test_race.py
```

Auditor citation enforcement and Visualizer payload validation, with the LLM
stubbed — also free:

```bash
cd backend && python test_commit7.py
```

> **Gemini free tier is ~20 requests/day per model.** As of Commit 7 a mission
> costs **4 calls** — planner, conflict analyst, auditor, visualizer (5 if you
> narrow the scope) — so roughly 5 missions/day. If you see
> `Gemini quota exhausted`, wait for the midnight-Pacific reset or enable
> billing on the Google Cloud project.

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
| `audit_node` | **Node 3** — extracts findings and deletes any claim whose citation doesn't resolve |
| `visualize_node` | **Node 4** — picks table / SWOT / chart / report and fills the matching schema |
| `finalize_node` | Emits `COMPLETE` with `ui` and `data` |

### Auditor and Visualizer (Commit 7)

The **Auditor** asks Gemini to extract factual claims, each tagged with the URL
it came from — then verifies every citation **in code** against the URLs the
Researcher actually gathered. A claim citing a URL that was never fetched is
deleted. The model is not trusted to police itself, which is what makes this a
hallucination check rather than a second opinion from the same model. URL
matching normalises scheme, `www.`, trailing slash, case and fragment, so
cosmetic rewrites don't cause false deletions.

The **Visualizer** picks the output shape in a single call (one call rather than
choose-then-generate, to keep request count down). The result is then validated
in code: a `table` with ragged rows is padded or truncated to the header width,
and a `table` with no payload, an empty `swot`, or a `chart` with fewer than two
points is downgraded to `report` rather than shipped to the UI as a broken
component.

Both fail open — if Gemini is unavailable the mission still completes with its
sources, as a plain report.

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

### The interface

One workspace at `/dashboard` (`/` redirects to it). Three panels at ≥1280px,
collapsing to drawers below:

- **Missions** — history for this browser, with live status per mission.
- **Thought stream** — the agent's actions on a vertical rail, with a phase
  stepper (Plan → Research → Analyse → Audit → Present) driven by the same
  `STATUS_UPDATE` phases the graph emits.
- **Evidence** — every source, with favicon, publication year and a filter.

When the agent hits an ambiguity junction the stream is replaced by a decision
card that states the question in plain language, explains why it's being asked,
and takes keyboard focus. Status colour is never the only signal — every state
ships with an icon and a label.

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

## Not yet built (commits 8–10)

`ResponseDispatcher` proper — a sortable/filterable Shadcn DataTable, a
four-quadrant SWOT grid, Recharts charts, and per-cell audit-trail tooltips.
(`ResultPanel.tsx` renders Commit 7's output plainly in the meantime.) Also:
Playwright scraper, contradiction badges in the output table, Supabase
persistence of missions and reports, pgvector embeddings, mission history
sidebar, deployment config.
