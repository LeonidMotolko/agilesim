#!/bin/sh
# Runs once, when the PostgreSQL data directory is first initialised (official image hook).
# Creates the login role the application uses at run time. It is not a superuser and owns
# nothing; its privileges come from the app_write group role that the migrations create.
set -eu

: "${POSTGRES_APP_PASSWORD:?POSTGRES_APP_PASSWORD must be set (see .env.example)}"

psql -v ON_ERROR_STOP=1 -v app_password="$POSTGRES_APP_PASSWORD" \
     --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<'SQL'
CREATE ROLE agilesim_app LOGIN PASSWORD :'app_password'
    NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
SQL
