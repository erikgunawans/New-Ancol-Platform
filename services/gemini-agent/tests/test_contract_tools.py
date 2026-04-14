"""Tests for CLM Gemini tool handlers (contracts, obligations, drafting, Q&A)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from gemini_agent.tools.contract_qa import handle_ask_contract_question
from gemini_agent.tools.contracts import (
    handle_check_contract_status,
    handle_get_contract_portfolio,
    handle_upload_contract,
)
from gemini_agent.tools.drafting import handle_generate_draft
from gemini_agent.tools.obligations import (
    handle_fulfill_obligation,
    handle_list_obligations,
)


def _mock_user():
    return {"id": "u-001", "email": "legal@ancol.co.id", "role": "legal_compliance"}


def _mock_api():
    api = AsyncMock()
    api.upload_contract = AsyncMock(return_value={
        "id": "c-001", "title": "NDA PT XYZ", "status": "draft",
        "contract_type": "nda", "contract_number": None,
        "effective_date": None, "expiry_date": None,
        "total_value": None, "currency": "IDR",
        "risk_level": None, "risk_score": None,
        "page_count": None, "created_at": "2026-04-14", "updated_at": "2026-04-14",
    })
    api.get_contract = AsyncMock(return_value={
        "id": "c-001", "title": "NDA PT XYZ", "status": "active",
        "contract_type": "nda", "contract_number": "NDA-2026-001",
        "effective_date": "2026-01-01", "expiry_date": "2027-01-01",
        "total_value": 500000000, "currency": "IDR",
        "risk_level": "low", "risk_score": 25.0,
        "page_count": 12, "created_at": "2026-01-01", "updated_at": "2026-04-14",
    })
    api.list_contracts = AsyncMock(return_value={
        "contracts": [
            {"id": "c-001", "title": "NDA PT XYZ", "status": "active", "contract_type": "nda"},
            {
                "id": "c-002", "title": "Sewa Tanah Ancol",
                "status": "expiring", "contract_type": "land_lease",
            },
        ],
        "total": 2,
    })
    api.get_contract_clauses = AsyncMock(return_value={
        "contract_id": "c-001", "clauses": [],
    })
    api.get_contract_risk = AsyncMock(return_value={
        "contract_id": "c-001", "risk_level": "low", "risk_score": 25.0,
        "extraction_data": {},
    })
    api.list_obligations = AsyncMock(return_value={
        "obligations": [
            {
                "id": "ob-001", "contract_id": "c-001",
                "obligation_type": "renewal", "description": "Perpanjangan NDA",
                "due_date": "2026-12-01", "status": "upcoming",
                "responsible_party_name": "Legal",
            },
        ],
        "total": 1,
    })
    api.get_upcoming_obligations = AsyncMock(return_value={
        "upcoming": [], "total": 0, "within_days": 30,
    })
    api.fulfill_obligation = AsyncMock(return_value={
        "obligation_id": "ob-001", "status": "fulfilled",
    })
    api.generate_draft = AsyncMock(return_value={
        "status": "stub",
        "message": "Draft generation will be powered by Gemini in Phase 2.",
        "contract_type": "vendor",
        "key_terms": {},
    })
    return api


# -- Upload contract --

@pytest.mark.asyncio
async def test_upload_contract_no_file():
    result = await handle_upload_contract({}, _mock_api(), _mock_user())
    assert "Tidak ada file" in result


@pytest.mark.asyncio
async def test_upload_contract_success():
    api = _mock_api()
    params = {
        "file_bytes": b"fake-pdf-content",
        "filename": "NDA-XYZ.pdf",
        "title": "NDA PT XYZ",
        "contract_type": "nda",
    }
    result = await handle_upload_contract(params, api, _mock_user())
    assert "berhasil diunggah" in result
    api.upload_contract.assert_called_once()


# -- Check contract status --

@pytest.mark.asyncio
async def test_check_contract_status_no_id():
    result = await handle_check_contract_status({}, _mock_api(), _mock_user())
    assert "contract_id" in result


@pytest.mark.asyncio
async def test_check_contract_status_success():
    api = _mock_api()
    result = await handle_check_contract_status(
        {"contract_id": "c-001"}, api, _mock_user()
    )
    assert "NDA PT XYZ" in result
    assert "Aktif" in result


# -- Portfolio --

@pytest.mark.asyncio
async def test_get_contract_portfolio():
    api = _mock_api()
    result = await handle_get_contract_portfolio({}, api, _mock_user())
    assert "Portfolio Kontrak" in result
    assert "2 kontrak" in result


# -- Obligations --

@pytest.mark.asyncio
async def test_list_obligations():
    api = _mock_api()
    result = await handle_list_obligations({}, api, _mock_user())
    assert "Kewajiban Kontrak" in result
    assert "Perpanjangan NDA" in result


@pytest.mark.asyncio
async def test_list_obligations_upcoming():
    api = _mock_api()
    result = await handle_list_obligations(
        {"upcoming_only": True}, api, _mock_user()
    )
    assert "Tidak ada kewajiban" in result


@pytest.mark.asyncio
async def test_fulfill_obligation_no_id():
    result = await handle_fulfill_obligation({}, _mock_api(), _mock_user())
    assert "obligation_id" in result


@pytest.mark.asyncio
async def test_fulfill_obligation_success():
    api = _mock_api()
    result = await handle_fulfill_obligation(
        {"obligation_id": "ob-001"}, api, _mock_user()
    )
    assert "terpenuhi" in result


# -- Drafting --

@pytest.mark.asyncio
async def test_generate_draft_stub():
    api = _mock_api()
    result = await handle_generate_draft(
        {"contract_type": "vendor", "parties": []}, api, _mock_user()
    )
    assert "Phase 2" in result


# -- Contract Q&A --

@pytest.mark.asyncio
async def test_ask_contract_question_no_question():
    result = await handle_ask_contract_question({}, _mock_api(), _mock_user())
    assert "pertanyaan" in result.lower()


@pytest.mark.asyncio
async def test_ask_contract_question_stub():
    api = _mock_api()
    result = await handle_ask_contract_question(
        {"question": "Kapan kontrak NDA berakhir?"}, api, _mock_user()
    )
    assert "Phase 2" in result
    assert "Kapan kontrak NDA berakhir?" in result


@pytest.mark.asyncio
async def test_ask_contract_question_with_context():
    api = _mock_api()
    result = await handle_ask_contract_question(
        {"question": "Apa risiko kontrak ini?", "contract_id": "c-001"},
        api, _mock_user(),
    )
    assert "NDA PT XYZ" in result
