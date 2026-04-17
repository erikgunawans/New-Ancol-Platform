"""Tests for Neo4j AuraDS graph client implementation."""

from __future__ import annotations

import importlib.util
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from gemini_agent.rag.graph_client import ContractNode, RegulationNode

# Skip all tests if neo4j driver is not installed
pytestmark = pytest.mark.skipif(
    not importlib.util.find_spec("neo4j"),
    reason="neo4j driver not installed",
)


def _make_neo4j_client():
    """Create a Neo4jGraphClient with mocked driver."""
    with patch("neo4j.AsyncGraphDatabase") as mock_db:
        mock_driver = MagicMock()
        mock_db.driver.return_value = mock_driver
        from gemini_agent.rag.neo4j_graph import Neo4jGraphClient

        client = Neo4jGraphClient(uri="bolt://test:7687", username="neo4j", password="test")
        return client, mock_driver


class TestNeo4jContractRegulations:
    """Test get_related_regulations_for_contract Cypher query."""

    @pytest.mark.asyncio
    async def test_returns_regulation_nodes(self):
        client, _ = _make_neo4j_client()
        mock_rows = [
            {
                "id": "POJK-33-2014",
                "title": "POJK Direksi",
                "issuer": "OJK",
                "effective_date": "2014-12-01",
                "status": "active",
                "authority_level": 4,
            }
        ]
        with patch.object(client, "_run_query", new_callable=AsyncMock, return_value=mock_rows):
            result = await client.get_related_regulations_for_contract("contract-001")

        assert len(result) == 1
        assert isinstance(result[0], RegulationNode)
        assert result[0].id == "POJK-33-2014"
        assert result[0].authority_level == 4

    @pytest.mark.asyncio
    async def test_empty_result(self):
        client, _ = _make_neo4j_client()
        with patch.object(client, "_run_query", new_callable=AsyncMock, return_value=[]):
            result = await client.get_related_regulations_for_contract("unknown")
        assert result == []

    @pytest.mark.asyncio
    async def test_default_values(self):
        """Missing fields use safe defaults."""
        client, _ = _make_neo4j_client()
        mock_rows = [{"id": "REG-001"}]
        with patch.object(client, "_run_query", new_callable=AsyncMock, return_value=mock_rows):
            result = await client.get_related_regulations_for_contract("contract-001")

        assert result[0].title == ""
        assert result[0].issuer == ""
        assert result[0].status == "active"
        assert result[0].authority_level == 1


class TestNeo4jRelatedContracts:
    """Test get_related_contracts Cypher query."""

    @pytest.mark.asyncio
    async def test_returns_contract_nodes(self):
        client, _ = _make_neo4j_client()
        mock_rows = [
            {
                "id": "contract-002",
                "title": "Amendment",
                "contract_type": "amendment",
                "status": "active",
            }
        ]
        with patch.object(client, "_run_query", new_callable=AsyncMock, return_value=mock_rows):
            result = await client.get_related_contracts("contract-001")

        assert len(result) == 1
        assert isinstance(result[0], ContractNode)
        assert result[0].contract_type == "amendment"

    @pytest.mark.asyncio
    async def test_empty_result(self):
        client, _ = _make_neo4j_client()
        with patch.object(client, "_run_query", new_callable=AsyncMock, return_value=[]):
            result = await client.get_related_contracts("unknown")
        assert result == []

    @pytest.mark.asyncio
    async def test_multiple_hops(self):
        """Amendment chain can return multiple contracts."""
        client, _ = _make_neo4j_client()
        mock_rows = [
            {"id": "c-002", "title": "Amend 1", "contract_type": "amendment", "status": "active"},
            {"id": "c-003", "title": "Renewal", "contract_type": "renewal", "status": "active"},
        ]
        with patch.object(client, "_run_query", new_callable=AsyncMock, return_value=mock_rows):
            result = await client.get_related_contracts("c-001")

        assert len(result) == 2
        assert result[1].contract_type == "renewal"


class TestNeo4jDriverClose:
    """Test async driver cleanup."""

    @pytest.mark.asyncio
    async def test_close_calls_driver_close(self):
        client, mock_driver = _make_neo4j_client()
        mock_driver.close = AsyncMock()
        await client.close()
        mock_driver.close.assert_called_once()


class TestNeo4jImportGuard:
    """Test conditional import behavior."""

    def test_neo4j_available_flag(self):
        from gemini_agent.rag.neo4j_graph import _NEO4J_AVAILABLE

        assert _NEO4J_AVAILABLE is True

    def test_constructor_requires_driver(self):
        """When _NEO4J_AVAILABLE is False, constructor raises RuntimeError."""
        with patch("gemini_agent.rag.neo4j_graph._NEO4J_AVAILABLE", False):
            from gemini_agent.rag.neo4j_graph import Neo4jGraphClient

            with pytest.raises(RuntimeError, match="neo4j driver is not installed"):
                Neo4jGraphClient()
