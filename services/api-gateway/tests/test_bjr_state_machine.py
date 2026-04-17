"""Tests for the StrategicDecision state machine (DECISION_TRANSITIONS)."""

from __future__ import annotations

from ancol_common.db.repository import DECISION_TRANSITIONS


class TestDecisionStateMachine:
    """Verify the 14-state BJR decision state machine is complete and correct."""

    def test_all_fourteen_states_defined(self):
        expected_states = {
            "ideation",
            "dd_in_progress",
            "fs_in_progress",
            "rkab_verified",
            "board_proposed",
            "organ_approval_pending",
            "approved",
            "executing",
            "monitoring",
            "bjr_gate_5",
            "bjr_locked",
            "archived",
            "rejected",
            "cancelled",
        }
        assert set(DECISION_TRANSITIONS.keys()) == expected_states

    def test_ideation_is_starting_state(self):
        """New decisions start in ideation and flow forward to DD."""
        assert "dd_in_progress" in DECISION_TRANSITIONS["ideation"]
        assert "cancelled" in DECISION_TRANSITIONS["ideation"]

    def test_cannot_skip_dd_to_approved(self):
        """You can't jump from DD to approved — must pass through FS + RKAB + board."""
        assert "approved" not in DECISION_TRANSITIONS["dd_in_progress"]

    def test_fs_can_go_back_to_dd(self):
        """Back-edge: FS phase can revert to DD if findings need expansion."""
        assert "dd_in_progress" in DECISION_TRANSITIONS["fs_in_progress"]

    def test_rkab_verified_leads_to_board(self):
        """After RKAB match succeeds, the decision is ready for board proposal."""
        assert "board_proposed" in DECISION_TRANSITIONS["rkab_verified"]

    def test_organ_approval_gates_to_approved(self):
        transitions = DECISION_TRANSITIONS["organ_approval_pending"]
        assert "approved" in transitions
        assert "rejected" in transitions

    def test_executing_must_transition_to_monitoring(self):
        """Post-approval, execution feeds into monitoring phase — no skip."""
        assert DECISION_TRANSITIONS["executing"] == ["monitoring"]

    def test_monitoring_triggers_gate_5(self):
        """Sufficient post-decision evidence triggers Gate 5."""
        assert DECISION_TRANSITIONS["monitoring"] == ["bjr_gate_5"]

    def test_gate_5_can_lock_or_revert(self):
        """Gate 5 either locks the decision or sends it back for more evidence."""
        transitions = DECISION_TRANSITIONS["bjr_gate_5"]
        assert "bjr_locked" in transitions
        assert "monitoring" in transitions

    def test_locked_only_goes_to_archived(self):
        """Once locked, the only path forward is archival (decision is immutable)."""
        assert DECISION_TRANSITIONS["bjr_locked"] == ["archived"]

    def test_archived_is_terminal(self):
        assert DECISION_TRANSITIONS["archived"] == []

    def test_rejected_is_terminal(self):
        assert DECISION_TRANSITIONS["rejected"] == []

    def test_cancelled_is_terminal(self):
        assert DECISION_TRANSITIONS["cancelled"] == []


class TestDecisionTransitionsCoverage:
    """Verify no unreachable or dangling states."""

    def test_every_non_terminal_has_forward_transition(self):
        """No non-terminal state should have an empty transition list."""
        terminal = {"archived", "rejected", "cancelled"}
        for state, transitions in DECISION_TRANSITIONS.items():
            if state not in terminal:
                assert len(transitions) > 0, f"Non-terminal state '{state}' has no exits"

    def test_all_referenced_states_are_defined(self):
        """Every target state in a transition list must be a defined state."""
        defined = set(DECISION_TRANSITIONS.keys())
        for state, transitions in DECISION_TRANSITIONS.items():
            for target in transitions:
                assert target in defined, f"'{state}' → undefined state '{target}'"
