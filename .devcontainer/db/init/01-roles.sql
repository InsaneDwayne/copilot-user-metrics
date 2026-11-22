-- Runs once, when the pgdata volume is first created.
-- Dev-only passwords. Table grants and row-level security policies belong in
-- migrations so production gets them too; this file only creates the roles.

-- Sync worker: writes usage tables and runs procrastinate jobs.
CREATE ROLE copilot_worker LOGIN PASSWORD 'copilot_worker';

-- Dashboard API: read-only, must not bypass row-level security.
CREATE ROLE copilot_api LOGIN PASSWORD 'copilot_api' NOBYPASSRLS;

GRANT CONNECT ON DATABASE copilot_metrics TO copilot_worker, copilot_api;
GRANT USAGE ON SCHEMA public TO copilot_worker, copilot_api;

CREATE DATABASE copilot_metrics_test OWNER copilot;
