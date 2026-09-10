import { useEffect, useState } from "react";
import { Settings as SettingsIcon, ShieldCheck } from "lucide-react";
import { getHealth, getWatchlist } from "../services/api";
import type { WatchlistEntry } from "../types";
import StatusBadge from "../components/StatusBadge";

export default function Settings() {
  const [health, setHealth] = useState<{ status: string; database: string; demo_mode: boolean; version: string } | null>(null);
  const [watchlist, setWatchlist] = useState<WatchlistEntry[]>([]);

  useEffect(() => {
    getHealth().then(setHealth).catch(() => undefined);
    getWatchlist().then(setWatchlist).catch(() => undefined);
  }, []);

  return (
    <div className="space-y-6 max-w-3xl">
      <header>
        <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
          <SettingsIcon className="w-6 h-6 text-cyan-400" /> Settings
        </h1>
        <p className="text-sm text-slate-500">System status and demo configuration.</p>
      </header>

      <div className="glass p-5 space-y-3">
        <h3 className="text-sm font-semibold text-slate-300">Backend status</h3>
        {health ? (
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div>
              <div className="text-xs text-slate-500">API</div>
              <div className="text-slate-200">{health.status}</div>
            </div>
            <div>
              <div className="text-xs text-slate-500">Database</div>
              <div className="text-slate-200">{health.database}</div>
            </div>
            <div>
              <div className="text-xs text-slate-500">Version</div>
              <div className="text-slate-200 font-mono">{health.version}</div>
            </div>
            <div>
              <div className="text-xs text-slate-500">Demo mode</div>
              <div className="text-slate-200">{health.demo_mode ? "ACTIVE" : "OFF"}</div>
            </div>
          </div>
        ) : (
          <div className="text-sm text-red-400">Backend unreachable.</div>
        )}
      </div>

      <div className="glass p-5 space-y-3">
        <h3 className="text-sm font-semibold text-slate-300">Demo watchlist (seeded records)</h3>
        <p className="text-xs text-slate-500">
          These are locally seeded demo records — never a real government database.
        </p>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-slate-500 border-b border-night-700">
                <th className="px-3 py-2">Document No.</th>
                <th className="px-3 py-2">Name</th>
                <th className="px-3 py-2">Status</th>
                <th className="px-3 py-2">Notes</th>
              </tr>
            </thead>
            <tbody>
              {watchlist.map((w) => (
                <tr key={w.id} className="border-b border-night-800">
                  <td className="px-3 py-2 font-mono text-xs text-cyan-300">{w.document_number}</td>
                  <td className="px-3 py-2 text-slate-300">{w.name}</td>
                  <td className="px-3 py-2"><StatusBadge status={w.status} /></td>
                  <td className="px-3 py-2 text-xs text-slate-500">{w.notes}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="glass p-5 space-y-2 text-sm text-slate-400">
        <h3 className="text-sm font-semibold text-slate-300">About SatyaNetra</h3>
        <p>
          SatyaNetra is an AI-assisted document screening prototype for Smart India Hackathon
          Problem Statement 26188. It combines OCR, document forensics, face verification, watchlist
          checks, identity consistency analysis, and a weighted risk engine.
        </p>
        <p className="text-xs text-slate-600">
          All indicators are probabilistic signals, not legal proof of fraud. Human review is the
          final authority for any real-world security decision.
        </p>
      </div>
    </div>
  );
}