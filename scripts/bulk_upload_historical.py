#!/usr/bin/env python3
"""Bulk upload historical MoMs from a CSV manifest to GCS and register via API.

Reads a validated CSV manifest (filename, file_path, meeting_date, mom_type),
uploads each file to the GCS raw bucket under historical/<uuid>/<filename>,
and outputs a JSON records file for batch registration via the API Gateway.

Usage:
    python scripts/bulk_upload_historical.py manifest.csv \
        --bucket ancol-mom-raw-dev --output records.json

Prerequisites:
    - Run validate_historical.py first
    - Authenticated to GCP (gcloud auth application-default login)
    - pip install google-cloud-storage
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import uuid
from pathlib import Path

# Add shared package to path
_COMMON_PATH = str(Path(__file__).resolve().parent.parent / "packages" / "ancol-common" / "src")
sys.path.insert(0, _COMMON_PATH)

from ancol_common.utils import SYSTEM_USER_ID, detect_document_format, get_gcs_client  # noqa: E402

_EXTENSION_TO_CONTENT_TYPE: dict[str, str] = {
    "pdf": "application/pdf",
    "doc": "application/msword",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "tiff": "image/tiff",
    "tif": "image/tiff",
}


def upload_manifest(
    manifest_path: str,
    bucket_name: str,
    output_path: str,
    dry_run: bool = False,
) -> None:
    """Upload all files from manifest to GCS and write records JSON."""
    client = get_gcs_client()
    bucket = client.bucket(bucket_name)
    records: list[dict] = []

    with Path(manifest_path).open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    total = len(rows)
    print(f"Uploading {total} documents to gs://{bucket_name}/historical/")

    for i, row in enumerate(rows, start=1):
        filename = row["filename"].strip()
        file_path = row["file_path"].strip()
        meeting_date = row["meeting_date"].strip()
        mom_type = row["mom_type"].strip()

        doc_id = str(uuid.uuid4())
        doc_format = detect_document_format(filename)
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "pdf"
        content_type = _EXTENSION_TO_CONTENT_TYPE.get(ext, "application/pdf")

        blob_name = f"historical/{doc_id}/{filename}"
        gcs_uri = f"gs://{bucket_name}/{blob_name}"
        file_size = Path(file_path).stat().st_size

        if dry_run:
            print(f"  [{i}/{total}] DRY RUN: {filename} -> {gcs_uri}")
        else:
            blob = bucket.blob(blob_name)
            blob.metadata = {
                "document_id": doc_id,
                "source": "historical-bulk-upload",
            }
            blob.upload_from_filename(file_path, content_type=content_type)
            print(f"  [{i}/{total}] Uploaded: {filename} -> {gcs_uri}")

        records.append(
            {
                "document_id": doc_id,
                "filename": filename,
                "format": doc_format,
                "file_size_bytes": file_size,
                "gcs_raw_uri": gcs_uri,
                "mom_type": mom_type,
                "meeting_date": meeting_date,
                "source": "historical-bulk-upload",
                "uploaded_by": SYSTEM_USER_ID,
            }
        )

    with open(output_path, "w", encoding="utf-8") as out:
        json.dump(records, out, indent=2, ensure_ascii=False)

    print(f"\nDone. {len(records)} records written to {output_path}")
    print(f"Next: POST {output_path} to API Gateway /api/batch/register-documents")


def main() -> None:
    parser = argparse.ArgumentParser(description="Bulk upload historical MoMs to GCS")
    parser.add_argument("manifest", help="Path to validated CSV manifest")
    parser.add_argument("--bucket", required=True, help="GCS raw bucket name")
    parser.add_argument("--output", default="records.json", help="Output JSON records file")
    parser.add_argument("--dry-run", action="store_true", help="Validate without uploading")
    args = parser.parse_args()

    upload_manifest(args.manifest, args.bucket, args.output, args.dry_run)


if __name__ == "__main__":
    main()
