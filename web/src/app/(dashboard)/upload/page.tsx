"use client";

import { useCallback, useState } from "react";
import { uploadDocument } from "@/lib/api";

export default function UploadPage() {
  const [files, setFiles] = useState<File[]>([]);
  const [momType, setMomType] = useState("regular");
  const [meetingDate, setMeetingDate] = useState("");
  const [uploading, setUploading] = useState(false);
  const [results, setResults] = useState<{ filename: string; status: string; id?: string }[]>([]);
  const [dragActive, setDragActive] = useState(false);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragActive(false);
    const dropped = Array.from(e.dataTransfer.files);
    setFiles((prev) => [...prev, ...dropped]);
  }, []);

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) setFiles((prev) => [...prev, ...Array.from(e.target.files!)]);
  };

  const handleUpload = async () => {
    setUploading(true);
    const uploadResults = [];

    for (const file of files) {
      try {
        const res = await uploadDocument(file, momType, meetingDate || undefined);
        uploadResults.push({ filename: file.name, status: "success", id: res.id });
      } catch (err) {
        uploadResults.push({ filename: file.name, status: "error" });
      }
    }

    setResults(uploadResults);
    setFiles([]);
    setUploading(false);
  };

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Upload Risalah Rapat</h1>

      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
        {/* Drop Zone */}
        <div
          onDragOver={(e) => { e.preventDefault(); setDragActive(true); }}
          onDragLeave={() => setDragActive(false)}
          onDrop={handleDrop}
          className={`border-2 border-dashed rounded-xl p-12 text-center transition-colors ${
            dragActive ? "border-ancol-500 bg-ancol-50" : "border-gray-300 hover:border-gray-400"
          }`}
        >
          <div className="text-4xl mb-3">📄</div>
          <p className="text-gray-600 mb-2">Drag & drop file risalah rapat di sini</p>
          <p className="text-sm text-gray-400 mb-4">PDF, Word, atau scan (JPG/PNG/TIFF)</p>
          <label className="inline-block px-4 py-2 bg-ancol-500 text-white rounded-lg cursor-pointer hover:bg-ancol-600 transition-colors">
            Pilih File
            <input type="file" className="hidden" multiple accept=".pdf,.doc,.docx,.jpg,.png,.tiff" onChange={handleFileInput} />
          </label>
        </div>

        {/* File List */}
        {files.length > 0 && (
          <div className="mt-4 space-y-2">
            {files.map((f, i) => (
              <div key={i} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                <div>
                  <span className="text-sm font-medium">{f.name}</span>
                  <span className="text-xs text-gray-400 ml-2">({(f.size / 1024).toFixed(0)} KB)</span>
                </div>
                <button onClick={() => setFiles(files.filter((_, j) => j !== i))} className="text-gray-400 hover:text-red-500 text-sm">Hapus</button>
              </div>
            ))}
          </div>
        )}

        {/* Options */}
        <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Jenis Rapat</label>
            <select value={momType} onChange={(e) => setMomType(e.target.value)} className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm">
              <option value="regular">Rapat Rutin</option>
              <option value="circular">Keputusan Sirkuler</option>
              <option value="extraordinary">Rapat Luar Biasa</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Tanggal Rapat</label>
            <input type="date" value={meetingDate} onChange={(e) => setMeetingDate(e.target.value)} className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm" />
          </div>
        </div>

        {/* Upload Button */}
        <button
          onClick={handleUpload}
          disabled={files.length === 0 || uploading}
          className="mt-6 w-full py-3 bg-ancol-500 text-white rounded-lg font-medium hover:bg-ancol-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {uploading ? "Mengupload..." : `Upload ${files.length} File`}
        </button>
      </div>

      {/* Results */}
      {results.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h2 className="text-lg font-semibold mb-3">Hasil Upload</h2>
          {results.map((r, i) => (
            <div key={i} className={`p-3 rounded-lg mb-2 ${r.status === "success" ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"}`}>
              <span className="font-medium">{r.filename}</span>
              {r.status === "success" ? <span className="ml-2 text-sm">Berhasil diupload</span> : <span className="ml-2 text-sm">Gagal</span>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
