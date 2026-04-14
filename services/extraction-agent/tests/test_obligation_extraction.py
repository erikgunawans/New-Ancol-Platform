"""Tests for obligation auto-extraction during contract parsing."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest


def _make_gemini_response(extracted: dict) -> MagicMock:
    response = MagicMock()
    response.text = json.dumps(extracted)
    response.usage_metadata = MagicMock()
    response.usage_metadata.prompt_token_count = 100
    response.usage_metadata.candidates_token_count = 200
    return response


BASE_EXTRACTION = {
    "clauses": [
        {
            "clause_number": "Pasal 1",
            "title": "Scope",
            "text": "Services provided.",
            "category": "scope",
            "risk_level": "low",
            "risk_reason": "Standard",
            "confidence": 0.9,
        }
    ],
    "parties": [
        {"name": "PT Ancol", "role": "principal", "entity_type": "internal"},
    ],
    "key_dates": {},
    "financial_terms": {},
    "risk_summary": {
        "overall_risk_level": "low",
        "overall_risk_score": 20,
        "top_risks": [],
    },
    "obligations": [],
    "applicable_regulations": [],
}


@pytest.fixture
def mock_gemini():
    with (
        patch("extraction_agent.contract_parser.get_gemini_client") as mock_client,
        patch(
            "extraction_agent.contract_parser.get_pro_model",
            return_value="gemini-2.5-pro",
        ),
    ):
        client_instance = MagicMock()
        mock_client.return_value = client_instance
        yield client_instance


class TestObligationExtraction:
    """Test obligation extraction from contract text."""

    @pytest.mark.asyncio
    async def test_renewal_obligation(self, mock_gemini):
        data = {
            **BASE_EXTRACTION,
            "obligations": [
                {
                    "obligation_type": "renewal",
                    "description": "Contract renewal opt-out notice",
                    "due_date": "2027-11-30",
                    "recurrence": "annual",
                    "responsible_party": "PT Ancol",
                }
            ],
        }
        mock_gemini.models.generate_content.return_value = _make_gemini_response(data)

        from extraction_agent.contract_parser import extract_contract

        result = await extract_contract("text", "c-1", "vendor")
        assert len(result.obligations) == 1
        assert result.obligations[0].obligation_type == "renewal"
        assert result.obligations[0].recurrence == "annual"

    @pytest.mark.asyncio
    async def test_payment_obligation_with_date(self, mock_gemini):
        data = {
            **BASE_EXTRACTION,
            "obligations": [
                {
                    "obligation_type": "payment",
                    "description": "Monthly service fee",
                    "due_date": "2026-05-01",
                    "recurrence": "monthly",
                    "responsible_party": "PT Ancol",
                }
            ],
        }
        mock_gemini.models.generate_content.return_value = _make_gemini_response(data)

        from extraction_agent.contract_parser import extract_contract

        result = await extract_contract("text", "c-1", "vendor")
        assert result.obligations[0].due_date.isoformat() == "2026-05-01"

    @pytest.mark.asyncio
    async def test_no_obligations_from_nda(self, mock_gemini):
        data = {**BASE_EXTRACTION, "obligations": []}
        mock_gemini.models.generate_content.return_value = _make_gemini_response(data)

        from extraction_agent.contract_parser import extract_contract

        result = await extract_contract("text", "c-1", "nda")
        assert len(result.obligations) == 0

    @pytest.mark.asyncio
    async def test_multiple_obligations(self, mock_gemini):
        data = {
            **BASE_EXTRACTION,
            "obligations": [
                {
                    "obligation_type": "payment",
                    "description": "Quarterly payment",
                    "due_date": "2026-06-30",
                    "recurrence": "quarterly",
                    "responsible_party": "PT Ancol",
                },
                {
                    "obligation_type": "reporting",
                    "description": "Annual audit report",
                    "due_date": "2027-01-31",
                    "recurrence": "annual",
                    "responsible_party": "PT Vendor",
                },
                {
                    "obligation_type": "termination_notice",
                    "description": "30-day termination notice",
                    "due_date": "2027-11-01",
                    "recurrence": None,
                    "responsible_party": "PT Ancol",
                },
            ],
        }
        mock_gemini.models.generate_content.return_value = _make_gemini_response(data)

        from extraction_agent.contract_parser import extract_contract

        result = await extract_contract("text", "c-1", "vendor")
        assert len(result.obligations) == 3
        types = {o.obligation_type for o in result.obligations}
        assert types == {"payment", "reporting", "termination_notice"}

    @pytest.mark.asyncio
    async def test_missing_due_date_handled(self, mock_gemini):
        data = {
            **BASE_EXTRACTION,
            "obligations": [
                {
                    "obligation_type": "deliverable",
                    "description": "Project deliverable",
                    "due_date": None,
                    "recurrence": None,
                    "responsible_party": "PT Vendor",
                }
            ],
        }
        mock_gemini.models.generate_content.return_value = _make_gemini_response(data)

        from extraction_agent.contract_parser import extract_contract

        result = await extract_contract("text", "c-1", "vendor")
        assert result.obligations[0].due_date is None

    @pytest.mark.asyncio
    async def test_applicable_regulations_extracted(self, mock_gemini):
        data = {
            **BASE_EXTRACTION,
            "applicable_regulations": [
                {
                    "regulation_id": "UU 40/2007",
                    "relevance": "Company law applies to all PT entities",
                },
                {
                    "regulation_id": "POJK 23/2023",
                    "relevance": "Public company disclosure requirements",
                },
            ],
        }
        mock_gemini.models.generate_content.return_value = _make_gemini_response(data)

        from extraction_agent.contract_parser import extract_contract

        result = await extract_contract("text", "c-1", "vendor")
        assert len(result.applicable_regulations) == 2
        assert result.applicable_regulations[0].regulation_id == "UU 40/2007"
