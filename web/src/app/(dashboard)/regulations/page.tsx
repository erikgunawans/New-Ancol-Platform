"use client";

const REGULATIONS = [
  { id: "UU-PT-40-2007", title: "UU No. 40/2007 tentang Perseroan Terbatas", type: "external", domain: "Corporate Governance", date: "2007-08-16" },
  { id: "POJK-33-2014", title: "POJK 33/2014 tentang Direksi dan Komisaris Emiten", type: "external", domain: "Board Governance", date: "2014-12-08" },
  { id: "POJK-42-2020", title: "POJK 42/2020 tentang Transaksi Afiliasi", type: "external", domain: "Related Party Transactions", date: "2020-07-01" },
  { id: "POJK-21-2015", title: "POJK 21/2015 tentang Tata Kelola Perusahaan Terbuka", type: "external", domain: "Corporate Governance", date: "2015-11-16" },
  { id: "IDX-I-A", title: "Peraturan BEI No. I-A tentang Pencatatan Saham", type: "external", domain: "Listing Rules", date: "2018-02-06" },
  { id: "ADART-PJAA", title: "Anggaran Dasar PT Pembangunan Jaya Ancol Tbk", type: "internal", domain: "Corporate Charter", date: "2022-06-15" },
  { id: "BOD-CHARTER-PJAA", title: "Piagam Direksi PJAA", type: "internal", domain: "Board Charter", date: "2023-01-01" },
  { id: "BOC-CHARTER-PJAA", title: "Piagam Dewan Komisaris PJAA", type: "internal", domain: "Board Charter", date: "2023-01-01" },
  { id: "RPT-POLICY-PJAA", title: "Kebijakan Transaksi Pihak Berelasi PJAA", type: "internal", domain: "Related Party Transactions", date: "2021-07-01" },
];

export default function RegulationsPage() {
  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Corpus Regulasi</h1>

      {/* External */}
      <div className="mb-8">
        <h2 className="text-lg font-semibold text-gray-800 mb-3">Regulasi Eksternal</h2>
        <div className="space-y-2">
          {REGULATIONS.filter((r) => r.type === "external").map((reg) => (
            <div key={reg.id} className="bg-white rounded-xl shadow-sm border border-gray-200 p-4 flex items-center justify-between">
              <div>
                <h3 className="font-medium text-gray-900 text-sm">{reg.title}</h3>
                <div className="flex gap-3 mt-1">
                  <span className="text-xs text-gray-500">{reg.id}</span>
                  <span className="text-xs px-2 py-0.5 bg-blue-50 text-blue-700 rounded">{reg.domain}</span>
                  <span className="text-xs text-gray-400">Efektif: {reg.date}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Internal */}
      <div>
        <h2 className="text-lg font-semibold text-gray-800 mb-3">Regulasi Internal</h2>
        <div className="space-y-2">
          {REGULATIONS.filter((r) => r.type === "internal").map((reg) => (
            <div key={reg.id} className="bg-white rounded-xl shadow-sm border border-gray-200 p-4 flex items-center justify-between">
              <div>
                <h3 className="font-medium text-gray-900 text-sm">{reg.title}</h3>
                <div className="flex gap-3 mt-1">
                  <span className="text-xs text-gray-500">{reg.id}</span>
                  <span className="text-xs px-2 py-0.5 bg-purple-50 text-purple-700 rounded">{reg.domain}</span>
                  <span className="text-xs text-gray-400">Efektif: {reg.date}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
