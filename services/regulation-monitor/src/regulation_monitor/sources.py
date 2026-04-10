"""Regulation source definitions and scraper configurations.

Each source defines where to check for new/amended regulations,
how to detect changes, and how to extract metadata.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RegulationSource:
    """A regulation publication source to monitor."""

    source_id: str
    name: str
    base_url: str
    search_path: str
    domain: str
    keywords: list[str] = field(default_factory=list)
    content_selector: str = "article, .content, main"
    title_selector: str = "h1, .title, .regulation-title"
    date_selector: str = "time, .date, .published-date"


# OJK (Otoritas Jasa Keuangan) — Financial Services Authority
OJK_SOURCE = RegulationSource(
    source_id="ojk",
    name="OJK Regulations",
    base_url="https://www.ojk.go.id",
    search_path="/regulasi/peraturan-ojk",
    domain="capital_markets",
    keywords=[
        "emiten",
        "perusahaan terbuka",
        "direksi",
        "komisaris",
        "tata kelola",
        "corporate governance",
        "transaksi afiliasi",
        "benturan kepentingan",
        "RUPS",
        "keterbukaan informasi",
    ],
    title_selector=".regulation-title, h3.title",
    date_selector=".regulation-date, .date",
)

# IDX (Bursa Efek Indonesia) — Indonesia Stock Exchange
IDX_SOURCE = RegulationSource(
    source_id="idx",
    name="IDX Rules",
    base_url="https://www.idx.co.id",
    search_path="/peraturan/peraturan-bursa",
    domain="listing_rules",
    keywords=[
        "pencatatan saham",
        "keterbukaan informasi",
        "transaksi material",
        "listing",
        "delisting",
        "perdagangan",
        "emiten",
    ],
    title_selector=".rule-title, h3",
    date_selector=".rule-date, .date",
)

# Kemenparekraf (Ministry of Tourism)
KEMENPAREKRAF_SOURCE = RegulationSource(
    source_id="kemenparekraf",
    name="Kemenparekraf Regulations",
    base_url="https://jdih.kemenparekraf.go.id",
    search_path="/regulasi",
    domain="tourism",
    keywords=[
        "pariwisata",
        "destinasi",
        "akomodasi",
        "rekreasi",
        "taman hiburan",
        "ancol",
        "pantai",
    ],
)

# KLHK (Ministry of Environment and Forestry)
KLHK_SOURCE = RegulationSource(
    source_id="klhk",
    name="KLHK Regulations",
    base_url="https://jdih.menlhk.go.id",
    search_path="/regulasi",
    domain="environment",
    keywords=[
        "lingkungan hidup",
        "amdal",
        "UKL-UPL",
        "limbah",
        "pencemaran",
        "pesisir",
        "pantai",
        "reklamasi",
    ],
)

# ATR/BPN (Ministry of Agrarian Affairs and Spatial Planning)
ATR_BPN_SOURCE = RegulationSource(
    source_id="atr_bpn",
    name="ATR/BPN Regulations",
    base_url="https://jdih.atrbpn.go.id",
    search_path="/regulasi",
    domain="land",
    keywords=[
        "pertanahan",
        "hak guna bangunan",
        "HGB",
        "sertifikat",
        "reklamasi",
        "pemanfaatan ruang",
        "tata ruang",
    ],
)

ALL_SOURCES = [OJK_SOURCE, IDX_SOURCE, KEMENPAREKRAF_SOURCE, KLHK_SOURCE, ATR_BPN_SOURCE]

# Sources for MVP (corporate governance + capital markets)
PRIORITY_SOURCES = [OJK_SOURCE, IDX_SOURCE]
