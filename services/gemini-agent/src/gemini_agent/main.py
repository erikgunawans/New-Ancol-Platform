"""Gemini Agent Builder webhook — routes tool calls to the Ancol MoM Compliance pipeline.

Task 11 (Phase 6.4a) wired the BJR read-only chat tool suite:
`get_decision`, `list_decisions`, `list_my_decisions`, `get_readiness`,
`get_checklist`, `show_document_indicators`, `show_decision_evidence`,
`get_passport_url`. RBAC on these tools is defined in `_ROLE_ALLOWED_TOOLS`
per spec § 4.2 — chat-side first-line defense; API Gateway's per-endpoint
`require_permission` remains the authoritative check.
"""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Ancol Gemini Agent Webhook",
    version="0.1.0",
)


# -- BJR read-only tool names (Phase 6.4a) --
_BJR_READ_TOOLS: frozenset[str] = frozenset(
    {
        "get_decision",
        "list_decisions",
        "list_my_decisions",
        "get_readiness",
        "get_checklist",
        "show_document_indicators",
        "show_decision_evidence",
        "get_passport_url",
    }
)


# -- Per-role allowed chat tools --
#
# Chat-side RBAC: dispatcher rejects disallowed calls with a friendly
# Indonesian denial. Authoritative RBAC remains in the API Gateway via
# `require_permission(...)` on every route.
#
# Spec § 4.2 BJR allocation:
# - admin / corp_secretary / legal_compliance / internal_auditor → all 8 BJR read tools
# - business_dev → all except `get_passport_url` (no passport access)
# - komisaris / dewan_pengawas → 7 (no `list_my_decisions` — not owners)
# - direksi → 6 (owners: list_my_decisions + core read + passport; no list_decisions/evidence)
# - contract_manager → no BJR tools (out of scope for BJR chat surface)
_ROLE_ALLOWED_TOOLS: dict[str, frozenset[str]] = {
    "corp_secretary": frozenset(
        {
            # Baseline MoM + CLM tools
            "upload_document",
            "check_status",
            "review_gate",
            "get_review_detail",
            "submit_decision",
            "get_report",
            "upload_contract",
            "check_contract_status",
            "list_obligations",
        }
    )
    | _BJR_READ_TOOLS,
    "internal_auditor": frozenset(
        {
            "review_gate",
            "get_review_detail",
            "submit_decision",
            "get_report",
            "get_dashboard",
            "check_status",
            "check_contract_status",
            "get_contract_risk",
            "list_obligations",
        }
    )
    | _BJR_READ_TOOLS,
    "komisaris": frozenset(
        {
            "get_report",
            "get_dashboard",
            "search_regulations",
            "check_status",
            "check_contract_status",
            "get_contract_portfolio",
        }
    )
    | (_BJR_READ_TOOLS - {"list_my_decisions"}),
    "dewan_pengawas": frozenset(
        {
            # Supervisory board — same chat surface as komisaris for BJR, minimal baseline
            "get_report",
            "check_status",
            "search_regulations",
        }
    )
    | (_BJR_READ_TOOLS - {"list_my_decisions"}),
    "direksi": frozenset(
        {
            # Board directors — owners of decisions, passport consumers
            "check_status",
            "get_report",
        }
    )
    | frozenset(
        {
            "list_my_decisions",
            "get_decision",
            "get_readiness",
            "get_checklist",
            "show_document_indicators",
            "get_passport_url",
        }
    ),
    "legal_compliance": frozenset(
        {
            "review_gate",
            "get_review_detail",
            "submit_decision",
            "search_regulations",
            "check_status",
            "get_report",
            "upload_contract",
            "check_contract_status",
            "get_contract_risk",
            "list_obligations",
            "generate_draft",
            "ask_contract_question",
        }
    )
    | _BJR_READ_TOOLS,
    "contract_manager": frozenset(
        {
            "upload_contract",
            "check_contract_status",
            "get_contract_risk",
            "get_contract_portfolio",
            "list_obligations",
            "fulfill_obligation",
            "generate_draft",
            "ask_contract_question",
            "search_regulations",
            "check_status",
            "get_report",
        }
    ),
    "business_dev": frozenset(
        {
            "generate_draft",
            "check_contract_status",
            "ask_contract_question",
            "search_regulations",
            "check_status",
        }
    )
    | (_BJR_READ_TOOLS - {"get_passport_url"}),
    "admin": frozenset(
        {
            "upload_document",
            "review_gate",
            "get_review_detail",
            "submit_decision",
            "check_status",
            "get_report",
            "search_regulations",
            "get_dashboard",
            "upload_contract",
            "check_contract_status",
            "get_contract_risk",
            "get_contract_portfolio",
            "list_obligations",
            "fulfill_obligation",
            "generate_draft",
            "ask_contract_question",
        }
    )
    | _BJR_READ_TOOLS,
}


def _role_allowed_tools(role: str) -> frozenset[str]:
    """Return the set of tool names a role may invoke from chat.

    Unknown roles get an empty frozenset — fail-closed, never fail-open.
    """
    return _ROLE_ALLOWED_TOOLS.get(role, frozenset())


def _get_api_client():
    """Lazy import to avoid circular imports during testing.

    ApiClient reads `API_GATEWAY_URL` and `ENVIRONMENT` from env internally,
    so we only need to supply `base_url` explicitly when overriding the default.
    """
    from gemini_agent.api_client import ApiClient

    return ApiClient(
        base_url=os.getenv("API_GATEWAY_URL", "http://localhost:8080"),
    )


