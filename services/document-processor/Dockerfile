FROM python:3.12-slim AS base

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install ancol-common first (shared package)
COPY packages/ancol-common /tmp/ancol-common
RUN pip install --no-cache-dir /tmp/ancol-common && rm -rf /tmp/ancol-common

# Install service dependencies
COPY services/document-processor/pyproject.toml .
RUN pip install --no-cache-dir .

# Copy service code
COPY services/document-processor/src/ ./src/

# Non-root user
RUN useradd -r -s /bin/false appuser
USER appuser

EXPOSE 8080

CMD ["uvicorn", "document_processor.main:app", "--host", "0.0.0.0", "--port", "8080"]
