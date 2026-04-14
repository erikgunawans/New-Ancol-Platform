"""Format raw API JSON responses into Bahasa Indonesia chat text.

All output is Markdown-formatted, concise for chat. English legal terms
are preserved as-is per convention.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# -- Severity emoji mapping --

_SEVERITY_INDICATOR: dict[str, str] = {
    "critical": "[CRITICAL]",
    "high": "[HIGH]",
    "medium": "[MEDIUM]",
    "low": "[LOW]",
}

# -- Status labels in Bahasa Indonesia --

_STATUS_LABEL: dict[str, str] = {
    "pending": "Menunggu",
    "processing_ocr": "Proses OCR",
    "ocr_complete": "OCR Selesai",
    "extracting": "Ekstraksi AI",
    "hitl_gate_1": "Review Gate 1 (Ekstraksi)",
    "researching": "Riset Regulasi",
    "hitl_gate_2": "Review Gate 2 (Regulasi)",
    "comparing": "Analisis Kepatuhan",
    "hitl_gate_3": "Review Gate 3 (Temuan)",
    "reporting": "Pembuatan Laporan",
    "hitl_gate_4": "Review Gate 4 (Laporan)",
    "complete": "Selesai",
    "failed": "Gagal",
    "rejected": "Ditolak",
}


def _safe_get(data: dict, key: str, default: str = "-") -> str:
    """Safely retrieve a value, returning default if missing or None."""
    val = data.get(key)
    return str(val) if val is not None else default


def _pct_bar(score: float, width: int = 10) -> str:
    """Build a simple text-based percentage bar."""
    filled = round(score / 100 * width)
    return f"[{'#' * filled}{'.' * (width - filled)}] {score:.1f}%"


# -- Public formatters --


def format_extraction(data: dict) -> str:
    """Format Gate 1 extraction output for chat display."""
    ai = data.get("ai_output", data)

    title = _safe_get(ai, "meeting_number", "Rapat")
    meeting_date = _safe_get(ai, "meeting_date")
    meeting_type = _safe_get(ai, "meeting_type")
    chairman = _safe_get(ai, "chairman")

    lines = [
        "**Hasil Ekstraksi MoM**",
        f"**Judul:** {title}",
        f"**Tanggal:** {meeting_date}",
        f"**Jenis:** {meeting_type}",
        f"**Ketua Rapat:** {chairman}",
        "",
    ]

    # Attendees
    attendees = ai.get("attendees", [])
    if attendees:
        lines.append("**Daftar Hadir:**")
        for att in attendees:
            name = att.get("name", "-")
            title_att = att.get("title", "")
            present = "Hadir" if att.get("present", True) else "Tidak Hadir"
            suffix = f" ({title_att})" if title_att else ""
            lines.append(f"- {name}{suffix} — {present}")
        lines.append("")

    # Quorum
    quorum = ai.get("quorum_met")
    if quorum is not None:
        status = "Terpenuhi" if quorum else "TIDAK Terpenuhi"
        total = ai.get("total_directors", "-")
        present_count = ai.get("directors_present", "-")
        lines.append(f"**Kuorum:** {status} ({present_count}/{total} direktur)")
        lines.append("")

    # Resolutions
    resolutions = ai.get("resolutions", [])
    if resolutions:
        lines.append("**Keputusan Rapat:**")
        for res in resolutions:
            num = res.get("number", "-")
            text = res.get("text", "")
            assignee = res.get("assignee")
            deadline = res.get("deadline")
            detail = f"  {num}. {text}"
            if assignee:
                detail += f" (PIC: {assignee})"
            if deadline:
                detail += f" [Deadline: {deadline}]"
            lines.append(detail)
        lines.append("")

    # Deviation flags
    deviations = data.get("deviation_flags", [])
    if deviations:
        lines.append("**Deviasi Struktural:**")
        for d in deviations:
            sev = d.get("severity", "medium")
            desc = d.get("description", "")
            lines.append(f"- {_SEVERITY_INDICATOR.get(sev, '')} {desc}")

    return "\n".join(lines).strip()


def format_regulatory_mapping(data: dict) -> str:
    """Format Gate 2 regulatory mapping output."""
    ai = data.get("ai_output", data)

    lines = ["**Pemetaan Regulasi (Gate 2)**", ""]

    mappings = ai.get("mappings", ai.get("regulatory_mapping", []))
    if isinstance(mappings, list):
        for m in mappings:
            reg = m.get("regulation", m.get("regulation_id", "-"))
            article = m.get("article", "")
            status = m.get("compliance_status", m.get("status", "-"))
            lines.append(f"- **{reg}** {article}")
            lines.append(f"  Status: {status}")
    elif isinstance(mappings, dict):
        for key, val in mappings.items():
            lines.append(f"- **{key}:** {val}")

    citations = ai.get("citations", [])
    if citations:
        lines.append("")
        lines.append("**Referensi Hukum:**")
        for c in citations:
            if isinstance(c, dict):
                lines.append(f"- {c.get('text', c.get('citation', str(c)))}")
            else:
                lines.append(f"- {c}")

    return "\n".join(lines).strip()


def format_compliance_findings(data: dict) -> str:
    """Format Gate 3 compliance findings with red flags."""
    ai = data.get("ai_output", data)
    red_flags = data.get("red_flags", ai.get("red_flags", {}))

    lines = ["**Temuan Kepatuhan (Gate 3)**", ""]

    findings = ai.get("findings", [])
    if isinstance(findings, list):
        for f in findings:
            sev = f.get("severity", "medium")
            indicator = _SEVERITY_INDICATOR.get(sev, "")
            category = f.get("category", f.get("type", "-"))
            desc = f.get("description", f.get("finding", "-"))
            lines.append(f"- {indicator} **{category}:** {desc}")
            suggestion = f.get("recommendation", f.get("suggestion", ""))
            if suggestion:
                lines.append(f"  Rekomendasi: {suggestion}")

    if red_flags:
        lines.append("")
        lines.append("**Red Flags:**")
        if isinstance(red_flags, dict):
            for flag_type, flag_data in red_flags.items():
                if isinstance(flag_data, list):
                    for item in flag_data:
                        lines.append(f"- **{flag_type}:** {item}")
                else:
                    lines.append(f"- **{flag_type}:** {flag_data}")
        elif isinstance(red_flags, list):
            for rf in red_flags:
                lines.append(f"- {rf}")

    return "\n".join(lines).strip()


def format_scorecard(data: dict) -> str:
    """Format three-pillar scorecard with percentage bars."""
    scorecard = data.get("scorecard", data)

    structural = float(scorecard.get("structural", 0))
    substantive = float(scorecard.get("substantive", 0))
    regulatory = float(scorecard.get("regulatory", 0))
    composite = float(scorecard.get("composite", 0))

    lines = [
        "**Scorecard Kepatuhan**",
        "",
        f"**Struktural:**  {_pct_bar(structural)}",
        f"**Substantif:**  {_pct_bar(substantive)}",
        f"**Regulasi:**    {_pct_bar(regulatory)}",
        "",
        f"**Skor Komposit:** {_pct_bar(composite)}",
    ]

    return "\n".join(lines).strip()


def format_report(data: dict) -> str:
    """Format full report summary with download links."""
    lines = [
        "**Laporan Kepatuhan MoM**",
        "",
        f"**Report ID:** {_safe_get(data, 'id')}",
        f"**Dokumen:** {_safe_get(data, 'document_id')}",
        "",
    ]

    # Scores
    for label, key in [
        ("Struktural", "structural_score"),
        ("Substantif", "substantive_score"),
        ("Regulasi", "regulatory_score"),
        ("Komposit", "composite_score"),
    ]:
        score = data.get(key)
        if score is not None:
            lines.append(f"**{label}:** {_pct_bar(float(score))}")

    lines.append("")

    # Corrective suggestions
    suggestions = data.get("corrective_suggestions", [])
    if suggestions:
        lines.append("**Saran Perbaikan:**")
        for i, s in enumerate(suggestions, 1):
            if isinstance(s, dict):
                lines.append(f"  {i}. {s.get('suggestion', s.get('text', str(s)))}")
            else:
                lines.append(f"  {i}. {s}")
        lines.append("")

    # Download links
    pdf_uri = data.get("pdf_uri")
    excel_uri = data.get("excel_uri")
    report_id = data.get("id", "")
    if pdf_uri or excel_uri:
        lines.append("**Unduhan:**")
        if pdf_uri:
            lines.append(f"- [Download PDF](/api/reports/{report_id}/download/pdf)")
        if excel_uri:
            lines.append(f"- [Download Excel](/api/reports/{report_id}/download/excel)")

    return "\n".join(lines).strip()


def format_dashboard(data: dict) -> str:
    """Format dashboard stats overview."""
    lines = [
        "**Dashboard Kepatuhan MoM**",
        "",
        f"**Total Dokumen:** {_safe_get(data, 'total_documents', '0')}",
        f"**Menunggu Review:** {_safe_get(data, 'pending_review', '0')}",
        f"**Selesai:** {_safe_get(data, 'completed', '0')}",
        f"**Gagal:** {_safe_get(data, 'failed', '0')}",
        f"**Ditolak:** {_safe_get(data, 'rejected', '0')}",
        "",
    ]

    avg_composite = data.get("avg_composite_score")
    if avg_composite is not None:
        lines.append(f"**Rata-rata Skor Komposit:** {float(avg_composite):.1f}%")
        lines.append("")

    # Status breakdown
    by_status = data.get("documents_by_status", {})
    if by_status:
        lines.append("**Distribusi Status:**")
        for status, count in by_status.items():
            label = _STATUS_LABEL.get(status, status)
            lines.append(f"- {label}: {count}")
        lines.append("")

    # Batch info
    active = data.get("active_batch_jobs", 0)
    queued = data.get("batch_documents_queued", 0)
    if active or queued:
        lines.append(f"**Batch Aktif:** {active} job, {queued} dokumen antri")

    # Trends (if included)
    trends = data.get("trends", [])
    if trends:
        lines.append("")
        lines.append("**Tren Bulanan:**")
        for t in trends:
            period = t.get("period", "-")
            avg = t.get("avg_composite")
            count = t.get("document_count", 0)
            score_str = f"{float(avg):.1f}%" if avg is not None else "N/A"
            lines.append(f"- {period}: {score_str} ({count} dokumen)")

    return "\n".join(lines).strip()


def format_hitl_queue(items: list) -> str:
    """Format pending HITL review items list."""
    if not items:
        return "Tidak ada dokumen yang menunggu review saat ini."

    lines = [f"**Antrian Review HITL** ({len(items)} item)", ""]

    for i, item in enumerate(items, 1):
        doc_id = item.get("document_id", "-")
        filename = item.get("filename", "-")
        gate = item.get("gate", "-")
        gate_label = _STATUS_LABEL.get(gate, gate)
        meeting_date = item.get("meeting_date", "")

        line = f"  {i}. **{filename}**"
        if meeting_date:
            line += f" ({meeting_date})"
        lines.append(line)
        lines.append(f"     Gate: {gate_label} | ID: `{doc_id}`")

    return "\n".join(lines).strip()


def format_document_status(data: dict) -> str:
    """Format current document state in the 14-state machine."""
    doc_id = _safe_get(data, "id")
    filename = _safe_get(data, "filename")
    status = data.get("status", "unknown")
    status_label = _STATUS_LABEL.get(status, status)
    mom_type = _safe_get(data, "mom_type")
    meeting_date = _safe_get(data, "meeting_date")
    fmt = _safe_get(data, "format")

    lines = [
        "**Status Dokumen**",
        "",
        f"**File:** {filename}",
        f"**ID:** `{doc_id}`",
        f"**Status:** {status_label} (`{status}`)",
        f"**Jenis MoM:** {mom_type}",
        f"**Tanggal Rapat:** {meeting_date}",
        f"**Format:** {fmt}",
    ]

    page_count = data.get("page_count")
    if page_count:
        lines.append(f"**Halaman:** {page_count}")

    ocr_conf = data.get("ocr_confidence")
    if ocr_conf is not None:
        lines.append(f"**Confidence OCR:** {float(ocr_conf):.1%}")

    created = data.get("created_at")
    updated = data.get("updated_at")
    if created:
        lines.append(f"**Dibuat:** {created}")
    if updated:
        lines.append(f"**Diperbarui:** {updated}")

    return "\n".join(lines).strip()


# -- Contract status labels --

_CONTRACT_STATUS_LABEL: dict[str, str] = {
    "draft": "Draf",
    "pending_review": "Menunggu Review",
    "in_review": "Dalam Review",
    "approved": "Disetujui",
    "executed": "Ditandatangani",
    "active": "Aktif",
    "expiring": "Akan Berakhir",
    "expired": "Berakhir",
    "terminated": "Dibatalkan",
    "amended": "Diamandemen",
    "failed": "Gagal",
}

_CONTRACT_TYPE_LABEL: dict[str, str] = {
    "nda": "NDA",
    "vendor": "Vendor",
    "sale_purchase": "Jual Beli",
    "joint_venture": "Joint Venture",
    "land_lease": "Sewa Tanah/HGB",
    "employment": "Ketenagakerjaan",
    "sop_board_resolution": "SOP/SK Direksi",
}

_OBLIGATION_TYPE_LABEL: dict[str, str] = {
    "renewal": "Perpanjangan",
    "reporting": "Pelaporan",
    "payment": "Pembayaran",
    "termination_notice": "Notifikasi Pemutusan",
    "deliverable": "Deliverable",
    "compliance_filing": "Filing Kepatuhan",
}

_OBLIGATION_STATUS_LABEL: dict[str, str] = {
    "upcoming": "Akan Datang",
    "due_soon": "Segera Jatuh Tempo",
    "overdue": "Terlambat",
    "fulfilled": "Terpenuhi",
    "waived": "Dikesampingkan",
}

_RISK_INDICATOR: dict[str, str] = {
    "high": "[HIGH]",
    "medium": "[MEDIUM]",
    "low": "[LOW]",
}


def format_contract_status(data: dict) -> str:
    """Format contract status for chat display."""
    status = data.get("status", "unknown")
    status_label = _CONTRACT_STATUS_LABEL.get(status, status)
    ctype = data.get("contract_type", "")
    type_label = _CONTRACT_TYPE_LABEL.get(ctype, ctype)

    lines = [
        "**Status Kontrak**",
        "",
        f"**Judul:** {_safe_get(data, 'title')}",
        f"**ID:** `{_safe_get(data, 'id')}`",
        f"**Nomor:** {_safe_get(data, 'contract_number')}",
        f"**Tipe:** {type_label}",
        f"**Status:** {status_label} (`{status}`)",
    ]

    effective = data.get("effective_date")
    expiry = data.get("expiry_date")
    if effective:
        lines.append(f"**Berlaku:** {effective}")
    if expiry:
        lines.append(f"**Berakhir:** {expiry}")

    value = data.get("total_value")
    currency = data.get("currency", "IDR")
    if value:
        lines.append(f"**Nilai:** {currency} {float(value):,.0f}")

    risk = data.get("risk_level")
    if risk:
        lines.append(f"**Risiko:** {_RISK_INDICATOR.get(risk, risk)}")

    return "\n".join(lines).strip()


def format_contract_risk(data: dict) -> str:
    """Format clause-level risk analysis."""
    lines = [
        "**Analisis Risiko Kontrak**",
        "",
        f"**ID:** `{_safe_get(data, 'contract_id')}`",
        f"**Level Risiko:** {_RISK_INDICATOR.get(data.get('risk_level', ''), '-')}",
    ]

    score = data.get("risk_score")
    if score is not None:
        lines.append(f"**Skor Risiko:** {float(score):.1f}/100")

    clauses = data.get("extraction_data", {}).get("clauses", [])
    if clauses:
        lines.append("")
        lines.append("**Klausul Berisiko:**")
        for cl in clauses:
            risk = cl.get("risk_level")
            if risk:
                lines.append(
                    f"- {_RISK_INDICATOR.get(risk, '')} "
                    f"**{cl.get('title', '-')}**: {cl.get('risk_reason', '-')}"
                )

    return "\n".join(lines).strip()


def format_obligations(data: dict) -> str:
    """Format obligation list for chat."""
    items = data.get("obligations", data.get("upcoming", []))
    if not items:
        return "Tidak ada kewajiban kontrak yang ditemukan."

    total = data.get("total", len(items))
    lines = [f"**Kewajiban Kontrak** ({total} item)", ""]

    for i, o in enumerate(items, 1):
        status = o.get("status", "")
        status_label = _OBLIGATION_STATUS_LABEL.get(status, status)
        otype = o.get("obligation_type", "")
        type_label = _OBLIGATION_TYPE_LABEL.get(otype, otype)

        lines.append(f"  {i}. **{o.get('description', '-')}**")
        lines.append(f"     Tipe: {type_label} | Status: {status_label}")
        lines.append(f"     Jatuh tempo: {o.get('due_date', '-')}")
        lines.append(f"     Penanggung jawab: {o.get('responsible_party_name', '-')}")
        lines.append("")

    return "\n".join(lines).strip()


def format_draft_output(data: dict) -> str:
    """Format draft generation result."""
    if data.get("status") == "stub":
        return (
            "Fitur drafting kontrak akan tersedia di Phase 2.\n"
            f"Permintaan untuk tipe **{data.get('contract_type', '-')}** telah dicatat."
        )

    lines = [
        "**Draft Kontrak**",
        "",
        f"**ID:** `{_safe_get(data, 'contract_id')}`",
        f"**Tipe:** {_CONTRACT_TYPE_LABEL.get(data.get('contract_type', ''), '-')}",
    ]

    clauses = data.get("clauses", [])
    if clauses:
        lines.append(f"**Klausul:** {len(clauses)} klausul")

    draft_uri = data.get("gcs_draft_uri")
    if draft_uri:
        lines.append(f"**Download:** [Draft kontrak]({draft_uri})")

    return "\n".join(lines).strip()


def format_contract_portfolio(data: dict) -> str:
    """Format portfolio-level contract summary."""
    contracts = data.get("contracts", [])
    total = data.get("total", len(contracts))

    lines = [f"**Portfolio Kontrak** ({total} kontrak)", ""]

    # Group by status
    by_status: dict[str, int] = {}
    by_type: dict[str, int] = {}
    for c in contracts:
        s = c.get("status", "unknown")
        by_status[s] = by_status.get(s, 0) + 1
        t = c.get("contract_type", "unknown")
        by_type[t] = by_type.get(t, 0) + 1

    if by_status:
        lines.append("**Distribusi Status:**")
        for status, count in sorted(by_status.items()):
            label = _CONTRACT_STATUS_LABEL.get(status, status)
            lines.append(f"- {label}: {count}")
        lines.append("")

    if by_type:
        lines.append("**Distribusi Tipe:**")
        for ctype, count in sorted(by_type.items()):
            label = _CONTRACT_TYPE_LABEL.get(ctype, ctype)
            lines.append(f"- {label}: {count}")

    return "\n".join(lines).strip()


def format_regulation_result(data: dict) -> str:
    """Format regulation search result with citation chain."""
    if not data:
        return "Tidak ditemukan regulasi yang relevan."

    lines = ["**Hasil Pencarian Regulasi**", ""]

    query = data.get("query", "")
    if query:
        lines.append(f"**Query:** {query}")
        lines.append("")

    results = data.get("results", [])
    if not results:
        lines.append("Tidak ditemukan hasil.")
        return "\n".join(lines).strip()

    for i, r in enumerate(results, 1):
        title = r.get("title", r.get("regulation", "-"))
        snippet = r.get("snippet", r.get("text", ""))
        source = r.get("source", "")
        relevance = r.get("relevance_score", "")

        lines.append(f"  {i}. **{title}**")
        if snippet:
            lines.append(f"     {snippet[:200]}")
        if source:
            lines.append(f"     Sumber: {source}")
        if relevance:
            lines.append(f"     Relevansi: {relevance}")
        lines.append("")

    # Citation chain
    citations = data.get("citation_chain", [])
    if citations:
        lines.append("**Rantai Sitasi:**")
        for c in citations:
            lines.append(f"- {c}")

    return "\n".join(lines).strip()
