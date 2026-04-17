"""BJR (Business Judgment Rule) scoring and evaluation engine.

This subpackage computes a decision's BJR readiness score by evaluating the
16-item checklist per UU PT Pasal 97(5). It is consumed by the api-gateway
decisions router; a future `services/bjr-agent/` Cloud Run service can wrap
these functions to offload scoring to a dedicated worker.

Modules:
  scorer      — pure scoring formula (no DB, no side effects)
  evaluators  — the 16 checklist item evaluators (DB-facing, async)
  compute     — orchestrator: runs all evaluators and upserts checklist rows
  retroactive — proposes StrategicDecisions from completed MoMs
"""
