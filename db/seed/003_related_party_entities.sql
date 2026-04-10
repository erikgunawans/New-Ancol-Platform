-- Seed: Related Party Transaction entities
-- PT Pembangunan Jaya Ancol Tbk (PJAA) corporate group structure
-- Source: Annual Reports, public filings, IDX disclosures

INSERT INTO related_party_entities (entity_name, entity_type, relationship_description, effective_from, is_active) VALUES

-- Parent company
('PT Pembangunan Jaya', 'parent_company',
 'Pemegang saham pengendali PJAA (>60%). Induk perusahaan utama.',
 '1992-07-10', true),

-- Ultimate parent
('Pemerintah Provinsi DKI Jakarta', 'government_shareholder',
 'Pemegang saham tidak langsung melalui PT Pembangunan Jaya dan kepemilikan langsung.',
 '1992-07-10', true),

-- Subsidiaries
('PT Taman Impian Jaya Ancol', 'subsidiary',
 'Anak perusahaan PJAA. Pengelola kawasan rekreasi Ancol.',
 '1992-07-10', true),

('PT Jaya Ancol', 'subsidiary',
 'Anak perusahaan. Pengelolaan properti dan kawasan.',
 '2000-01-01', true),

('PT Seabreeze Indonesia', 'subsidiary',
 'Anak perusahaan. Pengelolaan hotel dan hospitality.',
 '2010-01-01', true),

-- Affiliated companies (same group)
('PT Jaya Real Property Tbk', 'affiliate',
 'Afiliasi melalui PT Pembangunan Jaya. Pengembang properti (IDX: JRPT).',
 '1994-01-01', true),

('PT Jaya Konstruksi Manggala Pratama Tbk', 'affiliate',
 'Afiliasi melalui PT Pembangunan Jaya. Konstruksi (IDX: JKON).',
 '2007-01-01', true),

('PT Jaya Celcon Prima', 'affiliate',
 'Afiliasi melalui PT Pembangunan Jaya. Material bangunan.',
 '1995-01-01', true),

('PT Jaya Teknik Indonesia', 'affiliate',
 'Afiliasi melalui PT Pembangunan Jaya. Mekanikal-elektrikal.',
 '1990-01-01', true),

('PT Jaya Trade Indonesia', 'affiliate',
 'Afiliasi melalui PT Pembangunan Jaya. Trading.',
 '1988-01-01', true),

-- Key personnel entities (directors who may have interests)
('Direksi PT Pembangunan Jaya', 'key_personnel_group',
 'Direksi induk perusahaan yang juga mungkin menjabat posisi di PJAA.',
 '2020-01-01', true),

('Komisaris PT Pembangunan Jaya', 'key_personnel_group',
 'Dewan Komisaris induk perusahaan.',
 '2020-01-01', true),

-- Joint ventures / partnerships
('Ancol Temasek Consortium', 'joint_venture',
 'Konsorsium pengembangan kawasan. Kerjasama strategis.',
 '2018-01-01', true)

ON CONFLICT DO NOTHING;
