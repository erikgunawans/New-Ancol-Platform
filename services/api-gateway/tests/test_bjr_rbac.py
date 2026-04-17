"""Tests for BJR RBAC permissions and new roles."""

from __future__ import annotations

from typing import ClassVar

from ancol_common.auth.rbac import ROLE_PERMISSIONS
from ancol_common.schemas.mom import UserRole


class TestBJRNewRoles:
    """Verify the 2 new BJR roles are wired into the UserRole enum."""

    def test_dewan_pengawas_exists(self):
        assert UserRole.DEWAN_PENGAWAS.value == "dewan_pengawas"

    def test_direksi_exists(self):
        assert UserRole.DIREKSI.value == "direksi"

    def test_role_count_expanded(self):
        # Was 7 (pre-BJR), now 9
        assert len(UserRole) == 9


class TestBJRPermissionsRegistered:
    """Verify all 24 BJR permission keys exist in ROLE_PERMISSIONS."""

    BJR_PERMS: ClassVar[list[str]] = [
        "decisions:create",
        "decisions:list",
        "decisions:edit",
        "decisions:link_evidence",
        "decisions:passport",
        "decisions:retroactive_bundle",
        "bjr:compute",
        "bjr:read",
        "bjr:gate_5_komisaris",
        "bjr:gate_5_legal",
        "rkab:view",
        "rkab:manage",
        "rjpp:view",
        "rjpp:manage",
        "dd:create",
        "dd:review",
        "fs:create",
        "fs:review",
        "spi:submit",
        "spi:view",
        "audit_committee:submit",
        "audit_committee:view",
        "material_disclosure:file",
        "organ_approval:sign",
    ]

    def test_all_bjr_perms_present(self):
        for perm in self.BJR_PERMS:
            assert perm in ROLE_PERMISSIONS, f"Missing BJR permission: {perm}"

    def test_bjr_perm_count(self):
        bjr_perms = [
            k
            for k in ROLE_PERMISSIONS
            if k.startswith(
                (
                    "decisions:",
                    "bjr:",
                    "rkab:",
                    "rjpp:",
                    "dd:",
                    "fs:",
                    "spi:",
                    "audit_committee:",
                    "material_disclosure:",
                    "organ_approval:",
                )
            )
        ]
        assert len(bjr_perms) == len(self.BJR_PERMS)


class TestBJRGate5Permissions:
    """Gate 5 is dual-approval: Komisaris + Legal only."""

    def test_gate_5_komisaris_restricted(self):
        allowed = ROLE_PERMISSIONS["bjr:gate_5_komisaris"]
        assert UserRole.KOMISARIS in allowed
        assert UserRole.ADMIN in allowed
        assert UserRole.DIREKSI not in allowed  # direksi cannot approve their own
        assert UserRole.LEGAL_COMPLIANCE not in allowed  # legal has its own half

    def test_gate_5_legal_restricted(self):
        allowed = ROLE_PERMISSIONS["bjr:gate_5_legal"]
        assert UserRole.LEGAL_COMPLIANCE in allowed
        assert UserRole.ADMIN in allowed
        assert UserRole.KOMISARIS not in allowed
        assert UserRole.BUSINESS_DEV not in allowed


class TestBJRDecisionPermissions:
    def test_decisions_create_includes_bd(self):
        """BD is the proactive owner per the BJR document's PIC column."""
        allowed = ROLE_PERMISSIONS["decisions:create"]
        assert UserRole.BUSINESS_DEV in allowed
        assert UserRole.CORP_SECRETARY in allowed
        assert UserRole.DIREKSI in allowed

    def test_decisions_retroactive_restricted(self):
        """Retroactive bundling is an audit/legal operation."""
        allowed = ROLE_PERMISSIONS["decisions:retroactive_bundle"]
        assert UserRole.LEGAL_COMPLIANCE in allowed
        assert UserRole.INTERNAL_AUDITOR in allowed
        assert UserRole.BUSINESS_DEV not in allowed
        assert UserRole.KOMISARIS not in allowed

    def test_passport_visible_to_oversight_roles(self):
        allowed = ROLE_PERMISSIONS["decisions:passport"]
        assert UserRole.KOMISARIS in allowed
        assert UserRole.DEWAN_PENGAWAS in allowed
        assert UserRole.DIREKSI in allowed


class TestBJRRegistryPermissions:
    def test_rkab_view_broad_access(self):
        """Everyone involved in decisions can see RKAB."""
        allowed = ROLE_PERMISSIONS["rkab:view"]
        assert UserRole.BUSINESS_DEV in allowed
        assert UserRole.KOMISARIS in allowed
        assert UserRole.DEWAN_PENGAWAS in allowed
        assert UserRole.DIREKSI in allowed

    def test_rkab_manage_restricted(self):
        """Only BD and Corp Sec manage RKAB line items."""
        allowed = ROLE_PERMISSIONS["rkab:manage"]
        assert UserRole.BUSINESS_DEV in allowed
        assert UserRole.CORP_SECRETARY in allowed
        assert UserRole.KOMISARIS not in allowed
        assert UserRole.INTERNAL_AUDITOR not in allowed

    def test_rjpp_manage_most_restricted(self):
        """RJPP is a 5-year plan — only BD + Admin can change it."""
        allowed = ROLE_PERMISSIONS["rjpp:manage"]
        assert UserRole.BUSINESS_DEV in allowed
        assert UserRole.ADMIN in allowed
        assert len(allowed) == 2


class TestBJRArtifactPermissions:
    def test_spi_submit_internal_audit_only(self):
        """Only Internal Audit + Admin can submit SPI reports."""
        allowed = ROLE_PERMISSIONS["spi:submit"]
        assert UserRole.INTERNAL_AUDITOR in allowed
        assert UserRole.ADMIN in allowed
        assert len(allowed) == 2

    def test_organ_approval_sign_board_level(self):
        """Only board-level organs can sign organ_approvals."""
        allowed = ROLE_PERMISSIONS["organ_approval:sign"]
        assert UserRole.KOMISARIS in allowed
        assert UserRole.DEWAN_PENGAWAS in allowed
        assert UserRole.DIREKSI in allowed
        assert UserRole.CORP_SECRETARY not in allowed
        assert UserRole.BUSINESS_DEV not in allowed

    def test_material_disclosure_file_restricted(self):
        allowed = ROLE_PERMISSIONS["material_disclosure:file"]
        assert UserRole.CORP_SECRETARY in allowed
        assert UserRole.LEGAL_COMPLIANCE in allowed
        assert UserRole.KOMISARIS not in allowed
