#!/usr/bin/env bash
# Runs once, the first time the Postgres container starts with an empty data volume.
# Creates one database user and one schema per service, so each service can only see
# its own tables (ADR 0003/0017: one schema and one user per service).
#
# To re-run it after changing it, delete the volume:  docker compose down -v
#
# Note: the Postgres entrypoint may source this file instead of executing it, so it
# must not call `exit` or change shell options.

create_service_schema() {
  local service="$1"
  local password="$2"
  echo "getdrove init: creating user and schema '${service}'"
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
    -v svc="$service" -v pw="$password" <<'SQL'
CREATE ROLE :"svc" LOGIN PASSWORD :'pw';
CREATE SCHEMA :"svc" AUTHORIZATION :"svc";
REVOKE ALL ON SCHEMA :"svc" FROM PUBLIC;
-- Look in the service's own schema first, then public (where the PostGIS types live).
ALTER ROLE :"svc" SET search_path = :"svc", public;
GRANT CONNECT ON DATABASE :"DBNAME" TO :"svc";
SQL
}

# PostGIS lives in the public schema. Service users can use its types and functions,
# but nobody except the admin user can create objects in public.
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<'SQL'
CREATE EXTENSION IF NOT EXISTS postgis;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
REVOKE CONNECT ON DATABASE :"DBNAME" FROM PUBLIC;
SQL

create_service_schema accounts "${ACCOUNTS_DB_PASSWORD:-accounts}"
create_service_schema trips "${TRIPS_DB_PASSWORD:-trips}"
create_service_schema routing "${ROUTING_DB_PASSWORD:-routing}"
create_service_schema payments "${PAYMENTS_DB_PASSWORD:-payments}"
create_service_schema notifications "${NOTIFICATIONS_DB_PASSWORD:-notifications}"