async def _dispatch_tool(
    tool_name: str,
    params: dict,
    api,
    user: dict,
) -> str:
    """Route a tool call to the appropriate handler.

    ``api`` is injected so the dispatcher is a pure routing function —
    tests can pass an ``AsyncMock`` directly without monkey-patching the
    ApiClient factory.
    """
    if tool_name == "upload_document":
        from gemini_agent.tools.upload import handle_upload_document

        return await handle_upload_document(params, api, user)

    if tool_name == "review_gate":
        from gemini_agent.tools.review import handle_review_gate

        return await handle_review_gate(params, api, user)

    if tool_name == "get_review_detail":
        from gemini_agent.tools.review import handle_get_review_detail

        return await handle_get_review_detail(params, api, user)

    if tool_name == "submit_decision":
        from gemini_agent.tools.review import handle_submit_decision

        return await handle_submit_decision(params, api, user)

    if tool_name == "check_status":
        from gemini_agent.tools.status import handle_check_status

        return await handle_check_status(params, api, user)

    if tool_name == "get_report":
        from gemini_agent.tools.reports import handle_get_report

        return await handle_get_report(params, api, user)

    if tool_name == "search_regulations":
        from gemini_agent.tools.regulations import (
            handle_search_regulations,
        )

        return await handle_search_regulations(params, api, user)

    if tool_name == "get_dashboard":
        from gemini_agent.tools.dashboard import handle_get_dashboard

        return await handle_get_dashboard(params, api, user)

    # -- Contract tools --

    if tool_name == "upload_contract":
        from gemini_agent.tools.contracts import handle_upload_contract

        return await handle_upload_contract(params, api, user)

    if tool_name == "check_contract_status":
        from gemini_agent.tools.contracts import handle_check_contract_status

        return await handle_check_contract_status(params, api, user)

    if tool_name == "get_contract_portfolio":
        from gemini_agent.tools.contracts import handle_get_contract_portfolio

        return await handle_get_contract_portfolio(params, api, user)

    if tool_name == "get_contract_risk":
        contract_id = params.get("contract_id", "")
        if not contract_id:
            return "Error: Mohon berikan contract_id."
        data = await api.get_contract_risk(contract_id)
        from gemini_agent.formatting import format_contract_risk

        return format_contract_risk(data)

    if tool_name == "list_obligations":
        from gemini_agent.tools.obligations import handle_list_obligations

        return await handle_list_obligations(params, api, user)

    if tool_name == "fulfill_obligation":
        from gemini_agent.tools.obligations import handle_fulfill_obligation

        return await handle_fulfill_obligation(params, api, user)

    if tool_name == "generate_draft":
        from gemini_agent.tools.drafting import handle_generate_draft

        return await handle_generate_draft(params, api, user)

    if tool_name == "ask_contract_question":
        from gemini_agent.tools.contract_qa import handle_ask_contract_question

        return await handle_ask_contract_question(params, api, user)

    # -- BJR read-only tools (Phase 6.4a) --

    if tool_name == "get_decision":
        from gemini_agent.tools.bjr_decisions import handle_get_decision

        return await handle_get_decision(params, api, user)

    if tool_name == "list_decisions":
        from gemini_agent.tools.bjr_decisions import handle_list_decisions

        return await handle_list_decisions(params, api, user)

    if tool_name == "list_my_decisions":
        from gemini_agent.tools.bjr_decisions import handle_list_my_decisions

        return await handle_list_my_decisions(params, api, user)

    if tool_name == "get_readiness":
        from gemini_agent.tools.bjr_readiness import handle_get_readiness

        return await handle_get_readiness(params, api, user)

    if tool_name == "get_checklist":
        from gemini_agent.tools.bjr_readiness import handle_get_checklist

        return await handle_get_checklist(params, api, user)

    if tool_name == "show_document_indicators":
        from gemini_agent.tools.bjr_evidence import handle_show_document_indicators

        return await handle_show_document_indicators(params, api, user)

    if tool_name == "show_decision_evidence":
        from gemini_agent.tools.bjr_evidence import handle_show_decision_evidence

        return await handle_show_decision_evidence(params, api, user)

    if tool_name == "get_passport_url":
        from gemini_agent.tools.bjr_passport import handle_get_passport_url

        return await handle_get_passport_url(params, api, user)

    raise ValueError(f"Unknown tool: {tool_name}")


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "gemini-agent",
        "version": "0.1.0",
    }


@app.post("/webhook")
async def webhook(request: Request):
    """Handle incoming tool calls from Vertex AI Agent Builder."""
    body = await request.json()

    tool_call = body.get("tool_call", {})
    tool_name = tool_call.get("name", "")
    params = tool_call.get("parameters", {})

    user = body.get("user_identity", {})
    user_role = user.get("role", "")

    # Chat-side RBAC — fail-closed for unknown roles
    allowed = _role_allowed_tools(user_role)
    if tool_name not in allowed:
        logger.warning("Access denied: role=%s tool=%s", user_role, tool_name)
        return JSONResponse(
            content={
                "tool_response": {
                    "name": tool_name,
                    "content": (
                        "Maaf, Anda tidak memiliki akses untuk "
                        f"fungsi '{tool_name}' dengan peran "
                        f"'{user_role}'."
                    ),
                }
            },
            status_code=200,
        )

    api = _get_api_client()
    try:
        result = await _dispatch_tool(tool_name, params, api, user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        logger.exception("Tool execution failed: %s", tool_name)
        return JSONResponse(
            content={
                "tool_response": {
                    "name": tool_name,
                    "content": ("Terjadi kesalahan saat memproses permintaan. Silakan coba lagi."),
                }
            },
            status_code=200,
        )

    return {
        "tool_response": {
            "name": tool_name,
            "content": result,
        }
    }
