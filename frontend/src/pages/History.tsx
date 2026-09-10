import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { History as HistoryIcon, Search } from "lucide-react";
import { apiErrorMessage, getScreeningHistory } from "../services/api";
import type { ScreeningHistoryItem } from "../types";
import StatusBadge from "../components/StatusBadge";

export default function History() {
  const [items, setItems] = useState<ScreeningHistoryItem[]>([]);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");

  useEffect(() => {
    getScreeningHistory(100)
      .then(setItems)
      .catch((e) => setError(apiErrorMessage(e)));
  }, []);

  const filtered = items.filter(
    (i) =>
      !query ||
      i.verification_id.toLowerCase().includes(query.toLowerCase()) ||
      i.filename.toLowerCase().includes(query.toLowerCase()) ||
      i.document_type.toLowerCase().includes(query.toLowerCase())
  );

  return (
    <div className="space-y-5">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
          <HistoryIcon className="w-6 h-6 text-cyan-400" /> Search History
        </h1>
        <div className="relative">
          <Search className="w-4 h-4 text-slate-500 absolute left-3 top-2.5" />
          <input
            className="input-field pl-9 w-64"
            placeholder="Search ID, filename, type…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
      </header>

      {error && <div className="glass p-4 border-red-500/40 text-red-300 text-sm">{error}</div>}

      <div className="glass overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-slate-500 border-b border-night-700">
              <th className="px-4 py-3">Verification ID</th>
              <th className="px-4 py-3">Document</th>
              <th className="px-4 py-3">Type</th>
              <th className="px-4 py-3">Risk</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Time</th>
              <th className="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((i) => (
              <tr key={i.id} className="border-b border-night-800 hover:bg-night-800/40">
                <td className="px-4 py-2.5 font-mono text-xs text-cyan-300">{i.verification_id}</td>
                <td className="px-4 py-2.5 text-slate-300 max-w-40 truncate">{i.filename}</td>
                <td className="px-4 py-2.5 text-slate-400 text-xs">{i.document_type}</td>
                <td className="px-4 py-2.5">
                  {i.risk_score != null ? (
                    <span className="flex items-center gap-2">
                      <span className="font-bold text-slate-200">{i.risk_score}</span>
                      <StatusBadge status={i.risk_level} />
                    </span>
                  ) : (
                    "—"
                  )}
                </td>
                <td className="px-4 py-2.5"><StatusBadge status={i.status} /></td>
                <td className="px-4 py-2.5 text-xs text-slate-500">
                  {new Date(i.created_at).toLocaleString()}
                </td>
                <td className="px-4 py-2.5">
                  <Link to={`/result/${i.verification_id}`} className="text-cyan-400 hover:text-cyan-300 text-xs font-medium">
                    View →
                  </Link>
                </td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-slate-500">
                  No screenings found. <Link to="/screening" className="text-cyan-400">Run one now →</Link>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}