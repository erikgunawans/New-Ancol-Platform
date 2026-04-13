"""Tests for obligation schemas and validation."""

from __future__ import annotations

from ancol_common.schemas.obligation import (
    Obligation,
    ObligationStatus,
    ObligationType,
)


class TestObligationSchemas:
    """Verify obligation Pydantic schemas."""

    def test_obligation_type_values(self):
        assert ObligationType.RENEWAL == "renewal"
        assert ObligationType.PAYMENT == "payment"
        assert ObligationType.TERMINATION_NOTICE == "termination_notice"
        assert len(ObligationType) == 6

    def test_obligation_status_values(self):
        assert ObligationStatus.UPCOMING == "upcoming"
        assert ObligationStatus.DUE_SOON == "due_soon"
        assert ObligationStatus.OVERDUE == "overdue"
        assert ObligationStatus.FULFILLED == "fulfilled"
        assert ObligationStatus.WAIVED == "waived"
        assert len(ObligationStatus) == 5

    def test_obligation_model_defaults(self):
        ob = Obligation(
            id="test-1",
            contract_id="contract-1",
            obligation_type=ObligationType.RENEWAL,
            description="Perpanjangan kontrak sewa",
            due_date="2026-12-31",
            responsible_party="PT Ancol",
        )
        assert ob.status == ObligationStatus.UPCOMING
        assert ob.reminder_sent_30d is False
        assert ob.recurrence is None

    def test_obligation_fulfilled_fields(self):
        ob = Obligation(
            id="test-2",
            contract_id="contract-1",
            obligation_type=ObligationType.PAYMENT,
            description="Pembayaran sewa Q1",
            due_date="2026-03-31",
            responsible_party="PT Ancol",
            status=ObligationStatus.FULFILLED,
            fulfilled_by="user-1",
        )
        assert ob.status == "fulfilled"
        assert ob.fulfilled_by == "user-1"
