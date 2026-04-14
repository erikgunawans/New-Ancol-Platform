"""Gemini Agent Builder webhook — routes tool calls to the Ancol MoM Compliance pipeline."""

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

# Role → allowed tool names
ROLE_TOOL_ACCESS: dict[str, set[str]] = {
    "corp_secretary": {
        "upload_document",
        "check_status",
        "review_gate",
        "get_review_detail",
        "submit_decision",
        "get_report",
        "upload_contract",
        "check_contract_status",
        "list_obligations",
    },
    "internal_auditor": {
        "review_gate",
        "get_review_detail",
        "submit_decision",
        "get_report",
        "get_dashboard",
        "check_status",
        "check_contract_status",
        "get_contract_risk",
        "list_obligations",
    },
    "komisaris": {
        "get_report",
        "get_dashboard",
        "search_regulations",
        "check_status",
        "check_contract_status",
        "get_contract_portfolio",
    },
    "legal_compliance": {
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
    },
    "contract_manager": {
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
    },
    "business_dev": {
        "generate_draft",
        "check_contract_status",
        "ask_contract_question",
        "search_regulations",
        "check_status",
    },
    "admin": {
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
    },
}


def _get_api_client():
    """Lazy import to avoid circular imports during testing."""
    from gemini_agent.api_client import ApiClient

    return ApiClient(
        base_url=os.getenv("API_GATEWAY_URL", "http://localhost:8080"),
        environment=os.getenv("ENVIRONMENT", "dev"),
    )


async def _dispatch_tool(
    tool_name: str,
    params: dict,
    user: dict,
) -> str:
    """Route a tool call to the appropriate handler."""
    api = _get_api_client()

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

    # Validate role-based access
    allowed = ROLE_TOOL_ACCESS.get(user_role, set())
    if tool_name not in allowed:
        logger.warning(
            "Access denied: role=%s tool=%s", user_role, tool_name
        )
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

    try:
        result = await _dispatch_tool(tool_name, params, user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        logger.exception("Tool execution failed: %s", tool_name)
        return JSONResponse(
            content={
                "tool_response": {
                    "name": tool_name,
                    "content": (
                        "Terjadi kesalahan saat memproses permintaan. "
                        "Silakan coba lagi."
                    ),
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
