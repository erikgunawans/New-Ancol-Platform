"use client";

import { useState } from "react";
import { generateDraft, generateDraftPdf } from "@/lib/api";
import { CONTRACT_TYPE_LABELS } from "@/lib/contracts";
import type { DraftFormData, DraftResult, ContractType } from "@/types";

interface PartyInput {
  name: string;
  role: "principal" | "counterparty" | "guarantor";
  entity_type: "internal" | "external" | "related_party";
  contact_email?: string;
}

const CONTRACT_TYPES = Object.entries(CONTRACT_TYPE_LABELS).map(
  ([value, label]) => ({ value: value as ContractType, label })
);

const ROLE_LABELS: Record<string, string> = {
  principal: "Pihak Pertama",
  counterparty: "Pihak Kedua",
  guarantor: "Penjamin",
};

const ENTITY_TYPE_LABELS: Record<string, string> = {
  internal: "Internal",
  external: "Eksternal",
  related_party: "Pihak Berelasi",
};

function renderDraftLine(line: string, i: number) {
  if (line.startsWith("# "))
    return (
      <h1 key={i} className="text-xl font-bold text-gray-900 mb-4">
        {line.slice(2)}
      </h1>
    );
  if (line.startsWith("## "))
    return (
      <h2
        key={i}
        className="text-base font-semibold text-gray-800 mt-6 mb-2 border-b pb-1"
      >
        {line.slice(3)}
      </h2>
    );
  if (line.startsWith("- "))
    return (
      <div key={i} className="text-sm text-gray-700 ml-4 mb-1">
        {line.slice(2)}
      </div>
    );
  if (line.trim() === "") return <div key={i} className="h-2" />;
  return (
    <p key={i} className="text-sm text-gray-700">
      {line}
    </p>
  );
}

const DEFAULT_PARTIES: PartyInput[] = [
  {
    name: "PT Pembangunan Jaya Ancol Tbk",
    role: "principal",
    entity_type: "internal",
  },
  { name: "", role: "counterparty", entity_type: "external" },
];

const DEFAULT_KEY_TERMS = [
  { key: "value", value: "" },
  { key: "duration", value: "" },
];

