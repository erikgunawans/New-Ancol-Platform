# Runbook: Phase 6.4a Deployment — BJR Chat-First Read Surface

**Why:** Phase 6.4a code is merged to `main` (v0.4.2.0). This runbook takes
that code from "merged" to "running and usable by PJAA stakeholders in
Gemini Enterprise chat."

**Owner:** Erik Gunawan
**Environment:** Jakarta (`asia-southeast2`) per data-sovereignty policy
**Blocker:** Task 13 region verification must be resolved before any
production chat mutations. Read-only deployment (this runbook) can proceed
to staging/demo environments before the region cert comes back, but
production go-live waits on the GCP support ticket.

**Total time:** ~60 min if everything goes cleanly. ~2 hours if Agent
Builder is first-time setup.

---

## Pre-flight checklist

- [ ] `gcloud auth application-default login` done, active project is the
      Ancol dev/staging/prod project as appropriate
- [ ] `terraform` 1.5+ installed, `gh` CLI authenticated
- [ ] Neo4j AuraDS instance provisioned in `asia-southeast2` (dev/staging/prod
      all use a single instance per env; see infra module)
- [ ] Cloud SQL PostgreSQL instance already running (it's been up since Phase 1)
- [ ] You have access to the Vertex AI Agent Builder console for the target project
- [ ] Local branch `main` synced (`git pull origin main`) and at commit
      `8258b3b` or later

---

## Step 1. Build + push container images (5-10 min)

The two services changed in Phase 6.4a:

- `services/gemini-agent/` — new BJR tool handlers + dispatcher + RBAC
- `services/api-gateway/` — new `GET /api/documents/{id}/bjr-indicators`
  endpoint + new `bjr:read` permission

If your CI pushes images automatically on merge to main, skip this step and
just verify the latest image tag exists in Artifact Registry. Otherwise:

```bash
# From repo root, for each changed service:
for svc in gemini-agent api-gateway; do
  gcloud builds submit \
    --region=asia-southeast2 \
    --config=services/$svc/cloudbuild.yaml \
    --substitutions=_SERVICE_NAME=$svc,_TAG=v0.4.2.0 \
    services/$svc/
done
```

Verify:
```bash
gcloud artifacts docker images list \
  asia-southeast2-docker.pkg.dev/<PROJECT>/ancol/gemini-agent \
  --filter="tags:v0.4.2.0" --limit=1
```

---

## Step 2. Update environment variables (2 min)

Both services need the graph-backend env vars. Use Terraform (preferred) or
`gcloud run services update` (quick).

**Required env for `gemini-agent`:**

| Variable | Value |
|---|---|
| `API_GATEWAY_URL` | `https://api-gateway-<hash>-et.a.run.app` (the Cloud Run URL of the api-gateway service in the same env) |
| `ENVIRONMENT` | `dev` / `staging` / `prod` |
| `GRAPH_BACKEND` | `neo4j` (see note below) |
| `NEO4J_URI` | `bolt+s://<aura-id>.databases.neo4j.io:7687` |
| `NEO4J_USER` | `neo4j` |
| `NEO4J_PASSWORD` | (from Secret Manager, not plaintext) |

**Required env for `api-gateway`:**

Same `GRAPH_BACKEND` / `NEO4J_*` vars — the `/bjr-indicators` endpoint
uses them directly. Plus the existing PG + IAP + MFA + WhatsApp env.

**⚠ `GRAPH_BACKEND` default is `spanner`.** If you don't set this explicitly,
the backfill script and the `/bjr-indicators` endpoint will both try to use
the Spanner client (stubs in Phase 6.4a — returns empty). **Explicitly set
`GRAPH_BACKEND=neo4j` on both services** or the chat tools will return empty
indicators even with data in the graph.

Quick `gcloud` path (dev):
```bash
gcloud run services update gemini-agent \
  --region=asia-southeast2 \
  --update-env-vars=GRAPH_BACKEND=neo4j,NEO4J_URI=bolt+s://xxx.databases.neo4j.io:7687,NEO4J_USER=neo4j \
  --update-secrets=NEO4J_PASSWORD=neo4j-password:latest

gcloud run services update api-gateway \
  --region=asia-southeast2 \
  --update-env-vars=GRAPH_BACKEND=neo4j,NEO4J_URI=bolt+s://xxx.databases.neo4j.io:7687,NEO4J_USER=neo4j \
  --update-secrets=NEO4J_PASSWORD=neo4j-password:latest
```

---

## Step 3. Deploy the new image versions (2 min)

```bash
gcloud run deploy gemini-agent \
  --region=asia-southeast2 \
  --image=asia-southeast2-docker.pkg.dev/<PROJECT>/ancol/gemini-agent:v0.4.2.0

gcloud run deploy api-gateway \
  --region=asia-southeast2 \
  --image=asia-southeast2-docker.pkg.dev/<PROJECT>/ancol/api-gateway:v0.4.2.0
```

Smoke both services after deploy:
```bash
GEMINI_URL=$(gcloud run services describe gemini-agent --region=asia-southeast2 --format='value(status.url)')
curl -s "$GEMINI_URL/health" | jq
# Expected: {"status":"ok","service":"gemini-agent","version":"0.1.0"}

API_URL=$(gcloud run services describe api-gateway --region=asia-southeast2 --format='value(status.url)')
curl -s "$API_URL/health" | jq
# Expected: {"status":"ok",...}
```

---

## Step 4. Run the graph backfill (30 sec – 5 min)

Populates Neo4j from existing PG state. Idempotent; safe to re-run.

```bash
# From repo root, with PROJECT DB creds in env (same as what Cloud Run uses):
PYTHONPATH=packages/ancol-common/src python3 scripts/bjr_graph_backfill.py --dry-run
# Expected: logs counts of strategic_decisions, decision_evidence, bjr_checklists rows

# If counts look right, run for real:
PYTHONPATH=packages/ancol-common/src \
  GRAPH_BACKEND=neo4j \
  NEO4J_URI=bolt+s://xxx.databases.neo4j.io:7687 \
  NEO4J_USER=neo4j \
  NEO4J_PASSWORD="$(gcloud secrets versions access latest --secret=neo4j-password)" \
  python3 scripts/bjr_graph_backfill.py
# Expected: "Backfill complete: {'decisions': N, 'edges': M}"
```

**If you have zero `strategic_decisions` rows in PG** (a fresh dev env),
run the seed script first (Step 4b) so the chat tools have something to
return.

### Step 4b (optional). Seed demo data (30 sec)

For demo / staging environments where no real BJR Decisions exist yet:

```bash
PYTHONPATH=packages/ancol-common/src python3 scripts/seed_bjr_demo.py --dry-run
PYTHONPATH=packages/ancol-common/src python3 scripts/seed_bjr_demo.py
# Creates 3 StrategicDecisions + 7 DecisionEvidence rows + 16 BJRChecklistItem
# rows covering the 3 distinct lifecycle states (ideation / dd_in_progress / bjr_locked).

# Then re-run the backfill to populate the graph:
PYTHONPATH=packages/ancol-common/src python3 scripts/bjr_graph_backfill.py
```

After this, every chat tool returns real data. `show_document_indicators`
on the seeded MoM documents returns non-empty cards.

---

## Step 5. Register the 8 tools in Vertex AI Agent Builder (20 min first time)

The function declarations are committed at
`docs/agent-builder/bjr-tools.json`. **Open that file, copy the JSON payload**.

### 5a. Find or create the Agent

1. Open https://console.cloud.google.com/gen-app-builder/engines
2. Make sure region is `asia-southeast2` (not `global`). If the Ancol
   agent doesn't exist here, Task 13's region runbook has NOT been executed
   — **stop**, escalate to the GCP support ticket first.
3. Open the Ancol agent. If none exists, create one:
   - Name: "Ancol BJR Agent"
   - Model: Gemini 2.5 Pro (must be available in `asia-southeast2`)
   - Region: `asia-southeast2`

### 5b. Add the 8 function declarations

In the agent's "Tools" section:

1. **If using the Function calling tool config UI:** paste the 8 function
   declarations from `docs/agent-builder/bjr-tools.json` (inside the
   `function_declarations` array).
2. **If using a Tool resource (OpenAPI-like):** the same JSON slots into the
   Agent's Tool resource config. Your exact path depends on console version.
3. **Set the webhook URL:** for each tool (or for all tools globally),
   webhook target = `<gemini-agent Cloud Run URL>/webhook`.

### 5c. Configure the system prompt

Paste or update the agent's system instructions to include this paragraph
(add to existing prompts; don't replace):

```
You have 8 BJR (Business Judgment Rule) tools available for decision
defensibility queries: get_decision, list_decisions, list_my_decisions,
get_readiness, get_checklist, show_document_indicators, show_decision_evidence,
get_passport_url. CRITICAL: when the user mentions any document by ID or
filename, proactively call show_document_indicators on that document —
do not ask for permission, do not explain. The tool is silent when there's
no BJR context. All output is Indonesian (Bahasa Indonesia). Never call
BJR tools with made-up UUIDs; always resolve the UUID from user context
first (list_decisions or list_my_decisions).
```

### 5d. Test from the console

Use the Agent Builder chat playground:

| Prompt | Expected tool call |
|---|---|
| "Tampilkan decision yang sedang saya kerjakan" | `list_my_decisions` |
| "Apa status readiness untuk decision <uuid>?" | `get_readiness` |
| "Checklist BJR untuk <uuid>?" | `get_checklist` |
| "Ada decision yang locked?" | `list_decisions({status: "bjr_locked"})` |
| "Tunjukkan Passport PDF untuk <locked-uuid>" | `get_passport_url` |

All should return formatted Indonesian responses. If the agent returns
"no data", check `GRAPH_BACKEND=neo4j` on both services and that the
backfill actually ran.

---

## Step 6. End-to-end smoke test (5 min)

From the Agent Builder chat playground:

1. **Read path.** Ask "Tampilkan semua decision." Agent should call
   `list_decisions`, return a list with emoji indicators (🔒 locked / 🟢
   unlockable / 🟡 in-progress / ⚪ unscored).
2. **Readiness path.** Pick a decision ID from step 1. Ask "Bagaimana
   readiness-nya?". Agent calls `get_readiness`, returns the dual-regime
   card with corporate + regional scores.
3. **Checklist path.** Ask "Apa yang masih kurang?". Agent calls
   `get_checklist`, returns 16-item grouped-by-phase view.
4. **Proactive path.** Mention a known document UUID in free text:
   "Saya lihat dokumen <uuid>, apa konteksnya?". Agent should proactively
   call `show_document_indicators` and display a card with any decisions
   the doc supports.
5. **Passport path** (only if you have a locked decision): "Bisa download
   Passport untuk <locked-uuid>?". Agent calls `get_passport_url`, returns
   a signed GCS link with expiry.

---

## Rollback

If any step breaks a production-critical path:

```bash
# Roll back to previous revision (one step for each service):
gcloud run services update-traffic gemini-agent \
  --region=asia-southeast2 \
  --to-revisions=<PREVIOUS_REVISION>=100

gcloud run services update-traffic api-gateway \
  --region=asia-southeast2 \
  --to-revisions=<PREVIOUS_REVISION>=100
```

Neo4j state is additive (MERGE semantics) — no rollback needed on the graph.
PG state is untouched by any of these steps.

**If the seed script caused issues in a non-demo environment:**
```sql
-- ONLY in demo envs — removes the 3 seeded decisions and their children via FK cascade
DELETE FROM strategic_decisions WHERE title IN (
  'Akuisisi Hotel Wahana',
  'Divestasi Unit Marine Park',
  'Kerjasama Strategis PT Jaya Konstruksi'
);
```

---

## Exit criteria

- [ ] Both services respond 200 on `/health`
- [ ] Backfill script logged non-zero decision count OR seed script was run
      and backfill completed
- [ ] All 8 tools registered in Agent Builder, webhook target set
- [ ] Agent chat playground returns formatted Indonesian responses for the
      5 smoke test prompts in Step 6
- [ ] No errors in Cloud Logging for the gemini-agent or api-gateway
      services during the smoke test window
- [ ] (Production only) Task 13 region verification runbook is closed
      before opening the agent to non-test users

---

## Related docs

- `docs/RUNBOOK-agent-builder-region-verification.md` — Task 13 blocker
  gate for production chat mutations
- `docs/agent-builder/bjr-tools.json` — the 8 function declarations
- `docs/superpowers/specs/2026-04-17-bjr-gemini-enterprise-primary-design.md` —
  the chat-first architectural rationale
- `CHANGELOG.md` — the `[0.4.2.0]` entry for what shipped
