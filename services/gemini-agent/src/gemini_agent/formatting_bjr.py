"""Markdown/card formatters for BJR chat responses.

All formatters apply moderate PII scrubbing (spec § 6.4):
- IDR values >= 1,000,000,000,000 rounded to "Rp X,Y triliun"
- IDR values >= 1,000,000,000 rounded to "Rp X,Y miliar"
- IDR values >= 1,000,000 rounded to "Rp X juta"
- Smaller values shown at full precision
"""

from __future__ import annotations


def _format_idr(value: int | float | None) -> str:
    """Moderate PII scrubbing for IDR values."""
    if value is None:
        return "—"
    v = float(value)
    if v >= 1_000_000_000_000:
        return f"Rp {v / 1_000_000_000_000:.1f} triliun".replace(".", ",")
    if v >= 1_000_000_000:
        return f"Rp {v / 1_000_000_000:.1f} miliar".replace(".", ",")
    if v >= 1_000_000:
        return f"Rp {v / 1_000_000:.0f} juta"
    return f"Rp {v:,.0f}"


def _state_emoji(status: str, is_locked: bool, readiness: float | None) -> str:
    if is_locked or status == "bjr_locked":
        return "🔒"
    if readiness is None:
        return "⚪"
    if readiness >= 85.0:
        return "🟢"
    return "🟡"


def format_decision_detail(decision: dict) -> str:
    """Render a single decision as a multi-line markdown card."""
    title = decision.get("title", "(Tidak ada judul)")
    status = decision.get("status", "unknown")
    readiness = decision.get("readiness_score")
    corp_score = decision.get("corporate_score")
    reg_score = decision.get("regional_score")
    initiative = decision.get("initiative_type", "—")
    value_idr = decision.get("estimated_value_idr")
    locked_at = decision.get("locked_at")
    is_locked = status == "bjr_locked" or locked_at is not None

    emoji = _state_emoji(status, is_locked, readiness)
    lines = [
        f"{emoji} **{title}**",
        f"Status: `{status}` • Initiative: `{initiative}`",
    ]
    if readiness is not None:
        reg_str = f"{reg_score:.0f}" if reg_score is not None else "—"
        corp_str = f"{corp_score:.0f}" if corp_score is not None else "—"
        lines.append(
            f"Readiness: **{readiness:.0f}/100** (Corporate: {corp_str}, Regional: {reg_str})"
        )
    if value_idr:
        lines.append(f"Estimated value: {_format_idr(value_idr)}")
    if is_locked and locked_at:
        lines.append(f"🔒 Locked at: {locked_at}")
    return "\n".join(lines)


def format_decision_list(result: dict, personalized_for: str | None = None) -> str:
    """Render a list of decisions as a compact markdown list."""
    items = result.get("items", [])
    total = result.get("total", len(items))

    if not items:
        suffix = f" untuk {personalized_for}" if personalized_for else ""
        return f"Tidak ada decision ditemukan{suffix}."

    header_suffix = f" milik {personalized_for}" if personalized_for else ""
    header = f"**{total} decision**{header_suffix}:\n"
    rows: list[str] = [header]
    for d in items:
        status = d.get("status", "")
        readiness = d.get("readiness_score")
        emoji = _state_emoji(status, status == "bjr_locked", readiness)
        r_str = f"{readiness:.0f}/100" if readiness is not None else "—"
        did = d.get("id", "?")
        rows.append(
            f"- {emoji} `{did[:8]}` — **{d.get('title', '—')}** "
            f"(readiness {r_str}, status `{status or '?'}`)"
        )
    return "\n".join(rows)


CRITICAL_ITEMS = frozenset({"PD-03-RKAB", "PD-05-COI", "D-06-QUORUM", "D-11-DISCLOSE"})


def format_readiness_card(readiness: dict) -> str:
    """Render readiness score + missing/flagged items as a chat card."""
    score = readiness.get("readiness_score")
    corp = readiness.get("corporate_score")
    reg = readiness.get("regional_score")
    unlockable = readiness.get("gate_5_unlockable", False)
    flagged_critical = readiness.get("critical_items_flagged", [])
    missing = readiness.get("missing_items", [])

    emoji = "🟢" if unlockable else "🟡"
    score_str = f"{score:.0f}" if score is not None else "—"
    corp_str = f"{corp:.0f}" if corp is not None else "—"
    reg_str = f"{reg:.0f}" if reg is not None else "—"
    lines = [
        f"{emoji} **BJR Readiness: {score_str}/100**",
        f"Corporate: {corp_str} • Regional: {reg_str}  (min = readiness)",
    ]
    if unlockable:
        lines.append("✅ **Gate 5 siap dibuka (ready)** — both regimes ≥ 85, no CRITICAL flagged.")
    else:
        lines.append("🔒 **Gate 5 belum bisa dibuka.**")
        if flagged_critical:
            flagged_str = ", ".join(f"`{c}`" for c in flagged_critical)
            lines.append(f"  🚨 CRITICAL items flagged: {flagged_str}")
        if missing:
            top_missing = [f"`{c}`" for c in missing[:5]]
            extra = f" (+{len(missing) - 5} more)" if len(missing) > 5 else ""
            lines.append(f"  ⚠ Missing items: {', '.join(top_missing)}{extra}")
    return "\n".join(lines)


