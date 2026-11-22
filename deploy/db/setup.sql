-- The app's login roles, run as the Postgres superuser on every start of the `db` service
-- (see entrypoint.sh). Idempotent:
--
-- - creates the three login roles if missing, none of them a superuser, and sets their
--   passwords from .env (so changing a password in .env applies on the next `up`);
-- - lets the owner role create objects in the public schema;
-- - hands the app's objects that the superuser still owns (stacks before the owner role
--   existed ran migrations as the superuser) to the owner role.
--
-- Table grants and row-level security come from the migrations (the `migrate` service,
-- which connects as the owner role).

\getenv owner_password OWNER_DB_PASSWORD
\getenv api_password API_DB_PASSWORD
\getenv worker_password WORKER_DB_PASSWORD

SELECT format('CREATE ROLE %I', name)
FROM unnest(ARRAY['copilot_owner', 'copilot_worker', 'copilot_api']) AS name
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = name)
\gexec

-- Owner: runs migrations, owns the schema objects, grants to the other two.
ALTER ROLE copilot_owner LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS
  PASSWORD :'owner_password';
-- Sync worker: the only writer of usage tables; runs procrastinate jobs.
ALTER ROLE copilot_worker LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS
  PASSWORD :'worker_password';
-- Dashboard API: read-only, must not bypass row-level security.
ALTER ROLE copilot_api LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS
  PASSWORD :'api_password';

SELECT format('GRANT CONNECT ON DATABASE %I TO copilot_owner, copilot_worker, copilot_api',
              current_database())
\gexec
GRANT USAGE, CREATE ON SCHEMA public TO copilot_owner;
GRANT USAGE ON SCHEMA public TO copilot_worker, copilot_api;

-- Ownership moves with grants and policies intact. Indexes, triggers and column-owned
-- sequences follow their table.
DO $$
DECLARE r record;
BEGIN
    FOR r IN
        SELECT format('ALTER %s %s OWNER TO copilot_owner',
                      CASE c.relkind WHEN 'S' THEN 'SEQUENCE' WHEN 'v' THEN 'VIEW'
                                     WHEN 'm' THEN 'MATERIALIZED VIEW' ELSE 'TABLE' END,
                      c.oid::regclass) AS stmt
        FROM pg_class c
        WHERE c.relnamespace = 'public'::regnamespace
          AND c.relowner = current_user::regrole
          AND c.relkind IN ('r', 'p', 'v', 'm', 'S')
          AND NOT EXISTS (SELECT FROM pg_depend d
                          WHERE d.classid = 'pg_class'::regclass AND d.objid = c.oid
                            AND d.deptype IN ('a', 'i', 'e'))
        UNION ALL
        SELECT format('ALTER ROUTINE %s OWNER TO copilot_owner', p.oid::regprocedure)
        FROM pg_proc p
        WHERE p.pronamespace = 'public'::regnamespace
          AND p.proowner = current_user::regrole
          AND NOT EXISTS (SELECT FROM pg_depend d
                          WHERE d.classid = 'pg_proc'::regclass AND d.objid = p.oid AND d.deptype = 'e')
        UNION ALL
        SELECT format('ALTER TYPE %s OWNER TO copilot_owner', t.oid::regtype)
        FROM pg_type t
        LEFT JOIN pg_class c ON c.oid = t.typrelid
        WHERE t.typnamespace = 'public'::regnamespace
          AND t.typowner = current_user::regrole
          AND (t.typtype IN ('e', 'd', 'r') OR (t.typtype = 'c' AND c.relkind = 'c'))
          AND NOT EXISTS (SELECT FROM pg_depend d
                          WHERE d.classid = 'pg_type'::regclass AND d.objid = t.oid AND d.deptype = 'e')
    LOOP
        EXECUTE r.stmt;
    END LOOP;
END $$;
