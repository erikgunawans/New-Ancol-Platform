#!/usr/bin/env python3
"""Retrieval Quality Test for Vertex AI Search regulatory corpus.

Runs 20 test queries across all compliance domains and measures
precision (P) and recall (R) against expected results.

Targets: P > 0.80, R > 0.70

Usage:
    python test_retrieval_quality.py                    # Run against live Vertex AI Search
    python test_retrieval_quality.py --local-only       # Test against local JSONL chunks
    python test_retrieval_quality.py --verbose           # Show per-query details

Environment:
    GCP_PROJECT, GCP_REGION, VERTEX_SEARCH_DATASTORE_ID
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

from google.api_core.client_options import ClientOptions


@dataclass
class TestQuery:
    """A test query with expected regulation matches."""

    id: int
    domain: str
    query: str
    expected_regulations: list[str]
    expected_articles: list[str] = field(default_factory=list)
    description: str = ""


# 20 test queries covering all compliance domains
TEST_QUERIES: list[TestQuery] = [
    # ── Corporate Governance (UU PT, POJK 21, AD/ART) ──
    TestQuery(
        id=1,
        domain="corporate_governance",
        query="Berapa kuorum minimum untuk Rapat Direksi?",
        expected_regulations=["ADART-PJAA", "UU-PT-40-2007", "BOD-CHARTER-PJAA"],
        expected_articles=["13", "86", "5"],
        description="Quorum rules for board meetings",
    ),
    TestQuery(
        id=2,
        domain="corporate_governance",
        query="Apa saja kewajiban Direksi dalam membuat risalah rapat?",
        expected_regulations=["UU-PT-40-2007", "POJK-33-2014", "ADART-PJAA"],
        expected_articles=["100", "11", "13"],
        description="Director obligations for meeting minutes",
    ),
    TestQuery(
        id=3,
        domain="corporate_governance",
        query="Bagaimana pengambilan keputusan jika musyawarah mufakat tidak tercapai?",
        expected_regulations=["ADART-PJAA", "POJK-33-2014", "BOD-CHARTER-PJAA"],
        expected_articles=["13", "11", "5"],
        description="Decision-making when consensus fails",
    ),
    TestQuery(
        id=4,
        domain="corporate_governance",
        query="Apakah keputusan sirkuler diperbolehkan dan apa syaratnya?",
        expected_regulations=["ADART-PJAA", "UU-PT-40-2007"],
        expected_articles=["14", "91"],
        description="Circular resolution validity and requirements",
    ),
    # ── Board Governance (POJK 33, Charters) ──
    TestQuery(
        id=5,
        domain="board_governance",
        query="Berapa frekuensi minimum rapat Direksi per bulan?",
        expected_regulations=["POJK-33-2014", "BOD-CHARTER-PJAA"],
        expected_articles=["11", "4"],
        description="Minimum board meeting frequency",
    ),
    TestQuery(
        id=6,
        domain="board_governance",
        query="Apa persyaratan Komisaris Independen?",
        expected_regulations=["POJK-33-2014", "BOC-CHARTER-PJAA", "ADART-PJAA"],
        expected_articles=["21", "2", "15"],
        description="Independent commissioner requirements",
    ),
    TestQuery(
        id=7,
        domain="board_governance",
        query="Siapa yang wajib menandatangani risalah rapat Direksi?",
        expected_regulations=["POJK-33-2014", "ADART-PJAA", "BOD-CHARTER-PJAA"],
        expected_articles=["11", "13", "4"],
        description="Signature requirements for board minutes",
    ),
    TestQuery(
        id=8,
        domain="board_governance",
        query="Apa yang harus dimuat dalam risalah Rapat Direksi?",
        expected_regulations=["BOD-CHARTER-PJAA", "POJK-33-2014", "ADART-PJAA"],
        expected_articles=["4", "11", "13"],
        description="Required contents of board meeting minutes",
    ),
    # ── Related Party Transactions (POJK 42, RPT Policy) ──
    TestQuery(
        id=9,
        domain="related_party_transactions",
        query="Kapan transaksi afiliasi wajib diungkapkan kepada publik?",
        expected_regulations=["POJK-42-2020", "RPT-POLICY-PJAA"],
        expected_articles=["3", "2"],
        description="RPT disclosure requirements and timeline",
    ),
    TestQuery(
        id=10,
        domain="related_party_transactions",
        query="Apa kewajiban Direksi jika ada benturan kepentingan dalam transaksi?",
        expected_regulations=["POJK-42-2020", "ADART-PJAA", "BOD-CHARTER-PJAA"],
        expected_articles=["12", "20", "6"],
        description="Director obligations in conflict of interest",
    ),
    TestQuery(
        id=11,
        domain="related_party_transactions",
        query="Transaksi afiliasi apa saja yang dikecualikan dari kewajiban pelaporan?",
        expected_regulations=["POJK-42-2020"],
        expected_articles=["10"],
        description="RPT exemptions",
    ),
    TestQuery(
        id=12,
        domain="related_party_transactions",
        query="Apa saja entitas pihak berelasi PT Pembangunan Jaya Ancol?",
        expected_regulations=["RPT-POLICY-PJAA"],
        expected_articles=["1"],
        description="PJAA related party entity list",
    ),
    # ── Listing Rules (IDX) ──
    TestQuery(
        id=13,
        domain="listing_rules",
        query="Kapan batas waktu penyampaian Laporan Tahunan ke BEI?",
        expected_regulations=["IDX-I-A"],
        expected_articles=["III.1"],
        description="Annual report deadline to IDX",
    ),
    TestQuery(
        id=14,
        domain="listing_rules",
        query="Informasi material apa yang wajib segera diungkapkan ke publik?",
        expected_regulations=["IDX-I-A"],
        expected_articles=["III.2"],
        description="Material information disclosure requirements",
    ),
    # ── Corporate Charter (AD/ART specific) ──
    TestQuery(
        id=15,
        domain="corporate_charter",
        query="Perbuatan hukum apa yang memerlukan persetujuan Dewan Komisaris?",
        expected_regulations=["ADART-PJAA"],
        expected_articles=["12"],
        description="Transactions requiring commissioner approval per AD/ART",
    ),
    TestQuery(
        id=16,
        domain="corporate_charter",
        query="Berapa jumlah minimum anggota Direksi menurut AD/ART PJAA?",
        expected_regulations=["ADART-PJAA", "BOD-CHARTER-PJAA"],
        expected_articles=["11", "2"],
        description="Minimum directors per AD/ART",
    ),
    # ── Cross-domain queries ──
    TestQuery(
        id=17,
        domain="cross_domain",
        query="Bagaimana prosedur pembahasan RPT dalam Rapat Direksi termasuk pencatatan dalam risalah?",
        expected_regulations=["POJK-42-2020", "RPT-POLICY-PJAA", "BOD-CHARTER-PJAA"],
        expected_articles=["12", "4", "6"],
        description="RPT discussion procedure in board meetings",
    ),
    TestQuery(
        id=18,
        domain="cross_domain",
        query="Apa hubungan antara frekuensi rapat dengan penilaian tata kelola perusahaan?",
        expected_regulations=["POJK-21-2015", "POJK-33-2014"],
        expected_articles=["8", "31"],
        description="Meeting frequency and governance assessment link",
    ),
    TestQuery(
        id=19,
        domain="cross_domain",
        query="Sanksi apa yang dapat dijatuhkan jika perusahaan tercatat melanggar ketentuan tata kelola?",
        expected_regulations=["IDX-I-A", "POJK-42-2020"],
        expected_articles=["V.1", "15"],
        description="Penalties for governance violations",
    ),
    TestQuery(
        id=20,
        domain="cross_domain",
        query="Apa kewajiban penilaian kinerja Dewan Komisaris dan bagaimana pelaporannya?",
        expected_regulations=["BOC-CHARTER-PJAA", "POJK-21-2015"],
        expected_articles=["7", "16"],
        description="Commissioner performance assessment obligations",
    ),
]


def test_local_retrieval(chunks_dirs: list[Path], verbose: bool = False) -> dict:
    """Test retrieval quality against local JSONL chunks using simple text matching.

    This tests the chunking quality — whether the right articles are in the right chunks.
    """
    # Load all chunks
    all_chunks = []
    for chunks_dir in chunks_dirs:
        for jsonl_path in sorted(chunks_dir.glob("*.jsonl")):
            if jsonl_path.name.startswith("_"):
                continue
            with open(jsonl_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        all_chunks.append(json.loads(line))

    print(f"Loaded {len(all_chunks)} chunks from {len(chunks_dirs)} directories\n")

    results = []

    for query in TEST_QUERIES:
        # Simple keyword matching (simulates retrieval)
        query_terms = query.query.lower().split()
        scored_chunks = []

        for chunk in all_chunks:
            content_lower = chunk["content"].lower()
            title_lower = chunk.get("article_title", "").lower()

            # Score by keyword overlap
            hits = sum(1 for term in query_terms if term in content_lower or term in title_lower)
            if hits > 0:
                scored_chunks.append((hits / len(query_terms), chunk))

        # Top-k results (k = 5)
        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        top_k = scored_chunks[:5]
        retrieved_regulations = {c["regulation_id"] for _, c in top_k}

        # Calculate precision and recall
        expected = set(query.expected_regulations)
        true_positives = retrieved_regulations & expected
        precision = len(true_positives) / max(len(retrieved_regulations), 1)
        recall = len(true_positives) / max(len(expected), 1)

        result = {
            "query_id": query.id,
            "domain": query.domain,
            "precision": round(precision, 2),
            "recall": round(recall, 2),
            "expected": sorted(expected),
            "retrieved": sorted(retrieved_regulations),
            "true_positives": sorted(true_positives),
        }
        results.append(result)

        if verbose:
            status = "PASS" if precision >= 0.8 and recall >= 0.7 else "FAIL"
            print(
                f"  Q{query.id:2d} [{status}] P={precision:.2f} R={recall:.2f} -- {query.description}"
            )
            if status == "FAIL":
                missing = expected - retrieved_regulations
                if missing:
                    print(f"       Missing: {sorted(missing)}")

    return _compute_summary(results)


def test_vertex_search_retrieval(
    project: str, region: str, datastore_id: str, verbose: bool = False
) -> dict:
    """Test retrieval quality against live Vertex AI Search."""
    try:
        from google.cloud import discoveryengine_v1 as discoveryengine

        client_options = ClientOptions(api_endpoint=f"{region}-discoveryengine.googleapis.com")
        client = discoveryengine.SearchServiceClient(client_options=client_options)
    except Exception as e:
        print(f"Cannot connect to Vertex AI Search: {e}")
        print("Falling back to local-only mode.\n")
        return {}

    serving_config = (
        f"projects/{project}/locations/{region}"
        f"/collections/default_collection/dataStores/{datastore_id}"
        f"/servingConfigs/default_search"
    )

    results = []

    for query in TEST_QUERIES:
        try:
            request = discoveryengine.SearchRequest(
                serving_config=serving_config,
                query=query.query,
                page_size=5,
            )
            response = client.search(request=request)

            retrieved_regulations = set()
            for result in response.results:
                doc = result.document
                if doc.struct_data and "regulation_id" in doc.struct_data:
                    retrieved_regulations.add(doc.struct_data["regulation_id"])

            expected = set(query.expected_regulations)
            true_positives = retrieved_regulations & expected
            precision = len(true_positives) / max(len(retrieved_regulations), 1)
            recall = len(true_positives) / max(len(expected), 1)

            result_data = {
                "query_id": query.id,
                "domain": query.domain,
                "precision": round(precision, 2),
                "recall": round(recall, 2),
                "expected": sorted(expected),
                "retrieved": sorted(retrieved_regulations),
                "true_positives": sorted(true_positives),
            }
            results.append(result_data)

            if verbose:
                status = "PASS" if precision >= 0.8 and recall >= 0.7 else "FAIL"
                print(
                    f"  Q{query.id:2d} [{status}] P={precision:.2f} R={recall:.2f} -- {query.description}"
                )

        except Exception as e:
            print(f"  Q{query.id:2d} [ERROR] {e}")
            results.append(
                {
                    "query_id": query.id,
                    "domain": query.domain,
                    "precision": 0,
                    "recall": 0,
                    "error": str(e),
                }
            )

    return _compute_summary(results)


def _compute_summary(results: list[dict]) -> dict:
    """Compute aggregate metrics from individual query results."""
    if not results:
        return {"error": "No results"}

    precisions = [r["precision"] for r in results if "error" not in r]
    recalls = [r["recall"] for r in results if "error" not in r]

    avg_precision = sum(precisions) / max(len(precisions), 1)
    avg_recall = sum(recalls) / max(len(recalls), 1)

    passing_p = sum(1 for p in precisions if p >= 0.8)
    passing_r = sum(1 for r in recalls if r >= 0.7)

    # By domain
    domains: dict[str, dict] = {}
    for r in results:
        d = r["domain"]
        if d not in domains:
            domains[d] = {"precisions": [], "recalls": []}
        if "error" not in r:
            domains[d]["precisions"].append(r["precision"])
            domains[d]["recalls"].append(r["recall"])

    domain_summary = {}
    for d, vals in domains.items():
        domain_summary[d] = {
            "avg_precision": round(sum(vals["precisions"]) / max(len(vals["precisions"]), 1), 2),
            "avg_recall": round(sum(vals["recalls"]) / max(len(vals["recalls"]), 1), 2),
            "queries": len(vals["precisions"]),
        }

    summary = {
        "total_queries": len(results),
        "avg_precision": round(avg_precision, 2),
        "avg_recall": round(avg_recall, 2),
        "passing_precision": f"{passing_p}/{len(precisions)}",
        "passing_recall": f"{passing_r}/{len(recalls)}",
        "target_met": avg_precision >= 0.80 and avg_recall >= 0.70,
        "by_domain": domain_summary,
        "per_query": results,
    }

    return summary


def main():
    parser = argparse.ArgumentParser(description="Test retrieval quality of regulatory corpus")
    parser.add_argument("--local-only", action="store_true", help="Test against local chunks only")
    parser.add_argument("--project", default="ancol-mom-compliance")
    parser.add_argument("--region", default="asia-southeast2")
    parser.add_argument("--datastore-id", default="regulatory-corpus")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show per-query details")
    parser.add_argument("--output", type=Path, help="Write JSON results to file")
    args = parser.parse_args()

    corpus_root = Path(__file__).parent.parent
    chunks_dirs = [
        corpus_root / "internal" / "chunks",
        corpus_root / "external" / "chunks",
    ]

    print("=" * 60)
    print("Regulatory Corpus -- Retrieval Quality Test")
    print(f"Queries: {len(TEST_QUERIES)}  |  Targets: P > 0.80, R > 0.70")
    print("=" * 60)

    # Always run local test
    print("\n--- Local Chunk Retrieval ---")
    local_summary = test_local_retrieval(chunks_dirs, verbose=args.verbose)

    print(f"\n  Avg Precision: {local_summary['avg_precision']:.2f}  (target > 0.80)")
    print(f"  Avg Recall:    {local_summary['avg_recall']:.2f}  (target > 0.70)")
    print(f"  Target Met:    {'YES' if local_summary['target_met'] else 'NO'}")

    # Run Vertex AI Search test if not local-only
    vertex_summary = {}
    if not args.local_only:
        print("\n--- Vertex AI Search Retrieval ---")
        vertex_summary = test_vertex_search_retrieval(
            args.project, args.region, args.datastore_id, verbose=args.verbose
        )
        if vertex_summary and "error" not in vertex_summary:
            print(f"\n  Avg Precision: {vertex_summary['avg_precision']:.2f}")
            print(f"  Avg Recall:    {vertex_summary['avg_recall']:.2f}")
            print(f"  Target Met:    {'YES' if vertex_summary['target_met'] else 'NO'}")

    # Write results
    if args.output:
        output_data = {
            "local": local_summary,
            "vertex_search": vertex_summary,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        print(f"\nResults written to {args.output}")

    # Exit code based on local results
    sys.exit(0 if local_summary.get("target_met") else 1)


if __name__ == "__main__":
    main()
