"""Index contract clauses into Vertex AI Search for semantic retrieval."""

from __future__ import annotations

import logging
import re

from ancol_common.config import get_settings

logger = logging.getLogger(__name__)


async def index_contract_clauses(
    contract_id: str,
    contract_title: str,
    contract_type: str,
    clauses: list[dict],
) -> int:
    """Index extracted clauses into Vertex AI Search contracts datastore.

    Each clause becomes one document with structured metadata.
    Returns count of indexed documents. Best-effort — logs warnings on failure.
    """
    try:
        from google.cloud import discoveryengine
    except ImportError:
        logger.error("google-cloud-discoveryengine not installed — indexing unavailable")
        return 0

    settings = get_settings()
    datastore = settings.vertex_search_contracts_datastore
    parent = f"{datastore}/branches/default_branch"

    client = discoveryengine.DocumentServiceClient()
    indexed = 0

    for clause in clauses:
        clause_number = clause.get("clause_number", "unknown")
        # Sanitize clause number for document ID
        doc_id = f"{contract_id}_{re.sub(r'[^a-zA-Z0-9_-]', '_', clause_number)}"

        struct_data = {
            "contract_id": contract_id,
            "contract_title": contract_title,
            "contract_type": contract_type,
            "clause_number": clause_number,
            "clause_category": clause.get("category", "other"),
            "risk_level": clause.get("risk_level", "low"),
            "title": clause.get("title", ""),
        }

        document = discoveryengine.Document(
            id=doc_id,
            struct_data=struct_data,
            content=discoveryengine.Document.Content(
                raw_bytes=clause.get("text", "").encode("utf-8"),
                mime_type="text/plain",
            ),
        )

        try:
            client.create_document(
                parent=parent,
                document=document,
                document_id=doc_id,
            )
            indexed += 1
        except Exception as e:
            if "ALREADY_EXISTS" in str(e):
                try:
                    document.name = f"{parent}/documents/{doc_id}"
                    client.update_document(document=document)
                    indexed += 1
                except Exception:
                    logger.warning("Failed to update clause %s: %s", doc_id, e)
            else:
                logger.warning("Failed to index clause %s: %s", doc_id, e)

    logger.info("Indexed %d/%d clauses for contract %s", indexed, len(clauses), contract_id)
    return indexed
