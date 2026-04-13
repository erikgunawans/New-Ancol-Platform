"""Tests for WhatsApp notification module."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from ancol_common.notifications.whatsapp import (
    send_approval_request,
    send_notification,
    send_obligation_reminder,
)


@pytest.mark.asyncio
async def test_send_notification_no_config():
    """When WhatsApp is not configured, returns False without error."""
    with patch("ancol_common.notifications.whatsapp.get_settings") as mock:
        mock.return_value.whatsapp_api_token = ""
        mock.return_value.whatsapp_api_url = ""
        result = await send_notification("+628123456789", "test_template", {})
        assert result is False


@pytest.mark.asyncio
async def test_send_notification_success():
    """When configured, sends HTTP POST and returns True."""
    with (
        patch("ancol_common.notifications.whatsapp.get_settings") as mock_settings,
        patch("ancol_common.notifications.whatsapp.httpx.AsyncClient") as mock_client_cls,
    ):
        mock_settings.return_value.whatsapp_api_token = "test-token"
        mock_settings.return_value.whatsapp_api_url = "https://api.twilio.com/test"

        mock_response = AsyncMock()
        mock_response.raise_for_status = lambda: None

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await send_notification(
            "+628123456789", "obligation_reminder", {"due_date": "2026-12-01"}
        )
        assert result is True
        mock_client.post.assert_called_once()


@pytest.mark.asyncio
async def test_send_obligation_reminder_builds_deep_link():
    """Obligation reminder includes contract title and deep link."""
    mock_path = "ancol_common.notifications.whatsapp.send_notification"
    with patch(mock_path, new_callable=AsyncMock) as mock_send:
        mock_send.return_value = True
        result = await send_obligation_reminder(
            to_phone="+628123456789",
            contract_title="NDA PT XYZ",
            due_date="2026-12-01",
            obligation_id="ob-001",
        )
        assert result is True
        call_args = mock_send.call_args
        assert call_args[1]["template_id"] == "obligation_reminder"
        assert "NDA PT XYZ" in call_args[1]["template_params"]["contract_title"]
        assert "ob-001" in call_args[1]["template_params"]["deep_link"]


@pytest.mark.asyncio
async def test_send_approval_request_builds_deep_link():
    """Approval request includes document title and deep link."""
    mock_path = "ancol_common.notifications.whatsapp.send_notification"
    with patch(mock_path, new_callable=AsyncMock) as mock_send:
        mock_send.return_value = True
        result = await send_approval_request(
            to_phone="+628123456789",
            document_title="Kontrak Sewa Tanah",
            document_type="Kontrak",
            document_id="c-001",
        )
        assert result is True
        call_args = mock_send.call_args
        assert call_args[1]["template_id"] == "approval_request"
        assert "c-001" in call_args[1]["template_params"]["deep_link"]
