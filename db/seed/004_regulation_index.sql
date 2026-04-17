-- Seed: Regulation index (metadata only, corpus content in Vertex AI Search)
-- Indonesian corporate governance regulatory framework for PJAA

INSERT INTO regulation_index (regulation_id, title, source_type, domain, effective_date, expiry_date, version, chunk_count) VALUES

-- Primary corporate law
('UU-PT-40-2007', 'Undang-Undang No. 40 Tahun 2007 tentang Perseroan Terbatas',
 'external', 'corporate_governance', '2007-08-16', NULL, 1, 0),

-- OJK regulations
('POJK-33-2014', 'POJK No. 33/POJK.04/2014 tentang Direksi dan Dewan Komisaris Emiten',
 'external', 'board_governance', '2014-12-08', NULL, 1, 0),

('POJK-42-2020', 'POJK No. 42/POJK.04/2020 tentang Transaksi Afiliasi dan Benturan Kepentingan',
 'external', 'related_party_transactions', '2020-07-01', NULL, 1, 0),

('POJK-15-2020', 'POJK No. 15/POJK.04/2020 tentang Rencana dan Penyelenggaraan RUPS',
 'external', 'general_meeting', '2020-04-20', NULL, 1, 0),

('POJK-21-2015', 'POJK No. 21/POJK.04/2015 tentang Penerapan Pedoman Tata Kelola Perusahaan Terbuka',
 'external', 'corporate_governance', '2015-11-16', NULL, 1, 0),

('POJK-30-2020', 'POJK No. 30/POJK.04/2020 tentang Laporan Tahunan Emiten atau Perusahaan Publik',
 'external', 'annual_reporting', '2020-06-22', NULL, 1, 0),

-- IDX regulations
('IDX-I-A', 'Peraturan Pencatatan No. I-A tentang Pencatatan Saham dan Efek Bersifat Ekuitas',
 'external', 'listing_rules', '2018-02-06', NULL, 1, 0),

('IDX-I-H', 'Peraturan Pencatatan No. I-H tentang Sanksi',
 'external', 'listing_rules', '2018-02-06', NULL, 1, 0),

-- Internal regulations
('ADART-PJAA', 'Anggaran Dasar PT Pembangunan Jaya Ancol Tbk',
 'internal', 'corporate_charter', '2022-06-15', NULL, 3, 0),

('BOD-CHARTER-PJAA', 'Piagam Direksi PT Pembangunan Jaya Ancol Tbk',
 'internal', 'board_charter', '2023-01-01', NULL, 2, 0),

('BOC-CHARTER-PJAA', 'Piagam Dewan Komisaris PT Pembangunan Jaya Ancol Tbk',
 'internal', 'board_charter', '2023-01-01', NULL, 2, 0),

('AUDIT-COMMITTEE-CHARTER', 'Piagam Komite Audit PT Pembangunan Jaya Ancol Tbk',
 'internal', 'committee_charter', '2023-01-01', NULL, 1, 0),

('CODE-OF-CONDUCT-PJAA', 'Pedoman Perilaku (Code of Conduct) PJAA',
 'internal', 'ethics', '2022-01-01', NULL, 1, 0),

('RPT-POLICY-PJAA', 'Kebijakan Transaksi Pihak Berelasi PJAA',
 'internal', 'related_party_transactions', '2021-07-01', NULL, 1, 0)

ON CONFLICT (regulation_id) DO NOTHING;


-- ─────────────────────────────────────────────────────────────────────────────
-- BJR expansion: backfill regulatory_regime + layer on existing 14 regulations.
-- These columns drive dual-regime BJR scoring (corporate vs regional_finance).
-- ─────────────────────────────────────────────────────────────────────────────

UPDATE regulation_index SET regulatory_regime = 'corporate', layer = 'uu'
  WHERE regulation_id IN ('UU-PT-40-2007');

