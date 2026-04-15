#!/usr/bin/env python3
"""Seed Spanner Graph with regulation data from corpus.

Reads regulation source files (structured Markdown with YAML frontmatter) and
pre-chunked JSONL files from corpus/external/ and corpus/internal/, then
inserts nodes and edges into the Spanner-backed RegulationGraph.

Relationship detection:
  - AMENDS:     text mentions "mengubah" or "amandemen" of another regulation
  - SUPERSEDES: text mentions "menggantikan" or "mencabut" of another regulation
  - REFERENCES: text cites another regulation by ID pattern

Domain detection (keyword-based):
  - quorum, conflict_of_interest, reporting, signatures, governance, rpt

Usage:
    python corpus/scripts/seed_regulation_graph.py \\
        --instance ancol-regulation-graph \\
        --database ancol-regulations \\
        --project ancol-mom-compliance

    python corpus/scripts/seed_regulation_graph.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class RegulationNode:
    """A regulation to insert into the Regulations table."""

    id: str
    title: str
    issuer: str
    effective_date: str | None
    status: str
    authority_level: int


@dataclass
class ClauseNode:
    """A clause (article) to insert into the Clauses table."""

    id: str
    regulation_id: str
    clause_number: str
    text_summary: str
    domain: str


@dataclass
class Edge:
    """Generic edge between two nodes."""

    table: str
    columns: dict[str, str]


@dataclass
class GraphData:
    """Aggregated data ready for Spanner insertion."""

    regulations: list[RegulationNode] = field(default_factory=list)
    clauses: list[ClauseNode] = field(default_factory=list)
    domains: set[str] = field(default_factory=set)
    regulation_domains: list[dict[str, str]] = field(default_factory=list)
    clause_domains: list[dict[str, str]] = field(default_factory=list)
    amends: list[dict[str, str]] = field(default_factory=list)
    supersedes: list[dict[str, str]] = field(default_factory=list)
    references: list[dict[str, str]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CORPUS_ROOT = Path(__file__).resolve().parent.parent

# Map issuer prefixes to human-readable names and authority levels.
# Authority levels: 1 = law (UU), 2 = government regulation (PP),
# 3 = OJK regulation (POJK), 4 = ministerial (Permen), 5 = exchange (IDX),
# 6 = internal policy
ISSUER_MAP: dict[str, tuple[str, int]] = {
    "UU": ("DPR RI", 1),
    "PP": ("Pemerintah RI", 2),
    "POJK": ("OJK", 3),
    "PERMEN": ("Kementerian", 4),
    "IDX": ("BEI", 5),
}

# Keywords for domain detection on clause content
DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "quorum": [
        "kuorum",
        "quorum",
        "lebih dari 1/2",
        "satu per dua",
        "jumlah anggota",
        "hadir atau diwakili",
    ],
    "conflict_of_interest": [
        "benturan kepentingan",
        "conflict of interest",
        "kepentingan ekonomis pribadi",
        "afiliasi",
        "transaksi benturan",
    ],
    "reporting": [
        "pelaporan",
        "laporan tahunan",
        "laporan keuangan",
        "annual report",
        "wajib menyampaikan laporan",
        "pengungkapan",
        "keterbukaan informasi",
    ],
    "signatures": [
        "ditandatangani",
        "tanda tangan",
        "risalah rapat",
        "menandatangani",
        "penandatanganan",
    ],
    "governance": [
        "tata kelola",
        "good corporate governance",
        "gcg",
        "komisaris independen",
        "komite audit",
        "organ perseroan",
        "pengawasan",
    ],
    "rpt": [
        "transaksi afiliasi",
        "transaksi pihak berelasi",
        "related party",
        "pihak berelasi",
        "transaksi material",
    ],
}

# Patterns that identify regulation IDs in free text
REGULATION_ID_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"UU[\s-]*(?:No\.?\s*)?(\d+)[\s/]*(?:Tahun\s*)?(\d{4})", re.IGNORECASE),
    re.compile(r"PP[\s-]*(?:No\.?\s*)?(\d+)[\s/]*(?:Tahun\s*)?(\d{4})", re.IGNORECASE),
    re.compile(
        r"POJK[\s-]*(?:No\.?\s*)?(\d+)/POJK\.\d+/(\d{4})",
        re.IGNORECASE,
    ),
    re.compile(
        r"Permen[\s-]*ATR[\s/]*(?:BPN\s*)?(?:No\.?\s*)?(\d+)[\s/]*(?:Tahun\s*)?(\d{4})",
        re.IGNORECASE,
    ),
    re.compile(r"IDX[\s-]*([A-Z0-9-]+)", re.IGNORECASE),
]


# ---------------------------------------------------------------------------
# Frontmatter parsing (reuses pattern from chunk_regulations.py)
# ---------------------------------------------------------------------------


def parse_frontmatter(text: str) -> dict[str, str]:
    """Extract YAML-like frontmatter from a markdown file."""
    meta: dict[str, str] = {}
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not match:
        # Some files use **Key:** Value format instead
        for line in text.split("\n")[:10]:
            kv = re.match(r"\*\*(.+?):\*\*\s*(.+)", line)
            if kv:
                key = kv.group(1).strip().lower().replace(" ", "_")
                meta[key] = kv.group(2).strip()
        return meta

    for line in match.group(1).strip().split("\n"):
        line = line.strip()
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        meta[key.strip()] = value.strip().strip("\"'")

    return meta


def detect_issuer(regulation_id: str) -> tuple[str, int]:
    """Derive issuer name and authority level from regulation ID prefix."""
    for prefix, (issuer, level) in ISSUER_MAP.items():
        if regulation_id.upper().startswith(prefix):
            return issuer, level
    # Internal documents (ADART, BOD-CHARTER, etc.)
    return "PT Pembangunan Jaya Ancol Tbk", 6


def detect_clause_domains(text: str) -> list[str]:
    """Detect compliance domains from clause text content."""
    text_lower = text.lower()
    detected: list[str] = []
    for domain, keywords in DOMAIN_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in text_lower:
                detected.append(domain)
                break
    return detected


def normalize_regulation_id(raw: str) -> str:
    """Normalize a regulation ID to the canonical form used in filenames."""
    # Remove extra whitespace and standardize separators
    raw = raw.strip().upper()
    raw = re.sub(r"\s+", "-", raw)
    # UU No. 40 Tahun 2007 -> UU-PT-40-2007  (special case: the PT law)
    # POJK No. 33/POJK.04/2014 -> POJK-33-2014
    raw = re.sub(r"/POJK\.\d+/", "-", raw)
    raw = re.sub(r"NO\.?-?", "", raw)
    raw = re.sub(r"TAHUN-?", "", raw)
    raw = re.sub(r"--+", "-", raw)
    return raw.strip("-")


# ---------------------------------------------------------------------------
# Relationship detection
# ---------------------------------------------------------------------------

AMEND_PATTERNS = [
    re.compile(r"mengubah\s+(?:ketentuan\s+)?(?:dalam\s+)?(.*?)(?:\.|,|;)", re.IGNORECASE),
    re.compile(r"amandemen\s+(?:atas\s+|terhadap\s+)?(.*?)(?:\.|,|;)", re.IGNORECASE),
    re.compile(r"perubahan\s+(?:atas\s+)?(.*?)(?:\.|,|;)", re.IGNORECASE),
]

SUPERSEDE_PATTERNS = [
    re.compile(r"menggantikan\s+(.*?)(?:\.|,|;)", re.IGNORECASE),
    re.compile(r"mencabut\s+(.*?)(?:\.|,|;)", re.IGNORECASE),
    re.compile(
        r"tidak\s+berlaku\s+lagi.*?(?:digantikan|dicabut)\s+(?:oleh\s+)?(.*?)(?:\.|,|;)",
        re.IGNORECASE,
    ),
]


def extract_regulation_ids_from_text(text: str) -> list[str]:
    """Find all regulation ID references in a text fragment."""
    found: list[str] = []
    for pattern in REGULATION_ID_PATTERNS:
        for match in pattern.finditer(text):
            groups = [g for g in match.groups() if g]
            "-".join(groups)
            found.append(normalize_regulation_id(match.group(0)))
    return found


def detect_amends(
    full_text: str,
    source_id: str,
    effective_date: str | None,
) -> list[dict[str, str]]:
    """Detect AMENDS relationships from regulation text."""
    edges: list[dict[str, str]] = []
    for pattern in AMEND_PATTERNS:
        for match in pattern.finditer(full_text):
            fragment = match.group(1)
            target_ids = extract_regulation_ids_from_text(fragment)
            for tid in target_ids:
                if tid != source_id:
                    edges.append(
                        {
                            "source_id": source_id,
                            "target_id": tid,
                            "effective_date": effective_date or "",
                            "change_type": "amendment",
                        }
                    )
    return edges


def detect_supersedes(
    full_text: str,
    source_id: str,
    effective_date: str | None,
) -> list[dict[str, str]]:
    """Detect SUPERSEDES relationships from regulation text."""
    edges: list[dict[str, str]] = []
    for pattern in SUPERSEDE_PATTERNS:
        for match in pattern.finditer(full_text):
            fragment = match.group(1)
            target_ids = extract_regulation_ids_from_text(fragment)
            for tid in target_ids:
                if tid != source_id:
                    edges.append(
                        {
                            "source_id": source_id,
                            "target_id": tid,
                            "effective_date": effective_date or "",
                        }
                    )
    return edges


def detect_references(
    clause_id: str,
    clause_text: str,
    regulation_id: str,
    all_clause_ids: dict[str, str],
) -> list[dict[str, str]]:
    """Detect REFERENCES edges from clause text citing other regulations.

    Args:
        clause_id: ID of the source clause.
        clause_text: Content of the source clause.
        regulation_id: Regulation that owns this clause.
        all_clause_ids: Map of regulation_id -> first clause ID (for linking).
    """
    edges: list[dict[str, str]] = []
    ref_ids = extract_regulation_ids_from_text(clause_text)
    for ref_id in ref_ids:
        if ref_id == regulation_id:
            continue
        target_clause = all_clause_ids.get(ref_id)
        if target_clause:
            edges.append(
                {
                    "source_clause_id": clause_id,
                    "target_clause_id": target_clause,
                    "reference_type": "cites",
                }
            )
    return edges


# ---------------------------------------------------------------------------
# Corpus reading
# ---------------------------------------------------------------------------


def read_regulation_files(corpus_root: Path) -> GraphData:
    """Read all regulation markdown and chunk files, build graph data."""
    data = GraphData()
    # Track first clause per regulation for cross-references
    first_clause: dict[str, str] = {}
    # Collect all clause info for second-pass reference detection
    clause_texts: list[tuple[str, str, str]] = []  # (clause_id, text, reg_id)

    for subdir in ["external", "internal"]:
        source_dir = corpus_root / subdir
        if not source_dir.exists():
            print(f"  SKIP {source_dir}: directory not found")
            continue

        for md_file in sorted(source_dir.glob("*.md")):
            if md_file.name.startswith("_") or md_file.name == "README.md":
                continue

            text = md_file.read_text(encoding="utf-8")
            meta = parse_frontmatter(text)

            reg_id = meta.get("regulation_id", md_file.stem.upper())
            title = meta.get("title", reg_id)
            effective_date = meta.get("effective_date")
            meta.get("source_type", subdir)
            domain = meta.get("domain", "")

            issuer, authority_level = detect_issuer(reg_id)
            status = "active"

            reg_node = RegulationNode(
                id=reg_id,
                title=title,
                issuer=issuer,
                effective_date=effective_date,
                status=status,
                authority_level=authority_level,
            )
            data.regulations.append(reg_node)

            # Add regulation-level domain
            if domain:
                data.domains.add(domain)
                data.regulation_domains.append(
                    {
                        "regulation_id": reg_id,
                        "domain_name": domain,
                        "scope": "primary",
                    }
                )

            # Detect amends/supersedes from full text
            data.amends.extend(detect_amends(text, reg_id, effective_date))
            data.supersedes.extend(detect_supersedes(text, reg_id, effective_date))

            # Read clauses from pre-chunked JSONL if available
            chunks_dir = source_dir / "chunks"
            jsonl_file = chunks_dir / f"{reg_id}.jsonl"
            if jsonl_file.exists():
                _read_clauses_from_jsonl(
                    jsonl_file,
                    reg_id,
                    data,
                    first_clause,
                    clause_texts,
                )
            else:
                # Fall back: extract clauses from markdown H2 headers
                _extract_clauses_from_markdown(
                    text,
                    reg_id,
                    data,
                    first_clause,
                    clause_texts,
                )

    # Second pass: detect cross-regulation REFERENCES at clause level
    for clause_id, clause_text, reg_id in clause_texts:
        refs = detect_references(clause_id, clause_text, reg_id, first_clause)
        data.references.extend(refs)

    return data


def _read_clauses_from_jsonl(
    jsonl_file: Path,
    reg_id: str,
    data: GraphData,
    first_clause: dict[str, str],
    clause_texts: list[tuple[str, str, str]],
) -> None:
    """Read clause nodes from a pre-chunked JSONL file."""
    with open(jsonl_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            chunk = json.loads(line)
            clause_id = chunk.get("id", str(uuid.uuid4()))
            content = chunk.get("content", "")
            article_num = chunk.get("article_number", "")
            chunk.get("article_title", "")

            # Truncate text_summary to 4096 chars (Spanner column limit)
            summary = content[:4096] if content else ""

            clause_domains = detect_clause_domains(content)
            primary_domain = clause_domains[0] if clause_domains else ""

            clause_node = ClauseNode(
                id=clause_id,
                regulation_id=reg_id,
                clause_number=article_num,
                text_summary=summary,
                domain=primary_domain,
            )
            data.clauses.append(clause_node)

            # Track first clause per regulation
            if reg_id not in first_clause:
                first_clause[reg_id] = clause_id

            # Register domains
            for d in clause_domains:
                data.domains.add(d)
                data.clause_domains.append(
                    {
                        "clause_id": clause_id,
                        "domain_name": d,
                    }
                )

            clause_texts.append((clause_id, content, reg_id))


def _extract_clauses_from_markdown(
    text: str,
    reg_id: str,
    data: GraphData,
    first_clause: dict[str, str],
    clause_texts: list[tuple[str, str, str]],
) -> None:
    """Extract clause nodes from markdown H2 article headers."""
    pattern = re.compile(
        r"^##\s+"
        r"(?:Pasal|Article|Bagian|BAB|Section|Ketentuan)\s+"
        r"([^\n\u2014\u2013-]+)"
        r"(?:\s*[\u2014\u2013-]\s*([^\n]*))?"
        r"\s*$",
        re.MULTILINE | re.IGNORECASE,
    )

    matches = list(pattern.finditer(text))
    for i, match in enumerate(matches):
        article_num = match.group(1).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[start:end].strip()

        if not content:
            continue

        clause_id = str(uuid.uuid4())
        summary = content[:4096]

        clause_domains = detect_clause_domains(content)
        primary_domain = clause_domains[0] if clause_domains else ""

        clause_node = ClauseNode(
            id=clause_id,
            regulation_id=reg_id,
            clause_number=article_num,
            text_summary=summary,
            domain=primary_domain,
        )
        data.clauses.append(clause_node)

        if reg_id not in first_clause:
            first_clause[reg_id] = clause_id

        for d in clause_domains:
            data.domains.add(d)
            data.clause_domains.append(
                {
                    "clause_id": clause_id,
                    "domain_name": d,
                }
            )

        clause_texts.append((clause_id, content, reg_id))


# ---------------------------------------------------------------------------
# Spanner insertion
# ---------------------------------------------------------------------------


def insert_to_spanner(
    data: GraphData,
    instance_id: str,
    database_id: str,
    project_id: str,
) -> None:
    """Batch-insert graph data into Spanner."""
    from google.cloud import spanner  # type: ignore[import-untyped]

    client = spanner.Client(project=project_id)
    instance = client.instance(instance_id)
    database = instance.database(database_id)

    def _write(transaction: spanner.Transaction) -> None:  # type: ignore[name-defined]
        # Insert Domains
        if data.domains:
            transaction.insert(
                table="Domains",
                columns=["name"],
                values=[[d] for d in sorted(data.domains)],
            )

        # Insert Regulations
        if data.regulations:
            transaction.insert(
                table="Regulations",
                columns=["id", "title", "issuer", "effective_date", "status", "authority_level"],
                values=[
                    [
                        r.id,
                        r.title,
                        r.issuer,
                        r.effective_date,
                        r.status,
                        r.authority_level,
                    ]
                    for r in data.regulations
                ],
            )

        # Insert Clauses
        if data.clauses:
            transaction.insert(
                table="Clauses",
                columns=["id", "regulation_id", "clause_number", "text_summary", "domain"],
                values=[
                    [c.id, c.regulation_id, c.clause_number, c.text_summary, c.domain]
                    for c in data.clauses
                ],
            )

        # Insert RegulationDomains
        if data.regulation_domains:
            transaction.insert(
                table="RegulationDomains",
                columns=["regulation_id", "domain_name", "scope"],
                values=[
                    [rd["regulation_id"], rd["domain_name"], rd["scope"]]
                    for rd in data.regulation_domains
                ],
            )

        # Insert ClauseDomains
        if data.clause_domains:
            transaction.insert(
                table="ClauseDomains",
                columns=["clause_id", "domain_name"],
                values=[[cd["clause_id"], cd["domain_name"]] for cd in data.clause_domains],
            )

        # Insert Amends edges
        if data.amends:
            transaction.insert(
                table="Amends",
                columns=["source_id", "target_id", "effective_date", "change_type"],
                values=[
                    [a["source_id"], a["target_id"], a["effective_date"], a["change_type"]]
                    for a in data.amends
                ],
            )

        # Insert Supersedes edges
        if data.supersedes:
            transaction.insert(
                table="Supersedes",
                columns=["source_id", "target_id", "effective_date"],
                values=[
                    [s["source_id"], s["target_id"], s["effective_date"]] for s in data.supersedes
                ],
            )

        # Insert References edges
        if data.references:
            transaction.insert(
                table="References",
                columns=["source_clause_id", "target_clause_id", "reference_type"],
                values=[
                    [r["source_clause_id"], r["target_clause_id"], r["reference_type"]]
                    for r in data.references
                ],
            )

    database.run_in_transaction(_write)


# ---------------------------------------------------------------------------
# Dry-run printer
# ---------------------------------------------------------------------------


def print_dry_run(data: GraphData) -> None:
    """Print summary of what would be inserted."""
    print("\n=== DRY RUN — Spanner Graph Seed ===\n")

    print(f"Domains ({len(data.domains)}):")
    for d in sorted(data.domains):
        print(f"  - {d}")

    print(f"\nRegulations ({len(data.regulations)}):")
    for r in data.regulations:
        print(f"  [{r.id}] {r.title}")
        print(f"    issuer={r.issuer}  authority={r.authority_level}  date={r.effective_date}")

    print(f"\nClauses ({len(data.clauses)}):")
    for c in data.clauses:
        label = c.clause_number or "full"
        summary = c.text_summary[:80].replace("\n", " ")
        print(f"  [{c.regulation_id} / {label}] {summary}...")

    print(f"\nRegulationDomains ({len(data.regulation_domains)}):")
    for rd in data.regulation_domains:
        print(f"  {rd['regulation_id']} -> {rd['domain_name']} ({rd['scope']})")

    print(f"\nClauseDomains ({len(data.clause_domains)}):")
    for cd in data.clause_domains:
        print(f"  {cd['clause_id'][:8]}... -> {cd['domain_name']}")

    print(f"\nAmends edges ({len(data.amends)}):")
    for a in data.amends:
        print(f"  {a['source_id']} --amends--> {a['target_id']} ({a['change_type']})")

    print(f"\nSupersedes edges ({len(data.supersedes)}):")
    for s in data.supersedes:
        print(f"  {s['source_id']} --supersedes--> {s['target_id']}")

    print(f"\nReferences edges ({len(data.references)}):")
    for r in data.references:
        print(f"  {r['source_clause_id'][:8]}... --cites--> {r['target_clause_id'][:8]}...")

    # Summary
    total_nodes = len(data.regulations) + len(data.clauses) + len(data.domains)
    total_edges = (
        len(data.amends)
        + len(data.supersedes)
        + len(data.references)
        + len(data.regulation_domains)
        + len(data.clause_domains)
    )
    print(f"\n--- Total: {total_nodes} nodes, {total_edges} edges ---")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed Spanner RegulationGraph from corpus regulation files",
    )
    parser.add_argument(
        "--instance",
        default="ancol-regulation-graph",
        help="Spanner instance ID (default: ancol-regulation-graph)",
    )
    parser.add_argument(
        "--database",
        default="ancol-regulations",
        help="Spanner database ID (default: ancol-regulations)",
    )
    parser.add_argument(
        "--project",
        default="ancol-mom-compliance",
        help="GCP project ID (default: ancol-mom-compliance)",
    )
    parser.add_argument(
        "--corpus-root",
        type=Path,
        default=CORPUS_ROOT,
        help="Path to corpus/ directory (auto-detected by default)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be inserted without writing to Spanner",
    )
    args = parser.parse_args()

    print(f"Reading regulations from {args.corpus_root}...")
    data = read_regulation_files(args.corpus_root)

    if args.dry_run:
        print_dry_run(data)
        return

    print(f"Inserting into Spanner: {args.project}/{args.instance}/{args.database}")
    print(
        f"  {len(data.regulations)} regulations, "
        f"{len(data.clauses)} clauses, "
        f"{len(data.domains)} domains"
    )

    try:
        insert_to_spanner(data, args.instance, args.database, args.project)
    except ImportError:
        print(
            "ERROR: google-cloud-spanner is not installed.\n  pip install google-cloud-spanner",
            file=sys.stderr,
        )
        sys.exit(1)

    print("Done.")


if __name__ == "__main__":
    main()
