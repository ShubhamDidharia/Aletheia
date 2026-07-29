-- Aletheia — reset Supabase tables to the schema the backend expects.
--
-- WHEN TO USE THIS
-- Only if `missions` / `sources` / `reports` already exist from an earlier
-- design. `create table if not exists` will NOT alter an existing table, so a
-- mismatched one is skipped silently and every write then fails at runtime.
--
-- ** DESTRUCTIVE: this DROPS those three tables and everything in them. **
-- Check they are empty first:
--     select
--       (select count(*) from missions) as missions,
--       (select count(*) from sources)  as sources,
--       (select count(*) from reports)  as reports;
-- If any count is non-zero and you want to keep it, back it up before running.
--
-- Otherwise use supabase_schema.sql, which is non-destructive.

drop table if exists reports cascade;
drop table if exists sources cascade;
drop table if exists missions cascade;
drop function if exists match_reports(vector, int);

create extension if not exists vector;

-- ── Missions ────────────────────────────────────────────────────────────────
-- id is TEXT, not uuid: it is the WebSocket session id, which falls back to a
-- non-UUID form when crypto.randomUUID() is unavailable.
-- user_id is NULLABLE: missions are keyed by session today, and nothing sets a
-- user id yet. A NOT NULL constraint here would reject every insert.
create table missions (
  id          text primary key,
  user_id     uuid references auth.users(id) on delete cascade,
  title       text,
  query       text not null,
  status      text not null default 'running'
              check (status in ('idle','running','awaiting_input','complete','error')),
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

create index missions_user_created_idx on missions (user_id, created_at desc);

-- ── Sources ─────────────────────────────────────────────────────────────────
create table sources (
  id              bigserial primary key,
  mission_id      text not null references missions(id) on delete cascade,
  url             text not null,
  title           text,
  snippet         text,
  source_type     text default 'web',
  published_year  int,
  favicon_url     text,
  scraped_at      timestamptz not null default now(),
  unique (mission_id, url)          -- required: the backend upserts on this
);

create index sources_mission_idx on sources (mission_id);

-- ── Reports ─────────────────────────────────────────────────────────────────
-- vector(768) matches gemini-embedding-001 with output_dimensionality=768.
-- If you change one, change the other and match_reports() below.
create table reports (
  id               bigserial primary key,
  mission_id       text not null references missions(id) on delete cascade,
  output_type      text not null default 'report'
                   check (output_type in ('table','swot','chart','report')),
  content          text,
  structured_data  jsonb,
  embedding        vector(768),
  created_at       timestamptz not null default now(),
  unique (mission_id)               -- required: the backend upserts on this
);

-- HNSW, not ivfflat. ivfflat clusters rows into `lists` buckets and probes one
-- per query, so on a small table nearly every bucket is empty and a query
-- returns NOTHING even though matching rows exist. HNSW is accurate from the
-- first row and needs no training pass.
create index reports_embedding_idx
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
-- The backend writes with the secret key, which bypasses RLS. These policies
-- govern browser reads. Note: they match on user_id, which is not populated
-- yet — so nothing is readable from the client until missions carry a user.
alter table missions enable row level security;
alter table sources  enable row level security;
alter table reports  enable row level security;

create policy "own missions" on missions
  for select using (auth.uid() = user_id);

create policy "own sources" on sources
  for select using (
    exists (select 1 from missions m where m.id = sources.mission_id and m.user_id = auth.uid())
  );

create policy "own reports" on reports
  for select using (
    exists (select 1 from missions m where m.id = reports.mission_id and m.user_id = auth.uid())
  );
