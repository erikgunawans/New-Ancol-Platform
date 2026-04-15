#!/usr/bin/env python3
"""Upload chunked regulation JSON to Vertex AI Search datastore.

Reads JSONL chunk files and imports them into a Vertex AI Search datastore
as structured documents with metadata for filtering.

Usage:
    python upload_to_vertex_search.py --chunks-dir ../internal/chunks ../external/chunks
    python upload_to_vertex_search.py --all

Environment:
    GCP_PROJECT: GCP project ID (default: ancol-mom-compliance)
    GCP_REGION: GCP region (default: asia-southeast2)
    VERTEX_SEARCH_DATASTORE_ID: Datastore ID (default: regulatory-corpus)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from google.api_core.client_options import ClientOptions
from google.cloud import discoveryengine_v1 as discoveryengine


def get_client(region: str) -> discoveryengine.DocumentServiceClient:
    """Create Discovery Engine document service client."""
    client_options = ClientOptions(api_endpoint=f"{region}-discoveryengine.googleapis.com")
    return discoveryengine.DocumentServiceClient(client_options=client_options)


def upload_chunks(
    project: str,
    region: str,
    datastore_id: str,
    chunks_dirs: list[Path],
    dry_run: bool = False,
) -> dict:
    """Upload all JSONL chunk files to Vertex AI Search.

    Each chunk becomes a document in the datastore with:
      - document_id: chunk UUID
      - struct_data: full chunk metadata + content
    """
    client = get_client(region)

    parent = (
        f"projects/{project}/locations/{region}"
        f"/collections/default_collection/dataStores/{datastore_id}"
        f"/branches/default_branch"
    )

    stats = {
        "files_processed": 0,
        "documents_uploaded": 0,
        "documents_failed": 0,
        "regulations": [],
    }

    for chunks_dir in chunks_dirs:
        if not chunks_dir.exists():
            print(f"  SKIP {chunks_dir}: directory not found")
            continue

        for jsonl_path in sorted(chunks_dir.glob("*.jsonl")):
            if jsonl_path.name.startswith("_"):
                continue

            reg_chunks = []
            with open(jsonl_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        reg_chunks.append(json.loads(line))

            if not reg_chunks:
                continue

            reg_id = reg_chunks[0].get("regulation_id", jsonl_path.stem)
            print(f"  {reg_id}: {len(reg_chunks)} chunks...", end=" ")

            uploaded = 0
            failed = 0

            for chunk in reg_chunks:
                doc_id = chunk["id"]

                # Build struct data for Vertex AI Search
                struct_data = {
                    "regulation_id": chunk["regulation_id"],
                    "title": chunk["title"],
                    "source_type": chunk["source_type"],
                    "domain": chunk["domain"],
                    "effective_date": chunk["effective_date"],
                    "version": chunk["version"],
                    "article_number": chunk["article_number"],
                    "article_title": chunk["article_title"],
                    "content": chunk["content"],
                    "language": chunk["language"],
                }

                if chunk.get("expiry_date"):
                    struct_data["expiry_date"] = chunk["expiry_date"]

                if dry_run:
                    uploaded += 1
                    continue

                try:
                    document = discoveryengine.Document(
                        id=doc_id,
                        struct_data=struct_data,
                    )

                    client.create_document(
                        parent=parent,
                        document=document,
                        document_id=doc_id,
                    )
                    uploaded += 1
                except Exception as e:
                    if "ALREADY_EXISTS" in str(e):
                        # Update existing document
                        try:
                            document = discoveryengine.Document(
                                name=f"{parent}/documents/{doc_id}",
                                struct_data=struct_data,
                            )
                            client.update_document(document=document)
                            uploaded += 1
                        except Exception as update_err:
                            print(f"\n    FAIL update {doc_id}: {update_err}")
                            failed += 1
                    else:
                        print(f"\n    FAIL {doc_id}: {e}")
                        failed += 1

                # Rate limiting
                time.sleep(0.1)

            status = "OK" if failed == 0 else f"{failed} FAILED"
            print(f"{uploaded} uploaded ({status})")

            stats["files_processed"] += 1
            stats["documents_uploaded"] += uploaded
            stats["documents_failed"] += failed
            stats["regulations"].append(
                {
                    "regulation_id": reg_id,
                    "chunks": len(reg_chunks),
                    "uploaded": uploaded,
                    "failed": failed,
                }
            )

    return stats


def main():
    parser = argparse.ArgumentParser(description="Upload regulation chunks to Vertex AI Search")
    parser.add_argument(
        "--chunks-dir", type=Path, nargs="+", help="Directories containing .jsonl files"
    )
    parser.add_argument(
        "--all", action="store_true", help="Upload from both internal/chunks and external/chunks"
    )
    parser.add_argument("--project", default="ancol-mom-compliance", help="GCP project ID")
    parser.add_argument("--region", default="asia-southeast2", help="GCP region")
    parser.add_argument(
        "--datastore-id", default="regulatory-corpus", help="Vertex AI Search datastore ID"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Parse and validate without uploading"
    )
    args = parser.parse_args()

    corpus_root = Path(__file__).parent.parent

    if args.all:
        chunks_dirs = [
            corpus_root / "internal" / "chunks",
            corpus_root / "external" / "chunks",
        ]
    elif args.chunks_dir:
        chunks_dirs = args.chunks_dir
    else:
        parser.print_help()
        sys.exit(1)

    mode = "DRY RUN" if args.dry_run else "LIVE"
    print(f"\nUploading to Vertex AI Search [{mode}]")
    print(f"  Project: {args.project}")
    print(f"  Region: {args.region}")
    print(f"  Datastore: {args.datastore_id}")
    print()

    stats = upload_chunks(
        project=args.project,
        region=args.region,
        datastore_id=args.datastore_id,
        chunks_dirs=chunks_dirs,
        dry_run=args.dry_run,
    )

    print(f"\nDone: {stats['documents_uploaded']} uploaded, {stats['documents_failed']} failed")

    if args.dry_run:
        print("(dry run — no documents were actually uploaded)")


if __name__ == "__main__":
    main()
