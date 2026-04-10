# Ancol MoM Compliance System

Agentic AI system for auditing Board of Directors Minutes of Meetings (MoM) at PT Pembangunan Jaya Ancol Tbk.

Built on Google Cloud Platform with Gemini Enterprise.

## Architecture

Multi-Agent + Human-in-the-Loop (HITL) system with 4 specialized agents:

1. **Extraction Agent** (Gemini 2.5 Flash) — Parse documents into structured MoM JSON
2. **Legal Research Agent** (Gemini 2.5 Pro + RAG) — Time-aware regulatory retrieval
3. **Comparison & Reasoning Agent** (Gemini 2.5 Pro) — Cross-reference MoM vs regulations
4. **Reporting Agent** (Gemini 2.5 Flash) — Compliance scorecard and board-ready reports

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Agents + API | Python 3.12, FastAPI, Pydantic v2 |
| Frontend | Next.js 15, React 19, Tailwind CSS |
| Database | PostgreSQL 15 (Cloud SQL) |
| AI Models | Gemini 2.5 Flash + Pro |
| RAG | Vertex AI Search |
| Orchestration | Cloud Workflows + Cloud Pub/Sub |
| Document Processing | Google Document AI |
| Infrastructure | Terraform, Cloud Run, asia-southeast2 |

## Project Structure

```
infra/           Terraform (13 modules)
packages/        Shared Python packages
services/        Cloud Run microservices (6 services)
web/             Next.js frontend
db/              Alembic migrations + seed data
corpus/          Regulatory corpus source files
```

## Getting Started

See `docs/deployment-guide.md` for setup instructions.
