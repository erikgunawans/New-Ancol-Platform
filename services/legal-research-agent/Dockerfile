FROM python:3.12-slim AS base

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY packages/ancol-common /tmp/ancol-common
RUN pip install --no-cache-dir /tmp/ancol-common && rm -rf /tmp/ancol-common

COPY services/legal-research-agent/pyproject.toml .
RUN pip install --no-cache-dir .

COPY services/legal-research-agent/src/ ./src/

RUN useradd -r -s /bin/false appuser
USER appuser

EXPOSE 8080

CMD ["uvicorn", "legal_research_agent.main:app", "--host", "0.0.0.0", "--port", "8080"]
