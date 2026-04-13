"""Tool handler — dashboard statistics and trend overview."""

from __future__ import annotations

import logging

from gemini_agent.api_client import ApiClient
from gemini_agent.formatting import format_dashboard

logger = logging.getLogger(__name__)


async def handle_get_dashboard(
    params: dict,
    api: ApiClient,
    user: dict,
) -> str:
    """Fetch dashboard statistics and optionally include monthly trends.

    Parameters
    ----------
    params:
        include_trends (bool): Whether to include monthly trend data (default True).
        months (int): Number of months for trend data (default 6).
    """
    include_trends: bool = params.get("include_trends", True)
    months: int = params.get("months", 6)

    logger.info("Fetching dashboard stats (trends=%s, months=%d)", include_trends, months)

    try:
        stats = await api.get_dashboard_stats()
    except Exception:
        logger.exception("Failed to fetch dashboard stats")
        return "Gagal mengambil statistik dashboard dari server."

    if include_trends:
        try:
            trends_data = await api.get_dashboard_trends(months=months)
            stats["trends"] = trends_data.get("trends", [])
        except Exception:
            logger.warning("Failed to fetch trends, returning stats only")

    return format_dashboard(stats)
