# Runbook: Vertex AI Agent Builder — Region Verification

**Why:** BJR design places Gemini Enterprise as primary UI. All chat payloads
include sensitive BJR context (RKAB values, DD findings, COI names). Indonesian
data sovereignty law + internal policy pin all personal + financial data to
`asia-southeast2` (Jakarta). We must confirm Agent Builder respects this.

**Owner:** Erik Gunawan + Platform team
**When:** Week 1 of Phase 6.4a
**Blocker:** Phase 6.4b does NOT start until this is complete.

## What to verify

1. **Agent resource location.** The Vertex AI Agent Builder agent must be
   created in `asia-southeast2` (not `global`, not `us-central1`).
2. **Model routing.** The Gemini model the agent uses must serve from
   `asia-southeast2`. If a model is only available in `asia-southeast1`
   (Singapore), escalate for approval before use.
3. **Conversation storage.** Whether Agent Builder retains chat history
   in-region. Confirm in writing with GCP support.
4. **Tool-call payload routing.** Our webhook is a Cloud Run service we
   deploy to `asia-southeast2` — this part is under our control.
5. **Logging region.** Cloud Logging sinks for Agent Builder events must
   also be regional.

## Steps

1. **Open a GCP Support case** (Premium/Enhanced tier).
   - Subject: "Data residency confirmation: Vertex AI Agent Builder + Gemini in asia-southeast2"
   - Attach this runbook.
   - Ask specifically for written confirmation on points 1-5 above.
2. **In parallel, check the public documentation:**
   - https://cloud.google.com/vertex-ai/docs/general/locations
   - https://cloud.google.com/agent-builder/docs/locations
   - Record findings in `docs/region-verification-findings.md` (new).
3. **If all five points verified in-region:** mark this blocker resolved.
   Move to Phase 6.4b.
4. **If any point lives outside asia-southeast2:**
   a. Escalate to TAM (Technical Account Manager).
   b. Option: use `asia-southeast1` (Singapore) if legal approves — needs
      written sign-off from Legal & Compliance + Dewan Pengawas.
   c. Option: self-host a proxy agent (NOT recommended — high maintenance).
   d. Option: revert to web-primary plan (original Phase 6.4 scope).

## Exit criteria

- [ ] GCP support ticket reply received with in-region confirmation for
      points 1, 2, 3, 5. Point 4 is self-verified (our Cloud Run config).
- [ ] Region findings documented in `docs/region-verification-findings.md`.
- [ ] Screenshot of Agent Builder console showing region attached to
      this runbook.
- [ ] If any item uses `asia-southeast1` fallback: written Legal sign-off
      filed in `docs/legal-approvals/`.

## Rollback / escalation tree

| Finding | Action |
|---|---|
| All 5 in `asia-southeast2` | ✅ proceed to 6.4b |
| Model only in `asia-southeast1` | Legal approval → proceed |
| Conversation storage outside region | Escalate; likely revert to web-primary |
| No in-region option at all | Revert to original web-primary Phase 6.4 plan |
