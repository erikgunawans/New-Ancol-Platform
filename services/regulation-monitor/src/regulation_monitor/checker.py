"""Regulation change checker — detects new/amended regulations.

Periodically checks configured regulation sources for changes,
compares against the current corpus, and notifies Legal team
when new or amended regulations are found.
"""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import UTC, date, datetime

import httpx
from ancol_common.db.connection import get_session
from ancol_common.db.models import RegulationIndex
from ancol_common.pubsub.publisher import publish_message

from .sources import ALL_SOURCES, RegulationSource

logger = logging.getLogger(__name__)


async def check_all_sources() -> list[dict]:
    """Check all regulation sources concurrently.

    Returns list of detected changes.
    """
    import asyncio

    results = await asyncio.gather(
        *(check_source(source) for source in ALL_SOURCES),
        return_exceptions=True,
    )
    changes = []
    for source, result in zip(ALL_SOURCES, results, strict=True):
        if isinstance(result, Exception):
            logger.exception("Failed to check source %s: %s", source.source_id, result)
        else:
            changes.extend(result)
    return changes


async def check_source(source: RegulationSource) -> list[dict]:
    """Check a single regulation source for changes.

    Returns list of detected new/amended regulations.
    """
    logger.info("Checking source: %s (%s)", source.name, source.base_url)
    changes = []

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(f"{source.base_url}{source.search_path}")
            response.raise_for_status()
            html = response.text
    except httpx.HTTPError:
        logger.warning("Failed to fetch %s%s", source.base_url, source.search_path)
        return changes

    # Extract regulation entries from HTML
    entries = _parse_regulation_entries(html, source)
    logger.info("Found %d entries from %s", len(entries), source.source_id)

    # Filter by relevance (keyword matching)
    relevant = [e for e in entries if _is_relevant(e, source.keywords)]
    logger.info("Filtered to %d relevant entries", len(relevant))

    # Batch-fetch existing regulations to avoid N+1
    async with get_session() as session:
        from sqlalchemy import select

        relevant_titles = [e["title"] for e in relevant]
        existing_result = await session.execute(
            select(RegulationIndex).where(RegulationIndex.title.in_(relevant_titles))
        )
        existing_by_title = {r.title: r for r in existing_result.scalars().all()}

    for entry in relevant:
        content_hash = hashlib.sha256(entry.get("url", "").encode()).hexdigest()[:16]
        existing_reg = existing_by_title.get(entry["title"])

        if existing_reg is None:
            change = {
                "type": "new",
                "source": source.source_id,
                "domain": source.domain,
                "title": entry["title"],
                "url": entry.get("url", ""),
                "published_date": entry.get("date"),
                "content_hash": content_hash,
                "detected_at": datetime.now(UTC).isoformat(),
            }
            changes.append(change)
            logger.info("NEW regulation: %s", entry["title"])
        else:
            if entry.get("date") and existing_reg.effective_date:
                try:
                    entry_date = date.fromisoformat(entry["date"])
                    if entry_date > existing_reg.effective_date:
                        change = {
                            "type": "amended",
                            "source": source.source_id,
                            "domain": source.domain,
                            "title": entry["title"],
                            "url": entry.get("url", ""),
                            "published_date": entry["date"],
                            "previous_date": existing_reg.effective_date.isoformat(),
                            "content_hash": content_hash,
                            "detected_at": datetime.now(UTC).isoformat(),
                        }
                        changes.append(change)
                        logger.info("AMENDED regulation: %s", entry["title"])
                except ValueError:
                    pass

    # Notify on changes
    for change in changes:
        _publish_change_notification(change)

    return changes


def _parse_regulation_entries(html: str, source: RegulationSource) -> list[dict]:
    """Extract regulation entries from HTML page.

    Uses simple regex parsing as a fallback when selectolax is not available.
    """
    entries = []

    try:
        from selectolax.parser import HTMLParser

        tree = HTMLParser(html)
        # Try to find regulation listing items
        for node in tree.css("li, tr, .regulation-item, .rule-item, article"):
            title_node = node.css_first(source.title_selector)
            date_node = node.css_first(source.date_selector)
            link_node = node.css_first("a[href]")

            if title_node and title_node.text(strip=True):
                entry = {"title": title_node.text(strip=True)}
                if date_node:
                    date_text = date_node.text(strip=True)
                    parsed = _parse_indonesian_date(date_text)
                    if parsed:
                        entry["date"] = parsed
                if link_node:
                    href = link_node.attributes.get("href", "")
                    if href.startswith("/"):
                        href = source.base_url + href
                    entry["url"] = href
                entries.append(entry)
    except ImportError:
        # Fallback: basic regex extraction
        title_matches = re.findall(r"<h[23][^>]*>(.*?)</h[23]>", html, re.DOTALL)
        for title in title_matches:
            clean_title = re.sub(r"<[^>]+>", "", title).strip()
            if clean_title:
                entries.append({"title": clean_title})

    return entries


def _parse_indonesian_date(text: str) -> str | None:
    """Parse an Indonesian date string to ISO format."""
    from ancol_common.utils import parse_indonesian_date

    return parse_indonesian_date(text)


def _is_relevant(entry: dict, keywords: list[str]) -> bool:
    """Check if a regulation entry is relevant based on keywords."""
    text = entry.get("title", "").lower()
    return any(kw.lower() in text for kw in keywords)


def _publish_change_notification(change: dict) -> None:
    """Publish a regulation change notification to Pub/Sub."""
    try:
        publish_message("regulation-change", change)
    except Exception:
        logger.warning("Failed to publish regulation change notification", exc_info=True)
