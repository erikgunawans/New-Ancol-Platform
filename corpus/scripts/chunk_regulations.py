#!/usr/bin/env python3
"""Regulation Chunking Script.

Processes regulation source files (structured Markdown) into chunked JSON
documents ready for Vertex AI Search ingestion.

Each chunk contains:
  - regulation_id: Unique identifier (e.g., "UU-PT-40-2007")
  - title: Full regulation title
  - source_type: "external" or "internal"
  - domain: Compliance domain (e.g., "corporate_governance")
  - effective_date: ISO date string
  - version: Integer version
  - article_number: Article/pasal identifier
  - article_title: Article heading
  - content: The article text content
  - chunk_index: Sequential index within this regulation
  - language: "id" for Bahasa Indonesia

Usage:
    python chunk_regulations.py --input-dir ../internal --output-dir ../internal/chunks
    python chunk_regulations.py --input-dir ../external --output-dir ../external/chunks
    python chunk_regulations.py --all  # Process both internal and external
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class RegulationMetadata:
    """Metadata extracted from regulation file frontmatter."""

    regulation_id: str = ""
    title: str = ""
    source_type: str = ""  # external or internal
    domain: str = ""
    effective_date: str = ""
    expiry_date: str | None = None
    version: int = 1
    language: str = "id"


@dataclass
class RegulationChunk:
    """A single chunk of a regulation, ready for indexing."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    regulation_id: str = ""
    title: str = ""
    source_type: str = ""
    domain: str = ""
    effective_date: str = ""
    expiry_date: str | None = None
    version: int = 1
    article_number: str = ""
    article_title: str = ""
    content: str = ""
    chunk_index: int = 0
    language: str = "id"


def parse_frontmatter(text: str) -> tuple[RegulationMetadata, str]:
    """Parse YAML-like frontmatter from regulation file.

    Expected format:
    ---
    regulation_id: UU-PT-40-2007
    title: ...
    ---
    (body content)
    """
    meta = RegulationMetadata()

    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text, re.DOTALL)
    if not match:
        return meta, text

    frontmatter = match.group(1)
    body = match.group(2)

    for line in frontmatter.strip().split("\n"):
        line = line.strip()
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key == "regulation_id":
            meta.regulation_id = value
        elif key == "title":
            meta.title = value
        elif key == "source_type":
            meta.source_type = value
        elif key == "domain":
            meta.domain = value
        elif key == "effective_date":
            meta.effective_date = value
        elif key == "expiry_date" and value:
            meta.expiry_date = value
        elif key == "version":
            meta.version = int(value)
        elif key == "language":
            meta.language = value

    return meta, body


def chunk_by_articles(body: str) -> list[tuple[str, str, str]]:
    """Split regulation body into article-level chunks.

    Recognizes patterns:
      ## Pasal 98 — Rapat Direksi
      ## Pasal 98
      ## Article 98 — Board Meetings
      ## Bagian 1: Ketentuan Umum
      ## BAB III — DIREKSI

    Returns list of (article_number, article_title, content).
    """
    # Split on markdown H2 headers that look like articles
    pattern = re.compile(
        r"^##\s+"
        r"(?:Pasal|Article|Bagian|BAB|Section|Ketentuan)\s+"
        r"([^\n—–-]+)"
        r"(?:\s*[—–-]\s*([^\n]*))?"
        r"\s*$",
        re.MULTILINE | re.IGNORECASE,
    )

    chunks = []
    matches = list(pattern.finditer(body))

    if not matches:
        # No article structure found — treat entire body as one chunk
        clean_body = body.strip()
        if clean_body:
            chunks.append(("full", "Full Text", clean_body))
        return chunks

    # Content before first article (preamble)
    preamble = body[: matches[0].start()].strip()
    if preamble:
        chunks.append(("preamble", "Pendahuluan", preamble))

    for i, match in enumerate(matches):
        article_number = match.group(1).strip()
        article_title = match.group(2).strip() if match.group(2) else ""

        # Content extends to next article or end of file
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        content = body[start:end].strip()

        if content:
            chunks.append((article_number, article_title, content))

    return chunks


