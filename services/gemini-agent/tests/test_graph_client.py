"""Tests for graph client implementations."""

from __future__ import annotations

from gemini_agent.rag.graph_client import (
    AmendmentEdge,
    ClauseNode,
    CrossReference,
    RegulationNode,
)


class TestDataClasses:
    """Test that data classes are properly defined."""

    def test_regulation_node(self):
        node = RegulationNode(
            id="POJK-33-2014",
            title="POJK tentang Direksi dan Dewan Komisaris",
            issuer="OJK",
            effective_date="2014-12-01",
            status="active",
            authority_level=4,
        )
        assert node.id == "POJK-33-2014"
        assert node.authority_level == 4

    def test_clause_node(self):
        node = ClauseNode(
            id="POJK-33-2014-P15",
            regulation_id="POJK-33-2014",
            clause_number="Pasal 15",
            text_summary="Kuorum rapat direksi",
            domain="quorum",
        )
        assert node.domain == "quorum"

    def test_amendment_edge(self):
        edge = AmendmentEdge(
            source_id="POJK-18-2023",
            target_id="POJK-33-2014",
            effective_date="2024-01-01",
            change_type="partial",
        )
        assert edge.change_type == "partial"

    def test_cross_reference(self):
        ref = CrossReference(
            source_clause_id="POJK-33-P15",
            target_clause_id="UUPT-40-P86",
            reference_type="citation",
        )
        assert ref.reference_type == "citation"
