-- Aletheia — Supabase schema (Commits 2 + 9)
-- Run this once in the Supabase SQL editor.

create extension if not exists vector;

-- ── Missions ────────────────────────────────────────────────────────────────
create table if not exists missions (
  id          text primary key,              -- the WebSocket session id
  user_id     uuid references auth.users(id) on delete cascade,
  title       text,
  query       text not null,
  status      text not null default 'running'
              check (status in ('idle','running','awaiting_input','complete','error')),
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

create index if not exists missions_user_created_idx
  on missions (user_id, created_at desc);

-- ── Sources ─────────────────────────────────────────────────────────────────
create table if not exists sources (
  id              bigserial primary key,
  mission_id      text not null references missions(id) on delete cascade,
  url             text not null,
  title           text,
  snippet         text,
  source_type     text default 'web',
  published_year  int,
  favicon_url     text,
  scraped_at      timestamptz not null default now(),
  unique (mission_id, url)                    -- upsert target
);

create index if not exists sources_mission_idx on sources (mission_id);

-- ── Reports (with pgvector embedding) ───────────────────────────────────────
create table if not exists reports (
  id               bigserial primary key,
  mission_id       text not null references missions(id) on delete cascade,
  output_type      text not null default 'report'
                   check (output_type in ('table','swot','chart','report')),
  content          text,
  structured_data  jsonb,
  embedding        vector(768),               -- gemini-embedding-001 @ 768 dims
  created_at       timestamptz not null default now(),
  unique (mission_id)                         -- upsert target
);

-- HNSW, not ivfflat. ivfflat clusters rows into `lists` buckets and probes one
-- per query, so on a small table nearly every bucket is empty and a query
-- returns NOTHING even though matching rows exist. HNSW is accurate from the
-- first row and needs no training pass.
create index if not exists reports_embedding_idx
  on reports using hnsw (embedding vector_cosine_ops);

-- ── Semantic search over past research ──────────────────────────────────────
create or replace function match_reports(
  query_embedding vector(768),
  match_count int default 5
)
returns table (
  mission_id text,
  query text,
  content text,
  output_type text,
  similarity float
)
language sql stable
as $$
  select
    r.mission_id,
    m.query,
    r.content,
    r.output_type,
    1 - (r.embedding <=> query_embedding) as similarity
  from reports r
  join missions m on m.id = r.mission_id
  where r.embedding is not null
  order by r.embedding <=> query_embedding
  limit match_count;
$$;

-- ── Row Level Security ──────────────────────────────────────────────────────
-- The backend writes with the service-role key, which bypasses RLS. These
-- policies govern what a signed-in user can read from the browser.
alter table missions enable row level security;
alter table sources  enable row level security;
alter table reports  enable row level security;

drop policy if exists "own missions" on missions;
create policy "own missions" on missions
  for select using (auth.uid() = user_id);

drop policy if exists "own sources" on sources;
create policy "own sources" on sources
  for select using (
    exists (select 1 from missions m where m.id = sources.mission_id and m.user_id = auth.uid())
  );

drop policy if exists "own reports" on reports;
create policy "own reports" on reports
  for select using (
    exists (select 1 from missions m where m.id = reports.mission_id and m.user_id = auth.uid())
  );