export default function DraftGeneratorPage() {
  const [contractType, setContractType] = useState<ContractType>("vendor");
  const [parties, setParties] = useState<PartyInput[]>(
    DEFAULT_PARTIES.map((p) => ({ ...p }))
  );
  const [keyTerms, setKeyTerms] = useState<Array<{ key: string; value: string }>>(
    DEFAULT_KEY_TERMS.map((t) => ({ ...t }))
  );
  const [language, setLanguage] = useState<"id" | "en">("id");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<DraftResult | null>(null);
  const [pdfHtml, setPdfHtml] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const validParties = parties.filter((p) => p.name.trim() !== "");
  const canGenerate = !loading && validParties.length > 0;

  function buildFormData(): DraftFormData {
    const keyTermsMap: Record<string, string> = {};
    for (const t of keyTerms) {
      if (t.key.trim()) keyTermsMap[t.key.trim()] = t.value;
    }
    return {
      contract_type: contractType,
      parties: validParties.map((p) => ({
        name: p.name,
        role: p.role,
        entity_type: p.entity_type,
        contact_email: p.contact_email || undefined,
      })),
      key_terms: keyTermsMap,
      language,
    };
  }

  async function handleGenerate() {
    setLoading(true);
    setError(null);
    setResult(null);
    setPdfHtml(null);
    try {
      const data = buildFormData();
      const [draftRes, pdfRes] = await Promise.all([
        generateDraft(data),
        generateDraftPdf(data),
      ]);
      setResult(draftRes);
      setPdfHtml(pdfRes.html);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Gagal membuat draf");
    } finally {
      setLoading(false);
    }
  }

  function handlePdfExport() {
    if (!pdfHtml) return;
    const blob = new Blob([pdfHtml], { type: "text/html" });
    const url = URL.createObjectURL(blob);
    window.open(url, "_blank", "noopener,noreferrer");
    setTimeout(() => URL.revokeObjectURL(url), 10_000);
  }

  function updateParty(index: number, field: keyof PartyInput, value: string) {
    setParties((prev) =>
      prev.map((p, i) =>
        i === index ? { ...p, [field]: value } : p
      )
    );
  }

  function removeParty(index: number) {
    setParties((prev) => prev.filter((_, i) => i !== index));
  }

  function addParty() {
    setParties((prev) => [
      ...prev,
      { name: "", role: "counterparty", entity_type: "external" },
    ]);
  }

  function updateKeyTerm(index: number, field: "key" | "value", val: string) {
    setKeyTerms((prev) =>
      prev.map((t, i) => (i === index ? { ...t, [field]: val } : t))
    );
  }

  function removeKeyTerm(index: number) {
    setKeyTerms((prev) => prev.filter((_, i) => i !== index));
  }

  function addKeyTerm() {
    setKeyTerms((prev) => [...prev, { key: "", value: "" }]);
  }

  return (
    <div className="max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Buat Draf Kontrak</h1>

      {/* Contract Type Picker */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
        <h2 className="text-sm font-semibold text-gray-700 mb-3">Tipe Kontrak</h2>
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
          {CONTRACT_TYPES.map((ct) => (
            <button
              key={ct.value}
              type="button"
              onClick={() => setContractType(ct.value)}
              className={`rounded-lg border px-4 py-3 text-sm font-medium transition-colors ${
                contractType === ct.value
                  ? "border-blue-500 bg-blue-50 text-blue-700"
                  : "border-gray-200 bg-white text-gray-700 hover:border-gray-300 hover:bg-gray-50"
              }`}
            >
              {ct.label}
            </button>
          ))}
        </div>
      </div>

      {/* Parties Section */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
        <h2 className="text-sm font-semibold text-gray-700 mb-3">Pihak-Pihak</h2>
        <div className="space-y-4">
          {parties.map((party, idx) => (
            <div key={idx} className="flex flex-wrap items-start gap-3">
              <input
                type="text"
                placeholder="Nama pihak"
                value={party.name}
                onChange={(e) => updateParty(idx, "name", e.target.value)}
                className="border border-gray-300 rounded-lg px-3 py-2 text-sm flex-1 min-w-[180px]"
              />
              <select
                value={party.role}
                onChange={(e) => updateParty(idx, "role", e.target.value)}
                className="border border-gray-300 rounded-lg px-3 py-2 text-sm"
              >
                {Object.entries(ROLE_LABELS).map(([val, label]) => (
                  <option key={val} value={val}>
                    {label}
                  </option>
                ))}
              </select>
              <select
                value={party.entity_type}
                onChange={(e) => updateParty(idx, "entity_type", e.target.value)}
                className="border border-gray-300 rounded-lg px-3 py-2 text-sm"
              >
                {Object.entries(ENTITY_TYPE_LABELS).map(([val, label]) => (
                  <option key={val} value={val}>
                    {label}
                  </option>
                ))}
              </select>
              <input
                type="email"
                placeholder="Email (opsional)"
                value={party.contact_email || ""}
                onChange={(e) => updateParty(idx, "contact_email", e.target.value)}
                className="border border-gray-300 rounded-lg px-3 py-2 text-sm w-48"
              />
              <button
                type="button"
                onClick={() => removeParty(idx)}
                className="text-gray-400 hover:text-red-500 px-2 py-2 text-sm font-medium"
              >
                x
              </button>
            </div>
          ))}
        </div>
        <button
          type="button"
          onClick={addParty}
          className="mt-3 text-sm text-blue-600 hover:text-blue-700 font-medium"
        >
          + Tambah Pihak
        </button>
      </div>

      {/* Key Terms Section */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
        <h2 className="text-sm font-semibold text-gray-700 mb-3">Ketentuan Utama</h2>
        <div className="space-y-3">
          {keyTerms.map((term, idx) => (
            <div key={idx} className="flex items-center gap-3">
              <input
                type="text"
                placeholder="Kunci"
                value={term.key}
                onChange={(e) => updateKeyTerm(idx, "key", e.target.value)}
                className="border border-gray-300 rounded-lg px-3 py-2 text-sm w-40"
              />
              <input
                type="text"
                placeholder="Nilai"
                value={term.value}
                onChange={(e) => updateKeyTerm(idx, "value", e.target.value)}
                className="border border-gray-300 rounded-lg px-3 py-2 text-sm flex-1"
              />
              <button
                type="button"
                onClick={() => removeKeyTerm(idx)}
                className="text-gray-400 hover:text-red-500 px-2 py-2 text-sm font-medium"
              >
                x
              </button>
            </div>
          ))}
        </div>
        <button
          type="button"
          onClick={addKeyTerm}
          className="mt-3 text-sm text-blue-600 hover:text-blue-700 font-medium"
        >
          + Tambah
        </button>
      </div>

      {/* Language Selector + Generate Button */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
        <div className="flex items-center justify-between">
          <div>
            <label className="text-sm font-semibold text-gray-700 mr-3">Bahasa</label>
            <select
              value={language}
              onChange={(e) => setLanguage(e.target.value as "id" | "en")}
              className="border border-gray-300 rounded-lg px-3 py-2 text-sm"
            >
              <option value="id">Bahasa Indonesia</option>
              <option value="en">English</option>
            </select>
          </div>
          <button
            type="button"
            onClick={handleGenerate}
            disabled={!canGenerate}
            className={`px-6 py-2.5 rounded-lg text-sm font-medium text-white transition-colors ${
              canGenerate
                ? "bg-blue-600 hover:bg-blue-700"
                : "bg-gray-300 cursor-not-allowed"
            }`}
          >
            {loading ? "Memproses..." : "Buat Draf"}
          </button>
        </div>
      </div>

      {/* Error Display */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 mb-6">
          <p className="text-sm text-red-700">{error}</p>
        </div>
      )}

      {/* Preview Section */}
      {result && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-900">Pratinjau Draf</h2>
            <button
              type="button"
              onClick={handlePdfExport}
              disabled={!pdfHtml}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                !pdfHtml
                  ? "bg-gray-300 text-gray-500 cursor-not-allowed"
                  : "bg-green-600 hover:bg-green-700 text-white"
              }`}
            >
              Buka sebagai PDF
            </button>
          </div>

          {/* Draft Text */}
          <div className="border border-gray-100 rounded-lg p-6 bg-gray-50 mb-6">
            {result.draft_text.split("\n").map((line, i) => renderDraftLine(line, i))}
          </div>

          {/* Risk Assessment */}
          {result.risk_assessment && result.risk_assessment.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-gray-700 mb-3">
                Penilaian Risiko
              </h3>
              <div className="space-y-2">
                {result.risk_assessment.map((item, idx) => (
                  <div
                    key={idx}
                    className="border border-gray-200 rounded-lg px-4 py-3 bg-gray-50"
                  >
                    {Object.entries(item).map(([k, v]) => (
                      <p key={k} className="text-sm text-gray-700">
                        <span className="font-medium text-gray-900">{k}:</span> {v}
                      </p>
                    ))}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
