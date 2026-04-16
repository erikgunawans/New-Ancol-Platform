-- Seed: initial users for dev/pilot environment
-- PT Pembangunan Jaya Ancol Tbk roles

INSERT INTO users (id, email, display_name, role, department, is_active) VALUES
  -- Corporate Secretary team
  ('a0000000-0000-0000-0000-000000000001', 'corpsec@ancol.co.id', 'Corporate Secretary', 'corp_secretary', 'Corporate Secretary', true),
  ('a0000000-0000-0000-0000-000000000002', 'corpsec.staff@ancol.co.id', 'Staff Sekretaris Perusahaan', 'corp_secretary', 'Corporate Secretary', true),

  -- Internal Audit team
  ('a0000000-0000-0000-0000-000000000003', 'audit.head@ancol.co.id', 'Kepala SPI', 'internal_auditor', 'Internal Audit', true),
  ('a0000000-0000-0000-0000-000000000004', 'auditor@ancol.co.id', 'Auditor Internal', 'internal_auditor', 'Internal Audit', true),

  -- Komisaris
  ('a0000000-0000-0000-0000-000000000005', 'komisaris.utama@ancol.co.id', 'Komisaris Utama', 'komisaris', 'Board of Commissioners', true),
  ('a0000000-0000-0000-0000-000000000006', 'komisaris@ancol.co.id', 'Anggota Dewan Komisaris', 'komisaris', 'Board of Commissioners', true),

  -- Legal & Compliance
  ('a0000000-0000-0000-0000-000000000007', 'legal.head@ancol.co.id', 'Kepala Legal & Compliance', 'legal_compliance', 'Legal', true),
  ('a0000000-0000-0000-0000-000000000008', 'legal@ancol.co.id', 'Staff Legal', 'legal_compliance', 'Legal', true),

  -- Admin
  ('a0000000-0000-0000-0000-000000000009', 'admin@ancol.co.id', 'System Administrator', 'admin', 'IT', true)
ON CONFLICT (email) DO NOTHING;

-- Set manager chains for escalation
UPDATE users SET manager_id = 'a0000000-0000-0000-0000-000000000001' WHERE id = 'a0000000-0000-0000-0000-000000000002';
UPDATE users SET manager_id = 'a0000000-0000-0000-0000-000000000003' WHERE id = 'a0000000-0000-0000-0000-000000000004';
UPDATE users SET manager_id = 'a0000000-0000-0000-0000-000000000005' WHERE id = 'a0000000-0000-0000-0000-000000000006';
UPDATE users SET manager_id = 'a0000000-0000-0000-0000-000000000007' WHERE id = 'a0000000-0000-0000-0000-000000000008';

-- Set phone numbers for WhatsApp notifications (Indonesian +62 format)
UPDATE users SET phone_number = '+6281234567001' WHERE email = 'corpsec@ancol.co.id';
UPDATE users SET phone_number = '+6281234567002' WHERE email = 'corpsec.staff@ancol.co.id';
UPDATE users SET phone_number = '+6281234567003' WHERE email = 'audit.head@ancol.co.id';
UPDATE users SET phone_number = '+6281234567004' WHERE email = 'auditor@ancol.co.id';
UPDATE users SET phone_number = '+6281234567005' WHERE email = 'komisaris.utama@ancol.co.id';
UPDATE users SET phone_number = '+6281234567006' WHERE email = 'komisaris@ancol.co.id';
UPDATE users SET phone_number = '+6281234567007' WHERE email = 'legal.head@ancol.co.id';
UPDATE users SET phone_number = '+6281234567008' WHERE email = 'legal@ancol.co.id';
UPDATE users SET phone_number = '+6281234567009' WHERE email = 'admin@ancol.co.id';
