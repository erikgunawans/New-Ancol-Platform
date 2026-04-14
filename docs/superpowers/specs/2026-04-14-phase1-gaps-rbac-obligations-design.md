# Phase 1 Gaps — RBAC Enforcement + Obligation Auto-Transition

**Date:** 2026-04-14
**Status:** Draft
**Scope:** Two deferred Phase 1 items that close operational gaps before CLM Phase 2

---

## 1. Problem Statement

Two Phase 1 gaps leave the system incomplete:

1. **RBAC not enforced.** The auth middleware resolves IAP identity to a database user and attaches `request.state.user_role`, but no endpoint checks it. Every authenticated user can access every endpoint. The `require_permission()` dependency and `ROLE_PERMISSIONS` matrix (24 permissions, 8 roles) exist in `rbac.py` but are unused.

2. **No obligation auto-transition.** The `ObligationRecord` model defines five statuses (`upcoming`, `due_soon`, `overdue`, `fulfilled`, `waived`) but nothing moves obligations through them automatically. The Cloud Scheduler job at 07:00 WIB calls a read-only `GET /upcoming` endpoint. Obligations past their due date stay `upcoming` forever. Reminders never fire.

---

## 2. RBAC Enforcement

### 2.1 Approach

Add `require_permission("permission_key")` as a FastAPI `Depends()` parameter to every endpoint across all 13 routers. The dependency reads `request.state.user_role` (set by `AuthMiddleware`) and checks it against `ROLE_PERMISSIONS` in `rbac.py`. Unauthorized requests get HTTP 403.

No new permission keys needed. The existing 24 in `ROLE_PERMISSIONS` cover all endpoints.

### 2.2 Endpoint-to-Permission Mapping

#### documents.py (3 endpoints)

| Method | Path | Permission |
|--------|------|------------|
| POST | `/documents/upload` | `documents:upload` |
| GET | `/documents` | `documents:list` |
| GET | `/documents/{document_id}` | `documents:list` |

#### hitl.py (3 endpoints)

| Method | Path | Permission |
|--------|------|------------|
| GET | `/hitl/queue` | `hitl:gate_1` |
| GET | `/hitl/review/{document_id}` | `hitl:gate_1` |
| POST | `/hitl/decide/{document_id}` | `hitl:gate_1` |

Note: Ideally HITL decide would check the document's current gate and match against `hitl:gate_2`, `hitl:gate_3`, etc. For Phase 1 gap closure, we use `hitl:gate_1` permissions (Corp Secretary + Admin) for queue visibility, and the decide endpoint allows any role that can approve any gate (`hitl:gate_1` through `hitl:gate_4_*`). Gate-specific enforcement is a Phase 2 refinement.

#### reports.py (3 endpoints)

| Method | Path | Permission |
|--------|------|------------|
| GET | `/reports` | `reports:view_approved` |
| GET | `/reports/{report_id}` | `reports:view_approved` |
| GET | `/reports/{report_id}/download/{format}` | `reports:view_approved` |

#### dashboard.py (2 endpoints)

| Method | Path | Permission |
|--------|------|------------|
| GET | `/dashboard/stats` | `dashboard:view` |
| GET | `/dashboard/stats/trends` | `dashboard:view` |

#### analytics.py (4 endpoints)

| Method | Path | Permission |
|--------|------|------------|
| GET | `/analytics/trends` | `dashboard:view` |
| GET | `/analytics/violations` | `dashboard:view` |
| GET | `/analytics/coverage` | `dashboard:view` |
| GET | `/analytics/hitl-performance` | `dashboard:view` |

#### audit.py (1 endpoint)

| Method | Path | Permission |
|--------|------|------------|
| GET | `/audit` | `audit_trail:view` |

#### batch.py (5 endpoints)

| Method | Path | Permission |
|--------|------|------------|
| POST | `/batch` | `documents:upload` |
| GET | `/batch` | `documents:upload` |
| GET | `/batch/{job_id}` | `documents:upload` |
| POST | `/batch/{job_id}/pause` | `documents:upload` |
| POST | `/batch/{job_id}/resume` | `documents:upload` |

