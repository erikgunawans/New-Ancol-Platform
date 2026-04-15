// Shared label and color maps for contract + obligation UI components.

export const CONTRACT_STATUS_LABELS: Record<string, string> = {
  draft: "Draf",
  pending_review: "Menunggu Review",
  in_review: "Dalam Review",
  approved: "Disetujui",
  executed: "Ditandatangani",
  active: "Aktif",
  expiring: "Akan Berakhir",
  expired: "Berakhir",
  terminated: "Dibatalkan",
  amended: "Diamandemen",
  failed: "Gagal",
};

export const CONTRACT_STATUS_COLORS: Record<string, string> = {
  draft: "bg-gray-100 text-gray-700",
  pending_review: "bg-yellow-100 text-yellow-700",
  in_review: "bg-blue-100 text-blue-700",
  approved: "bg-green-100 text-green-700",
  executed: "bg-green-100 text-green-700",
  active: "bg-emerald-100 text-emerald-700",
  expiring: "bg-orange-100 text-orange-700",
  expired: "bg-red-100 text-red-700",
  terminated: "bg-red-100 text-red-700",
  amended: "bg-purple-100 text-purple-700",
  failed: "bg-red-100 text-red-700",
};

export const CONTRACT_TYPE_LABELS: Record<string, string> = {
  nda: "NDA",
  vendor: "Vendor",
  sale_purchase: "Jual Beli",
  joint_venture: "Joint Venture",
  land_lease: "Sewa Tanah",
  employment: "Ketenagakerjaan",
  sop_board_resolution: "SOP/SK Direksi",
};

export const RISK_COLORS: Record<string, string> = {
  high: "bg-red-100 text-red-700",
  medium: "bg-yellow-100 text-yellow-700",
  low: "bg-green-100 text-green-700",
};

export const OBLIGATION_STATUS_LABELS: Record<string, string> = {
  upcoming: "Akan Datang",
  due_soon: "Segera Jatuh Tempo",
  overdue: "Terlambat",
  fulfilled: "Terpenuhi",
  waived: "Dikesampingkan",
};

export const OBLIGATION_STATUS_COLORS: Record<string, string> = {
  upcoming: "bg-blue-100 text-blue-700",
  due_soon: "bg-orange-100 text-orange-700",
  overdue: "bg-red-100 text-red-700",
  fulfilled: "bg-green-100 text-green-700",
  waived: "bg-gray-100 text-gray-600",
};

export const OBLIGATION_TYPE_LABELS: Record<string, string> = {
  renewal: "Perpanjangan",
  reporting: "Pelaporan",
  payment: "Pembayaran",
  termination_notice: "Notifikasi Pemutusan",
  deliverable: "Deliverable",
  compliance_filing: "Filing Kepatuhan",
};
