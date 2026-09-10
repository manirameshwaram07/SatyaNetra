import { useEffect, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import {
  Activity, BellRing, BarChart3, Eye, FileSearch, FolderKanban,
  History, LayoutDashboard, LogOut, ShieldCheck,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { getHealth } from "../services/api";

const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/screening", label: "Document Screening", icon: FileSearch },
  { to: "/history", label: "History", icon: History },
  { to: "/cases", label: "Cases", icon: FolderKanban },
  { to: "/alerts", label: "Alerts", icon: BellRing },
  { to: "/analytics", label: "Analytics", icon: BarChart3 },
  { to: "/audit", label: "Audit Trail", icon: ShieldCheck },
];

export default function MainLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [backend, setBackend] = useState<{ demo_mode: boolean; database: string } | null>(null);

  useEffect(() => {
    getHealth().then(setBackend).catch(() => setBackend(null));
    const t = setInterval(() => getHealth().then(setBackend).catch(() => setBackend(null)), 15000);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="min-h-full flex">
      {/* Sidebar */}
      <aside className="w-60 shrink-0 border-r border-night-700/70 bg-night-900/60 backdrop-blur flex flex-col">
        <div className="px-5 py-5 flex items-center gap-3 border-b border-night-700/70">
          <div className="p-2 rounded-lg bg-gradient-to-br from-cyan-500/20 to-blue-600/20 border border-cyan-500/30">
            <Eye className="w-6 h-6 text-cyan-400" />
          </div>
          <div>
            <div className="font-bold tracking-widest text-cyan-300">SATYANETRA</div>
            <div className="text-[10px] text-slate-500 font-mono">SIH 26188 · v1.0</div>
          </div>
        </div>

        <nav className="flex-1 px-3 py-4 space-y-1">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                  isActive
                    ? "bg-cyan-500/10 text-cyan-300 border border-cyan-500/30"
                    : "text-slate-400 hover:text-slate-200 hover:bg-night-800 border border-transparent"
                }`
              }
            >
              <Icon className="w-4 h-4" />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="px-4 py-4 border-t border-night-700/70 space-y-2">
          <div className="flex items-center gap-2 text-xs">
            <span
              className={`w-2 h-2 rounded-full ${
                backend ? (backend.database === "connected" ? "bg-emerald-400" : "bg-red-400") : "bg-red-500"
              } animate-pulse`}
            />
            <span className="text-slate-400">
              {backend ? `Backend ${backend.database}` : "Backend offline"}
            </span>
          </div>
          {backend?.demo_mode && (
            <div className="badge bg-amber-500/10 text-amber-300 border border-amber-500/30">
              DEMO MODE ACTIVE
            </div>
          )}
          <div className="flex items-center justify-between pt-1">
            <div>
              <div className="text-sm text-slate-200">{user?.username}</div>
              <div className="text-[10px] text-slate-500 font-mono">{user?.role}</div>
            </div>
            <button
              onClick={() => {
                logout();
                navigate("/login");
              }}
              className="p-2 rounded-lg text-slate-400 hover:text-red-400 hover:bg-red-500/10"
              title="Logout"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 min-w-0">
        <div className="max-w-7xl mx-auto px-6 py-6">
          <Outlet />
        </div>
      </main>
    </div>
  );
}