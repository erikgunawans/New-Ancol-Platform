-- Seed: Known regulatory conflict precedences
-- These encode which regulation prevails when two regulations address the same topic differently

INSERT INTO conflict_precedences (regulation_a_id, regulation_b_id, prevailing_regulation, rationale) VALUES

-- UU PT is lex generalis, POJK is lex specialis for public companies
('UU-PT-40-2007', 'POJK-33-2014',
 'POJK-33-2014',
 'POJK 33/2014 sebagai lex specialis mengatur ketentuan khusus untuk Direksi dan Komisaris emiten. UU PT berlaku untuk ketentuan yang tidak diatur oleh POJK.'),

-- OJK RPT rules override company-level RPT policy
('POJK-42-2020', 'RPT-POLICY-PJAA',
 'POJK-42-2020',
 'Ketentuan POJK 42/2020 tentang Transaksi Afiliasi berlaku sebagai standar minimum. Kebijakan internal PJAA boleh lebih ketat tetapi tidak boleh lebih longgar.'),

-- AD/ART quorum rules vs UU PT quorum rules
('UU-PT-40-2007', 'ADART-PJAA',
 'ADART-PJAA',
 'UU PT Pasal 86 memperbolehkan AD/ART menetapkan kuorum yang lebih tinggi. AD/ART PJAA berlaku sepanjang lebih ketat dari UU PT.'),

-- Board charter vs POJK on board composition
('POJK-33-2014', 'BOD-CHARTER-PJAA',
 'POJK-33-2014',
 'Ketentuan POJK tentang komposisi dan independensi Direksi bersifat imperatif. Piagam Direksi harus sejalan dan tidak boleh bertentangan.'),

-- IDX listing rules vs OJK regulations
('IDX-I-A', 'POJK-21-2015',
 'POJK-21-2015',
 'Peraturan OJK memiliki hierarki lebih tinggi dari peraturan BEI. Namun keduanya berlaku kumulatif — emiten harus memenuhi keduanya.')

ON CONFLICT DO NOTHING;
