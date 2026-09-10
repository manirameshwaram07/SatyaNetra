import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { CloudUpload, FileSearch, Loader2, ShieldAlert } from "lucide-react";
import { apiErrorMessage, startScreening, uploadDocument } from "../services/api";
import type { UploadResponse } from "../types";

const DOC_TYPES = ["", "PASSPORT", "VISA", "NATIONAL_ID", "DRIVING_LICENSE", "PERMIT"];
const ACCEPT = ".jpg,.jpeg,.png,.webp,.pdf";

export default function Screening() {
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [docType, setDocType] = useState("");
  const [uploaded, setUploaded] = useState<UploadResponse | null>(null);

  const handleFile = async (file: File) => {
    setError("");
    setUploaded(null);
    setBusy(true);
    try {
      const res = await uploadDocument(file, docType);
      setUploaded(res);
      // Immediately start the AI screening pipeline
      const vid = await startScreening(res.document_id);
      navigate(`/analysis/${vid}`);
    } catch (e) {
      setError(apiErrorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file) void handleFile(file);
  };

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
          <FileSearch className="w-6 h-6 text-cyan-400" /> Document Screening
        </h1>
        <p className="text-sm text-slate-500">
          Upload a passport, visa, national ID, driving licence or permit. The file is sent to the
          FastAPI backend where the full AI pipeline runs.
        </p>
      </header>

      <div className="glass p-4">
        <label className="text-xs text-slate-400 font-medium">Document type (optional hint)</label>
        <select
          className="input-field mt-1 max-w-xs"
          value={docType}
          onChange={(e) => setDocType(e.target.value)}
        >
          {DOC_TYPES.map((t) => (
            <option key={t} value={t}>{t || "Auto-detect"}</option>
          ))}
        </select>
      </div>

      <motion.div
        initial={{ opacity: 0, scale: 0.98 }}
        animate={{ opacity: 1, scale: 1 }}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
        className={`relative cursor-pointer rounded-2xl border-2 border-dashed p-14 text-center transition-all
          ${dragOver ? "border-cyan-400 bg-cyan-500/5" : "border-night-700 hover:border-cyan-500/50"}`}
      >
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPT}
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) void handleFile(f);
            e.target.value = "";
          }}
        />
        <div className="relative">
          {busy ? (
            <Loader2 className="w-14 h-14 text-cyan-400 mx-auto animate-spin" />
          ) : (
            <CloudUpload className="w-14 h-14 text-cyan-400 mx-auto" />
          )}
          <div className="mt-4 text-lg font-semibold text-slate-200">
            {busy ? "Uploading to backend…" : "Drag & drop a document here"}
          </div>
          <div className="text-sm text-slate-500 mt-1">
            or click to browse — PDF, PNG, JPG, JPEG, WEBP (max 10 MB)
          </div>
          <div className="mt-4 inline-flex items-center gap-2 text-xs text-cyan-300/80 font-mono
            bg-cyan-500/5 border border-cyan-500/20 rounded-full px-3 py-1">
            Upload → FastAPI → OCR → Forensics → Risk Engine → Result
          </div>
        </div>
        {dragOver && (
          <div className="pointer-events-none absolute inset-x-8 top-0 h-1 rounded-full bg-cyan-400/60 animate-scan-line" />
        )}
      </motion.div>

      {error && (
        <div className="glass p-4 border-red-500/40 flex items-start gap-3 text-red-300">
          <ShieldAlert className="w-5 h-5 mt-0.5 shrink-0" />
          <div>
            <div className="font-semibold">Upload failed</div>
            <div className="text-sm text-red-300/80">{error}</div>
          </div>
        </div>
      )}

      {uploaded && !error && (
        <div className="glass p-4 text-sm text-slate-300">
          Stored document <span className="font-mono text-cyan-300">#{uploaded.document_id}</span>{" "}
          · SHA-256 <span className="font-mono text-xs text-slate-500">{uploaded.document_hash.slice(0, 24)}…</span>
        </div>
      )}
    </div>
  );
}