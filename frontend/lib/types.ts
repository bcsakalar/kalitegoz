export type Role = "admin" | "supervisor" | "quality" | "agent";

export interface Me {
  id: number;
  email: string;
  name: string;
  role: Role;
  tenant_id: number;
  tenant_name: string;
  team_id: number | null;
  agent_id: number | null;
}

export interface Agent {
  id: number;
  name: string;
}

export interface Campaign {
  id: number;
  name: string;
  channel: string;
  description: string;
}

export interface CallListItem {
  id: number;
  filename: string;
  channel: "voice" | "chat";
  status: "pending" | "transcribing" | "scoring" | "done" | "failed";
  duration_sec: number | null;
  category: string | null;
  total_score: number | null;
  zeroed: boolean;
  is_crisis: boolean;
  predicted_csat: number | null;
  customer_ref: string | null;
  is_repeat: boolean;
  repeat_of_id: number | null;
  emotion: Emotion | null;
  churn_risk: RiskLevel | null;
  emotion_mismatch: boolean;
  intent_tags: string[];
  is_golden: boolean;
  tags: string[];
  created_at: string;
  processed_at: string | null;
  agent: Agent | null;
  campaign: Campaign | null;
}

export type Emotion =
  | "ofke" | "hayal_kirikligi" | "endise" | "memnuniyet"
  | "notr" | "saskinlik" | "minnettarlik" | "uzuntu";
export type RiskLevel = "dusuk" | "orta" | "yuksek";
export type Trajectory = "yukselen" | "dusen" | "sabit";