def process_file(
    file_path: Path, meta_override: RegulationMetadata | None = None
) -> list[RegulationChunk]:
    """Process a single regulation file into chunks."""
    text = file_path.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(text)

    if meta_override:
        for k, v in asdict(meta_override).items():
            if v and not getattr(meta, k):
                setattr(meta, k, v)

    if not meta.regulation_id:
        meta.regulation_id = file_path.stem.upper().replace(" ", "-")

    if not meta.source_type:
        meta.source_type = "internal" if "internal" in str(file_path) else "external"

    articles = chunk_by_articles(body)
    chunks = []

    for i, (article_num, article_title, content) in enumerate(articles):
        chunk = RegulationChunk(
            regulation_id=meta.regulation_id,
            title=meta.title,
            source_type=meta.source_type,
            domain=meta.domain,
            effective_date=meta.effective_date,
            expiry_date=meta.expiry_date,
            version=meta.version,
            article_number=article_num,
            article_title=article_title,
            content=content,
            chunk_index=i,
            language=meta.language,
        )
        chunks.append(chunk)

    return chunks


def process_directory(input_dir: Path, output_dir: Path) -> dict:
    """Process all regulation files in a directory."""
    output_dir.mkdir(parents=True, exist_ok=True)
    stats = {"files_processed": 0, "total_chunks": 0, "regulations": []}

    for file_path in sorted(input_dir.glob("*.md")):
        if file_path.name.startswith("_") or file_path.name == "README.md":
            continue

        chunks = process_file(file_path)
        if not chunks:
            print(f"  SKIP {file_path.name}: no chunks extracted")
            continue

        reg_id = chunks[0].regulation_id

        # Write chunks as JSONL (one JSON per line — Vertex AI Search format)
        output_file = output_dir / f"{reg_id}.jsonl"
        with open(output_file, "w", encoding="utf-8") as f:
            for chunk in chunks:
                f.write(json.dumps(asdict(chunk), ensure_ascii=False) + "\n")

        stats["files_processed"] += 1
        stats["total_chunks"] += len(chunks)
        stats["regulations"].append(
            {
                "regulation_id": reg_id,
                "title": chunks[0].title,
                "chunks": len(chunks),
                "source": str(file_path.name),
            }
        )
        print(f"  {file_path.name} → {len(chunks)} chunks → {output_file.name}")

    # Write manifest
    manifest_path = output_dir / "_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)

    return stats


def main():
    parser = argparse.ArgumentParser(description="Chunk regulations into Vertex AI Search format")
    parser.add_argument("--input-dir", type=Path, help="Directory containing regulation .md files")
    parser.add_argument("--output-dir", type=Path, help="Directory for output .jsonl chunks")
    parser.add_argument("--all", action="store_true", help="Process both internal/ and external/")
    args = parser.parse_args()

    corpus_root = Path(__file__).parent.parent

    if args.all:
        dirs = [
            (corpus_root / "internal", corpus_root / "internal" / "chunks"),
            (corpus_root / "external", corpus_root / "external" / "chunks"),
        ]
    elif args.input_dir:
        output = args.output_dir or args.input_dir / "chunks"
        dirs = [(args.input_dir, output)]
    else:
        parser.print_help()
        sys.exit(1)

    total_stats = {"files_processed": 0, "total_chunks": 0}

    for input_dir, output_dir in dirs:
        print(f"\nProcessing {input_dir}...")
        stats = process_directory(input_dir, output_dir)
        total_stats["files_processed"] += stats["files_processed"]
        total_stats["total_chunks"] += stats["total_chunks"]

    print(f"\nDone: {total_stats['files_processed']} files → {total_stats['total_chunks']} chunks")


if __name__ == "__main__":
    main()
