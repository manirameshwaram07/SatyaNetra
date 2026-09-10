import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { BellRing, CheckCheck } from "lucide-react";
import { apiErrorMessage, getAlerts, updateAlertStatus } from "../services/api";
import type { Alert } from "../types";
import StatusBadge from "../components/StatusBadge";

const FILTERS = ["", "OPEN", "ACKNOWLEDGED", "RESOLVED"];

export default function Alerts() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [filter, setFilter] = useState("");
  const [error, setError] = useState("");

  const load = () => {
    getAlerts(filter || undefined)
      .then(setAlerts)
      .catch((e) => setError(apiErrorMessage(e)));
  };

  useEffect(load, [filter]);

  const ack = async (id: number) => {
    try {
      await updateAlertStatus(id, "ACKNOWLEDGED");
      load();
    } catch (e) {
      setError(apiErrorMessage(e));
    }
  };

  return (
    <div className="space-y-5">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
          <BellRing className="w-6 h-6 text-cyan-400" /> Alerts
        </h1>
        <div className="flex gap-1">
          {FILTERS.map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
                filter === f
                  ? "border-cyan-500/50 text-cyan-300 bg-cyan-500/10"
                  : "border-night-700 text-slate-400 hover:text-slate-200"
              }`}
            >
              {f || "ALL"}
            </button>
          ))}
        </div>
      </header>

      {error && <div className="glass p-4 border-red-500/40 text-red-300 text-sm">{error}</div>}

      <div className="space-y-2">
        {alerts.map((a) => (
          <div key={a.id} className="glass p-4 flex items-start gap-4">
            <div className="shrink-0 pt-0.5">
              <StatusBadge status={a.severity} />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-sm font-semibold text-slate-200">{a.category}</span>
                <StatusBadge status={a.status} />
                <span className="text-[10px] text-slate-500 font-mono">
                  {new Date(a.created_at).toLocaleString()}
                </span>
              </div>
              <p className="text-sm text-slate-400 mt-1">{a.message}</p>
              {a.verification_id && (
                <Link to={`/result/${a.verification_id}`} className="text-xs text-cyan-400 hover:text-cyan-300 mt-1 inline-block">
                  {a.verification_id} → view result
                </Link>
              )}
            </div>
            {a.status === "OPEN" && (
              <button className="btn-ghost shrink-0" onClick={() => ack(a.id)}>
                <CheckCheck className="w-4 h-4" /> Acknowledge
              </button>
            )}
          </div>
        ))}
        {alerts.length === 0 && (
          <div className="glass p-8 text-center text-slate-500 text-sm">
            No alerts {filter ? `with status ${filter}` : ""} — the pipeline creates alerts automatically when risks are detected.
          </div>
        )}
      </div>
    </div>
  );
}