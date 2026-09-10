// Shared TypeScript types for the SatyaNetra frontend.

export interface User {
  id: number;
  username: string;
  email: string;
  role: string;
}

export interface UploadResponse {
  document_id: number;
  filename: string;
  document_hash: string;
  status: string;
  demo_mode: boolean;
}

export interface StepStatus {
  name: string;
  status: "PENDING" | "PROCESSING" | "COMPLETED" | "FAILED" | "SKIPPED";
  detail: string;
}

export interface ScreeningStatus {
  status: string;
  progress: number;
  current_step: string;
  steps: StepStatus[];
}

export interface ValidationCheck {
  name: string;
  status: string;
  message: string;
}

export interface ScreeningResult {
  verification_id: string;
  document_type: string;
  completed_at?: string | null;
  created_at?: string | null;
  classification_confidence?: number;
  risk_score?: number;
  risk_level?: string;
  risk_factors?: RiskFactor[];
  risk_components?: Record<string, number>;
  ocr_confidence?: number;
  ocr_data_source?: string;
  ocr_engine?: string;
  extracted?: ExtractedData;
  validation?: { overall_status: string; checks: ValidationCheck[]; expired?: boolean };
  mrz?: {
    found: boolean;
    format: string;
    check_digits_valid: boolean;
    comparisons: { field: string; mrz: string; ocr: string; status: string }[];
    parse_error?: string;
  };
  tampering?: {
    tampering_score: number;
    risk_level: string;
    photo_tampering_indicator: number;
    indicators: { type: string; severity: string; message: string }[];
    notes: string[];
    engine: string;
  };
  face?: FaceResult | null;
  face_detection?: { faces_detected: number; quality?: number | null; note?: string };
  watchlist?: { found: boolean; status: string; source: string; details: Record<string, unknown> };
  identity?: {
    status: string;
    conflicts: { field: string; message: string; values: Record<string, string> }[];
    comparisons: { field: string; status: string; message: string }[];
    message: string;
  };
  ai?: { summary: string; ai_source: string };
  audit?: { chain_valid: boolean; message: string; records: AuditRecord[] };
  alerts_generated?: string[];
  warnings?: string[];
  report_path?: string;
  demo_mode?: boolean;
}

export interface RiskFactor {
  factor: string;
  description: string;
  signal: number;
  weight: number;
  contribution: number;
}

export interface ExtractedData {
  name?: string;
  document_number?: string;
  nationality?: string;
  date_of_birth?: string;
  gender?: string;
  issue_date?: string;
  expiry_date?: string;
  data_source?: string;
}

export interface FaceResult {
  match: boolean;
  similarity: number;
  status: string;
  faces_detected_document: number;
  faces_detected_presented: number;
  message: string;
  engine?: string;
  demo_mode?: boolean;
}

export interface AuditRecord {
  id: number;
  event_type: string;
  document_hash: string;
  previous_hash: string;
  current_hash: string;
  event_data: string;
  timestamp: string;
}

export interface ScreeningHistoryItem {
  id: number;
  verification_id: string;
  status: string;
  risk_score: number | null;
  risk_level: string;
  ocr_confidence: number | null;
  tampering_score: number | null;
  face_match_score: number | null;
  created_at: string;
  processing_ms: number | null;
  document_type: string;
  filename: string;
  document_hash: string;
}

export interface DashboardStats {
  total_screenings: number;
  high_risk: number;
  medium_risk: number;
  low_risk: number;
  critical_risk: number;
  tampering_detections: number;
  face_mismatches: number;
  expired_documents: number;
  avg_processing_ms: number;
  open_alerts: number;
  trend: { date: string; count: number }[];
  risk_distribution: { level: string; count: number }[];
  demo_mode: boolean;
}

export interface Alert {
  id: number;
  screening_id: number;
  verification_id: string | null;
  severity: string;
  category: string;
  message: string;
  status: string;
  created_at: string;
}

export interface CaseItem {
  id: number;
  screening_id: number;
  verification_id: string | null;
  title: string;
  status: string;
  assigned_to: string;
  notes: string;
  created_at: string;
  updated_at: string;
}

export interface WatchlistEntry {
  id: number;
  document_number: string;
  name: string;
  nationality: string;
  date_of_birth: string;
  status: string;
  notes: string;
}

export interface AuditChainResponse {
  verification_id: string;
  chain_valid: boolean;
  records: AuditRecord[];
  message: string;
}