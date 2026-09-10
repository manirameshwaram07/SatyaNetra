import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { motion } from "framer-motion";
import { AlertTriangle, Radar } from "lucide-react";
import { apiErrorMessage, getScreeningStatus } from "../services/api";
import type { ScreeningStatus } from "../types";
import { StepIcon } from "../components/StatusBadge";

export default function LiveAnalysis() {
  const { verificationId = "" } = useParams();
  const navigate = useNavigate();
  const [status, setStatus] = useState<ScreeningStatus | null>(null);
  const [error, setError] = useState("");
  const timerRef = useRef<number | null>(null);

  const poll = useCallback(async () => {
    try {
      const s = await getScreeningStatus(verificationId);
      setStatus(s);
      if (s.status !== "PENDING" && s.status !== "PROCESSING") {
        if (timerRef.current) window.clearInterval(timerRef.current);
        // small delay so the user sees 100%
        window.setTimeout(() => navigate(`/result/${verificationId}`), 900);
      }
    } catch (e) {
      setError(apiErrorMessage(e));
      if (timerRef.current) window.clearInterval(timerRef.current);
    }
  }, [verificationId, navigate]);

  useEffect(() => {
    void poll();
    timerRef.current = window.setInterval(poll, 1200);
    return () => {
      if (timerRef.current) window.clearInterval(timerRef.current);
    };
  }, [poll]);

  const done = status && status.status !== "PENDING" && status.status !== "PROCESSING";

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <header className="text-center">
        <motion.div
          className="mx-auto w-fit p-4 rounded-full border border-cyan-500/30 bg-cyan-500/5"
          animate={{ boxShadow: ["0 0 0px #22d3ee55", "0 0 24px #22d3ee55", "0 0 0px #22d3ee55"] }}
          transition={{ repeat: Infinity, duration: 2 }}
        >
          <Radar className="w-10 h-10 text-cyan-400" />
        </motion.div>
        <h1 className="mt-4 text-2xl font-bold tracking-widest text-cyan-300">
          SATYANETRA AI ANALYSIS
        </h1>
        <p className="text-xs text-slate-500 font-mono mt-1">
          VERIFICATION {verificationId}
        </p>
      </header>

      {error && (
        <div className="glass p-4 border-red-500/40 text-red-300 text-sm flex items-center gap-2">
          <AlertTriangle className="w-4 h-4" /> {error}
        </div>
      )}

      <div className="glass p-6">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm text-slate-400">
            {done ? "Pipeline finished" : `Current step: ${status?.current_step ?? "Starting…"}`}
          </span>
          <span className="font-mono text-cyan-300">{status?.progress ?? 0}%</span>
        </div>
        <div className="h-2.5 rounded-full bg-night-800 overflow-hidden">
          <motion.div
            className="h-full rounded-full bg-gradient-to-r from-cyan-500 to-blue-500"
            animate={{ width: `${status?.progress ?? 0}%` }}
            transition={{ duration: 0.5 }}
          />
        </div>

        <div className="mt-6 space-y-1.5">
          {(status?.steps ?? []).map((step) => (
            <div
              key={step.name}
              className={`flex items-center gap-3 px-3 py-2 rounded-lg border ${
                step.status === "PROCESSING"
                  ? "border-cyan-500/40 bg-cyan-500/5"
                  : step.status === "FAILED"
                  ? "border-red-500/30 bg-red-500/5"
                  : "border-transparent"
              }`}
            >
              <StepIcon status={step.status} />
              <div className="flex-1 min-w-0">
                <div className={`text-sm ${step.status === "PENDING" ? "text-slate-500" : "text-slate-200"}`}>
                  {step.name}
                </div>
                {step.detail && (
                  <div className="text-[11px] text-slate-500 truncate">{step.detail}</div>
                )}
              </div>
              <span
                className={`text-[10px] font-mono uppercase ${
                  step.status === "COMPLETED"
                    ? "text-emerald-400"
                    : step.status === "PROCESSING"
                    ? "text-cyan-400"
                    : step.status === "FAILED"
                    ? "text-red-400"
                    : "text-slate-600"
                }`}
              >
                {step.status}
              </span>
            </div>
          ))}
        </div>
      </div>

      {done && (
        <div className="text-center">
          <Link to={`/result/${verificationId}`} className="btn-primary">
            View Verification Result →
          </Link>
        </div>
      )}
    </div>
  );
}