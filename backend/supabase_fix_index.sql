-- One-off fix: swap the report embedding index from ivfflat to HNSW.
--
-- Why: ivfflat clusters rows into `lists` buckets and probes only one per
-- query. On a small table almost every bucket is empty, so a search returns
-- ZERO rows even when a matching report exists — semantic search silently
-- finds nothing until the table holds thousands of rows.
--
-- HNSW is accurate from the very first row and needs no training pass.
-- Non-destructive: this touches only the index, never the data.

drop index if exists reports_embedding_idx;

create index reports_embedding_idx
  on reports using hnsw (embedding vector_cosine_ops);
