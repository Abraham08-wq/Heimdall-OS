#!/bin/bash
set -e
# Install pgvector (requires apt-get available in the image)
apt-get update && apt-get install -y postgresql-15-pgvector

# Enable the extension
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE EXTENSION IF NOT EXISTS vector;
EOSQL