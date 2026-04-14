"""Tests for contract and drafting Pydantic schemas."""

from __future__ import annotations

from ancol_common.schemas.contract import (
    ContractClause,
    ContractExtractionOutput,
    ContractMetadata,
    ContractParty,
    ContractStatus,
    ContractType,
    RiskLevel,
)
from ancol_common.schemas.drafting import (
    ClauseLibraryEntry,
    DraftOutput,
    DraftRequest,
)
from ancol_common.schemas.mom import ProcessingMetadata, UserRole


class TestContractEnums:
    def test_contract_type_values(self):
        assert ContractType.NDA == "nda"
        assert ContractType.VENDOR == "vendor"
        assert ContractType.LAND_LEASE == "land_lease"
        assert len(ContractType) == 7

    def test_contract_status_values(self):
        assert ContractStatus.DRAFT == "draft"
        assert ContractStatus.ACTIVE == "active"
        assert ContractStatus.EXPIRED == "expired"
        assert ContractStatus.FAILED == "failed"
        assert len(ContractStatus) == 11

    def test_risk_level_values(self):
        assert RiskLevel.HIGH == "high"
        assert RiskLevel.MEDIUM == "medium"
        assert RiskLevel.LOW == "low"
        assert len(RiskLevel) == 3

    def test_new_user_roles_exist(self):
        assert UserRole.CONTRACT_MANAGER == "contract_manager"
        assert UserRole.BUSINESS_DEV == "business_dev"
        assert len(UserRole) == 7


class TestContractSchemas:
    def test_contract_party_minimal(self):
        party = ContractParty(
            name="PT Ancol",
            role="principal",
            entity_type="internal",
        )
        assert party.related_party_entity_id is None
        assert party.contact_email is None

    def test_contract_clause_with_risk(self):
        clause = ContractClause(
            clause_number="3.1",
            title="Indemnification",
            text="Party A shall indemnify...",
            category="indemnification",
            risk_level=RiskLevel.HIGH,
            risk_reason="Unlimited liability exposure",
            confidence=0.92,
        )
        assert clause.risk_level == "high"
        assert clause.confidence == 0.92

    def test_contract_metadata_defaults(self):
        meta = ContractMetadata(
            id="test-1",
            title="NDA with PT XYZ",
            contract_type=ContractType.NDA,
            status=ContractStatus.DRAFT,
        )
        assert meta.currency == "IDR"
        assert meta.total_value is None
        assert meta.risk_level is None

    def test_contract_extraction_output(self):
        output = ContractExtractionOutput(
            contract_id="test-1",
            processing_metadata=ProcessingMetadata(
                agent_version="0.1.0",
                model_used="gemini-2.5-flash",
            ),
        )
        assert output.clauses == []
        assert output.parties == []
        assert output.key_dates == {}


class TestDraftingSchemas:
    def test_clause_library_entry(self):
        entry = ClauseLibraryEntry(
            id="cl-1",
            contract_type=ContractType.NDA,
            clause_category="confidentiality",
            title_id="Kerahasiaan",
            text_id="Para pihak wajib menjaga kerahasiaan...",
        )
        assert entry.is_mandatory is False
        assert entry.version == 1
        assert entry.title_en is None

    def test_draft_request_defaults(self):
        req = DraftRequest(
            contract_type=ContractType.VENDOR,
            parties=[
                ContractParty(name="PT Ancol", role="principal", entity_type="internal"),
            ],
        )
        assert req.language == "id"
        assert req.key_terms == {}
        assert req.clause_overrides == []

    def test_draft_output(self):
        output = DraftOutput(
            contract_id="test-1",
            draft_text="Draft kontrak vendor...",
        )
        assert output.clauses == []
        assert output.risk_assessment == []
        assert output.gcs_draft_uri is None
