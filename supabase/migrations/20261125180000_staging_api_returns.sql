-- Raw answers from agent APIs (e.g. OpenAI Responses API with web search), held until Claude extracts and loads them
-- as Shopping Query Returns. One row per turn: turn 0 = the shopping query, turn 1 = the matching follow-up.
create schema if not exists staging;
create table if not exists staging.api_returns (
  id            bigserial primary key,
  run_id        text not null,
  agent         text not null,
  query_id      text not null,
  turn          int  not null check (turn >= 0),
  requested_at  timestamptz not null,
  model         text,
  location      jsonb,
  prompt        text not null,
  output_text   text,
  citations     jsonb,
  response      jsonb,
  error         text,
  created_at    timestamptz not null default now(),
  unique (run_id, turn)
);
alter table staging.api_returns enable row level security;
