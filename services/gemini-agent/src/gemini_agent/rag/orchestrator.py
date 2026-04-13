"""Hybrid RAG orchestrator — Vector Search + Graph RAG + Re-ranking.

Combines three retrieval layers:
1. **Vector search** via Vertex AI Search (Discovery Engine)
2. **Graph expansion** via Spanner or Neo4j knowledge graph
3. **Re-ranking** based on relevance, recency, and authority level

The ``query_regulations`` function is the single entry-point consumed by the
Gemini Agent webhook tool handlers.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import date, datetime

from ancol_common.config import get_settings

from .graph_client import GraphClient

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Authority level mapping (higher = more authoritative)
# ---------------------------------------------------------------------------
AUTHORITY_LEVELS: dict[str, int] = {
    "UUPT": 5,  # Undang-Undang Perseroan Terbatas
    "POJK": 4,  # Peraturan OJK
    "SE-OJK": 3,  # Surat Edaran OJK
    "IDX": 2,  # Peraturan Bursa Efek Indonesia
    "Internal": 1,  # Peraturan internal perusahaan
}


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def get_graph_client() -> GraphClient | None:
    """Instantiate the configured graph backend.

    Reads the ``GRAPH_BACKEND`` env var:
    - ``"spanner"`` (default) — uses :class:`SpannerGraphClient`
    - ``"neo4j"`` — uses :class:`Neo4jGraphClient`
    - ``"none"`` / ``"disabled"`` — returns ``None`` (vector-only mode)

    Returns ``None`` (with a warning) if the chosen backend fails to
    initialise, so the orchestrator can still operate in vector-only mode.
    """
    backend = os.getenv("GRAPH_BACKEND", "spanner").lower().strip()

    if backend in ("none", "disabled", ""):
        logger.info("Graph backend disabled — running in vector-only mode")
        return None

    if backend == "spanner":
        try:
            from .spanner_graph import SpannerGraphClient

            return SpannerGraphClient()
        except Exception:
            logger.exception(
                "Failed to initialise SpannerGraphClient — falling back to vector-only mode"
            )
            return None

    if backend == "neo4j":
        try:
            from .neo4j_graph import Neo4jGraphClient

            return Neo4jGraphClient()
        except Exception:
            logger.exception(
                "Failed to initialise Neo4jGraphClient — falling back to vector-only mode"
            )
            return None

    logger.warning(
        "Unknown GRAPH_BACKEND=%r — falling back to vector-only mode",
        backend,
    )
    return None


# ---------------------------------------------------------------------------
# Vector search (Vertex AI Search / Discovery Engine)
# ---------------------------------------------------------------------------


async def _vector_search(query: str) -> list[dict]:
    """Run a vector search against the Vertex AI Search datastore.

    Returns a list of dicts, each containing at minimum:
    - ``regulation_id``
    - ``title``
    - ``issuer``
    - ``relevance_score`` (float, 0-1)
    - ``clauses`` (list of clause snippets from the search result)
    """
    try:
        from google.cloud import discoveryengine  # type: ignore[import-untyped]
    except ImportError:
        logger.error("google-cloud-discoveryengine not installed — vector search unavailable")
        return []

    settings = get_settings()

    try:
        client = discoveryengine.SearchServiceAsyncClient()

        # Build the serving config path from the datastore resource name
        datastore = settings.vertex_search_datastore
        serving_config = f"{datastore}/servingConfigs/default_search"

        request = discoveryengine.SearchRequest(
            serving_config=serving_config,
            query=query,
            page_size=20,
            query_expansion_spec=discoveryengine.SearchRequest.QueryExpansionSpec(
                condition=discoveryengine.SearchRequest.QueryExpansionSpec.Condition.AUTO,
            ),
            spell_correction_spec=discoveryengine.SearchRequest.SpellCorrectionSpec(
                mode=discoveryengine.SearchRequest.SpellCorrectionSpec.Mode.AUTO,
            ),
        )

        response = await client.search(request=request)

        results: list[dict] = []
        async for page in response.pages:
            for result in page.results:
                doc = result.document
                struct_data = dict(doc.struct_data) if doc.struct_data else {}

                regulation_id = struct_data.get(
                    "regulation_id",
                    doc.id,
                )
                title = struct_data.get("title", "")
                issuer = struct_data.get("issuer", "")
                effective_date = struct_data.get("effective_date", "")
                authority = struct_data.get("authority_level", "Internal")
                domain = struct_data.get("domain", "")

                # Extract clause snippets from derived_struct_data
                clauses: list[dict] = []
                if doc.derived_struct_data:
                    snippets = doc.derived_struct_data.get("snippets", [])
                    for snippet in snippets:
                        clauses.append(
                            {
                                "clause_number": snippet.get("clause_number", ""),
                                "text_summary": snippet.get("snippet", snippet.get("text", "")),
                            }
                        )

                results.append(
                    {
                        "regulation_id": regulation_id,
                        "title": title,
                        "issuer": issuer,
                        "effective_date": effective_date,
                        "authority_level_name": authority,
                        "domain": domain,
                        "relevance_score": float(getattr(result, "relevance_score", 0.5)),
                        "clauses": clauses,
                    }
                )

        logger.info(
            "Vector search returned %d results for query: %s",
            len(results),
            query[:80],
        )
        return results

    except Exception:
        logger.exception("Vertex AI Search query failed")
        return []


# ---------------------------------------------------------------------------
# Re-ranking helpers
# ---------------------------------------------------------------------------


def _recency_weight(effective_date_str: str) -> float:
    """Compute a recency multiplier based on how old the regulation is.

    - Last 2 years:  1.0
    - 2-5 years:     0.8
    - Older:         0.6
    """
    if not effective_date_str:
        return 0.6

    try:
        eff_date = datetime.fromisoformat(effective_date_str).date()
    except (ValueError, TypeError):
        # Try common date formats
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
            try:
                eff_date = datetime.strptime(effective_date_str, fmt).date()
                break
            except (ValueError, TypeError):
                continue
        else:
            return 0.6

    age_days = (date.today() - eff_date).days
    if age_days <= 730:  # 2 years
        return 1.0
    if age_days <= 1825:  # 5 years
        return 0.8
    return 0.6


def _authority_score(authority_name: str) -> int:
    """Map authority level name to numeric score."""
    return AUTHORITY_LEVELS.get(authority_name, 1)


def _compute_score(relevance: float, effective_date: str, authority_name: str) -> float:
    """Composite score = relevance * recency_weight * authority_level."""
    return relevance * _recency_weight(effective_date) * _authority_score(authority_name)


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------


async def query_regulations(query: str, graph_client: GraphClient | None = None) -> dict:
    """Hybrid RAG query combining vector search, graph expansion, and re-ranking.

    Parameters
    ----------
    query:
        Natural-language query describing the regulatory context needed.
    graph_client:
        Optional graph backend.  When ``None`` the orchestrator operates in
        vector-only mode (no graph expansion).

    Returns
    -------
    dict
        A dict with ``results`` (list of scored regulation entries),
        ``query``, and ``total_results``.
    """
    # ------------------------------------------------------------------
    # 1. Vector search
    # ------------------------------------------------------------------
    vector_results = await _vector_search(query)

    if not vector_results:
        return {"results": [], "query": query, "total_results": 0}

    # ------------------------------------------------------------------
    # 2. Graph expansion (if graph backend is available)
    # ------------------------------------------------------------------
    enriched: dict[str, dict] = {}

    for vr in vector_results:
        reg_id = vr["regulation_id"]
        if reg_id in enriched:
            # Merge clauses into existing entry, keep higher relevance
            enriched[reg_id]["clauses"].extend(vr.get("clauses", []))
            enriched[reg_id]["relevance_score"] = max(
                enriched[reg_id]["relevance_score"], vr["relevance_score"]
            )
            continue

        enriched[reg_id] = {
            "regulation_id": reg_id,
            "title": vr["title"],
            "issuer": vr["issuer"],
            "effective_date": vr.get("effective_date", ""),
            "authority_level_name": vr.get("authority_level_name", "Internal"),
            "authority_level": _authority_score(vr.get("authority_level_name", "Internal")),
            "is_active": True,  # default; refined by graph
            "relevant_clauses": [],
            "clauses": vr.get("clauses", []),
            "amendment_chain": [],
            "cross_references": [],
            "relevance_score": vr["relevance_score"],
            "domain": vr.get("domain", ""),
        }

    if graph_client is not None:
        await _expand_with_graph(enriched, graph_client)

    # ------------------------------------------------------------------
    # 3. Build final clause list and compute scores
    # ------------------------------------------------------------------
    scored_results: list[dict] = []

    for entry in enriched.values():
        # Deduplicate clauses
        seen_clauses: set[str] = set()
        unique_clauses: list[dict] = []
        for clause in entry.get("clauses", []) + entry.get("relevant_clauses", []):
            key = clause.get("clause_number", "") + clause.get("text_summary", "")
            if key and key not in seen_clauses:
                seen_clauses.add(key)
                unique_clauses.append(
                    {
                        "clause_number": clause.get("clause_number", ""),
                        "text_summary": clause.get("text_summary", ""),
                    }
                )

        score = _compute_score(
            entry["relevance_score"],
            entry["effective_date"],
            entry["authority_level_name"],
        )

        scored_results.append(
            {
                "regulation_id": entry["regulation_id"],
                "title": entry["title"],
                "issuer": entry["issuer"],
                "authority_level": entry["authority_level"],
                "is_active": entry["is_active"],
                "relevant_clauses": unique_clauses,
                "amendment_chain": entry["amendment_chain"],
                "cross_references": entry["cross_references"],
                "relevance_score": round(score, 4),
            }
        )

    # ------------------------------------------------------------------
    # 4. Sort by score descending, deduplicate by regulation_id
    # ------------------------------------------------------------------
    scored_results.sort(key=lambda r: r["relevance_score"], reverse=True)

    final: list[dict] = []
    seen_ids: set[str] = set()
    for r in scored_results:
        if r["regulation_id"] not in seen_ids:
            seen_ids.add(r["regulation_id"])
            final.append(r)

    logger.info(
        "Hybrid RAG returned %d results (from %d vector hits) for: %s",
        len(final),
        len(vector_results),
        query[:80],
    )

    return {
        "results": final,
        "query": query,
        "total_results": len(final),
    }


# ---------------------------------------------------------------------------
# Graph expansion (internal)
# ---------------------------------------------------------------------------


async def _expand_with_graph(enriched: dict[str, dict], graph_client: GraphClient) -> None:
    """Enrich vector results with graph traversal data.

    For each regulation found by vector search:
    - Fetch the amendment chain
    - Check whether the regulation is still active
    - Collect cross-references from its clauses
    - Pull related regulations from the same domain
    """
    reg_ids = list(enriched.keys())

    # Run graph queries concurrently per regulation
    async def _expand_one(reg_id: str) -> None:
        entry = enriched[reg_id]

        # Amendment chain + active status in parallel
        amendment_task = graph_client.get_amendment_chain(reg_id)
        active_task = graph_client.check_active_status(reg_id)
        amendments, is_active = await asyncio.gather(amendment_task, active_task)

        entry["is_active"] = is_active
        entry["amendment_chain"] = [
            {
                "amends": a.target_id,
                "effective_date": a.effective_date,
            }
            for a in amendments
        ]

        # Cross-references (from any clause we already know about)
        all_xrefs: list[dict] = []
        for clause in entry.get("clauses", []):
            clause_id = clause.get("clause_id", "")
            if clause_id:
                xrefs = await graph_client.find_cross_references(clause_id)
                all_xrefs.extend(
                    {
                        "target": x.target_clause_id,
                        "type": x.reference_type,
                    }
                    for x in xrefs
                )
        entry["cross_references"] = all_xrefs

        # Related regulations by domain
        domain = entry.get("domain", "")
        if domain:
            related = await graph_client.get_regulations_by_domain(domain)
            for rel in related:
                if rel.id not in enriched:
                    enriched[rel.id] = {
                        "regulation_id": rel.id,
                        "title": rel.title,
                        "issuer": rel.issuer,
                        "effective_date": rel.effective_date,
                        "authority_level_name": _resolve_authority_name(rel.authority_level),
                        "authority_level": rel.authority_level,
                        "is_active": rel.status == "active",
                        "relevant_clauses": [],
                        "clauses": [],
                        "amendment_chain": [],
                        "cross_references": [],
                        # Domain-related but not directly matched — lower base
                        "relevance_score": 0.3,
                        "domain": domain,
                    }

    await asyncio.gather(*[_expand_one(rid) for rid in reg_ids])


def _resolve_authority_name(level: int) -> str:
    """Reverse-map numeric authority level to its name."""
    for name, value in AUTHORITY_LEVELS.items():
        if value == level:
            return name
    return "Internal"
