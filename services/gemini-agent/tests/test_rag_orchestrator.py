"""Tests for the hybrid RAG orchestrator."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from gemini_agent.rag.graph_client import (
    AmendmentEdge,
    GraphClient,
    RegulationNode,
)
from gemini_agent.rag.orchestrator import get_graph_client


class MockGraphClient(GraphClient):
    """In-memory graph client for testing."""

    async def query_related_regulations(
        self, regulation_id: str
    ) -> list[RegulationNode]:
        if regulation_id == "POJK-33-2014":
            return [
                RegulationNode(
                    id="POJK-18-2023",
                    title="Amandemen POJK 33",
                    issuer="OJK",
                    effective_date="2024-01-01",
                    status="active",
                    authority_level=4,
                )
            ]
        return []

    async def get_amendment_chain(
        self, regulation_id: str
    ) -> list[AmendmentEdge]:
        if regulation_id == "POJK-33-2014":
            return [
                AmendmentEdge(
                    source_id="POJK-18-2023",
                    target_id="POJK-33-2014",
                    effective_date="2024-01-01",
                    change_type="partial",
                )
            ]
        return []

    async def find_cross_references(self, clause_id: str) -> list:
        return []

    async def get_regulations_by_domain(
        self, domain: str
    ) -> list[RegulationNode]:
        if domain == "quorum":
            return [
                RegulationNode(
                    id="UUPT-40-2007",
                    title="UU Perseroan Terbatas",
                    issuer="UUPT",
                    effective_date="2007-08-16",
                    status="active",
                    authority_level=5,
                )
            ]
        return []

    async def check_active_status(self, regulation_id: str) -> bool:
        return regulation_id != "POJK-OLD-SUPERSEDED"


def test_get_graph_client_disabled():
    """When GRAPH_BACKEND is disabled, returns None."""
    with patch.dict("os.environ", {"GRAPH_BACKEND": "none"}):
        client = get_graph_client()
        assert client is None


def test_get_graph_client_spanner():
    """When GRAPH_BACKEND is spanner, returns SpannerGraphClient."""
    with patch.dict(
        "os.environ",
        {
            "GRAPH_BACKEND": "spanner",
            "GCP_PROJECT": "test",
            "SPANNER_INSTANCE": "test-instance",
            "SPANNER_DATABASE": "test-db",
        },
    ):
        client = get_graph_client()
        assert client is not None
        assert "Spanner" in type(client).__name__


@pytest.mark.asyncio
async def test_mock_graph_client_amendment_chain():
    """Test that MockGraphClient returns amendment chain."""
    client = MockGraphClient()
    chain = await client.get_amendment_chain("POJK-33-2014")
    assert len(chain) == 1
    assert chain[0].source_id == "POJK-18-2023"


@pytest.mark.asyncio
async def test_mock_graph_client_domain_lookup():
    """Test domain-based regulation lookup."""
    client = MockGraphClient()
    regs = await client.get_regulations_by_domain("quorum")
    assert len(regs) == 1
    assert regs[0].authority_level == 5


@pytest.mark.asyncio
async def test_mock_graph_client_active_status():
    """Test active status check."""
    client = MockGraphClient()
    assert await client.check_active_status("POJK-33-2014") is True
    assert await client.check_active_status("POJK-OLD-SUPERSEDED") is False