#### retroactive.py (2 endpoints)

| Method | Path | Permission |
|--------|------|------------|
| POST | `/retroactive/scan` | `corpus:search` |
| POST | `/retroactive/scan-and-reprocess` | `corpus:search` |

#### templates.py (3 endpoints)

| Method | Path | Permission |
|--------|------|------------|
| GET | `/templates` | `documents:list` |
| GET | `/templates/resolve` | `documents:list` |
| GET | `/templates/timeline/{mom_type}` | `documents:list` |

#### users.py (2 endpoints)

| Method | Path | Permission |
|--------|------|------------|
| GET | `/users` | `audit_trail:view` |
| GET | `/users/{user_id}` | `audit_trail:view` |

#### contracts.py (8 endpoints)

| Method | Path | Permission |
|--------|------|------------|
| POST | `/contracts` | `contracts:create` |
| GET | `/contracts` | `contracts:list` |
| GET | `/contracts/{contract_id}` | `contracts:list` |
| PATCH | `/contracts/{contract_id}` | `contracts:review` |
| POST | `/contracts/{contract_id}/status` | `contracts:review` |
| GET | `/contracts/{contract_id}/clauses` | `contracts:list` |
| GET | `/contracts/{contract_id}/risk` | `contracts:list` |
| GET | `/contracts/{contract_id}/download` | `contracts:list` |

#### obligations.py (5 endpoints + 1 new)

| Method | Path | Permission |
|--------|------|------------|
| GET | `/obligations` | `obligations:list` |
| GET | `/obligations/upcoming` | `obligations:list` |
| GET | `/obligations/{obligation_id}` | `obligations:list` |
| POST | `/obligations/{obligation_id}/fulfill` | `obligations:fulfill` |
| POST | `/obligations/{obligation_id}/waive` | `obligations:fulfill` |
| POST | `/obligations/check-deadlines` | *(scheduler-only, no RBAC — see §3.5)* |

#### drafting.py (5 endpoints)

| Method | Path | Permission |
|--------|------|------------|
| GET | `/drafting/templates` | `drafting:generate` |
| GET | `/drafting/templates/{contract_type}` | `drafting:generate` |
| POST | `/drafting/generate` | `drafting:generate` |
| GET | `/drafting/clause-library` | `drafting:generate` |
| GET | `/drafting/clause-library/{clause_id}` | `drafting:generate` |

### 2.3 Implementation Pattern

Each endpoint adds the dependency as a parameter:

```python
from ancol_common.auth.rbac import require_permission

@router.get("", response_model=ContractListResponse)
async def list_contracts_endpoint(
    _auth=require_permission("contracts:list"),
    status: str | None = Query(None),
    ...
):
```

The `_auth` parameter is unused in the function body. The dependency runs before the endpoint and raises 403 if unauthorized.

### 2.4 HITL Decide — Gate-Aware Enforcement (Simplified)

The HITL decide endpoint currently doesn't check which gate the document is in. For this gap closure, we create a combined permission set for decide:

```python
# In rbac.py — add a union permission for HITL decide
"hitl:decide": {
    UserRole.CORP_SECRETARY,
    UserRole.INTERNAL_AUDITOR,
    UserRole.LEGAL_COMPLIANCE,
    UserRole.ADMIN,
},
```

This allows any role that can approve at least one gate to access the decide endpoint. The endpoint already validates the decision is valid for the document's current state. Per-gate role enforcement (e.g., only Internal Auditor can approve Gate 2) is a Phase 2 refinement.

### 2.5 Testing

Add RBAC tests to the existing API Gateway test suite:

- **Per-router tests (~3 each):** Mock `request.state.user_role` to an authorized role (expect 200), an unauthorized role (expect 403), and missing role (expect 403).
- **Coverage:** At least one test per router. The permission matrix itself is already defined and doesn't need testing; we're testing the wiring.
- **Estimated:** ~15-20 new tests.

