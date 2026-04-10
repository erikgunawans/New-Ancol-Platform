-- Seed: MoM template registry v1
-- Templates based on PJAA corporate governance structure and Indonesian corporate law

-- Regular Board of Directors Meeting (Rapat Direksi Rutin)
INSERT INTO mom_templates (id, name, version, mom_type, effective_from, required_sections, quorum_rules, signature_rules, field_definitions, is_active) VALUES
(
  'b0000000-0000-0000-0000-000000000001',
  'Rapat Direksi Rutin (Post-2020)',
  1,
  'regular',
  '2020-01-01',
  '{
    "sections": [
      {"name": "opening", "label": "Pembukaan", "required": true},
      {"name": "attendance", "label": "Daftar Hadir", "required": true},
      {"name": "quorum_verification", "label": "Verifikasi Kuorum", "required": true},
      {"name": "agenda", "label": "Agenda Rapat", "required": true},
      {"name": "discussion", "label": "Pembahasan", "required": true},
      {"name": "resolutions", "label": "Keputusan Rapat", "required": true},
      {"name": "performance_review", "label": "Tinjauan Kinerja", "required": false},
      {"name": "closing", "label": "Penutup", "required": true},
      {"name": "signatures", "label": "Tanda Tangan", "required": true}
    ]
  }',
  '{
    "min_directors_present": 3,
    "min_percentage": 50,
    "chairman_required": true,
    "voting_rule": "majority",
    "abstention_allowed": true,
    "proxy_allowed": false,
    "reference": "UU PT 40/2007 Pasal 98"
  }',
  '{
    "required_signers": ["chairman", "secretary"],
    "all_present_must_sign": false,
    "digital_signature_allowed": false,
    "reference": "AD/ART PJAA"
  }',
  '{
    "meeting_date": {"type": "date", "required": true},
    "meeting_time": {"type": "time", "required": true},
    "location": {"type": "string", "required": true},
    "meeting_number": {"type": "string", "required": true},
    "chairman": {"type": "string", "required": true},
    "secretary": {"type": "string", "required": true},
    "attendees": {"type": "array", "required": true},
    "agenda_items": {"type": "array", "required": true},
    "resolutions": {"type": "array", "required": true}
  }',
  true
),

-- Circular Resolution (Keputusan Sirkuler)
(
  'b0000000-0000-0000-0000-000000000002',
  'Keputusan Sirkuler Direksi',
  1,
  'circular',
  '2020-01-01',
  '{
    "sections": [
      {"name": "preamble", "label": "Pendahuluan", "required": true},
      {"name": "background", "label": "Latar Belakang", "required": true},
      {"name": "resolution_text", "label": "Bunyi Keputusan", "required": true},
      {"name": "effective_date", "label": "Tanggal Berlaku", "required": true},
      {"name": "signatures", "label": "Tanda Tangan", "required": true}
    ]
  }',
  '{
    "min_directors_present": 0,
    "min_percentage": 100,
    "chairman_required": false,
    "voting_rule": "unanimous",
    "abstention_allowed": false,
    "proxy_allowed": false,
    "reference": "UU PT 40/2007 Pasal 91, AD/ART PJAA"
  }',
  '{
    "required_signers": ["all_directors"],
    "all_present_must_sign": true,
    "digital_signature_allowed": false,
    "reference": "UU PT 40/2007 Pasal 91"
  }',
  '{
    "circulation_date": {"type": "date", "required": true},
    "response_deadline": {"type": "date", "required": true},
    "resolution_number": {"type": "string", "required": true},
    "resolution_text": {"type": "text", "required": true},
    "all_director_signatures": {"type": "array", "required": true}
  }',
  true
),

-- Extraordinary Board Meeting (Rapat Direksi Luar Biasa)
(
  'b0000000-0000-0000-0000-000000000003',
  'Rapat Direksi Luar Biasa',
  1,
  'extraordinary',
  '2020-01-01',
  '{
    "sections": [
      {"name": "opening", "label": "Pembukaan", "required": true},
      {"name": "urgency_statement", "label": "Pernyataan Urgensi", "required": true},
      {"name": "attendance", "label": "Daftar Hadir", "required": true},
      {"name": "quorum_verification", "label": "Verifikasi Kuorum", "required": true},
      {"name": "agenda", "label": "Agenda Rapat", "required": true},
      {"name": "discussion", "label": "Pembahasan", "required": true},
      {"name": "resolutions", "label": "Keputusan Rapat", "required": true},
      {"name": "closing", "label": "Penutup", "required": true},
      {"name": "signatures", "label": "Tanda Tangan", "required": true}
    ]
  }',
  '{
    "min_directors_present": 4,
    "min_percentage": 67,
    "chairman_required": true,
    "voting_rule": "supermajority",
    "abstention_allowed": false,
    "proxy_allowed": false,
    "reference": "AD/ART PJAA, UU PT 40/2007"
  }',
  '{
    "required_signers": ["chairman", "all_present"],
    "all_present_must_sign": true,
    "digital_signature_allowed": false,
    "reference": "AD/ART PJAA"
  }',
  '{
    "meeting_date": {"type": "date", "required": true},
    "meeting_time": {"type": "time", "required": true},
    "location": {"type": "string", "required": true},
    "meeting_number": {"type": "string", "required": true},
    "urgency_reason": {"type": "text", "required": true},
    "convened_by": {"type": "string", "required": true},
    "notice_date": {"type": "date", "required": true},
    "chairman": {"type": "string", "required": true},
    "secretary": {"type": "string", "required": true},
    "attendees": {"type": "array", "required": true},
    "resolutions": {"type": "array", "required": true}
  }',
  true
)
ON CONFLICT DO NOTHING;
