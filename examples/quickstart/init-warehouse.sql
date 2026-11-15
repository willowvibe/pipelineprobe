-- PipelineProbe quickstart warehouse fixture.
--
-- Runs once on the Postgres container's first start, because
-- docker-compose.yml mounts this file at /docker-entrypoint-initdb.d/.  All
-- data here is synthetic and generated locally; nothing is copied from a real
-- warehouse.
--
-- Two tables are sized to trip the Postgres rules:
--
--   analytics.fact_orders   10,000,100 rows, has created_at / updated_at
--                           -> "table is very large" warning (> 10,000,000)
--   raw.stg_events           1,200,100 rows, no audit timestamp columns
--                           -> "no updated_at/created_at" warning (> 1,000,000)
--
-- Tables are UNLOGGED and deliberately have no indexes: the bulk load stays
-- fast and the data is disposable.  Rows are produced with generate_series()
-- arithmetic -- no per-row loops and no UUIDs.

CREATE DATABASE warehouse;
\connect warehouse

CREATE SCHEMA IF NOT EXISTS analytics;
CREATE SCHEMA IF NOT EXISTS raw;

-- Idempotent-ish: the whole script only runs on an empty data directory, but
-- dropping the tables first keeps the table DDL safe to replay inside the
-- warehouse database by hand.
DROP TABLE IF EXISTS analytics.fact_orders;
DROP TABLE IF EXISTS raw.stg_events;

CREATE UNLOGGED TABLE analytics.fact_orders (
    order_id    bigint         NOT NULL,
    customer_id integer        NOT NULL,
    order_date  date           NOT NULL,
    amount      numeric(12, 2) NOT NULL,
    status      text           NOT NULL,
    created_at  timestamptz    NOT NULL,
    updated_at  timestamptz    NOT NULL
);

CREATE UNLOGGED TABLE raw.stg_events (
    event_id    bigint      NOT NULL,
    user_id     integer     NOT NULL,
    event_name  text        NOT NULL,
    occurred_at timestamptz NOT NULL,
    properties  text        NOT NULL
);

\echo 'quickstart: seeding analytics.fact_orders (10,000,100 rows)...'

INSERT INTO analytics.fact_orders (
    order_id, customer_id, order_date, amount, status, created_at, updated_at
)
SELECT
    g,
    (g % 50000) + 1,
    DATE '2024-01-01' + ((g % 730)::integer),
    ((g % 50000)::numeric / 100) + 5,
    CASE g % 5
        WHEN 0 THEN 'cancelled'
        WHEN 1 THEN 'returned'
        ELSE 'completed'
    END,
    TIMESTAMPTZ '2024-01-01 00:00:00+00' + ((g % 730)::integer * interval '1 day'),
    TIMESTAMPTZ '2024-01-01 00:00:00+00' + ((g % 730)::integer * interval '1 day')
        + interval '2 hours'
FROM generate_series(1, 10000100) AS g;

\echo 'quickstart: seeding raw.stg_events (1,200,100 rows)...'

INSERT INTO raw.stg_events (
    event_id, user_id, event_name, occurred_at, properties
)
SELECT
    g,
    (g % 20000) + 1,
    CASE g % 4
        WHEN 0 THEN 'page_view'
        WHEN 1 THEN 'add_to_cart'
        WHEN 2 THEN 'checkout_started'
        ELSE 'purchase'
    END,
    TIMESTAMPTZ '2024-06-01 00:00:00+00' + ((g % 365)::integer * interval '1 day'),
    '{"source":"web"}'
FROM generate_series(1, 1200100) AS g;

-- ANALYZE gives the planner statistics.  A plain VACUUM afterwards scans the
-- tables and reports the exact live-tuple count, so pg_stat_user_tables
-- exposes 10,000,100 / 1,200,100 rather than ANALYZE's sample-based estimate;
-- that keeps the demo's threshold checks deterministic.
ANALYZE analytics.fact_orders;
ANALYZE raw.stg_events;
VACUUM analytics.fact_orders;
VACUUM raw.stg_events;

\echo 'quickstart: warehouse fixture ready.'
