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
