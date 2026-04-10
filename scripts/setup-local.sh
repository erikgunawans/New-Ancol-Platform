#!/usr/bin/env bash
# Local development environment setup
set -euo pipefail

echo "=== Ancol MoM Compliance System — Local Setup ==="

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}' | cut -d. -f1,2)
if [[ "$PYTHON_VERSION" != "3.12" ]]; then
    echo "WARNING: Python 3.12 required, found $PYTHON_VERSION"
fi

# Install ancol-common in editable mode
echo "Installing ancol-common..."
pip install -e "packages/ancol-common[test]"

# Install service packages
for svc in services/*/; do
    if [ -f "$svc/pyproject.toml" ]; then
        echo "Installing $(basename "$svc")..."
        pip install -e "$svc[test]" 2>/dev/null || pip install -e "$svc" 2>/dev/null || true
    fi
done

# Set up environment variables for local dev
if [ ! -f .env ]; then
    cat > .env << 'ENVEOF'
# Local development environment
ENVIRONMENT=dev
DEBUG=true
GCP_PROJECT=ancol-mom-compliance-dev
GCP_REGION=asia-southeast2
DB_HOST=localhost
DB_PORT=5432
DB_NAME=ancol_compliance
DB_USER=ancol
DB_PASSWORD=localdev
BUCKET_RAW=ancol-mom-raw-dev
BUCKET_PROCESSED=ancol-mom-processed-dev
BUCKET_REPORTS=ancol-mom-reports-dev
GEMINI_FLASH_MODEL=gemini-2.5-flash
GEMINI_PRO_MODEL=gemini-2.5-pro
ENVEOF
    echo "Created .env file (edit with your values)"
fi

echo ""
echo "=== Setup complete ==="
echo "Next steps:"
echo "  1. Start PostgreSQL locally (docker or native)"
echo "  2. Run migrations: alembic upgrade head"
echo "  3. Seed data: psql -f db/seed/roles.sql"
echo "  4. Start a service: cd services/api-gateway && uvicorn src.api_gateway.main:app --reload"