---

## 3. Obligation Auto-Transition

### 3.1 Approach

New `POST /api/obligations/check-deadlines` endpoint on the API Gateway. Cloud Scheduler calls it daily at 07:00 WIB (re-pointing the existing `obligation_check` job). Single endpoint, single transaction.

### 3.2 Transition Logic

Executed in this order (most urgent first):

1. **Overdue:** All obligations where `status IN ('upcoming', 'due_soon')` AND `due_date <= today` → set `status = 'overdue'`.
2. **Due soon:** All obligations where `status = 'upcoming'` AND `due_date <= today + 30 days` AND `due_date > today` → set `status = 'due_soon'`.

Both use bulk `sqlalchemy.update()` statements (not ORM attribute mutation) to handle potentially detached sessions, consistent with the pattern established in `retroactive.py`.

### 3.3 Reminder Dispatch

After status transitions, query obligations that need reminders:

| Window | Condition | Flag |
|--------|-----------|------|
| 30 days | `due_date <= today + 30d` AND `reminder_30d_sent = false` | `reminder_30d_sent` |
| 14 days | `due_date <= today + 14d` AND `reminder_14d_sent = false` | `reminder_14d_sent` |
| 7 days | `due_date <= today + 7d` AND `reminder_7d_sent = false` | `reminder_7d_sent` |

For each obligation needing a reminder:
1. Look up the responsible user's phone number (via `responsible_user_id` → `users` table).
2. Look up the contract title (via `contract_id` → `contracts` table).
3. Call `send_obligation_reminder()` from `notifications/whatsapp.py`.
4. Set the corresponding `reminder_*_sent = true`.

Reminders are best-effort. If WhatsApp delivery fails (returns `False`), log the failure but don't flip the flag. The next daily run will retry.

### 3.4 Recurrence Handling

After processing reminders, check for fulfilled obligations with `recurrence` set:

- If `status = 'fulfilled'` AND `recurrence IS NOT NULL` AND `next_due_date IS NULL`:
  - Compute `next_due_date` based on `recurrence` value:
    - `"monthly"` → `due_date + 1 month`
    - `"quarterly"` → `due_date + 3 months`
    - `"annual"` → `due_date + 1 year`
  - Create a new `ObligationRecord` with:
    - Same `contract_id`, `obligation_type`, `description`, `responsible_*` fields
    - `due_date = computed next_due_date`
    - `status = 'upcoming'`
    - All reminder flags reset to `false`
  - Set `next_due_date` on the original record (prevents duplicate creation on next run).

### 3.5 Auth and Scheduling

The `check-deadlines` endpoint is machine-to-machine (Cloud Scheduler → API Gateway via OIDC). Two options for protecting it:

**Chosen approach:** Add `/api/obligations/check-deadlines` to the scheduler-allowed paths. The endpoint validates the request comes from Cloud Scheduler by checking the OIDC token's service account matches the expected invoker SA. This is the same pattern used by the email-scan and regulation-check scheduler jobs.

Add the path to `PUBLIC_PATHS` in `middleware.py` so the auth middleware doesn't try to resolve a DB user (there is no DB user for the scheduler SA).

### 3.6 Terraform Update

Re-point the existing `obligation_check` scheduler job:

```hcl
http_target {
  uri         = "${var.api_gateway_url}/api/obligations/check-deadlines"
  http_method = "POST"
  ...
}
```

### 3.7 Repository Layer

New function in `repository.py`:

```python
async def check_obligation_deadlines(session: AsyncSession) -> dict:
    """Run obligation status transitions and return a summary."""
    # 1. Bulk UPDATE: upcoming/due_soon past due → overdue
    # 2. Bulk UPDATE: upcoming within 30 days → due_soon
    # 3. Query obligations needing reminders, dispatch, flip flags
    # 4. Handle recurrences for fulfilled obligations
    return {
        "transitioned_overdue": int,
        "transitioned_due_soon": int,
        "reminders_sent": int,
        "recurrences_created": int,
    }
```

