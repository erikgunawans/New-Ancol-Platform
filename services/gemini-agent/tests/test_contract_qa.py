"""Tests for contract Q&A RAG tool handler and orchestrator."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


def _mock_rag_result(answer="Jawaban test", citations=None, regulations=None, related=None):
    return {
        "answer": answer,
        "citations": citations or [],
        "regulations": regulations or [],
        "related_contracts": related or [],
    }


class TestContractQaHandler:
    """Test the contract Q&A tool handler."""

    @pytest.mark.asyncio
    async def test_basic_question_returns_answer(self):
        with patch(
            "gemini_agent.tools.contract_qa.answer_contract_question"
        ) as mock_rag:
            mock_rag.return_value = _mock_rag_result(
                answer="Kontrak vendor memiliki klausul pembayaran NET 30.",
                citations=[
                    {
                        "contract_id": "c-1",
                        "contract_title": "Vendor Agreement",
                        "clause_number": "Pasal 3",
                        "category": "payment_terms",
                        "text_excerpt": "Pembayaran dalam 30 hari",
                        "risk_level": "low",
                    }
                ],
            )

            from gemini_agent.tools.contract_qa import handle_ask_contract_question

            result = await handle_ask_contract_question(
                {"question": "Bagaimana ketentuan pembayaran?"},
                AsyncMock(),
                {"email": "test@ancol.co.id"},
            )

            assert "Jawaban" in result
            assert "Pasal 3" in result

    @pytest.mark.asyncio
    async def test_contract_specific_question(self):
        with patch(
            "gemini_agent.tools.contract_qa.answer_contract_question"
        ) as mock_rag:
            mock_rag.return_value = _mock_rag_result()

            from gemini_agent.tools.contract_qa import handle_ask_contract_question

            await handle_ask_contract_question(
                {"question": "Status kontrak ini?", "contract_id": "c-123"},
                AsyncMock(),
                {"email": "test@ancol.co.id"},
            )

            mock_rag.assert_called_once_with(
                "Status kontrak ini?", "c-123", mock_rag.call_args[0][2]
            )

    @pytest.mark.asyncio
    async def test_empty_question_returns_error(self):
        from gemini_agent.tools.contract_qa import handle_ask_contract_question

        result = await handle_ask_contract_question(
            {"question": ""},
            AsyncMock(),
            {"email": "test@ancol.co.id"},
        )
        assert "Error" in result

    @pytest.mark.asyncio
    async def test_no_results_shows_fallback(self):
        with patch(
            "gemini_agent.tools.contract_qa.answer_contract_question"
        ) as mock_rag:
            mock_rag.return_value = _mock_rag_result(
                answer="Tidak ada informasi yang ditemukan."
            )

            from gemini_agent.tools.contract_qa import handle_ask_contract_question

            result = await handle_ask_contract_question(
                {"question": "Something obscure?"},
                AsyncMock(),
                {"email": "test@ancol.co.id"},
            )

            assert "Tidak ada informasi" in result


class TestContractQaFormatting:
    """Test the response formatter."""

    def test_format_with_citations(self):
        from gemini_agent.formatting import format_contract_qa_response

        result = format_contract_qa_response(
            _mock_rag_result(
                answer="Test answer",
                citations=[
                    {
                        "contract_title": "Vendor ABC",
                        "clause_number": "Pasal 5",
                        "text_excerpt": "excerpt here",
                        "risk_level": "medium",
                    }
                ],
            )
        )
        assert "Sumber" in result
        assert "Pasal 5" in result

    def test_format_with_regulations(self):
        from gemini_agent.formatting import format_contract_qa_response

        result = format_contract_qa_response(
            _mock_rag_result(
                answer="Test",
                regulations=[
                    {"regulation_id": "UU 40/2007", "title": "UUPT"},
                ],
            )
        )
        assert "Regulasi Terkait" in result
        assert "UU 40/2007" in result

    def test_format_with_related_contracts(self):
        from gemini_agent.formatting import format_contract_qa_response

        result = format_contract_qa_response(
            _mock_rag_result(
                answer="Test",
                related=[
                    {
                        "id": "rc-1",
                        "title": "Amendment #1",
                        "contract_type": "vendor",
                    },
                ],
            )
        )
        assert "Kontrak Terkait" in result
        assert "Amendment #1" in result

    def test_format_bahasa_indonesia(self):
        from gemini_agent.formatting import format_contract_qa_response

        result = format_contract_qa_response(_mock_rag_result(answer="Jawaban dalam Bahasa"))
        assert "Jawaban" in result
        assert result.startswith("**Jawaban:**")
