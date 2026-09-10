import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  AlertTriangle, FileClock, FileSearch, FileWarning, LayoutDashboard,
  ScanFace, ShieldAlert, ShieldCheck, Timer,
} from "lucide-react";
import {
  Area, AreaChart, Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { apiErrorMessage, getDashboardStats } from "../services/api";
import type { DashboardStats } from "../types";

function StatCard({
  label, value, icon: Icon, accent,
}: {
  label: string;
  value: string | number;
  icon: React.ElementType;
  accent: string;
}) {
  return (
    <div className="glass glass-hover p-4 flex items-center gap-4">
      <div className={`p-2.5 rounded-lg ${accent}`}>
        <Icon className="w-5 h-5" />
      </div>
      <div>
        <div className="text-2xl font-bold text-slate-100">{value}</div>
        <div className="text-xs text-slate-500">{label}</div>
      </div>
    </div>
  );
}

export default function Dashboard() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getDashboardStats()
      .then(setStats)
      .catch((e) => setError(apiErrorMessage(e)));
  }, []);

  if (error) {
    return (
      <div className="glass p-6 text-red-300 border-red-500/30">
        {error}
      </div>
    );
  }
  if (!stats) {
    return <div className="text-slate-500 p-8 font-mono animate-pulse">LOADING DASHBOARD DATA…</div>;
  }

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
            <LayoutDashboard className="w-6 h-6 text-cyan-400" /> Verification Dashboard
          </h1>
          <p className="text-sm text-slate-500">
            All values are computed live from the backend database.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {stats.demo_mode && (
            <span className="badge bg-amber-500/10 text-amber-300 border border-amber-500/30">
              DEMO MODE
            </span>
          )}
          <Link to="/screening" className="btn-primary">
            <FileSearch className="w-4 h-4" /> New Screening
          </Link>
        </div>
      </header>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Total Screened" value={stats.total_screenings} icon={LayoutDashboard} accent="text-cyan-400 bg-cyan-500/10" />
        <StatCard label="High Risk" value={stats.high_risk + stats.critical_risk} icon={ShieldAlert} accent="text-red-400 bg-red-500/10" />
        <StatCard label="Medium Risk" value={stats.medium_risk} icon={AlertTriangle} accent="text-amber-400 bg-amber-500/10" />
        <StatCard label="Low Risk" value={stats.low_risk} icon={ShieldCheck} accent="text-emerald-400 bg-emerald-500/10" />
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Tampering Detected" value={stats.tampering_detections} icon={FileWarning} accent="text-orange-400 bg-orange-500/10" />
        <StatCard label="Face Mismatches" value={stats.face_mismatches} icon={ScanFace} accent="text-red-400 bg-red-500/10" />
        <StatCard label="Expired Documents" value={stats.expired_documents} icon={FileClock} accent="text-amber-400 bg-amber-500/10" />
        <StatCard
          label="Avg Processing"
          value={`${(stats.avg_processing_ms / 1000).toFixed(1)}s`}
          icon={Timer}
          accent="text-cyan-400 bg-cyan-500/10"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="glass p-5">
          <h3 className="text-sm font-semibold text-slate-300 mb-4">Screenings — last 7 days</h3>
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={stats.trend}>
              <defs>
                <linearGradient id="dashGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#22D3EE" stopOpacity={0.5} />
                  <stop offset="100%" stopColor="#22D3EE" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="date" tick={{ fill: "#64748b", fontSize: 10 }} tickFormatter={(d: string) => d.slice(5)} />
              <YAxis allowDecimals={false} tick={{ fill: "#64748b", fontSize: 11 }} width={28} />
              <Tooltip contentStyle={{ background: "#0B1220", border: "1px solid #1B2740", borderRadius: 8 }} />
              <Area type="monotone" dataKey="count" stroke="#22D3EE" fill="url(#dashGrad)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
        <div className="glass p-5">
          <h3 className="text-sm font-semibold text-slate-300 mb-4">Risk distribution</h3>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={stats.risk_distribution}>
              <XAxis dataKey="level" tick={{ fill: "#64748b", fontSize: 11 }} />
              <YAxis allowDecimals={false} tick={{ fill: "#64748b", fontSize: 11 }} width={28} />
              <Tooltip contentStyle={{ background: "#0B1220", border: "1px solid #1B2740", borderRadius: 8 }} />
              <Bar dataKey="count" fill="#22D3EE" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}