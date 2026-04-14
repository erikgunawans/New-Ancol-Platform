"""Tests for contract clause extraction logic."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from ancol_common.schemas.contract import ContractExtractionOutput, RiskLevel


def _make_gemini_response(extracted: dict) -> MagicMock:
    """Create a mock Gemini response with the given extracted data."""
    response = MagicMock()
    response.text = json.dumps(extracted)
    response.usage_metadata = MagicMock()
    response.usage_metadata.prompt_token_count = 100
    response.usage_metadata.candidates_token_count = 200
    return response


SAMPLE_EXTRACTION = {
    "clauses": [
        {
            "clause_number": "Pasal 1",
            "title": "Ruang Lingkup Pekerjaan",
            "text": "Penyedia Jasa setuju untuk menyediakan layanan IT.",
            "category": "scope",
            "risk_level": "low",
            "risk_reason": "Standard scope clause",
            "confidence": 0.95,
        },
        {
            "clause_number": "Pasal 2",
            "title": "Ketentuan Pembayaran",
            "text": "Pembayaran dilakukan dalam 30 hari.",
            "category": "payment_terms",
            "risk_level": "low",
            "risk_reason": "Standard NET 30 terms",
            "confidence": 0.92,
        },
        {
            "clause_number": "Pasal 5",
            "title": "Tanggung Jawab",
            "text": "Tidak ada batasan tanggung jawab.",
            "category": "liability",
            "risk_level": "high",
            "risk_reason": "Unlimited liability — missing liability cap",
            "confidence": 0.88,
        },
    ],
    "parties": [
        {"name": "PT Ancol Tbk", "role": "principal", "entity_type": "internal"},
        {"name": "PT Vendor Indonesia", "role": "counterparty", "entity_type": "external"},
    ],
    "key_dates": {
        "effective_date": "2026-01-01",
        "expiry_date": "2027-12-31",
        "renewal_deadline": None,
    },
    "financial_terms": {
        "total_value": 500000000,
        "currency": "IDR",
        "payment_schedule": "NET 30",
    },
    "risk_summary": {
        "overall_risk_level": "medium",
        "overall_risk_score": 45.0,
        "top_risks": ["Unlimited liability in Pasal 5"],
    },
}


@pytest.fixture
def mock_gemini():
    """Patch Gemini client to return controlled responses."""
    with (
        patch("extraction_agent.contract_parser.get_gemini_client") as mock_client,
        patch("extraction_agent.contract_parser.get_pro_model", return_value="gemini-2.5-pro"),
    ):
        client_instance = MagicMock()
        mock_client.return_value = client_instance
        yield client_instance


class TestContractExtraction:
    """Test contract clause extraction via mocked Gemini."""

    @pytest.mark.asyncio
    async def test_basic_clause_extraction(self, mock_gemini):
        mock_gemini.models.generate_content.return_value = _make_gemini_response(SAMPLE_EXTRACTION)
        from extraction_agent.contract_parser import extract_contract

        result = await extract_contract("sample ocr text", "contract-1", "vendor")

        assert isinstance(result, ContractExtractionOutput)
        assert result.contract_id == "contract-1"
        assert len(result.clauses) == 3

    @pytest.mark.asyncio
    async def test_party_identification(self, mock_gemini):
        mock_gemini.models.generate_content.return_value = _make_gemini_response(SAMPLE_EXTRACTION)
        from extraction_agent.contract_parser import extract_contract

        result = await extract_contract("text", "c-1", "vendor")

        assert len(result.parties) == 2
        assert result.parties[0].name == "PT Ancol Tbk"
        assert result.parties[0].role == "principal"
        assert result.parties[1].entity_type == "external"

    @pytest.mark.asyncio
    async def test_risk_scoring_high(self, mock_gemini):
        mock_gemini.models.generate_content.return_value = _make_gemini_response(SAMPLE_EXTRACTION)
        from extraction_agent.contract_parser import extract_contract

        result = await extract_contract("text", "c-1", "vendor")

        high_risk = [c for c in result.clauses if c.risk_level == RiskLevel.HIGH]
        assert len(high_risk) == 1
        assert "liability" in high_risk[0].category

    @pytest.mark.asyncio
    async def test_risk_scoring_low(self, mock_gemini):
        mock_gemini.models.generate_content.return_value = _make_gemini_response(SAMPLE_EXTRACTION)
        from extraction_agent.contract_parser import extract_contract

        result = await extract_contract("text", "c-1", "vendor")

        low_risk = [c for c in result.clauses if c.risk_level == RiskLevel.LOW]
        assert len(low_risk) == 2

    @pytest.mark.asyncio
    async def test_key_date_extraction(self, mock_gemini):
        mock_gemini.models.generate_content.return_value = _make_gemini_response(SAMPLE_EXTRACTION)
        from extraction_agent.contract_parser import extract_contract

        result = await extract_contract("text", "c-1", "vendor")

        assert result.key_dates["effective_date"] == "2026-01-01"
        assert result.key_dates["expiry_date"] == "2027-12-31"

    @pytest.mark.asyncio
    async def test_financial_term_extraction(self, mock_gemini):
        mock_gemini.models.generate_content.return_value = _make_gemini_response(SAMPLE_EXTRACTION)
        from extraction_agent.contract_parser import extract_contract

        result = await extract_contract("text", "c-1", "vendor")

        assert result.financial_terms["total_value"] == 500000000
        assert result.financial_terms["currency"] == "IDR"

    @pytest.mark.asyncio
    async def test_mixed_risk_levels(self, mock_gemini):
        mock_gemini.models.generate_content.return_value = _make_gemini_response(SAMPLE_EXTRACTION)
        from extraction_agent.contract_parser import extract_contract

        result = await extract_contract("text", "c-1", "vendor")

        assert result.risk_summary["overall_risk_level"] == "medium"
        assert result.risk_summary["overall_risk_score"] == 45.0

    @pytest.mark.asyncio
    async def test_empty_text_returns_empty_extraction(self, mock_gemini):
        empty_extraction = {
            "clauses": [],
            "parties": [],
            "key_dates": {},
            "financial_terms": {},
            "risk_summary": {"overall_risk_level": "low", "overall_risk_score": 0, "top_risks": []},
        }
        mock_gemini.models.generate_content.return_value = _make_gemini_response(empty_extraction)
        from extraction_agent.contract_parser import extract_contract

        result = await extract_contract("", "c-1", "vendor")

        assert len(result.clauses) == 0
        assert len(result.parties) == 0

    @pytest.mark.asyncio
    async def test_processing_metadata(self, mock_gemini):
        mock_gemini.models.generate_content.return_value = _make_gemini_response(SAMPLE_EXTRACTION)
        from extraction_agent.contract_parser import extract_contract

        result = await extract_contract("text", "c-1", "vendor")

        assert result.processing_metadata.model_used == "gemini-2.5-pro"
        assert result.processing_metadata.prompt_tokens == 100
        assert result.processing_metadata.processing_time_ms >= 0

    @pytest.mark.asyncio
    async def test_clause_confidence_preserved(self, mock_gemini):
        mock_gemini.models.generate_content.return_value = _make_gemini_response(SAMPLE_EXTRACTION)
        from extraction_agent.contract_parser import extract_contract

        result = await extract_contract("text", "c-1", "vendor")

        assert result.clauses[0].confidence == 0.95
        assert result.clauses[2].confidence == 0.88
