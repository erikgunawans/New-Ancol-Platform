"""Tool handlers for Agent Builder function calls."""

from __future__ import annotations

from .dashboard import handle_get_dashboard
from .regulations import handle_search_regulations
from .reports import handle_get_report
from .review import handle_get_review_detail, handle_review_gate, handle_submit_decision
from .status import handle_check_status
from .upload import handle_upload_document

__all__ = [
    "handle_check_status",
    "handle_get_dashboard",
    "handle_get_report",
    "handle_get_review_detail",
    "handle_review_gate",
    "handle_search_regulations",
    "handle_submit_decision",
    "handle_upload_document",
]
