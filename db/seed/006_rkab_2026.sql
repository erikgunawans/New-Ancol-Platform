-- Seed: RKAB (Rencana Kerja dan Anggaran Bisnis) 2026 placeholder line items.
--
-- Illustrative placeholder data per Pergub DKI 127/2019 — BD team populates
-- real RKAB 2026 before pilot. BJR checklist item PD-03-RKAB matches
-- StrategicDecisions against these line items for the fiscal year.
--
-- Categories align with Ancol's operating segments: theme park, marine,
-- property, beach city, corporate.

INSERT INTO rkab_line_items
  (id, fiscal_year, code, category, activity_name, description, budget_idr, approval_status, rups_approval_date, effective_from, effective_until, is_active)
VALUES

  -- Theme Park operations (Dufan, Atlantis, Sea World)
  ('b0000000-0000-0000-0000-000000000001', 2026, 'TP-01-DUFAN-REFURB', 'theme_park',
   'Refurbishment wahana Dufan tahun 2026',
   'Peremajaan 3 wahana utama di Dunia Fantasi: Halilintar, Tornado, Ice Age.',
   45000000000.00, 'rups_approved', '2025-11-28', '2026-01-01', '2026-12-31', true),

  ('b0000000-0000-0000-0000-000000000002', 2026, 'TP-02-ATLANTIS-OP', 'theme_park',
   'Operasional dan pemeliharaan Atlantis Water Adventure 2026',
   'Biaya operasional rutin water park, termasuk filtrasi dan keselamatan.',
   28000000000.00, 'rups_approved', '2025-11-28', '2026-01-01', '2026-12-31', true),

  ('b0000000-0000-0000-0000-000000000003', 2026, 'TP-03-SEAWORLD-EXPAND', 'marine',
   'Ekspansi exhibit Sea World Ancol',
   'Penambahan 2 exhibit baru: Coral Triangle dan Deep Reef.',
   18000000000.00, 'rups_approved', '2025-11-28', '2026-01-01', '2026-12-31', true),

  -- Beach City (integrated resort development)
  ('b0000000-0000-0000-0000-000000000004', 2026, 'BC-01-PIER-CONSTRUCTION', 'beach_city',
   'Pembangunan dermaga wisata Ancol Beach City Fase 2',
   'Lanjutan konstruksi dermaga wisata terpadu, termasuk fasilitas drop-off.',
   120000000000.00, 'rups_approved', '2025-11-28', '2026-02-01', '2026-12-31', true),

  ('b0000000-0000-0000-0000-000000000005', 2026, 'BC-02-HOTEL-JV', 'beach_city',
   'Joint venture pengembangan hotel bintang 5 Ancol Beach City',
   'Partnership dengan investor strategis untuk pembangunan hotel 250 kamar.',
   200000000000.00, 'dewas_approved', NULL, '2026-03-01', '2027-12-31', true),

  -- Property (residential, commercial)
  ('b0000000-0000-0000-0000-000000000006', 2026, 'PR-01-RESIDENTIAL-LAUNCH', 'property',
   'Launching klaster residensial North Ancol Residence',
   'Pelepasan 120 unit tahap pertama, marketing + infrastruktur.',
   85000000000.00, 'rups_approved', '2025-11-28', '2026-04-01', '2026-12-31', true),

  ('b0000000-0000-0000-0000-000000000007', 2026, 'PR-02-RETAIL-LEASE', 'property',
   'Komersialisasi area retail strip mall Ancol',
   'Penyewaan 15 unit retail di area MCB dan Pantai Festival.',
   8000000000.00, 'direksi_approved', NULL, '2026-01-15', '2026-12-31', true),

  -- Corporate / strategic
  ('b0000000-0000-0000-0000-000000000008', 2026, 'CO-01-DIGITAL-TRANSFORM', 'corporate',
   'Transformasi digital sistem ticketing dan CRM',
   'Implementasi unified ticketing platform, mobile app, CRM terintegrasi.',
   22000000000.00, 'rups_approved', '2025-11-28', '2026-01-01', '2026-12-31', true),

  ('b0000000-0000-0000-0000-000000000009', 2026, 'CO-02-ESG-INITIATIVE', 'corporate',
   'Program ESG dan sustainability reporting',
   'Initiative pengurangan emisi, sertifikasi ISO 14001, laporan GRI.',
   5000000000.00, 'rups_approved', '2025-11-28', '2026-01-01', '2026-12-31', true),

  ('b0000000-0000-0000-0000-000000000010', 2026, 'CO-03-LAND-ACQUISITION', 'property',
   'Akuisisi lahan strategis untuk ekspansi kawasan',
   'Pembelian 3 hektar lahan adjacent untuk pengembangan terintegrasi.',
   150000000000.00, 'rups_approved', '2025-11-28', '2026-06-01', '2026-12-31', true)

ON CONFLICT (fiscal_year, code) DO NOTHING;


-- RJPP 2025-2029 themes placeholder
INSERT INTO rjpp_themes
  (id, period_start_year, period_end_year, theme_name, description, target_metrics, approval_ref, is_active)
VALUES
  ('c0000000-0000-0000-0000-000000000001', 2025, 2029,
   'Integrated Destination Revitalization',
   'Revitalisasi kawasan Ancol sebagai destinasi integrasi: theme park, marine, property, F&B.',
   '{"visitor_target": 25000000, "revenue_target_idr": 3500000000000}'::jsonb,
   'RJPP-PJAA-2025-2029-v1', true),

  ('c0000000-0000-0000-0000-000000000002', 2025, 2029,
   'Ancol Beach City Development',
   'Pengembangan integrated resort Ancol Beach City sebagai flagship property Ancol.',
   '{"gfa_target_sqm": 450000, "opening_year": 2028}'::jsonb,
   'RJPP-PJAA-2025-2029-v1', true),

  ('c0000000-0000-0000-0000-000000000003', 2025, 2029,
   'Digital & Operational Excellence',
   'Digital transformation + efisiensi operasional + ESG compliance.',
   '{"digital_revenue_pct": 60, "opex_reduction_pct": 15}'::jsonb,
   'RJPP-PJAA-2025-2029-v1', true)

ON CONFLICT (id) DO NOTHING;
