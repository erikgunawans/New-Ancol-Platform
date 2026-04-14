"""Contract Q&A RAG — 3-layer hybrid retrieval for contract questions.

Layers:
1. Vertex AI Search — semantic clause search across contract corpus
2. Spanner Graph — expand contract-regulation and contract-contract edges
3. Cloud SQL — exact contract/clause lookup when contract_id is specified

Results are re-ranked and synthesized by Gemini 2.5 Pro.
"""

from __future__ import annotations

import logging

from ancol_common.config import get_settings

from .orchestrator import get_graph_client

logger = logging.getLogger(__name__)


async def answer_contract_question(
    question: str,
    contract_id: str | None,
    api,
) -> dict:
    """3-layer RAG for contract Q&A.

    Args:
        question: Natural-language question in Bahasa Indonesia or English.
        contract_id: Optional contract ID for scoped queries.
        api: ApiClient for Cloud SQL lookups.

    Returns:
        dict with answer, citations, related_contracts, regulations.
    """
    chunks: list[dict] = []
    regulations: list[dict] = []
    related_contracts: list[dict] = []

    # Layer 1: Vertex AI Search (semantic)
    vector_results = await _contract_vector_search(question)
    for result in vector_results:
        chunks.append(
            {
                "source": "vector_search",
                "contract_id": result.get("contract_id", ""),
                "contract_title": result.get("contract_title", ""),
                "clause_number": result.get("clause_number", ""),
                "category": result.get("clause_category", ""),
                "text": result.get("content", ""),
                "risk_level": result.get("risk_level", ""),
                "relevance_score": result.get("relevance_score", 0.5),
            }
        )

    # Layer 2: Spanner Graph (relationship expansion)
    graph = get_graph_client()
    contract_ids = {c["contract_id"] for c in chunks if c.get("contract_id")}
    if contract_id:
        contract_ids.add(contract_id)

    if graph and contract_ids:
        import asyncio

        async def _graph_lookup(cid: str) -> tuple[list[dict], list[dict]]:
            regs, rels = [], []
            try:
                for reg in await graph.get_related_regulations_for_contract(cid):
                    regs.append(
                        {
                            "regulation_id": reg.id,
                            "title": reg.title,
                            "issuer": reg.issuer,
                            "status": reg.status,
                        }
                    )
            except Exception:
                logger.warning("Graph regulation lookup failed for %s", cid)
            try:
                for rc in await graph.get_related_contracts(cid):
                    rels.append(
                        {
                            "id": rc.id,
                            "title": rc.title,
                            "contract_type": rc.contract_type,
                            "status": rc.status,
                        }
                    )
            except Exception:
                logger.warning("Graph contract chain lookup failed for %s", cid)
            return regs, rels

        results = await asyncio.gather(*[_graph_lookup(cid) for cid in contract_ids])
        for regs, rels in results:
            regulations.extend(regs)
            related_contracts.extend(rels)

    # Layer 3: Cloud SQL (exact lookup)
    if contract_id:
        try:
            contract = await api.get_contract(contract_id)
            clauses_resp = await api.get_contract_clauses(contract_id)
            contract_clauses = clauses_resp.get("clauses", [])
            for cl in contract_clauses:
                chunks.append(
                    {
                        "source": "cloud_sql",
                        "contract_id": contract_id,
                        "contract_title": contract.get("title", ""),
                        "clause_number": cl.get("clause_number", ""),
                        "category": cl.get("category", ""),
                        "text": cl.get("text", ""),
                        "risk_level": cl.get("risk_level", ""),
                        "relevance_score": 1.0,  # direct match gets highest score
                    }
                )
        except Exception:
            logger.warning("Cloud SQL lookup failed for contract %s", contract_id)

    # Re-rank: direct SQL > vector search > graph-derived
    chunks = _rerank(chunks)

    # Limit context for Gemini
    top_chunks = chunks[:15]

    # Synthesize answer via Gemini
    answer = await _synthesize_answer(question, top_chunks, regulations, related_contracts)

    return {
        "answer": answer,
        "citations": [
            {
                "contract_id": c["contract_id"],
                "contract_title": c["contract_title"],
                "clause_number": c["clause_number"],
                "category": c["category"],
                "text_excerpt": c["text"][:200],
                "risk_level": c["risk_level"],
            }
            for c in top_chunks[:5]
        ],
        "regulations": regulations,
        "related_contracts": related_contracts,
    }