UPDATE regulation_index SET regulatory_regime = 'listing', layer = 'ojk_bei'
  WHERE regulation_id IN (
    'POJK-33-2014',
    'POJK-42-2020',
    'POJK-15-2020',
    'POJK-21-2015',
    'POJK-30-2020',
    'IDX-I-A',
    'IDX-I-H'
  );

UPDATE regulation_index SET regulatory_regime = 'internal', layer = 'internal'
  WHERE regulation_id IN (
    'ADART-PJAA',
    'BOD-CHARTER-PJAA',
    'BOC-CHARTER-PJAA',
    'AUDIT-COMMITTEE-CHARTER',
    'CODE-OF-CONDUCT-PJAA',
    'RPT-POLICY-PJAA'
  );

-- ─────────────────────────────────────────────────────────────────────────────
-- BJR expansion: seed the ~20 new regulations cited in the BJR matrix.
-- Chunk counts are 0 until the corpus .md files are uploaded + chunked by
-- corpus/scripts/chunk_regulations.py. Source .md content is BD/Legal work.
-- ─────────────────────────────────────────────────────────────────────────────

INSERT INTO regulation_index
  (regulation_id, title, source_type, domain, effective_date, version, chunk_count, regulatory_regime, layer)
VALUES
  -- UU layer
  ('UU-23-2014', 'Undang-Undang No. 23 Tahun 2014 tentang Pemerintahan Daerah',
   'external', 'regional_governance', '2014-10-02', 1, 0, 'regional_finance', 'uu'),
  ('UU-19-2003', 'Undang-Undang No. 19 Tahun 2003 tentang Badan Usaha Milik Negara',
   'external', 'state_owned_enterprise', '2003-06-19', 1, 0, 'corporate', 'uu'),
  ('UU-1-2025', 'Undang-Undang No. 1 Tahun 2025 tentang Perubahan UU BUMN',
   'external', 'state_owned_enterprise', '2025-02-04', 1, 0, 'corporate', 'uu'),
  ('UU-6-2023', 'Undang-Undang No. 6 Tahun 2023 tentang Cipta Kerja',
   'external', 'corporate_governance', '2023-03-31', 1, 0, 'corporate', 'uu'),

  -- PP layer
  ('PP-54-2017', 'PP No. 54 Tahun 2017 tentang Badan Usaha Milik Daerah',
   'external', 'regional_owned_enterprise', '2017-12-27', 1, 0, 'regional_finance', 'pp'),
  ('PP-23-2022', 'PP No. 23 Tahun 2022 tentang Pendirian, Pengurusan, Pengawasan dan Pembubaran BUMN',
   'external', 'state_owned_enterprise', '2022-06-13', 1, 0, 'corporate', 'pp'),
  ('PP-45-2005', 'PP No. 45 Tahun 2005 tentang Pendirian, Pengurusan, Pengawasan dan Pembubaran BUMN',
   'external', 'state_owned_enterprise', '2005-11-14', 1, 0, 'corporate', 'pp'),

  -- Pergub DKI Jakarta layer (all regional_finance regime)
  ('KEPGUB-DKI-96-2004', 'Keputusan Gubernur DKI No. 96 Tahun 2004 tentang Penerapan Praktik GCG pada BUMD DKI',
   'external', 'bumd_governance', '2004-06-14', 1, 0, 'regional_finance', 'pergub_dki'),
  ('KEPGUB-DKI-4-2004', 'Keputusan Gubernur DKI No. 4 Tahun 2004 tentang Penilaian Tingkat Kesehatan BUMD DKI',
   'external', 'bumd_performance', '2004-01-12', 1, 0, 'regional_finance', 'pergub_dki'),
  ('PERGUB-DKI-109-2011', 'Pergub DKI No. 109 Tahun 2011 tentang Kepengurusan BUMD',
   'external', 'bumd_governance', '2011-08-16', 2, 0, 'regional_finance', 'pergub_dki'),
  ('PERGUB-DKI-10-2012', 'Pergub DKI No. 10 Tahun 2012 tentang Penyusunan RJPP BUMD',
   'external', 'bumd_strategic_plan', '2012-02-08', 1, 0, 'regional_finance', 'pergub_dki'),
  ('PERGUB-DKI-204-2016', 'Pergub DKI No. 204 Tahun 2016 tentang Kebijakan Pengadaan Barang/Jasa BUMD',
   'external', 'bumd_procurement', '2016-10-24', 1, 0, 'regional_finance', 'pergub_dki'),
  ('PERGUB-DKI-5-2018', 'Pergub DKI No. 5 Tahun 2018 tentang Tata Cara Pengangkatan dan Pemberhentian Direksi BUMD',
   'external', 'bumd_direksi', '2018-01-18', 1, 0, 'regional_finance', 'pergub_dki'),
  ('PERGUB-DKI-50-2018', 'Pergub DKI No. 50 Tahun 2018 tentang Dewan Pengawas BUMD',
   'external', 'bumd_oversight', '2018-05-14', 1, 0, 'regional_finance', 'pergub_dki'),
  ('PERGUB-DKI-79-2019', 'Pergub DKI No. 79 Tahun 2019 tentang Pedoman Penetapan Penghasilan Direksi, Dewan Pengawas, dan Komisaris BUMD',
   'external', 'bumd_remuneration', '2019-07-11', 1, 0, 'regional_finance', 'pergub_dki'),
  ('PERGUB-DKI-127-2019', 'Pergub DKI No. 127 Tahun 2019 tentang Rencana Bisnis dan RKAB BUMD',
   'external', 'bumd_business_plan', '2019-12-03', 1, 0, 'regional_finance', 'pergub_dki'),
  ('PERGUB-DKI-131-2019', 'Pergub DKI No. 131 Tahun 2019 tentang Pembinaan BUMD',
   'external', 'bumd_supervision', '2019-12-12', 1, 0, 'regional_finance', 'pergub_dki'),
  ('PERGUB-DKI-1-2020', 'Pergub DKI No. 1 Tahun 2020 tentang Sistem Pengendalian Internal BUMD',
   'external', 'bumd_internal_control', '2020-01-06', 1, 0, 'regional_finance', 'pergub_dki'),
  ('PERGUB-DKI-13-2020', 'Pergub DKI No. 13 Tahun 2020 tentang Komite Audit dan Komite Lainnya pada BUMD',
   'external', 'bumd_audit_committee', '2020-02-21', 1, 0, 'regional_finance', 'pergub_dki'),
  ('PERGUB-DKI-92-2020', 'Pergub DKI No. 92 Tahun 2020 tentang Pengelolaan Investasi pada BUMD',
   'external', 'bumd_investment', '2020-08-19', 1, 0, 'regional_finance', 'pergub_dki'),
  ('SE-GUB-DKI-13-2017', 'Surat Edaran Gubernur DKI No. 13 Tahun 2017 tentang Panduan Pengelolaan LHKPN di BUMD DKI',
   'external', 'bumd_lhkpn', '2017-05-15', 1, 0, 'regional_finance', 'pergub_dki'),

  -- Additional POJK layer (Komite Nominasi-Remunerasi, Sekretaris Perusahaan)
  ('POJK-34-2014', 'POJK No. 34/POJK.04/2014 tentang Komite Nominasi dan Remunerasi Emiten',
   'external', 'nomination_remuneration_committee', '2014-12-08', 1, 0, 'listing', 'ojk_bei'),
  ('POJK-35-2014', 'POJK No. 35/POJK.04/2014 tentang Sekretaris Perusahaan Emiten',
   'external', 'corporate_secretary', '2014-12-08', 1, 0, 'listing', 'ojk_bei')

ON CONFLICT (regulation_id) DO NOTHING;