_ITEM_STATUS_EMOJI = {
    "satisfied": "✓",
    "flagged": "⚠",
    "not_started": "○",
    "in_progress": "…",
}


def format_checklist_summary(checklist: dict) -> str:
    """Render the 16-item checklist grouped by phase."""
    items = checklist.get("items", [])
    by_phase: dict[str, list[dict]] = {
        "pre-decision": [],
        "decision": [],
        "post-decision": [],
    }
    for item in items:
        phase = (item.get("phase") or "").lower()
        if phase in by_phase:
            by_phase[phase].append(item)

    lines = ["**16-item BJR checklist:**"]
    for phase, title in [
        ("pre-decision", "Pre-decision"),
        ("decision", "Decision"),
        ("post-decision", "Post-decision"),
    ]:
        phase_items = by_phase[phase]
        if not phase_items:
            continue
        satisfied_count = sum(1 for it in phase_items if it.get("status") == "satisfied")
        lines.append(f"\n**{title}** — {satisfied_count}/{len(phase_items)} satisfied")
        for it in phase_items:
            code = it.get("code", "?")
            status = it.get("status", "unknown")
            emoji = _ITEM_STATUS_EMOJI.get(status, "?")
            marker = "  🚨 CRITICAL" if code in CRITICAL_ITEMS and status == "flagged" else ""
            lines.append(f"  {emoji} `{code}` ({status}){marker}")
    return "\n".join(lines)


def format_document_indicators(indicators: list[dict]) -> str:
    """Render per-document BJR indicators as a chat card.

    Returns empty string if the list is empty — chat response stays silent
    when a document has no BJR context (spec § 5.2).
    """
    if not indicators:
        return ""

    lines = [f"\nSupports {len(indicators)} strategic decision(s):"]
    for ind in indicators[:5]:
        is_locked = ind.get("is_locked", False)
        readiness = ind.get("readiness_score")
        emoji = _state_emoji(ind.get("status", ""), is_locked, readiness)
        title = ind.get("decision_title", "(untitled)")

        if is_locked:
            locked_at = ind.get("locked_at") or ""
            r_disp = f"{readiness:.0f}/100" if readiness is not None else "—"
            lines.append(f"\n  {emoji} **{title}**")
            lines.append(f"     readiness {r_disp} • LOCKED {locked_at[:10]}")
        else:
            r_str = f"{readiness:.0f}/100" if readiness is not None else "—"
            lines.append(f"\n  {emoji} **{title}**")
            lines.append(f"     readiness {r_str} • status `{ind.get('status', '?')}`")

        sat = ind.get("satisfied_items", [])
        missing = ind.get("missing_items", [])
        if sat:
            sat_str = " ".join(f"`{c}` ✓" for c in sat[:4])
            extra = f" (+{len(sat) - 4} more)" if len(sat) > 4 else ""
            lines.append(f"     Satisfies: {sat_str}{extra}")
        if missing:
            miss_str = " ".join(f"`{c}` ⚠" for c in missing[:4])
            extra = f" (+{len(missing) - 4} more)" if len(missing) > 4 else ""
            lines.append(f"     Missing:   {miss_str}{extra}")

    if len(indicators) > 5:
        lines.append(f"\n_(+{len(indicators) - 5} more decision(s) — ask for details)_")
    return "\n".join(lines)


def format_decision_evidence(payload: dict) -> str:
    """Render decision -> evidence list grouped by evidence type."""
    items: list[dict] = payload.get("evidence", [])
    if not items:
        return "Belum ada evidence terhubung ke decision ini."

    by_type: dict[str, list[dict]] = {}
    for ev in items:
        by_type.setdefault(ev.get("evidence_type", "other"), []).append(ev)

    lines = ["**Evidence untuk decision ini:**"]
    for ev_type, evs in by_type.items():
        lines.append(f"\n**{ev_type}** ({len(evs)}):")
        for ev in evs:
            sat = ev.get("satisfies_items", [])
            sat_str = " ".join(f"`{c}`" for c in sat) if sat else "_(belum dipetakan ke item)_"
            lines.append(f"  - **{ev.get('title', '—')}** — {sat_str}")
    return "\n".join(lines)
