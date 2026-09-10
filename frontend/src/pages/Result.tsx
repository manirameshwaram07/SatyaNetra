import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  AlertTriangle, Camera, CheckCircle2, Download, FileText, Fingerprint,
  Loader2, RefreshCw, ScanFace, ShieldCheck, XCircle,
} from "lucide-react";
import {
  apiErrorMessage, downloadReport, getScreeningResult, verifyFace,
} from "../services/api";
import type { ScreeningResult } from "../types";
import StatusBadge from "../components/StatusBadge";
import RiskMeter from "../components/RiskMeter";

function Card({ title, icon: Icon, children, right }: {
  title: string; icon: React.ElementType; children: React.ReactNode; right?: React.ReactNode;
}) {
  return (
    <div className="glass p-5">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-slate-300 flex items-center gap-2">
          <Icon className="w-4 h-4 text-cyan-400" /> {title}
        </h3>
        {right}
      </div>
      {children}
    </div>
  );
}

export default function Result() {
  const { verificationId = "" } = useParams();
  const [result, setResult] = useState<ScreeningResult | null>(null);
  const [error, setError] = useState("");
  const [downloading, setDownloading] = useState(false);

  // Face verification state
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [camOn, setCamOn] = useState(false);
  const [faceBusy, setFaceBusy] = useState(false);
  const [faceMsg, setFaceMsg] = useState("");

  const load = useCallback(() => {
    getScreeningResult(verificationId)
      .then(setResult)
      .catch((e) => setError(apiErrorMessage(e)));
  }, [verificationId]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => () => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
  }, []);

  const startCamera = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } });
      streamRef.current = stream;
      setCamOn(true);
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
    } catch {
      setFaceMsg("Camera unavailable. You can upload a photo file instead (use History → re-run, or place a selfie file).");
    }
  };

  const captureAndVerify = async () => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) return;
    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 480;
    canvas.getContext("2d")?.drawImage(video, 0, 0);
    const dataUrl = canvas.toDataURL("image/jpeg", 0.9);
    setFaceBusy(true);
    setFaceMsg("");
    try {
      const res = await verifyFace(verificationId, undefined, dataUrl);
      setFaceMsg(`${res.status} — similarity ${(res.similarity * 100).toFixed(1)}% · ${res.message}`);
      load(); // refresh result (face result now stored)
    } catch (e) {
      setFaceMsg(apiErrorMessage(e));
    } finally {
      setFaceBusy(false);
      streamRef.current?.getTracks().forEach((t) => t.stop());
      setCamOn(false);
    }
  };

  const onDownload = async () => {
    setDownloading(true);
    try {
      await downloadReport(verificationId);
    } catch (e) {
      setError(apiErrorMessage(e));
    } finally {
      setDownloading(false);
    }
  };

  if (error) {
    return (
      <div className="glass p-6 border-red-500/40 text-red-300">
        <div className="flex items-center gap-2 font-semibold mb-1">
          <AlertTriangle className="w-5 h-5" /> Could not load result
        </div>
        <p className="text-sm text-red-300/80">{error}</p>
        <Link to="/history" className="btn-ghost mt-4">Back to History</Link>
      </div>
    );
  }
  if (!result) {
    return <div className="text-slate-500 p-8 font-mono animate-pulse">LOADING RESULT…</div>;
  }

  const r = result;
  const tam = r.tampering;
  const face = r.face;

  return (
    <div className="space-y-6">
      {/* Header + risk meter */}
      <div className="glass p-6 flex flex-col md:flex-row items-center gap-8">
        <RiskMeter score={r.risk_score ?? 0} level={r.risk_level ?? "UNKNOWN"} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h1 className="text-xl font-bold text-slate-100">SATYANETRA RISK SCORE</h1>
            <StatusBadge status={r.risk_level ?? ""} />
            {r.demo_mode && (
              <span className="badge bg-amber-500/10 text-amber-300 border border-amber-500/30">DEMO MODE</span>
            )}
          </div>
          <div className="mt-2 text-sm text-slate-400 font-mono">
            {r.verification_id} · {r.document_type} ·{" "}
            {r.completed_at ? new Date(r.completed_at).toLocaleString() : ""}
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            <button className="btn-primary" onClick={onDownload} disabled={downloading}>
              {downloading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
              Download Verification Report
            </button>
            <Link to="/screening" className="btn-ghost">New Screening</Link>
          </div>
          {(r.warnings?.length ?? 0) > 0 && (
            <div className="mt-4 text-xs text-amber-300 bg-amber-500/5 border border-amber-500/30 rounded-lg p-3">
              <div className="font-semibold mb-1">Some analysis modules were unavailable:</div>
              <ul className="list-disc list-inside space-y-0.5 text-amber-300/80">
                {r.warnings!.map((w, i) => <li key={i}>{w}</li>)}
              </ul>
              <div className="mt-1">Manual review recommended.</div>
            </div>
          )}
        </div>
      </div>

      {/* Score cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <div className="glass p-4 text-center">
          <div className="text-xs text-slate-500 mb-1">Document Validation</div>
          <StatusBadge status={r.validation?.overall_status ?? "—"} />
        </div>
        <div className="glass p-4 text-center">
          <div className="text-xs text-slate-500 mb-1">OCR Confidence</div>
          <div className="text-xl font-bold text-cyan-300">
            {r.ocr_confidence != null ? `${Math.round(r.ocr_confidence * 100)}%` : "—"}
          </div>
          {r.ocr_data_source === "DEMO" && (
            <div className="text-[10px] text-amber-400">DEMO DATA</div>
          )}
        </div>
        <div className="glass p-4 text-center">
          <div className="text-xs text-slate-500 mb-1">Tampering Score</div>
          <div className={`text-xl font-bold ${(tam?.tampering_score ?? 0) >= 60 ? "text-red-400" : (tam?.tampering_score ?? 0) >= 35 ? "text-amber-400" : "text-emerald-400"}`}>
            {tam?.tampering_score ?? 0}%
          </div>
        </div>
        <div className="glass p-4 text-center">
          <div className="text-xs text-slate-500 mb-1">Face Match</div>
          {face ? (
            <>
              <div className="text-xl font-bold text-slate-100">{Math.round(face.similarity * 100)}%</div>
              <StatusBadge status={face.status} />
            </>
          ) : (
            <div className="text-sm text-slate-500">Not verified</div>
          )}
        </div>
        <div className="glass p-4 text-center">
          <div className="text-xs text-slate-500 mb-1">Watchlist</div>
          <StatusBadge status={r.watchlist?.status ?? "—"} />
          <div className="text-[10px] text-slate-500 mt-1">{r.watchlist?.source}</div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Extracted data */}
        <Card title="Extracted Data (OCR)" icon={FileText}
          right={r.extracted?.data_source === "DEMO" ? (
            <span className="badge bg-amber-500/10 text-amber-300 border border-amber-500/30">DEMO SOURCE</span>
          ) : undefined}>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
            {[
              ["Full Name", r.extracted?.name],
              ["Document No.", r.extracted?.document_number],
              ["Nationality", r.extracted?.nationality],
              ["Date of Birth", r.extracted?.date_of_birth],
              ["Gender", r.extracted?.gender],
              ["Expiry Date", r.extracted?.expiry_date],
            ].map(([k, v]) => (
              <div key={k as string}>
                <dt className="text-[11px] text-slate-500">{k}</dt>
                <dd className="text-slate-200 font-mono text-xs truncate">{v || "—"}</dd>
              </div>
            ))}
          </dl>
        </Card>

        {/* Validation checks */}
        <Card title="Validation Checks" icon={ShieldCheck}
          right={<StatusBadge status={r.validation?.overall_status ?? ""} />}>
          <div className="space-y-1.5 max-h-56 overflow-y-auto pr-1">
            {(r.validation?.checks ?? []).map((c, i) => (
              <div key={i} className="flex items-start gap-2 text-sm">
                {c.status === "PASS" ? (
                  <CheckCircle2 className="w-4 h-4 text-emerald-400 mt-0.5 shrink-0" />
                ) : c.status === "FAIL" ? (
                  <XCircle className="w-4 h-4 text-red-400 mt-0.5 shrink-0" />
                ) : (
                  <AlertTriangle className="w-4 h-4 text-amber-400 mt-0.5 shrink-0" />
                )}
                <div>
                  <span className="text-slate-300">{c.name}</span>
                  <span className="text-slate-500 text-xs"> — {c.message}</span>
                </div>
              </div>
            ))}
          </div>
        </Card>

        {/* Tampering */}
        <Card title="Tampering / Forensic Analysis" icon={Fingerprint}
          right={<StatusBadge status={tam?.risk_level ?? ""} />}>
          <div className="flex items-center gap-4 mb-3">
            <div className="text-3xl font-bold text-slate-100">{tam?.tampering_score ?? 0}<span className="text-sm text-slate-500">/100</span></div>
            <div className="text-xs text-slate-500">
              Photo-region indicator: <span className="text-slate-300">{tam?.photo_tampering_indicator ?? 0}%</span>
              <br />Engine: <span className="font-mono">{tam?.engine}</span>
            </div>
          </div>
          <ul className="space-y-1.5 text-xs">
            {(tam?.indicators ?? []).map((ind, i) => (
              <li key={i} className="flex gap-2">
                <span className={`badge shrink-0 ${
                  ind.severity === "HIGH" ? "bg-red-500/10 text-red-300 border border-red-500/30"
                  : ind.severity === "MEDIUM" ? "bg-amber-500/10 text-amber-300 border border-amber-500/30"
                  : "bg-slate-500/10 text-slate-400 border border-slate-500/30"}`}>
                  {ind.severity}
                </span>
                <span className="text-slate-400">{ind.message}</span>
              </li>
            ))}
          </ul>
          <p className="mt-3 text-[10px] text-slate-600">
            AI-assisted heuristic indicators — not proof of forgery. Manual inspection recommended.
          </p>
        </Card>

        {/* Face verification + camera */}
        <Card title="Face Verification" icon={ScanFace}
          right={face ? <StatusBadge status={face.status} /> : undefined}>
          {face ? (
            <div className="text-sm text-slate-300 space-y-1 mb-3">
              <div>Similarity: <span className="font-bold text-cyan-300">{Math.round(face.similarity * 100)}%</span></div>
              <div className="text-xs text-slate-500">{face.message}</div>
            </div>
          ) : (
            <p className="text-sm text-slate-500 mb-3">
              No face verification performed yet. Capture your face to compare against the document portrait.
            </p>
          )}
          <div className="rounded-lg overflow-hidden border border-night-700 bg-night-950 relative">
            <video ref={videoRef} className={`w-full ${camOn ? "" : "hidden"}`} muted playsInline />
            {!camOn && (
              <div className="p-6 text-center text-xs text-slate-600">
                Camera preview appears here
              </div>
            )}
            <canvas ref={canvasRef} className="hidden" />
          </div>
          <div className="mt-3 flex gap-2">
            {!camOn ? (
              <button className="btn-ghost" onClick={startCamera}>
                <Camera className="w-4 h-4" /> Use Camera
              </button>
            ) : (
              <button className="btn-primary" onClick={captureAndVerify} disabled={faceBusy}>
                {faceBusy ? <Loader2 className="w-4 h-4 animate-spin" /> : <ScanFace className="w-4 h-4" />}
                Capture & Verify
              </button>
            )}
            <button className="btn-ghost" onClick={load}>
              <RefreshCw className="w-4 h-4" /> Refresh
            </button>
          </div>
          {faceMsg && <div className="mt-2 text-xs text-slate-400">{faceMsg}</div>}
        </Card>

        {/* MRZ */}
        <Card title="MRZ Analysis" icon={FileText}
          right={r.mrz?.found ? <StatusBadge status={r.mrz.check_digits_valid ? "PASS" : "WARNING"} /> : <StatusBadge status="SKIPPED" />}>
          {r.mrz?.found ? (
            <div className="text-sm space-y-1">
              <div className="text-slate-300">Format: <span className="font-mono">{r.mrz.format}</span> ·
                Check digits: {r.mrz.check_digits_valid ?
                  <span className="text-emerald-400">VALID</span> :
                  <span className="text-amber-400">INVALID</span>}
              </div>
              {(r.mrz.comparisons ?? []).map((c, i) => (
                <div key={i} className="flex items-center gap-2 text-xs">
                  <StatusBadge status={c.status} />
                  <span className="text-slate-400">{c.field}: MRZ <span className="font-mono">{c.mrz}</span> vs OCR <span className="font-mono">{c.ocr}</span></span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-slate-500">
              No MRZ detected on this document (normal for many ID cards and licences).
            </p>
          )}
        </Card>

        {/* Identity consistency */}
        <Card title="Identity Consistency" icon={ShieldCheck}
          right={<StatusBadge status={r.identity?.status ?? "NOT_APPLICABLE"} />}>
          <p className="text-sm text-slate-400">{r.identity?.message}</p>
          {(r.identity?.conflicts ?? []).map((c, i) => (
            <div key={i} className="mt-2 text-xs bg-red-500/5 border border-red-500/30 rounded-lg p-2">
              <div className="text-red-300 font-semibold">{c.field} mismatch</div>
              <div className="text-slate-400">{c.message}</div>
              {Object.entries(c.values ?? {}).map(([src, val]) => (
                <div key={src} className="font-mono text-[11px] text-slate-500">{src}: {String(val)}</div>
              ))}
            </div>
          ))}
        </Card>

        {/* AI explanation */}
        <Card title="AI Explanation" icon={FileText}
          right={<span className="badge bg-cyan-500/10 text-cyan-300 border border-cyan-500/30">
            {r.ai?.ai_source}
          </span>}>
          <pre className="text-xs text-slate-300 whitespace-pre-wrap font-sans leading-relaxed">
            {r.ai?.summary}
          </pre>
        </Card>

        {/* Risk factors */}
        <Card title="Why this score?" icon={AlertTriangle}>
          <div className="space-y-2">
            {(r.risk_factors ?? []).map((f, i) => (
              <div key={i} className="text-xs">
                <div className="flex justify-between text-slate-300">
                  <span>{f.description}</span>
                  <span className="font-mono text-cyan-300">+{f.contribution}</span>
                </div>
                <div className="h-1.5 mt-1 rounded bg-night-800 overflow-hidden">
                  <div className="h-full bg-gradient-to-r from-cyan-500 to-red-500"
                    style={{ width: `${Math.min(100, f.contribution * 2)}%` }} />
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}