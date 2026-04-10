"""Shared utilities used across multiple services."""

from __future__ import annotations

import re
from functools import lru_cache

from google.cloud import storage

# ── Constants ──

SYSTEM_USER_ID = "a0000000-0000-0000-0000-000000000001"

EXTENSION_TO_FORMAT: dict[str, str] = {
    "pdf": "pdf",
    "doc": "word",
    "docx": "word",
    "png": "image",
    "jpg": "image",
    "jpeg": "image",
    "tiff": "scan",
    "tif": "scan",
}


# ── Indonesian Date Parsing ──

_MONTHS_ID: dict[str, str] = {
    "januari": "01",
    "februari": "02",
    "maret": "03",
    "april": "04",
    "mei": "05",
    "juni": "06",
    "juli": "07",
    "agustus": "08",
    "september": "09",
    "oktober": "10",
    "november": "11",
    "desember": "12",
}

_ID_DATE_RE = re.compile(
    r"(\d{1,2})\s+(" + "|".join(_MONTHS_ID.keys()) + r")\s+(\d{4})",
    re.IGNORECASE,
)

_ISO_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


def parse_indonesian_date(text: str) -> str | None:
    """Parse a date string containing Indonesian or ISO date to YYYY-MM-DD.

    Handles:
    - "15 Januari 2026" → "2026-01-15"
    - "2026-01-15" → "2026-01-15"
    - Embedded dates in longer text
    """
    # Try Indonesian format first
    match = _ID_DATE_RE.search(text)
    if match:
        day = match.group(1).zfill(2)
        month = _MONTHS_ID.get(match.group(2).lower(), "01")
        year = match.group(3)
        return f"{year}-{month}-{day}"

    # Fall back to ISO
    iso_match = _ISO_DATE_RE.search(text)
    return iso_match.group(1) if iso_match else None


# ── GCS Helpers ──


def parse_gcs_uri(uri: str) -> tuple[str, str]:
    """Parse a gs:// URI into (bucket_name, blob_path)."""
    stripped = uri.removeprefix("gs://")
    parts = stripped.split("/", 1)
    return parts[0], parts[1] if len(parts) > 1 else ""


@lru_cache
def get_gcs_client() -> storage.Client:
    """Get or create a singleton GCS client."""
    return storage.Client()


def detect_document_format(filename: str) -> str:
    """Detect document format from filename extension."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return EXTENSION_TO_FORMAT.get(ext, "pdf")
