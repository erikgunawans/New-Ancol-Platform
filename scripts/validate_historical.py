#!/usr/bin/env python3
"""Pre-flight validation for historical MoM bulk upload CSV manifest.

Checks:
- CSV structure (required columns: filename, file_path, meeting_date, mom_type)
- File existence on local disk
- Valid document format (pdf, doc, docx, png, jpg, jpeg, tiff, tif)
- Meeting date format (YYYY-MM-DD)
- Duplicate filename detection

Usage:
    python scripts/validate_historical.py manifest.csv
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

# Add shared package to path
_COMMON_PATH = str(Path(__file__).resolve().parent.parent / "packages" / "ancol-common" / "src")
sys.path.insert(0, _COMMON_PATH)

from ancol_common.utils import EXTENSION_TO_FORMAT  # noqa: E402

REQUIRED_COLUMNS = {"filename", "file_path", "meeting_date", "mom_type"}
VALID_MOM_TYPES = {"regular", "extraordinary", "circular"}
DATE_PATTERN = __import__("re").compile(r"^\d{4}-\d{2}-\d{2}$")


def validate(manifest_path: str) -> list[str]:
    """Validate manifest CSV and return list of errors."""
    errors: list[str] = []
    path = Path(manifest_path)

    if not path.exists():
        return [f"Manifest file not found: {manifest_path}"]

    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        if reader.fieldnames is None:
            return ["Empty CSV file or missing header row"]

        missing_cols = REQUIRED_COLUMNS - set(reader.fieldnames)
        if missing_cols:
            return [f"Missing required columns: {', '.join(sorted(missing_cols))}"]

        seen_filenames: dict[str, int] = {}
        for row_num, row in enumerate(reader, start=2):
            filename = row["filename"].strip()
            file_path = row["file_path"].strip()
            meeting_date = row["meeting_date"].strip()
            mom_type = row["mom_type"].strip()

            # Check file exists
            if not Path(file_path).exists():
                errors.append(f"Row {row_num}: File not found: {file_path}")

            # Check valid extension
            ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
            if ext not in EXTENSION_TO_FORMAT:
                errors.append(
                    f"Row {row_num}: Unsupported format '{ext}' for {filename}. "
                    f"Allowed: {', '.join(sorted(EXTENSION_TO_FORMAT.keys()))}"
                )

            # Check date format
            if not DATE_PATTERN.match(meeting_date):
                errors.append(
                    f"Row {row_num}: Invalid date format '{meeting_date}', expected YYYY-MM-DD"
                )

            # Check mom_type
            if mom_type not in VALID_MOM_TYPES:
                errors.append(
                    f"Row {row_num}: Invalid mom_type '{mom_type}'. "
                    f"Allowed: {', '.join(sorted(VALID_MOM_TYPES))}"
                )

            # Check duplicates
            if filename in seen_filenames:
                errors.append(
                    f"Row {row_num}: Duplicate filename '{filename}' "
                    f"(first seen row {seen_filenames[filename]})"
                )
            else:
                seen_filenames[filename] = row_num

    return errors


def main() -> None:
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <manifest.csv>")
        sys.exit(1)

    errors = validate(sys.argv[1])
    if errors:
        print(f"VALIDATION FAILED — {len(errors)} error(s):\n")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)
    else:
        print("VALIDATION PASSED — manifest is ready for upload.")


if __name__ == "__main__":
    main()
