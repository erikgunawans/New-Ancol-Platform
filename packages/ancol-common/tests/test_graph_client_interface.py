"""Abstract interface guard — ensures every GraphClient impl has the 6 new BJR methods."""

from __future__ import annotations

import inspect

from ancol_common.rag.graph_client import GraphClient


def test_graph_client_has_bjr_methods() -> None:
    """The 6 new BJR methods must exist and be abstract."""
    required = {
        "upsert_decision_node",
        "upsert_supported_by_edge",
        "upsert_satisfies_item_edge",
        "upsert_approved_by_edge",
        "get_document_indicators",
        "get_decision_evidence",
    }
    abstract = GraphClient.__abstractmethods__
    missing = required - abstract
    assert not missing, f"GraphClient missing abstract methods: {missing}"


def test_graph_client_method_signatures() -> None:
    """Signatures must match the spec § 4.6 so implementations align."""
    sig_get_indicators = inspect.signature(GraphClient.get_document_indicators)
    params = list(sig_get_indicators.parameters.keys())
    assert params == ["self", "doc_id"], params

    sig_get_evidence = inspect.signature(GraphClient.get_decision_evidence)
    params = list(sig_get_evidence.parameters.keys())
    assert params == ["self", "decision_id"], params
