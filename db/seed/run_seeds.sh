#!/usr/bin/env bash
# Apply seed data in order. Requires PGHOST, PGUSER, PGDATABASE env vars or defaults.
set -euo pipefail

DB_HOST="${PGHOST:-localhost}"
DB_PORT="${PGPORT:-5432}"
DB_NAME="${PGDATABASE:-ancol_compliance}"
DB_USER="${PGUSER:-ancol}"

SEED_DIR="$(cd "$(dirname "$0")" && pwd)"

for sql_file in "$SEED_DIR"/0*.sql; do
    echo "Applying $(basename "$sql_file")..."
    psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f "$sql_file"
done

echo "All seeds applied."
