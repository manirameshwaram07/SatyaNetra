import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Link2, ShieldCheck, ShieldX } from "lucide-react";
import {
  apiErrorMessage, getAuditTrail, getScreeningHistory,
} from "../services/api";
import type { AuditChainResponse, ScreeningHistoryItem } from "../types";

export default function AuditTrail() {
  const [screenings, setScreenings] = useState<ScreeningHistoryItem[]>([]);
  const [selected, setSelected] = useState("");
  const [chain, setChain] = useState<AuditChainResponse | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getScreeningHistory(50)
      .then((s) => {
        setScreenings(s);
        if (s.length > 0) setSelected(s[0].verification_id);
      })
      .catch((e) => setError(apiErrorMessage(e)));
  }, []);

  useEffect(() => {
    if (!selected) return;
    setChain(null);
    getAuditTrail(selected)
      .then(setChain)
      .catch((e) => setError(apiErrorMessage(e)));
  }, [selected]);

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
          <Link2 className="w-6 h-6 text-cyan-400" /> Audit Trail — Hash Chain
        </h1>
        <p className="text-sm text-slate-500">
          Blockchain-style local SHA-256 chain. If any record is modified, verification fails with
          <span className="text-red-400 font-semibold"> AUDIT INTEGRITY FAILURE</span>.
        </p>
      </header>

      {error && <div className="glass p-4 border-red-500/40 text-red-300 text-sm">{error}</div>}

      <div className="flex gap-2 items-center">
        <select
          className="input-field max-w-sm"
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
        >
          {screenings.map((s) => (
            <option key={s.id} value={s.verification_id}>
              {s.verification_id} — {s.document_type}
            </option>
          ))}
        </select>
      </div>

      {chain && (
        <div className={`glass p-4 flex items-center gap-3 ${
          chain.chain_valid ? "border-emerald-500/40" : "border-red-500/60"
        }`}>
          {chain.chain_valid ? (
            <ShieldCheck className="w-6 h-6 text-emerald-400" />
          ) : (
            <ShieldX className="w-6 h-6 text-red-400" />
          )}
          <div>
            <div className={`font-bold ${chain.chain_valid ? "text-emerald-300" : "text-red-300"}`}>
              {chain.chain_valid ? "AUDIT CHAIN VERIFIED" : "AUDIT INTEGRITY FAILURE"}
            </div>
            <div className="text-xs text-slate-400">{chain.message}</div>
          </div>
        </div>
      )}

      {chain && (
        <div className="space-y-2">
          {chain.records.map((rec, i) => (
            <div key={rec.id} className="glass p-4 font-mono text-xs">
              <div className="flex items-center justify-between mb-1">
                <span className="text-cyan-300 font-semibold">#{i + 1} {rec.event_type}</span>
                <span className="text-slate-500">{new Date(rec.timestamp).toLocaleString()}</span>
              </div>
              <div className="text-slate-500">prev: <span className="text-slate-400">{rec.previous_hash.slice(0, 32)}…</span></div>
              <div className="text-slate-500">hash: <span className="text-emerald-400/80">{rec.current_hash.slice(0, 32)}…</span></div>
              {rec.event_data && (
                <div className="text-slate-600 mt-1 truncate">{rec.event_data}</div>
              )}
            </div>
          ))}
          {chain.records.length === 0 && (
            <div className="glass p-6 text-center text-slate-500 text-sm">
              No audit records for this screening.
            </div>
          )}
        </div>
      )}
    </div>
  );
}