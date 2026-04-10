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
