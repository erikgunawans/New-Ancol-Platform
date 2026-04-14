"""Tests for obligation auto-transition logic."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest
from ancol_common.db.models import ObligationRecord
from ancol_common.db.repository import check_obligation_deadlines


def _make_mock_session(rowcounts=None, select_results=None):
    """Create a mock AsyncSession.

    Args:
        rowcounts: list of rowcounts for sequential execute() calls
            (5 UPDATEs: overdue, due_soon, reminder_30d, reminder_14d, reminder_7d)
        select_results: ORM objects returned by the 6th execute() (recurrence query)
    """
    session = AsyncMock()
    rowcounts = rowcounts or [0, 0, 0, 0, 0]
    select_results = select_results or []
    call_idx = {"i": 0}

    async def mock_execute(stmt):
        i = call_idx["i"]
        call_idx["i"] += 1
        result = MagicMock()
        if i < len(rowcounts):
            result.rowcount = rowcounts[i]
        else:
            # This is the recurrence SELECT
            result.scalars.return_value.all.return_value = select_results
        return result

    session.execute = mock_execute
    session.add = MagicMock()
    return session


class TestOverdueTransition:
    """Obligations past due date should transition to overdue."""

    @pytest.mark.asyncio
    async def test_overdue_transition_counts(self):
        session = _make_mock_session(rowcounts=[3, 0, 0, 0, 0])
        result = await check_obligation_deadlines(session)
        assert result["transitioned_overdue"] == 3

    @pytest.mark.asyncio
    async def test_due_soon_transition_counts(self):
        session = _make_mock_session(rowcounts=[0, 7, 0, 0, 0])
        result = await check_obligation_deadlines(session)
        assert result["transitioned_due_soon"] == 7

    @pytest.mark.asyncio
    async def test_no_op_when_nothing_due(self):
        session = _make_mock_session(rowcounts=[0, 0, 0, 0, 0])
        result = await check_obligation_deadlines(session)
        assert result["transitioned_overdue"] == 0
        assert result["transitioned_due_soon"] == 0
        assert result["reminders_flagged"] == 0
        assert result["recurrences_created"] == 0


class TestReminderFlags:
    """Reminder flags should be set for obligations in each window."""

    @pytest.mark.asyncio
    async def test_reminder_30d_flagged(self):
        session = _make_mock_session(rowcounts=[0, 0, 5, 0, 0])
        result = await check_obligation_deadlines(session)
        assert result["reminders_flagged"] == 5

    @pytest.mark.asyncio
    async def test_all_reminder_windows(self):
        session = _make_mock_session(rowcounts=[0, 0, 3, 2, 1])
        result = await check_obligation_deadlines(session)
        assert result["reminders_flagged"] == 6


class TestRecurrence:
    """Fulfilled obligations with recurrence spawn next occurrence."""

    @pytest.mark.asyncio
    async def test_monthly_recurrence_created(self):
        ob = MagicMock(spec=ObligationRecord)
        ob.contract_id = "contract-1"
        ob.obligation_type = "payment"
        ob.description = "Monthly payment"
        ob.due_date = date(2026, 3, 15)
        ob.recurrence = "monthly"
        ob.next_due_date = None
        ob.responsible_user_id = None
        ob.responsible_party_name = "PT Ancol"
        ob.id = "ob-1"
        ob.status = "fulfilled"

        session = _make_mock_session(
            rowcounts=[0, 0, 0, 0, 0],
            select_results=[ob],
        )
        result = await check_obligation_deadlines(session)
        assert result["recurrences_created"] == 1
        assert ob.next_due_date == date(2026, 4, 15)
        session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_recurrence_idempotent_when_next_date_set(self):
        """next_due_date already set -> no duplicate."""
        session = _make_mock_session(
            rowcounts=[0, 0, 0, 0, 0],
            select_results=[],
        )
        result = await check_obligation_deadlines(session)
        assert result["recurrences_created"] == 0
        session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_quarterly_recurrence_date(self):
        ob = MagicMock(spec=ObligationRecord)
        ob.contract_id = "contract-1"
        ob.obligation_type = "reporting"
        ob.description = "Quarterly report"
        ob.due_date = date(2026, 1, 31)
        ob.recurrence = "quarterly"
        ob.next_due_date = None
        ob.responsible_user_id = None
        ob.responsible_party_name = "PT Ancol"
        ob.id = "ob-2"
        ob.status = "fulfilled"

        session = _make_mock_session(
            rowcounts=[0, 0, 0, 0, 0],
            select_results=[ob],
        )
        result = await check_obligation_deadlines(session)
        assert result["recurrences_created"] == 1
        assert ob.next_due_date == date(2026, 4, 30)
