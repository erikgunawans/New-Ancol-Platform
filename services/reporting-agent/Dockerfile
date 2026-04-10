FROM python:3.12-slim AS base

WORKDIR /app

# WeasyPrint system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    libcairo2 \
    fonts-noto \
    && rm -rf /var/lib/apt/lists/*

COPY packages/ancol-common /tmp/ancol-common
RUN pip install --no-cache-dir /tmp/ancol-common && rm -rf /tmp/ancol-common

COPY services/reporting-agent/pyproject.toml .
RUN pip install --no-cache-dir .

COPY services/reporting-agent/src/ ./src/

RUN useradd -r -s /bin/false appuser
USER appuser

EXPOSE 8080

CMD ["uvicorn", "reporting_agent.main:app", "--host", "0.0.0.0", "--port", "8080"]
