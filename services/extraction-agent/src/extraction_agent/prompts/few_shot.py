"""Few-shot examples for the Extraction Agent.

Provides concrete input/output pairs to guide Gemini's extraction behavior.
"""

FEW_SHOT_EXAMPLE_1 = {
    "input": """RISALAH RAPAT DIREKSI
PT PEMBANGUNAN JAYA ANCOL TBK
Nomor: DIR/RR/003/III/2025

Pada hari Kamis, tanggal 20 Maret 2025, bertempat di Ruang Rapat Direksi, Gedung Ecovention Ancol, Jakarta Utara, telah diselenggarakan Rapat Direksi Rutin.

DAFTAR HADIR:
1. Budi Karya Sumadi - Direktur Utama (Ketua Rapat) - Hadir
2. Siti Rahayu - Direktur Keuangan - Hadir
3. Agus Pramono - Direktur Operasional - Hadir
4. Dewi Lestari - Direktur Pengembangan Bisnis - Tidak Hadir (sakit)
5. Hendro Susanto - Direktur SDM & Umum - Hadir

Sekretaris Rapat: Ratna Sari (Corporate Secretary)

Dengan hadirnya 4 dari 5 anggota Direksi (80%), kuorum rapat telah terpenuhi sesuai Pasal 13 AD/ART Perseroan.

AGENDA:
1. Laporan Kinerja Bulan Februari 2025
2. Rencana Pengembangan Kawasan Pantai Festival
3. Persetujuan Kontrak dengan PT Jaya Konstruksi
4. Lain-lain

PEMBAHASAN:

Agenda 1 - Laporan Kinerja:
Direktur Keuangan melaporkan:
- Pendapatan: Rp 85,2 miliar (naik 12% YoY)
- Jumlah pengunjung: 1,2 juta orang (naik 8% YoY)
- EBITDA margin: 35,4%

Agenda 3 - Kontrak PT Jaya Konstruksi:
Direksi membahas rencana kontrak renovasi area pantai dengan PT Jaya Konstruksi Manggala Pratama Tbk senilai Rp 25 miliar. Dicatat bahwa PT Jaya Konstruksi merupakan afiliasi melalui PT Pembangunan Jaya.

KEPUTUSAN:
1. Menyetujui laporan kinerja Februari 2025
2. Menyetujui dimulainya feasibility study pengembangan Kawasan Pantai Festival dengan anggaran Rp 500 juta, penanggung jawab: Direktur Pengembangan Bisnis, tenggat: 30 Juni 2025
3. Menyetujui kontrak renovasi dengan PT Jaya Konstruksi senilai Rp 25 miliar, dengan catatan perlu persetujuan Dewan Komisaris sesuai Pasal 12 AD/ART

Rapat ditutup pada pukul 15:30 WIB.

Ditandatangani oleh:
Budi Karya Sumadi (Ketua Rapat)
Ratna Sari (Sekretaris)""",
    "expected_output_summary": {
        "meeting_date": "2025-03-20",
        "meeting_type": "regular",
        "meeting_number": "DIR/RR/003/III/2025",
        "location": "Ruang Rapat Direksi, Gedung Ecovention Ancol, Jakarta Utara",
        "chairman": "Budi Karya Sumadi",
        "secretary": "Ratna Sari",
        "total_directors": 5,
        "directors_present": 4,
        "quorum_met": True,
        "resolutions_count": 3,
        "agenda_count": 4,
        "cross_references": ["Pasal 13 AD/ART", "Pasal 12 AD/ART", "PT Jaya Konstruksi (afiliasi)"],
        "rpt_flag": "PT Jaya Konstruksi is a related party via PT Pembangunan Jaya",
    },
}


def get_few_shot_messages() -> list[dict]:
    """Build few-shot messages for the extraction prompt."""
    return [
        {
            "role": "user",
            "content": (
                "Berikut adalah teks OCR dari risalah rapat. "
                "Ekstrak semua informasi terstruktur sesuai schema.\n\n"
                f"{FEW_SHOT_EXAMPLE_1['input']}"
            ),
        },
        {
            "role": "model",
            "content": (
                "Saya akan mengekstrak informasi terstruktur dari risalah rapat ini. "
                "Berikut hasilnya dalam format JSON sesuai ExtractionOutput schema."
            ),
        },
    ]
