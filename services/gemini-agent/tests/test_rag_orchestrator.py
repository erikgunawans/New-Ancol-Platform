"""Tests for the hybrid RAG orchestrator."""

from __future__ import annotations

import importlib.util
from unittest.mock import patch

import pytest
from ancol_common.rag.graph_client import (
    AmendmentEdge,
    ContractNode,
    GraphClient,
    RegulationNode,
)
from gemini_agent.rag.orchestrator import get_graph_client


class MockGraphClient(GraphClient):
    """In-memory graph client for testing."""

    async def query_related_regulations(self, regulation_id: str) -> list[RegulationNode]:
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

    async def get_amendment_chain(self, regulation_id: str) -> list[AmendmentEdge]:
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

    async def get_regulations_by_domain(self, domain: str) -> list[RegulationNode]:
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

    async def get_related_regulations_for_contract(self, contract_id: str) -> list:
        if contract_id == "contract-001":
            return [
                RegulationNode(
                    id="POJK-27-2016",
                    title="POJK tentang Perjanjian Perseroan",
                    issuer="OJK",
                    effective_date="2016-07-01",
                    status="active",
                    authority_level=4,
                )
            ]
        return []

    async def get_related_contracts(self, contract_id: str) -> list:
        if contract_id == "contract-001":
            return [
                ContractNode(
                    id="contract-002",
                    title="Amendment to Contract 001",
                    contract_type="amendment",
                    status="active",
                )
            ]
        return []


def test_get_graph_client_disabled():
    """When GRAPH_BACKEND is disabled, returns None."""
    with patch.dict("os.environ", {"GRAPH_BACKEND": "none"}):
        client = get_graph_client()
        assert client is None


@pytest.mark.skipif(
    not importlib.util.find_spec("google.cloud.spanner"),
    reason="google-cloud-spanner not installed",
)
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


@pytest.mark.skipif(
    not importlib.util.find_spec("neo4j"),
    reason="neo4j driver not installed",
)
def test_get_graph_client_neo4j():
    """When GRAPH_BACKEND is neo4j, returns Neo4jGraphClient."""
    with patch.dict(
        "os.environ",
        {
            "GRAPH_BACKEND": "neo4j",
            "NEO4J_URI": "bolt://localhost:7687",
            "NEO4J_USER": "neo4j",
            "NEO4J_PASSWORD": "test",
        },
    ):
        client = get_graph_client()
        assert client is not None
        assert "Neo4j" in type(client).__name__


@pytest.mark.asyncio
async def test_mock_graph_client_contract_regulations():
    """Test that MockGraphClient returns contract-linked regulations."""
    client = MockGraphClient()
    regs = await client.get_related_regulations_for_contract("contract-001")
    assert len(regs) == 1
    assert regs[0].id == "POJK-27-2016"


@pytest.mark.asyncio
async def test_mock_graph_client_contract_regulations_empty():
    """Unknown contract returns empty."""
    client = MockGraphClient()
    regs = await client.get_related_regulations_for_contract("unknown")
    assert regs == []


@pytest.mark.asyncio
async def test_mock_graph_client_related_contracts():
    """Test that MockGraphClient returns amendment chain."""
    client = MockGraphClient()
    contracts = await client.get_related_contracts("contract-001")
    assert len(contracts) == 1
    assert contracts[0].contract_type == "amendment"
