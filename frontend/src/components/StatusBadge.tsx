import { CheckCircle2, Clock, HelpCircle, XCircle } from "lucide-react";

const STYLES: Record<string, string> = {
  COMPLETED: "bg-emerald-500/10 text-emerald-300 border border-emerald-500/30",
  MATCH: "bg-emerald-500/10 text-emerald-300 border border-emerald-500/30",
  CLEAR: "bg-emerald-500/10 text-emerald-300 border border-emerald-500/30",
  CONSISTENT: "bg-emerald-500/10 text-emerald-300 border border-emerald-500/30",
  VALID: "bg-emerald-500/10 text-emerald-300 border border-emerald-500/30",
  PROCESSING: "bg-cyan-500/10 text-cyan-300 border border-cyan-500/30",
  REVIEW: "bg-amber-500/10 text-amber-300 border border-amber-500/30",
  WARNING: "bg-amber-500/10 text-amber-300 border border-amber-500/30",
  MEDIUM: "bg-amber-500/10 text-amber-300 border border-amber-500/30",
  SKIPPED: "bg-slate-500/10 text-slate-400 border border-slate-500/30",
  ERROR: "bg-orange-500/10 text-orange-300 border border-orange-500/30",
  FAILED: "bg-red-500/10 text-red-300 border border-red-500/30",
  FAIL: "bg-red-500/10 text-red-300 border border-red-500/30",
  MISMATCH: "bg-red-500/10 text-red-300 border border-red-500/30",
  HIGH: "bg-red-500/10 text-red-300 border border-red-500/30",
  CRITICAL: "bg-red-600/20 text-red-300 border border-red-500/50",
  CONFLICT: "bg-red-500/10 text-red-300 border border-red-500/30",
  REPORTED: "bg-red-600/20 text-red-300 border border-red-500/50",
  EXPIRED: "bg-amber-500/10 text-amber-300 border border-amber-500/30",
  DUPLICATE: "bg-orange-500/10 text-orange-300 border border-orange-500/30",
  SUSPICIOUS: "bg-orange-500/10 text-orange-300 border border-orange-500/30",
  PROCESSING_BADGE: "bg-cyan-500/10 text-cyan-300 border border-cyan-500/30",
};

export default function StatusBadge({ status, className = "" }: { status: string; className?: string }) {
  const key = (status || "").toUpperCase().replace(/\s+/g, "_");
  const style = STYLES[key] || "bg-slate-500/10 text-slate-300 border border-slate-500/30";
  return <span className={`badge ${style} ${className}`}>{status || "—"}</span>;
}

export function StepIcon({ status }: { status: string }) {
  if (status === "COMPLETED")
    return <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />;
  if (status === "PROCESSING")
    return <Clock className="w-4 h-4 text-cyan-400 animate-pulse shrink-0" />;
  if (status === "FAILED") return <CheckCircle2 className="w-5 h-5 text-red-400 shrink-0 rotate-45" />;
  if (status === "SKIPPED")
    return <CheckCircle2 className="w-5 h-5 text-slate-500 shrink-0" />;
  return <Clock className="w-5 h-5 text-slate-600 shrink-0" />;
}