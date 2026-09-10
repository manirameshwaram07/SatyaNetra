import { useEffect, useState } from "react";
import { BarChart3 } from "lucide-react";
import {
  Bar, BarChart, CartesianGrid, Cell, Legend, Pie, PieChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { apiErrorMessage, getDashboardStats } from "../services/api";
import type { DashboardStats } from "../types";

const PIE_COLORS = ["#34D399", "#FBBF24", "#F87171", "#EF4444"];

export default function Analytics() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getDashboardStats().then(setStats).catch((e) => setError(apiErrorMessage(e)));
  }, []);

  if (error) return <div className="glass p-4 border-red-500/40 text-red-300 text-sm">{error}</div>;
  if (!stats) return <div className="text-slate-500 p-8 font-mono animate-pulse">LOADING ANALYTICS…</div>;

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
          <BarChart3 className="w-6 h-6 text-cyan-400" /> Analytics
        </h1>
        <p className="text-sm text-slate-500">Charts are rendered from live backend statistics.</p>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="glass p-5">
          <h3 className="text-sm font-semibold text-slate-300 mb-4">Risk level distribution</h3>
          <ResponsiveContainer width="100%" height={260}>
            <PieChart>
              <Pie
                data={stats.risk_distribution.filter((d) => d.count > 0)}
                dataKey="count"
                nameKey="level"
                innerRadius={60}
                outerRadius={95}
                paddingAngle={4}
              >
                {stats.risk_distribution
                  .filter((d) => d.count > 0)
                  .map((entry, i) => (
                    <Cell key={entry.level} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                  ))}
              </Pie>
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Tooltip contentStyle={{ background: "#0B1220", border: "1px solid #1B2740", borderRadius: 8 }} />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div className="glass p-5">
          <h3 className="text-sm font-semibold text-slate-300 mb-4">Detection signals</h3>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart
              data={[
                { name: "Tampering", count: stats.tampering_detections },
                { name: "Face Mismatch", count: stats.face_mismatches },
                { name: "Expired", count: stats.expired_documents },
                { name: "Open Alerts", count: stats.open_alerts },
              ]}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#1B2740" />
              <XAxis dataKey="name" tick={{ fill: "#64748b", fontSize: 11 }} />
              <YAxis allowDecimals={false} tick={{ fill: "#64748b", fontSize: 11 }} width={28} />
              <Tooltip contentStyle={{ background: "#0B1220", border: "1px solid #1B2740", borderRadius: 8 }} />
              <Bar dataKey="count" fill="#22D3EE" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="glass p-5">
        <h3 className="text-sm font-semibold text-slate-300 mb-4">Screening volume — last 7 days</h3>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={stats.trend}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1B2740" />
            <XAxis dataKey="date" tick={{ fill: "#64748b", fontSize: 10 }} tickFormatter={(d: string) => d.slice(5)} />
            <YAxis allowDecimals={false} tick={{ fill: "#64748b", fontSize: 11 }} width={28} />
            <Tooltip contentStyle={{ background: "#0B1220", border: "1px solid #1B2740", borderRadius: 8 }} />
            <Bar dataKey="count" fill="#3B82F6" radius={[6, 6, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}