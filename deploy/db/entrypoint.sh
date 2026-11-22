#!/usr/bin/env bash
# Entrypoint of the `db` service: the official postgres entrypoint, plus db/setup.sql on
# every start, so the login roles and their passwords always match .env.
#
# - First start (empty data directory): the official entrypoint initialises the cluster and
#   runs /docker-entrypoint-initdb.d/setup.sql, like any init script.
# - Every later start: this script runs the same file first, on the official entrypoint's
#   temporary server (Unix socket only, no TCP), then hands over to the official entrypoint.
#
# Either way the server only listens on TCP once setup.sql has succeeded, which is what the
# healthcheck waits for, so `migrate` never sees a stale role. A failing setup.sql stops the
# container. The entrypoint is meant to be sourced for its functions
# (https://github.com/docker-library/postgres/pull/496); `exec` keeps postgres as PID 1.
set -Eeo pipefail

source /usr/local/bin/docker-entrypoint.sh

if [ "$1" = 'postgres' ] && ! _pg_want_help "$@"; then
	docker_setup_env
	docker_create_db_directories
	if [ "$(id -u)" = '0' ]; then
		# Like the official entrypoint: fix ownership as root, then go on as postgres.
		exec gosu postgres bash "${BASH_SOURCE[0]}" "$@"
	fi

	if [ -n "$DATABASE_ALREADY_EXISTS" ]; then
		export PGPASSWORD="${PGPASSWORD:-$POSTGRES_PASSWORD}"
		docker_temp_server_start "$@"
		printf '%s: running /docker-entrypoint-initdb.d/setup.sql\n' "$0"
		docker_process_sql -f /docker-entrypoint-initdb.d/setup.sql
		docker_temp_server_stop
		unset PGPASSWORD
	fi
fi

exec docker-entrypoint.sh "$@"