async def _contract_vector_search(query: str) -> list[dict]:
    """Search contract clauses via Vertex AI Search."""
    try:
        from google.cloud import discoveryengine
    except ImportError:
        logger.error("google-cloud-discoveryengine not installed")
        return []

    settings = get_settings()

    try:
        client = discoveryengine.SearchServiceAsyncClient()
        datastore = settings.vertex_search_contracts_datastore
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
                content = ""
                if doc.derived_struct_data:
                    snippets = doc.derived_struct_data.get("snippets", [])
                    if snippets:
                        content = snippets[0].get("snippet", "")

                results.append(
                    {
                        "contract_id": struct_data.get("contract_id", doc.id),
                        "contract_title": struct_data.get("contract_title", ""),
                        "clause_number": struct_data.get("clause_number", ""),
                        "clause_category": struct_data.get("clause_category", ""),
                        "risk_level": struct_data.get("risk_level", ""),
                        "content": content or struct_data.get("title", ""),
                        "relevance_score": 0.7,
                    }
                )

        return results

    except Exception:
        logger.exception("Vertex AI Search contract query failed")
        return []


def _rerank(chunks: list[dict]) -> list[dict]:
    """Re-rank chunks: Cloud SQL direct > vector search > others."""
    source_priority = {"cloud_sql": 3, "vector_search": 2, "graph": 1}

    def score(chunk):
        priority = source_priority.get(chunk.get("source", ""), 0)
        relevance = chunk.get("relevance_score", 0.5)
        return priority + relevance

    # Deduplicate by contract_id + clause_number
    seen = set()
    unique = []
    for chunk in chunks:
        key = (chunk.get("contract_id"), chunk.get("clause_number"))
        if key not in seen:
            seen.add(key)
            unique.append(chunk)

    return sorted(unique, key=score, reverse=True)


async def _synthesize_answer(
    question: str,
    chunks: list[dict],
    regulations: list[dict],
    related_contracts: list[dict],
) -> str:
    """Call Gemini 2.5 Pro to synthesize an answer from RAG chunks."""
    try:
        from ancol_common.gemini.client import get_gemini_client, get_pro_model
        from google.genai.types import GenerateContentConfig

        client = get_gemini_client()
        model = get_pro_model()

        context = "\n\n".join(
            f"[{c['contract_title']}, {c['clause_number']}] "
            f"({c['category']}, risiko: {c['risk_level']})\n{c['text'][:1000]}"
            for c in chunks
        )

        reg_context = ""
        if regulations:
            reg_context = "\n\nRegulasi terkait:\n" + "\n".join(
                f"- {r['regulation_id']}: {r.get('title', '')}" for r in regulations
            )

        system_prompt = (
            "Anda adalah asisten hukum untuk PT Pembangunan Jaya Ancol Tbk. "
            "Jawab pertanyaan berdasarkan konteks klausul kontrak yang diberikan. "
            "Gunakan Bahasa Indonesia dengan istilah hukum dalam Bahasa Inggris. "
            "Sebutkan nomor pasal dan judul kontrak dalam jawaban. "
            "Jika informasi tidak tersedia dalam konteks, katakan dengan jelas. "
            "Jangan mengarang informasi yang tidak ada dalam konteks."
        )

        user_message = (
            f"## Pertanyaan\n{question}\n\n## Konteks Klausul Kontrak\n{context}{reg_context}"
        )

        response = client.models.generate_content(
            model=model,
            contents=[
                {"role": "user", "parts": [{"text": system_prompt}]},
                {"role": "user", "parts": [{"text": user_message}]},
            ],
            config=GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=2048,
            ),
        )

        return response.text

    except Exception:
        logger.exception("Gemini synthesis failed for contract Q&A")
        return (
            "Maaf, terjadi kesalahan saat memproses pertanyaan Anda. "
            "Silakan coba lagi atau hubungi tim Legal & Compliance."
        )
