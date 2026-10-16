#!/usr/bin/env bash
set -euo pipefail

N8N_DATABASE="${N8N_DB_NAME:-n8n}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
SELECT 'CREATE DATABASE "${N8N_DATABASE}"'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '${N8N_DATABASE}')\gexec
EOSQL