### 3.8 Response Format

The endpoint returns the summary dict so Cloud Scheduler logs can capture what happened:

```json
{
  "status": "ok",
  "transitioned_overdue": 3,
  "transitioned_due_soon": 7,
  "reminders_sent": 5,
  "recurrences_created": 1,
  "checked_at": "2026-04-14T07:00:00+07:00"
}
```

### 3.9 Testing

~8 new tests in `services/api-gateway/tests/`:

1. Overdue transition: obligation past due date moves to `overdue`
2. Due-soon transition: obligation within 30 days moves to `due_soon`
3. No-op: obligation far in the future stays `upcoming`
4. Already fulfilled/waived: not affected by transitions
5. Reminder flag: 30d flag set after reminder window reached
6. Reminder idempotency: running twice doesn't double-send (flag already set)
7. Recurrence creation: fulfilled monthly obligation spawns next occurrence
8. Recurrence idempotency: `next_due_date` prevents duplicate creation

---

## 4. Files Modified

### RBAC Enforcement

| File | Change |
|------|--------|
| `services/api-gateway/src/api_gateway/routers/documents.py` | Add `require_permission` to 3 endpoints |
| `services/api-gateway/src/api_gateway/routers/hitl.py` | Add `require_permission` to 3 endpoints |
| `services/api-gateway/src/api_gateway/routers/reports.py` | Add `require_permission` to 3 endpoints |
| `services/api-gateway/src/api_gateway/routers/dashboard.py` | Add `require_permission` to 2 endpoints |
| `services/api-gateway/src/api_gateway/routers/analytics.py` | Add `require_permission` to 4 endpoints |
| `services/api-gateway/src/api_gateway/routers/audit.py` | Add `require_permission` to 1 endpoint |
| `services/api-gateway/src/api_gateway/routers/batch.py` | Add `require_permission` to 5 endpoints |
| `services/api-gateway/src/api_gateway/routers/retroactive.py` | Add `require_permission` to 2 endpoints |
| `services/api-gateway/src/api_gateway/routers/templates.py` | Add `require_permission` to 3 endpoints |
| `services/api-gateway/src/api_gateway/routers/users.py` | Add `require_permission` to 2 endpoints |
| `services/api-gateway/src/api_gateway/routers/contracts.py` | Add `require_permission` to 8 endpoints |
| `services/api-gateway/src/api_gateway/routers/obligations.py` | Add `require_permission` to 5 endpoints |
| `services/api-gateway/src/api_gateway/routers/drafting.py` | Add `require_permission` to 5 endpoints |
| `packages/ancol-common/src/ancol_common/auth/rbac.py` | Add `hitl:decide` permission key |
| `services/api-gateway/tests/test_rbac.py` | New file: ~15-20 RBAC enforcement tests |

### Obligation Auto-Transition

| File | Change |
|------|--------|
| `packages/ancol-common/src/ancol_common/db/repository.py` | Add `check_obligation_deadlines()` function |
| `services/api-gateway/src/api_gateway/routers/obligations.py` | Add `POST /check-deadlines` endpoint |
| `packages/ancol-common/src/ancol_common/auth/middleware.py` | Add `/api/obligations/check-deadlines` to `PUBLIC_PATHS` |
| `infra/modules/scheduler/main.tf` | Re-point `obligation_check` to POST `/check-deadlines` |
| `services/api-gateway/tests/test_obligations.py` | New file: ~8 obligation transition tests |

### Documentation

| File | Change |
|------|--------|
| `PROGRESS.md` | Add session entry for this work |
| `CLAUDE.md` | Update test count |

---

## 5. Out of Scope

- Per-gate HITL role enforcement (Phase 2)
- MFA (separate initiative)
- PWA manifest and push notifications (separate initiative)
- Frontend permission checks (frontend already has route-level RBAC via `auth.ts`)
