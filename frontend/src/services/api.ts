/**
 * Central API service - ALL backend communication goes through this module.
 * No component may hardcode API URLs (project requirement 32).
 */
import axios, { AxiosError } from "axios";
import type {
  Alert,
  AuditChainResponse,
  CaseItem,
  DashboardStats,
  ScreeningHistoryItem,
  ScreeningResult,
  ScreeningStatus,
  UploadResponse,
  User,
  WatchlistEntry,
} from "../types";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export const api = axios.create({
  baseURL: API_URL,
  timeout: 120_000,
});

// Attach JWT on every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("satyanetra_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Global 401 handling -> back to login
api.interceptors.response.use(
  (res) => res,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      localStorage.removeItem("satyanetra_token");
      localStorage.removeItem("satyanetra_user");
      if (!window.location.pathname.includes("/login")) {
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);

/** Extract a friendly message from an Axios error. */
export function apiErrorMessage(err: unknown): string {
  const e = err as AxiosError<{ detail?: string }>;
  const detail = e.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (e.response?.status === 413)
    return "File too large. Please upload a smaller document.";
  if (e.response?.status === 400)
    return "Unable to process this document. Please upload a clearer image (JPG/PNG/WEBP/PDF).";
  if (e.response?.status === 404) return "Requested resource not found.";
  if (e.code === "ECONNABORTED" || !e.response)
    return "Cannot reach the SatyaNetra backend. Ensure it is running on port 8000.";
  return "An unexpected error occurred. Please try again.";
}

// ---------------- Auth ----------------
export async function login(username: string, password: string) {
  const r = await api.post<{ access_token: string; username: string; role: string }>(
    "/api/auth/login",
    { username, password }
  );
  localStorage.setItem("satyanetra_token", r.data.access_token);
  return r.data;
}

export async function fetchMe(): Promise<User> {
  const r = await api.get<User>("/api/auth/me");
  return r.data;
}

export function logout() {
  localStorage.removeItem("satyanetra_token");
  localStorage.removeItem("satyanetra_user");
}

// ---------------- Documents ----------------
export async function uploadDocument(
  file: File,
  documentType = ""
): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  if (documentType) form.append("document_type", documentType);
  const r = await api.post<UploadResponse>("/api/documents/upload", form);
  return r.data;
}

// ---------------- Screening ----------------
export async function startScreening(documentId: number): Promise<string> {
  const r = await api.post<{ verification_id: string }>(
    `/api/screening/start/${documentId}`
  );
  return r.data.verification_id;
}

export async function getScreeningStatus(
  verificationId: string
): Promise<ScreeningStatus> {
  const r = await api.get<ScreeningStatus>(`/api/screening/${verificationId}/status`);
  return r.data;
}

export async function getScreeningResult(
  verificationId: string
): Promise<ScreeningResult> {
  const r = await api.get<ScreeningResult>(`/api/screening/${verificationId}/result`);
  return r.data;
}

export async function getScreeningHistory(
  limit = 50
): Promise<ScreeningHistoryItem[]> {
  const r = await api.get<ScreeningHistoryItem[]>("/api/screening", { params: { limit } });
  return r.data;
}

// ---------------- Face ----------------
export async function verifyFace(
  verificationId: string,
  file?: File,
  imageDataUrl?: string
) {
  const form = new FormData();
  form.append("verification_id", verificationId);
  if (file) form.append("image", file);
  if (imageDataUrl) form.append("image_data", imageDataUrl);
  const r = await api.post("/api/face/verify", form);
  return r.data as {
    match: boolean;
    similarity: number;
    status: string;
    faces_detected_document: number;
    faces_detected_presented: number;
    message: string;
    engine?: string;
  };
}

// ---------------- Dashboard ----------------
export async function getDashboardStats(): Promise<DashboardStats> {
  const r = await api.get<DashboardStats>("/api/dashboard/stats");
  return r.data;
}

// ---------------- Alerts ----------------
export async function getAlerts(status?: string): Promise<Alert[]> {
  const r = await api.get<Alert[]>("/api/alerts", { params: status ? { alert_status: status } : {} });
  return r.data;
}

export async function updateAlertStatus(id: number, status: string): Promise<Alert> {
  const r = await api.patch<Alert>(`/api/alerts/${id}`, { status });
  return r.data;
}

// ---------------- Cases ----------------
export async function getCases(status?: string): Promise<CaseItem[]> {
  const r = await api.get<CaseItem[]>("/api/cases", { params: status ? { case_status: status } : {} });
  return r.data;
}

export async function createCase(payload: {
  screening_id: number;
  title: string;
  notes?: string;
}): Promise<CaseItem> {
  const r = await api.post<CaseItem>("/api/cases", payload);
  return r.data;
}

export async function updateCase(
  id: number,
  patch: Partial<{ status: string; assigned_to: string; notes: string; title: string }>
): Promise<CaseItem> {
  const r = await api.patch<CaseItem>(`/api/cases/${id}`, patch);
  return r.data;
}

// ---------------- Audit ----------------
export async function getAuditTrail(
  verificationId: string
): Promise<AuditChainResponse> {
  const r = await api.get<AuditChainResponse>(`/api/audit/${verificationId}`);
  return r.data;
}

// ---------------- Watchlist ----------------
export async function checkWatchlist(documentNumber: string) {
  const r = await api.get(`/api/watchlist/check/${encodeURIComponent(documentNumber)}`);
  return r.data as { found: boolean; status: string; source: string; details: Record<string, unknown> };
}

export async function getWatchlist(): Promise<WatchlistEntry[]> {
  const r = await api.get<WatchlistEntry[]>("/api/watchlist");
  return r.data;
}

// ---------------- Reports ----------------
export async function downloadReport(verificationId: string): Promise<void> {
  const r = await api.get(`/api/reports/${verificationId}`, { responseType: "blob" });
  const url = window.URL.createObjectURL(new Blob([r.data], { type: "application/pdf" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = `SatyaNetra_Report_${verificationId}.pdf`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}

// ---------------- Health ----------------
export async function getHealth() {
  const r = await axios.get(`${API_URL}/health`, { timeout: 5000 });
  return r.data as { status: string; database: string; demo_mode: boolean; version: string };
}