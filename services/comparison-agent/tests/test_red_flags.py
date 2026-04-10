"""Tests for red flag detection — the core compliance scanner."""

from __future__ import annotations

from comparison_agent.analyzers.red_flags import (
    detect_all_red_flags,
    detect_circular_resolution_issues,
    detect_conflict_of_interest,
    detect_quorum_violations,
    detect_rpt_flags,
    detect_signature_issues,
)


def test_quorum_met():
    mom = {"directors_present": 4, "total_directors": 5, "chairman": "Budi"}
    flags = detect_quorum_violations(mom)
    assert len(flags) == 0


def test_quorum_not_met():
    mom = {"directors_present": 1, "total_directors": 5, "chairman": "Budi"}
    flags = detect_quorum_violations(mom)
    assert len(flags) == 1
    assert flags[0].flag_type == "quorum_not_met"
    assert flags[0].severity == "critical"


def test_quorum_data_missing():
    mom = {"chairman": "Budi"}
    flags = detect_quorum_violations(mom)
    assert any(f.flag_type == "quorum_data_missing" for f in flags)


def test_chairman_absent():
    mom = {"directors_present": 4, "total_directors": 5, "chairman": None}
    flags = detect_quorum_violations(mom)
    assert any(f.flag_type == "chairman_absent" for f in flags)


def test_rpt_detected():
    mom = {"full_text": ""}
    resolutions = [
        {"number": "2", "text": "Menyetujui kontrak dengan PT Jaya Konstruksi senilai Rp 25 miliar"}
    ]
    flags = detect_rpt_flags(mom, resolutions)
    assert any(f.flag_type == "rpt_detected" for f in flags)


def test_rpt_not_detected():
    mom = {"full_text": ""}
    resolutions = [{"number": "1", "text": "Menyetujui laporan keuangan"}]
    flags = detect_rpt_flags(mom, resolutions)
    assert not any(f.flag_type == "rpt_detected" for f in flags)


def test_rpt_keyword_detected():
    mom = {"full_text": "Transaksi ini merupakan transaksi afiliasi sesuai POJK 42/2020"}
    resolutions = [{"number": "1", "text": "Menyetujui laporan keuangan"}]
    flags = detect_rpt_flags(mom, resolutions)
    assert any(f.flag_type == "rpt_keyword_detected" for f in flags)


def test_coi_without_abstention():
    mom = {"full_text": "Terdapat benturan kepentingan dari Direktur A dalam transaksi ini"}
    flags = detect_conflict_of_interest(mom, [])
    assert any(f.flag_type == "coi_no_abstention" for f in flags)
    assert flags[0].severity == "critical"


def test_coi_with_abstention():
    mom = {
        "full_text": (
            "Terdapat benturan kepentingan dari Direktur A. "
            "Direktur A meninggalkan ruang rapat selama pembahasan."
        )
    }
    flags = detect_conflict_of_interest(mom, [])
    assert len(flags) == 0


def test_circular_not_unanimous():
    mom = {"meeting_type": "circular", "total_directors": 5, "signers": ["A", "B", "C"]}
    flags = detect_circular_resolution_issues(mom)
    assert any(f.flag_type == "circular_not_unanimous" for f in flags)


def test_circular_unanimous():
    mom = {"meeting_type": "circular", "total_directors": 3, "signers": ["A", "B", "C"]}
    flags = detect_circular_resolution_issues(mom)
    assert len(flags) == 0


def test_no_signatures():
    mom = {"signers": []}
    flags = detect_signature_issues(mom)
    assert any(f.flag_type == "no_signatures" for f in flags)


def test_insufficient_signatures():
    mom = {"signers": ["Budi"]}
    flags = detect_signature_issues(mom)
    assert any(f.flag_type == "insufficient_signatures" for f in flags)


def test_sufficient_signatures():
    mom = {"signers": ["Budi", "Ratna"]}
    flags = detect_signature_issues(mom)
    assert len(flags) == 0


def test_detect_all_combines_results():
    mom = {
        "directors_present": 1,
        "total_directors": 5,
        "chairman": None,
        "meeting_type": "regular",
        "signers": [],
        "full_text": "",
    }
    resolutions = [{"number": "1", "text": "Kontrak dengan PT Jaya Real Property senilai Rp 100M"}]
    all_flags = detect_all_red_flags(mom, resolutions)
    types = {f.flag_type for f in all_flags}
    assert "quorum_not_met" in types
    assert "chairman_absent" in types
    assert "rpt_detected" in types
    assert "no_signatures" in types
