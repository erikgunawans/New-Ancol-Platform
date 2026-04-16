"""Tests for WhatsApp notification delivery, dispatcher, and user profile."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from ancol_common.auth.rbac import GATE_PERMISSIONS, ROLE_PERMISSIONS
from ancol_common.notifications.dispatcher import (
    VALID_CHANNELS,
    notify_gate_reviewers,
    send_notification,
)
from pydantic import ValidationError


def _make_user(
    *,
    email: str = "test@ancol.co.id",
    display_name: str = "Test User",
    role: str = "corp_secretary",
    phone_number: str | None = None,
    notification_channels: list[str] | None = None,
) -> SimpleNamespace:
    """Create a mock user object."""
    return SimpleNamespace(
        id=uuid4(),
        email=email,
        display_name=display_name,
        role=role,
        phone_number=phone_number,
        notification_channels=notification_channels or ["email", "in_app"],
        is_active=True,
    )


class TestNotificationDispatcher:
    """Test unified notification dispatcher routing."""

    @pytest.mark.asyncio
    async def test_dispatch_email_only(self):
        """Default channels (email + in_app) should send both."""
        user = _make_user(notification_channels=["email", "in_app"])
        session = AsyncMock()

        with (
            patch(
                "ancol_common.notifications.dispatcher.create_in_app_notification",
                new_callable=AsyncMock,
                return_value="notif-1",
            ) as mock_in_app,
            patch(
                "ancol_common.notifications.dispatcher.send_email_notification",
                new_callable=AsyncMock,
                return_value=True,
            ) as mock_email,
        ):
            ids = await send_notification(
                recipient=user,
                title="Test",
                body="Test body",
                session=session,
            )
            assert len(ids) == 1  # in_app returns ID
            mock_in_app.assert_called_once()
            mock_email.assert_called_once()

    @pytest.mark.asyncio
    async def test_dispatch_with_whatsapp(self):
        """User with WhatsApp enabled + phone should trigger all 3 channels."""
        user = _make_user(
            phone_number="+6281234567001",
            notification_channels=["email", "in_app", "whatsapp"],
        )
        session = AsyncMock()

        with (
            patch(
                "ancol_common.notifications.dispatcher.create_in_app_notification",
                new_callable=AsyncMock,
                return_value="notif-1",
            ),
            patch(
                "ancol_common.notifications.dispatcher.send_email_notification",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "ancol_common.notifications.dispatcher.send_approval_request",
                new_callable=AsyncMock,
                return_value=True,
            ) as mock_wa,
        ):
            await send_notification(
                recipient=user,
                title="Review Required",
                body="Please review",
                related_document_id="doc-123",
                session=session,
            )
            mock_wa.assert_called_once()
            assert mock_wa.call_args.kwargs["to_phone"] == "+6281234567001"

    @pytest.mark.asyncio
    async def test_dispatch_whatsapp_skipped_without_phone(self):
        """WhatsApp in channels but no phone → skip gracefully."""
        user = _make_user(
            phone_number=None,
            notification_channels=["email", "in_app", "whatsapp"],
        )
        session = AsyncMock()

        with (
            patch(
                "ancol_common.notifications.dispatcher.create_in_app_notification",
                new_callable=AsyncMock,
                return_value="notif-1",
            ),
            patch(
                "ancol_common.notifications.dispatcher.send_email_notification",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "ancol_common.notifications.dispatcher.send_approval_request",
                new_callable=AsyncMock,
            ) as mock_wa,
        ):
            await send_notification(
                recipient=user,
                title="Test",
                body="Test body",
                session=session,
            )
            mock_wa.assert_not_called()

    @pytest.mark.asyncio
    async def test_dispatch_empty_channels_falls_back_to_defaults(self):
        """Empty channel list (falsy) falls back to default email + in_app."""
        user = _make_user(notification_channels=[])
        session = AsyncMock()

        with (
            patch(
                "ancol_common.notifications.dispatcher.create_in_app_notification",
                new_callable=AsyncMock,
                return_value="notif-1",
            ) as mock_in_app,
            patch(
                "ancol_common.notifications.dispatcher.send_email_notification",
                new_callable=AsyncMock,
                return_value=True,
            ) as mock_email,
        ):
            ids = await send_notification(
                recipient=user,
                title="Test",
                body="Test body",
                session=session,
            )
            assert len(ids) == 1  # in_app default
            mock_in_app.assert_called_once()
            mock_email.assert_called_once()

    @pytest.mark.asyncio
    async def test_dispatch_unknown_channel_ignored(self):
        """Unknown channel name is silently ignored."""
        user = _make_user(notification_channels=["sms", "in_app"])
        session = AsyncMock()

        with patch(
            "ancol_common.notifications.dispatcher.create_in_app_notification",
            new_callable=AsyncMock,
            return_value="notif-1",
        ) as mock_in_app:
            ids = await send_notification(
                recipient=user,
                title="Test",
                body="Test body",
                session=session,
            )
            assert len(ids) == 1
            mock_in_app.assert_called_once()


class TestGateReviewerNotification:
    """Test gate reviewer notification routing."""

    @pytest.mark.asyncio
    async def test_gate_1_notifies_corp_secretary(self):
        """Gate 1 should find corp_secretary and admin roles."""
        user = _make_user(role="corp_secretary")
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [user]
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        session = AsyncMock()
        session.execute = AsyncMock(return_value=mock_result)

        with patch(
            "ancol_common.notifications.dispatcher.send_notification",
            new_callable=AsyncMock,
            return_value=["nid-1"],
        ):
            count = await notify_gate_reviewers(
                document_id="doc-123",
                document_name="Test MoM.pdf",
                gate="hitl_gate_1",
                session=session,
            )
            assert count > 0

    @pytest.mark.asyncio
    async def test_no_active_reviewers_sends_zero(self):
        """No active reviewers → 0 notifications."""
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        session = AsyncMock()
        session.execute = AsyncMock(return_value=mock_result)

        count = await notify_gate_reviewers(
            document_id="doc-123",
            document_name="Test MoM.pdf",
            gate="hitl_gate_1",
            session=session,
        )
        assert count == 0

    @pytest.mark.asyncio
    async def test_unknown_gate_sends_zero(self):
        """Unknown gate → 0 notifications."""
        session = AsyncMock()
        count = await notify_gate_reviewers(
            document_id="doc-123",
            document_name="Test.pdf",
            gate="hitl_gate_99",
            session=session,
        )
        assert count == 0

    def test_all_gates_have_permissions(self):
        """Every HITL gate in GATE_PERMISSIONS maps to existing ROLE_PERMISSIONS."""
        for gate, perm_keys in GATE_PERMISSIONS.items():
            for pk in perm_keys:
                assert pk in ROLE_PERMISSIONS, f"Missing permission: {pk} for {gate}"


class TestUserProfileSchemas:
    """Test user profile update schemas."""

    def test_valid_e164_phone(self):
        from api_gateway.routers.users import UserProfileUpdateRequest

        req = UserProfileUpdateRequest(phone_number="+6281234567001")
        assert req.phone_number == "+6281234567001"

    def test_invalid_phone_format(self):
        from api_gateway.routers.users import UserProfileUpdateRequest

        with pytest.raises(ValidationError):
            UserProfileUpdateRequest(phone_number="081234567001")  # missing +

    def test_valid_channels(self):
        from api_gateway.routers.users import UserProfileUpdateRequest

        req = UserProfileUpdateRequest(
            notification_channels=["email", "whatsapp", "in_app"]
        )
        assert "whatsapp" in req.notification_channels

    def test_phone_with_channels(self):
        from api_gateway.routers.users import UserProfileUpdateRequest

        req = UserProfileUpdateRequest(
            phone_number="+6281234567001",
            notification_channels=["email", "in_app", "whatsapp"],
        )
        assert req.phone_number is not None
        assert len(req.notification_channels) == 3


class TestNotificationPreferencesSchemas:
    """Test notification preference endpoint schemas."""

    def test_preferences_response(self):
        from api_gateway.routers.notifications import NotificationPreferencesResponse

        resp = NotificationPreferencesResponse(
            channels=["email", "in_app"],
            phone_number="+6281234567001",
        )
        assert len(resp.channels) == 2

    def test_preferences_update_request(self):
        from api_gateway.routers.notifications import (
            NotificationPreferencesUpdateRequest,
        )

        req = NotificationPreferencesUpdateRequest(
            channels=["email", "in_app", "whatsapp"]
        )
        assert "whatsapp" in req.channels

    def test_valid_channels_constant(self):
        assert "email" in VALID_CHANNELS
        assert "in_app" in VALID_CHANNELS
        assert "whatsapp" in VALID_CHANNELS
        assert "push" in VALID_CHANNELS
        assert "sms" not in VALID_CHANNELS


class TestRBACProfilePermission:
    """Test RBAC permission for profile updates."""

    def test_update_profile_permission_exists(self):
        assert "users:update_profile" in ROLE_PERMISSIONS

    def test_all_roles_can_update_profile(self):
        from ancol_common.schemas.mom import UserRole

        allowed = ROLE_PERMISSIONS["users:update_profile"]
        for role in UserRole:
            assert role in allowed, f"{role} should be able to update profile"


class TestUserModelPhoneField:
    """Test User model has phone and notification fields."""

    def test_user_model_has_phone_number(self):
        from ancol_common.db.models import User

        assert hasattr(User, "phone_number")

    def test_user_model_has_notification_channels(self):
        from ancol_common.db.models import User

        assert hasattr(User, "notification_channels")

    def test_notification_model_has_whatsapp_channel(self):
        from ancol_common.db.models import Notification

        assert hasattr(Notification, "channel")


class TestWhatsAppModule:
    """Test existing WhatsApp module functions are importable and correct."""

    def test_send_notification_importable(self):
        from ancol_common.notifications.whatsapp import send_notification

        assert callable(send_notification)

    def test_send_approval_request_importable(self):
        from ancol_common.notifications.whatsapp import send_approval_request

        assert callable(send_approval_request)

    def test_send_obligation_reminder_importable(self):
        from ancol_common.notifications.whatsapp import send_obligation_reminder

        assert callable(send_obligation_reminder)


class TestRouterLoads:
    """Verify routers still load after changes."""

    def test_users_router_loads(self):
        from api_gateway.routers import users

        assert hasattr(users, "router")

    def test_notifications_router_loads(self):
        from api_gateway.routers import notifications

        assert hasattr(notifications, "router")

    def test_hitl_router_loads(self):
        from api_gateway.routers import hitl

        assert hasattr(hitl, "router")
