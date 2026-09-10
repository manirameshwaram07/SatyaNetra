import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { Eye, Loader2, ShieldCheck } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { apiErrorMessage } from "../services/api";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      setLoading(true);
      await login(username, password);
      navigate("/");
    } catch (err) {
      setError(
        (err as { response?: { status?: number } }).response?.status === 401
          ? "Invalid username or password."
          : "Cannot reach the backend. Ensure the FastAPI server is running on port 8000."
      );
    }
  };

  return (
    <div className="min-h-full flex items-center justify-center p-6">
      <motion.div
        initial={{ opacity: 0, y: 18 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="w-full max-w-md"
      >
        <div className="glass p-8">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2.5 rounded-xl bg-gradient-to-br from-cyan-500/20 to-blue-600/20 border border-cyan-500/40">
              <Eye className="w-7 h-7 text-cyan-400" />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-[0.2em] text-cyan-300">SATYANETRA</h1>
              <p className="text-xs text-slate-500 italic">See Beyond the Document. Verify the Identity.</p>
            </div>
          </div>
          <p className="text-sm text-slate-400 mb-6">
            AI-Based Fake Identity & Document Screening · SIH 26188
          </p>

          <form onSubmit={submit} className="space-y-4">
            <div>
              <label className="text-xs text-slate-400 font-medium">Username</label>
              <input
                className="input-field mt-1"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="admin"
                autoFocus
              />
            </div>
            <div>
              <label className="text-slate-400 text-xs">Password</label>
              <input
                type="password"
                className="input-field mt-1"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
              />
            </div>

            {error && (
              <div className="text-sm text-red-400 bg-red-500/10 border border-red-500/30 rounded-lg px-3 py-2">
                {error}
              </div>
            )}

            <button className="btn-primary w-full justify-center" disabled={loading}>
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <ShieldCheck className="w-4 h-4" />}
              {loading ? "Authenticating…" : "Sign In"}
            </button>
          </form>

          <div className="mt-6 text-xs text-slate-500 space-y-1 border-t border-night-700 pt-4">
            <div className="font-semibold text-slate-400">Demo credentials (seeded):</div>
            <div className="font-mono">admin / Admin@123 · officer / Officer@123</div>
          </div>
        </div>
      </motion.div>
    </div>
  );
}