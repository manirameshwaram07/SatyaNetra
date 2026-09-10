import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { FolderKanban, Plus } from "lucide-react";
import {
  apiErrorMessage, createCase, getCases, getScreeningHistory, updateCase,
} from "../services/api";
import type { CaseItem, ScreeningHistoryItem } from "../types";
import StatusBadge from "../components/StatusBadge";

const STATUSES = ["OPEN", "IN_PROGRESS", "ESCALATED", "RESOLVED"];

export default function Cases() {
  const [cases, setCases] = useState<CaseItem[]>([]);
  const [screenings, setScreenings] = useState<ScreeningHistoryItem[]>([]);
  const [error, setError] = useState("");
  const [showNew, setShowNew] = useState(false);
  const [newScreening, setNewScreening] = useState("");
  const [newTitle, setNewTitle] = useState("");
  const [newNotes, setNewNotes] = useState("");

  const load = () => {
    getCases().then(setCases).catch((e) => setError(apiErrorMessage(e)));
    getScreeningHistory(30).then(setScreenings).catch(() => undefined);
  };

  useEffect(load, []);

  const create = async () => {
    if (!newScreening || !newTitle) return;
    try {
      await createCase({
        screening_id: Number(newScreening),
        title: newTitle,
        notes: newNotes,
      });
      setShowNew(false);
      setNewTitle("");
      setNewNotes("");
      load();
    } catch (e) {
      setError(apiErrorMessage(e));
    }
  };

  const setStatus = async (id: number, status: string) => {
    try {
      await updateCase(id, { status });
      load();
    } catch (e) {
      setError(apiErrorMessage(e));
    }
  };

  return (
    <div className="space-y-5">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
          <FolderKanban className="w-6 h-6 text-cyan-400" /> Case Management
        </h1>
        <button className="btn-primary" onClick={() => setShowNew(!showNew)}>
          <Plus className="w-4 h-4" /> New Case
        </button>
      </header>

      {error && <div className="glass p-4 border-red-500/40 text-red-300 text-sm">{error}</div>}

      {showNew && (
        <div className="glass p-5 space-y-3">
          <h3 className="text-sm font-semibold text-slate-300">Create review case</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <select
              className="input-field"
              value={newScreening}
              onChange={(e) => setNewScreening(e.target.value)}
            >
              <option value="">Select screening…</option>
              {screenings.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.verification_id} — {s.document_type} ({s.risk_level || s.status})
                </option>
              ))}
            </select>
            <input
              className="input-field"
              placeholder="Case title"
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
            />
          </div>
          <textarea
            className="input-field"
            rows={2}
            placeholder="Notes (optional)"
            value={newNotes}
            onChange={(e) => setNewNotes(e.target.value)}
          />
          <div className="flex gap-2">
            <button className="btn-primary" onClick={create} disabled={!newScreening || !newTitle}>
              Create Case
            </button>
            <button className="btn-ghost" onClick={() => setShowNew(false)}>Cancel</button>
          </div>
        </div>
      )}

      <div className="space-y-2">
        {cases.map((c) => (
          <div key={c.id} className="glass p-4">
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-semibold text-slate-200">#{c.id} · {c.title}</span>
                  <StatusBadge status={c.status} />
                </div>
                <div className="text-xs text-slate-500 mt-1">
                  Assigned to <span className="text-slate-300">{c.assigned_to || "—"}</span> ·{" "}
                  {c.verification_id && (
                    <Link to={`/result/${c.verification_id}`} className="text-cyan-400 hover:text-cyan-300">
                      {c.verification_id} →
                    </Link>
                  )}{" "}
                  · updated {new Date(c.updated_at).toLocaleString()}
                </div>
                {c.notes && <p className="text-sm text-slate-400 mt-2">{c.notes}</p>}
              </div>
              <select
                className="input-field w-36 shrink-0"
                value={c.status}
                onChange={(e) => setStatus(c.id, e.target.value)}
              >
                {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
          </div>
        ))}
        {cases.length === 0 && (
          <div className="glass p-8 text-center text-slate-500 text-sm">
            No cases yet. Create one from a completed screening.
          </div>
        )}
      </div>
    </div>
  );
}