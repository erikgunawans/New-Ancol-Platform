"""Tests for the smart drafting assembly engine."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from ancol_common.schemas.contract import ContractParty
from ancol_common.schemas.drafting import DraftRequest


def _make_mock_template(contract_type="vendor"):
    """Create a mock ContractTemplate."""
    tmpl = MagicMock()
    tmpl.contract_type = contract_type
    tmpl.required_clauses = ["scope", "payment_terms", "governing_law"]
    tmpl.optional_clauses = ["force_majeure", "confidentiality"]
    tmpl.default_terms = {"payment_days": 30}
    return tmpl


def _make_mock_clause(category, title_id, text_id, is_mandatory=True):
    """Create a mock ClauseLibrary entry."""
    clause = MagicMock()
    clause.clause_category = category
    clause.title_id = title_id
    clause.title_en = title_id  # same for simplicity
    clause.text_id = text_id
    clause.text_en = text_id
    clause.risk_notes = f"Risk notes for {category}"
    clause.is_mandatory = is_mandatory
    clause.version = 1
    clause.id = f"clause-{category}"
    return clause


MOCK_CLAUSES = [
    _make_mock_clause(
        "scope",
        "Ruang Lingkup",
        "Penyedia setuju menyediakan layanan untuk {{party_principal}}.",
    ),
    _make_mock_clause(
        "payment_terms",
        "Pembayaran",
        "Pembayaran dalam {{payment_days}} hari.",
    ),
    _make_mock_clause("governing_law", "Hukum yang Berlaku", "Tunduk pada hukum RI."),
    _make_mock_clause(
        "force_majeure",
        "Keadaan Kahar",
        "Tidak bertanggung jawab atas keadaan kahar.",
        False,
    ),
    _make_mock_clause("confidentiality", "Kerahasiaan", "Wajib menjaga kerahasiaan.", False),
]


def _make_draft_request(**kwargs):
    defaults = {
        "contract_type": "vendor",
        "parties": [
            ContractParty(name="PT Ancol Tbk", role="principal", entity_type="internal"),
            ContractParty(name="PT Vendor", role="counterparty", entity_type="external"),
        ],
        "key_terms": {"payment_days": "30"},
        "language": "id",
    }
    defaults.update(kwargs)
    return DraftRequest(**defaults)


@pytest.fixture
def mock_deps():
    """Mock repository and Gemini dependencies."""
    with (
        patch("ancol_common.drafting.engine.get_contract_template") as mock_tmpl,
        patch("ancol_common.drafting.engine.get_clauses_for_template") as mock_clauses,
        patch("ancol_common.drafting.engine._get_ai_recommendations") as mock_ai,
    ):
        mock_tmpl.return_value = _make_mock_template()
        mock_clauses.return_value = MOCK_CLAUSES
        mock_ai.return_value = {"recommended_optional_clauses": [], "consistency_notes": []}
        yield {
            "template": mock_tmpl,
            "clauses": mock_clauses,
            "ai": mock_ai,
        }


class TestDraftAssembly:
    """Test the draft assembly engine."""

    @pytest.mark.asyncio
    async def test_template_lookup(self, mock_deps):
        from ancol_common.drafting.engine import assemble_draft

        session = AsyncMock()
        request = _make_draft_request()
        await assemble_draft(session, request)

        mock_deps["template"].assert_called_once_with(session, "vendor")

    @pytest.mark.asyncio
    async def test_required_clauses_assembled(self, mock_deps):
        from ancol_common.drafting.engine import assemble_draft

        session = AsyncMock()
        request = _make_draft_request()
        result = await assemble_draft(session, request)

        # Should have 3 required clauses
        assert len(result.clauses) == 3
        categories = [c.category for c in result.clauses]
        assert "scope" in categories
        assert "payment_terms" in categories
        assert "governing_law" in categories

    @pytest.mark.asyncio
    async def test_variable_substitution(self, mock_deps):
        from ancol_common.drafting.engine import assemble_draft

        session = AsyncMock()
        request = _make_draft_request()
        result = await assemble_draft(session, request)

        scope_clause = next(c for c in result.clauses if c.category == "scope")
        assert "PT Ancol Tbk" in scope_clause.text
        assert "{{party_principal}}" not in scope_clause.text

        payment_clause = next(c for c in result.clauses if c.category == "payment_terms")
        assert "30" in payment_clause.text
        assert "{{payment_days}}" not in payment_clause.text

    @pytest.mark.asyncio
    async def test_missing_template_raises(self, mock_deps):
        from ancol_common.drafting.engine import assemble_draft

        mock_deps["template"].return_value = None
        session = AsyncMock()
        request = _make_draft_request()

        with pytest.raises(ValueError, match="No active template"):
            await assemble_draft(session, request)

    @pytest.mark.asyncio
    async def test_clause_override(self, mock_deps):
        from ancol_common.drafting.engine import assemble_draft

        session = AsyncMock()
        request = _make_draft_request(
            clause_overrides=[
                {"category": "scope", "title": "Custom Scope", "text": "Custom scope text here."},
            ]
        )
        result = await assemble_draft(session, request)

        scope_clause = next(c for c in result.clauses if c.category == "scope")
        assert scope_clause.text == "Custom scope text here."
        assert scope_clause.is_from_library is False

    @pytest.mark.asyncio
    async def test_draft_output_has_text(self, mock_deps):
        from ancol_common.drafting.engine import assemble_draft

        session = AsyncMock()
        request = _make_draft_request()
        result = await assemble_draft(session, request)

        assert result.draft_text
        assert "PERJANJIAN PENYEDIAAN JASA" in result.draft_text
        assert "PT Ancol Tbk" in result.draft_text

    @pytest.mark.asyncio
    async def test_risk_assessment_from_library(self, mock_deps):
        from ancol_common.drafting.engine import assemble_draft

        session = AsyncMock()
        request = _make_draft_request()
        result = await assemble_draft(session, request)

        assert len(result.risk_assessment) >= 1
        categories_with_notes = [
            r.get("category") for r in result.risk_assessment if r.get("category")
        ]
        assert "scope" in categories_with_notes

    @pytest.mark.asyncio
    async def test_empty_key_terms_still_works(self, mock_deps):
        from ancol_common.drafting.engine import assemble_draft

        session = AsyncMock()
        request = _make_draft_request(key_terms={})
        result = await assemble_draft(session, request)

        # Should still produce a draft, placeholders remain
        assert result.draft_text
        assert len(result.clauses) == 3
