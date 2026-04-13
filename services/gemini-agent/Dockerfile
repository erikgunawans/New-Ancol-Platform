FROM python:3.12-slim

WORKDIR /app

COPY packages/ancol-common /tmp/ancol-common
RUN pip install --no-cache-dir /tmp/ancol-common && rm -rf /tmp/ancol-common

COPY services/gemini-agent/pyproject.toml .
RUN pip install --no-cache-dir .

COPY services/gemini-agent/src/ ./src/

ENV PORT=8080
EXPOSE 8080

CMD ["uvicorn", "gemini_agent.main:app", "--host", "0.0.0.0", "--port", "8080"]
