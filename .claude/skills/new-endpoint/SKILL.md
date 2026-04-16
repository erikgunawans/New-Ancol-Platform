---
name: new-endpoint
description: Create a new API endpoint with RBAC, MFA enforcement, and test stub
---

# /new-endpoint

Scaffold a new API Gateway endpoint following all Ancol project conventions.

## Arguments

- `/new-endpoint <router> <method> <path> <permission>` — e.g., `/new-endpoint contracts POST /contracts/{id}/archive contracts:archive`

## Checklist

Every new endpoint MUST have:

1. **RBAC permission** via `_auth=require_permission("<permission_key>")` parameter
2. **MFA enforcement** — if the endpoint is on a sensitive router (documents, hitl, contracts, drafting, reports, audit), the router already has `require_mfa_verified()` as a dependency
3. **Permission key in ROLE_PERMISSIONS** — add the new permission key to `packages/ancol-common/src/ancol_common/auth/rbac.py` with the correct role set
4. **Pydantic request/response models** — define inline in the router file
5. **Test coverage** — at least one test verifying the endpoint compiles and the permission key exists in RBAC matrix

## Steps

1. **Ask** the user which router file and what the endpoint does.

2. **Add permission key** to `ROLE_PERMISSIONS` in `packages/ancol-common/src/ancol_common/auth/rbac.py`:
   ```python
   "<permission_key>": {UserRole.ROLE1, UserRole.ROLE2, ...},
   ```

3. **Add the endpoint** to the router file in `services/api-gateway/src/api_gateway/routers/<router>.py`:
   - Include `_auth=require_permission("<key>")` parameter
   - Use `get_iap_user(request)` for user identity if needed
   - Use `async with get_session() as session:` for DB access
   - Use `UserResponse.from_user(u)` for user responses

4. **Add test** to `services/api-gateway/tests/test_rbac_enforcement.py`:
   - Verify permission key exists in `ROLE_PERMISSIONS`
   - Verify correct roles are assigned

5. **Run tests** to verify:
   ```bash
   PYTHONPATH=packages/ancol-common/src:services/api-gateway/src python3 -m pytest services/api-gateway/tests/ -q
   ```

6. **Run lint**:
   ```bash
   ruff check packages/ services/
   ```