export interface CallList {
  items: CallListItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface Segment {
  idx: number;
  speaker: "musteri" | "temsilci" | "bilinmeyen";
  start_sec: number;
  end_sec: number;
  text: string;
}

export interface Score {
  id: number;
  criterion_id: number | null;
  criterion_name: string;
  criterion_group: string;
  weight: number;
  score: number;
  rationale: string;
  evidence: string;
  evidence_ts: number | null;
  override_score: number | null;
  override_reason: string | null;
  effective_score: number;
}

export interface RiskyMoment {
  zaman: number;
  aciklama: string;
  onem: "dusuk" | "orta" | "yuksek";
}

export interface Violation {
  kind: string;
  category: string;
  severity: string;
  term: string;
  speaker: string;
  evidence: string;
  ts_sec: number | null;
}

export interface CallMetrics {
  temsilci_konusma_orani?: number;
  temsilci_konusma_sn?: number;
  musteri_konusma_sn?: number;
  temsilci_kesinti?: number;
  musteri_kesinti?: number;
  sessizlik_sn?: number;
  en_uzun_sessizlik_sn?: number;
  temsilci_kelime_dk?: number;
  ilk_yanit_sn?: number;
  ortalama_yanit_sn?: number;
  temsilci_mesaj?: number;
  musteri_mesaj?: number;
  toplam_mesaj?: number;
  // Akustik (nasıl söyledi)
  temsilci_pitch_hz?: number;
  temsilci_tonlama_sapmasi?: number;
  temsilci_monoton?: boolean;
  temsilci_ses_seviyesi?: number;
  temsilci_bagirma_sayisi?: number;
  temsilci_bagirma_anlari?: number[];
  musteri_pitch_hz?: number;
  musteri_monoton?: boolean;
  musteri_bagirma_sayisi?: number;
  musteri_bagirma_anlari?: number[];
}

export type Sentiment = "olumlu" | "notr" | "olumsuz";

export interface CallDetail extends CallListItem {
  summary: string | null;
  risky_moments: RiskyMoment[];
  metrics: CallMetrics | null;
  sentiment_start: Sentiment | null;
  sentiment_end: Sentiment | null;
  sentiment_trajectory: Trajectory | null;
  next_action: string | null;
  customer_effort: number | null;
  coaching: string | null;
  error: string | null;
  segments: Segment[];
  scores: Score[];
  violations: Violation[];
  pii_masked?: boolean;
}

export interface Criterion {
  id: number;
  name: string;
  description: string;
  group: string;
  weight: number;
  min_score: number;
  max_score: number;
  is_critical: boolean;
  critical_threshold: number;
  channel_scope: string;
  campaign_id: number | null;
  is_active: boolean;
}

export interface AgentSummary {
  id: number;
  name: string;
  call_count: number;
  avg_score: number | null;
  last_call_at: string | null;
}

export interface TrendPoint {
  date: string;
  avg_score: number;
  call_count: number;
}

export interface CriterionAvg {
  criterion_name: string;
  avg_score: number;
  count: number;
}

export interface Badge {
  code: string;
  name: string;
  icon: string;
  description: string;
  period: string;
}

export interface AgentScorecard {
  id: number;
  name: string;
  team_name: string | null;
  call_count: number;
  avg_score: number | null;
  avg_csat: number | null;
  zeroed_count: number;
  crisis_count: number;
  trend: TrendPoint[];
  criteria: CriterionAvg[];
  badges: Badge[];
  recent_calls: CallListItem[];
  weekly_coaching: string;
}

export interface Overview {
  total_calls: number;
  done_calls: number;
  processing_calls: number;
  failed_calls: number;
  avg_score: number | null;
  low_score_calls: number;
  zeroed_calls: number;
  crisis_calls: number;
  avg_csat: number | null;
  category_dist: Record<string, number>;
  trend: TrendPoint[];
}

export interface BannedWord {
  id: number;
  term: string;
  category: string;
  severity: string;
  match_type: string;
  is_active: boolean;
}

export interface Team {
  id: number;
  name: string;
  supervisor_id: number | null;
}

export interface UserRow {
  id: number;
  email: string;
  name: string;
  role: Role;
  team_id: number | null;
  agent_id: number | null;
  is_active: boolean;
  password_set: boolean;
}

// --- Kurumsal onboarding / auth ---
export interface AuthConfig {
  sso_enabled: boolean;
  demo_mode: boolean;
  needs_setup: boolean;
  org_slug: string | null;
  org_name: string | null;
}

export interface InviteInfo {
  valid: boolean;
  email: string;
  name: string;
  org_name: string;
}

export interface InviteResult {
  user: UserRow;
  invite_url: string;
  emailed: boolean;
}

export interface AgentAdmin {
  id: number;
  name: string;
  team_id: number | null;
}

export interface TenantSettings {
  org_name: string;
  retention_days: number;
  auto_process: boolean;
  notify_events: string[];
  brand_name: string | null;
  brand_color: string | null;
}

export interface SystemInfo {
  llm_provider: string;
  llm_model: string;
  whisper_model: string;
  whisper_device: string;
  vision_enabled: boolean;
  rag_enabled: boolean;
  sso_enabled: boolean;
  demo_mode: boolean;
  pii_masking: boolean;
  smtp_configured: boolean;
}

export interface OnboardingStatus {
  brand_set: boolean;
  has_teams: boolean;
  has_agents: boolean;
  has_users: boolean;
  has_rubric: boolean;
  has_calls: boolean;
  has_knowledge: boolean;
  complete: boolean;
}

// --- Coklu AI saglayici ---
export interface AIConfig {
  llm_provider: string;
  vision_provider: string;
  embed_provider: string;
  llm_models: Record<string, string>;
  vision_models: Record<string, string>;
  embed_models: Record<string, string>;
  keys_set: Record<string, boolean>;
  providers: string[];
  embed_providers: string[];
  vision_providers: string[];
}

export interface AICatalogItem { name: string; size: string; kind: string; desc: string; }
export interface AICatalog {
  ollama_recommended: AICatalogItem[];
  gemini: string[]; openai: string[]; openrouter: string[];
  gemini_embed: string[]; openai_embed: string[];
  gemini_vision: string[]; openai_vision: string[]; openrouter_vision: string[];
}
export interface OllamaModel { name: string; size: string; }

// --- Dalga 1 ---
export interface EmergingTopic { label: string; kind: string; now_count: number; prev_count: number; change_pct: number; }
export interface SimulateCriterion { criterion_id: number; weight: number; is_critical: boolean; critical_threshold: number; is_active: boolean; }
export interface SimulateChange { id: number; filename: string; before: number; after: number; delta: number; }
export interface SimulateResult { call_count: number; avg_before: number; avg_after: number; zeroed_before: number; zeroed_after: number; biggest_changes: SimulateChange[]; }
export interface WeakCriterion { name: string; avg: number; }
export interface CoachingPlan { agent_id: number; agent_name: string; call_count: number; weak_criteria: WeakCriterion[]; focus: string[]; plan: string; }
export interface AITestResult { ok: boolean; provider: string; model: string; output?: string; error?: string; }
export interface PullStatus { status: string; percent: number; done: boolean; error: string | null; }

// --- Dalga 2 ---
export interface CorrelationInsight { factor: string; label: string; corr: number; n: number; direction: string; strength: string; insight: string; }
export interface ExecSummary { period_days: number; call_count: number; avg_score: number | null; headline: string; wins: string[]; risks: string[]; actions: string[]; generated_at: string; }
export interface TargetIn { scope: string; scope_id: number | null; metric: string; target_value: number; }
export interface Target { id: number; scope: string; scope_id: number | null; metric: string; target_value: number; }
export interface TargetProgress { id: number; scope: string; scope_id: number | null; scope_name: string; metric: string; target_value: number; actual: number | null; met: boolean; call_count: number; }
export interface AiUsageRow { kind: string; provider: string; calls: number; prompt_tokens: number; completion_tokens: number; cost_usd: number; avg_latency_ms: number; }
export interface AiUsageSummary { period_days: number; total_calls: number; total_tokens: number; total_cost_usd: number; ok_rate: number; by_kind: AiUsageRow[]; by_provider: AiUsageRow[]; }

// --- Dalga 3 ---
export interface ChurnCall { id: number; filename: string; agent_name: string | null; category: string | null; churn_risk: string; total_score: number | null; predicted_csat: number | null; created_at: string; }
export interface ChurnSummary { period_days: number; high: number; medium: number; low: number; total_scored: number; high_rate: number; retention_list: ChurnCall[]; }
export interface AppealAnalytics { period_days: number; total: number; open: number; accepted: number; rejected: number; overturn_rate: number; avg_resolution_days: number | null; }

// --- Dalga 5 ---
export interface RubricVersion { id: number; note: string; criteria_count: number; created_by: number | null; created_at: string; }
export interface BulkResult { affected: number; action: string; }
export interface SimilarCall { id: number; filename: string; agent_name: string | null; category: string | null; total_score: number | null; similarity: number; shared_tags: string[]; }

// --- Dalga 6 ---
export interface NotificationItem { kind: string; ref_id: number; title: string; message: string; link: string; severity: string; created_at: string; }
export interface NotificationFeed { unread_count: number; items: NotificationItem[]; }

export interface Alert {
  id: number;
  call_id: number | null;
  type: string;
  severity: string;
  message: string;
  is_read: boolean;
  created_at: string;
}

export interface Appeal {
  id: number;
  call_id: number;
  created_by: number;
  reason: string;
  status: "open" | "accepted" | "rejected";
  resolution_note: string | null;
  created_at: string;
  resolved_at: string | null;
}

export interface CoachingTask {
  id: number;
  call_id: number;
  assignee_agent_id: number;
  note: string;
  status: "open" | "done";
  agent_comment: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface LeaderboardRow {
  agent_id: number;
  agent_name: string;
  team_name: string | null;
  avg_score: number;
  call_count: number;
  crisis_handled: number;
  points: number;
}

export interface CalibrationRow {
  criterion_name: string;
  ai_avg: number;
  human_avg: number;
  delta: number;
  override_count: number;
}

export interface CalibrationSession {
  id: number;
  call_id: number;
  title: string;
  status: "open" | "closed";
  created_by: number;
  scheduled_at: string | null;
  created_at: string;
  closed_at: string | null;
  evaluation_count: number;
  my_evaluation_id: number | null;
}

export interface CalibrationCriterionRow {
  criterion_id: number;
  criterion_name: string;
  scores: { evaluator: string; score: number }[];
  min: number;
  max: number;
  spread: number;
  avg: number;
  agreed: boolean;
  ai_score: number | null;
}

export interface CalibrationReport {
  session_id: number;
  call_id: number;
  status: string;
  agreement_pct: number | null;
  evaluator_count: number;
  meets_target: boolean | null;
  target: number;
  most_divergent: string | null;
  criteria: CalibrationCriterionRow[];
  ai_total: number | null;
  human_avg_total: number | null;
}

export interface TranscriptHit {
  call_id: number;
  filename: string;
  channel: string;
  agent_name: string | null;
  category: string | null;
  total_score: number | null;
  created_at: string;
  speaker: string;
  ts_sec: number;
  text: string;
  match_count: number;
}

export interface TranscriptSearchResult {
  query: string;
  total_hits: number;
  total_calls: number;
  items: TranscriptHit[];
}

export interface ProcessingStatus {
  paused: boolean;
  pending_calls: number;
  failed_calls: number;
  running_calls: number;
  done_calls: number;
  queued_now: number;
}

export interface KnowledgeDoc {
  id: number;
  title: string;
  source_filename: string;
  chunk_count: number;
  created_at: string;
}

export interface KnowledgeHit {
  doc_id: number;
  doc_title: string;
  idx: number;
  content: string;
  similarity: number;
}

export interface KnowledgeStats {
  documents: number;
  chunks: number;
  rag_active: boolean;
}

export interface SupervisorCockpit {
  team_id: number | null;
  avg_score: number | null;
  avg_csat: number | null;
  crisis_calls: number;
  zeroed_calls: number;
  avg_handle_sec: number | null;
  fcr_estimate: number | null;
  fcr_is_real: boolean;
  repeat_calls: number;
  unread_alerts: number;
  violation_dist: Record<string, number>;
  agents: LeaderboardRow[];
}

export interface Topic {
  baslik: string;
  kok_neden: string;
  aksiyon: string;
  cagri_sayisi: number;
  ortalama_puan: number | null;
  kategoriler: Record<string, number>;
  ornek_cagrilar: { id: number; filename: string; ozet: string }[];
}

export interface TopicsResult {
  cached: boolean;
  topics: Topic[];
}

// --- Analitik (Dalga 3a + 3b) ---
export interface TimeseriesPoint { date: string; avg: number | null; count: number; }
export interface VocTrend { kind: "category" | "intent"; label: string; recent: number; prior: number; change_pct: number; }
export interface CohortRow { label: string; count: number; avg_score: number | null; avg_csat: number | null; crisis: number; }

// --- QA inceleme (Dalga 2b) ---
export interface ReviewStats { counts: Record<string, number>; total: number; completion_rate: number; }
export interface ReviewAssignment {
  id: number; call_id: number; reviewer_id: number; reason: string; status: string;
  created_at: string; completed_at: string | null;
}

// --- Kocluk etkinlik (Dalga 2c) ---
export interface CoachingEffect {
  task_id: number; agent_id: number; agent_name: string; ref_date: string;
  before_avg: number; after_avg: number; delta: number; before_n: number; after_n: number; improved: boolean;
}
export interface CoachingEffectiveness {
  measurable_count: number; total_completed: number; improved_count: number;
  improved_rate: number; avg_delta: number; window_days: number; effects: CoachingEffect[];
}

// --- Gamification + self-servis (Dalga 3c + 3d) ---
export interface Challenge {
  id: number; title: string; description: string; metric: string; target: number;
  progress: number; completed: boolean; reward_points: number; ends_at: string | null;
}
export interface Gamification { points: number; streak: number; challenges: Challenge[]; }
export interface SelfAssessment {
  id: number; call_id: number; agent_id: number; self_score: number; note: string | null; created_at: string;
}

// --- Uyum paketleri (Dalga 4a) ---
export interface ComplianceRule { key: string; description: string; severity: string; kind: string; }
export interface CompliancePack { key: string; name: string; description: string; rules: ComplianceRule[]; }

// --- Vision + Assist (Dalga 5 + 6) ---
export interface AssistSuggestion { kind: string; severity: string; text: string; detail: string; }
export interface VisionStatus { enabled: boolean; provider: string; model: string; }
export interface VisionResult {
  aciklama: string; belge_turu: string; kvkk_riski: string; hassas_veri: string[]; ozet_not: string;
}

// --- Kurumsal katman (Dalga 13: satilabilir MVP) ---
export interface AuditEntry {
  id: number; user_id: number | null; user_name: string | null; action: string;
  entity_type: string; entity_id: number | null; detail: Record<string, unknown> | null;
  ip: string; created_at: string;
}
export interface AuditPage { items: AuditEntry[]; total: number; page: number; page_size: number; }

export interface SecurityPosture {
  deployment: string; llm_provider: string; data_leaves_premises: boolean;
  pii_masking_enabled: boolean; audit_log_enabled: boolean; sso_enabled: boolean;
  rbac_roles: string[]; retention_days: number; encryption_at_rest: boolean;
  multi_tenant_isolation: boolean; kvkk_pack_active: boolean; audit_events_30d: number;
}

export interface DraftCriterion {
  name: string; description: string; group: string; weight: number;
  is_critical: boolean; critical_threshold: number; channel_scope: string;
}
export interface ScorecardDraft { criteria: DraftCriterion[]; note: string; }

export interface RoiInputs {
  agents: number; calls_per_agent_day: number; minutes_per_manual_review: number;
  qa_hourly_cost: number; manual_coverage_pct: number; working_days_month: number;
}
export interface RoiResult {
  total_calls_month: number; manual_reviews_month: number; ai_coverage_pct: number;
  manual_hours_month: number; manual_cost_month: number; ai_equiv_hours_saved: number;
  ai_equiv_cost: number; coverage_multiplier: number; est_monthly_saving: number;
  est_annual_saving: number; payback_note: string;
}

export interface Branding { brand_name: string; brand_color: string; logo_data_url: string | null; }
