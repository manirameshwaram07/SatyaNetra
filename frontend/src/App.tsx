import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./context/AuthContext";
import MainLayout from "./layouts/MainLayout";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Screening from "./pages/Screening";
import LiveAnalysis from "./pages/LiveAnalysis";
import Result from "./pages/Result";
import History from "./pages/History";
import Cases from "./pages/Cases";
import Alerts from "./pages/Alerts";
import Analytics from "./pages/Analytics";
import AuditTrail from "./pages/AuditTrail";
import Settings from "./pages/Settings";

function Protected({ children }: { children: React.ReactElement }) {
  const { token, loading } = useAuth();
  if (loading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="animate-pulse text-cyan-400 font-mono">CONNECTING TO SATYANETRA…</div>
      </div>
    );
  }
  if (!token) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/"
        element={
          <Protected>
            <MainLayout />
          </Protected>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="screening" element={<Screening />} />
        <Route path="analysis/:verificationId" element={<LiveAnalysis />} />
        <Route path="result/:verificationId" element={<Result />} />
        <Route path="history" element={<History />} />
        <Route path="cases" element={<Cases />} />
        <Route path="alerts" element={<Alerts />} />
        <Route path="analytics" element={<Analytics />} />
        <Route path="audit" element={<AuditTrail />} />
        <Route path="settings" element={<Settings />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}