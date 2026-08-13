import type {
  Alert,
  Appeal,
  AgentScorecard,
  AgentSummary,
  BannedWord,
  CalibrationReport,
  CalibrationRow,
  CalibrationSession,
  CallDetail,
  CallList,
  CallListItem,
  Campaign,
  CoachingTask,
  Criterion,
  KnowledgeDoc,
  KnowledgeHit,
  KnowledgeStats,
  LeaderboardRow,
  Me,
  Overview,
  ProcessingStatus,
  SupervisorCockpit,
  Team,
  TopicsResult,
  TranscriptSearchResult,
  UserRow,
  TimeseriesPoint,
  TimeseriesResponse,
  VocResponse,
  VocTrend,
  CohortRow,
  ReviewStats,
  ReviewAssignment,
  CoachingEffectiveness,
  Gamification,
  SelfAssessment,
  Challenge,
  CompliancePack,
  AssistSuggestion,
  VisionStatus,
  VisionResult,
  AuditPage,
  SecurityPosture,
  ScorecardDraft,
  DraftCriterion,
  RoiInputs,
  RoiResult,
  Branding,
  AuthConfig,
  InviteInfo,
  InviteResult,
  AgentAdmin,
  TenantSettings,
  SystemInfo,
  OnboardingStatus,
  AIConfig,
  AICatalog,
  ModelListesi,
  OllamaModel,
  AITestResult,
  PullStatus,
  EmergingTopic,
  SimulateCriterion,
  SimulateResult,
  CoachingPlan,
  CorrelationInsight,
  ExecSummary,
  Target,
  TargetIn,
  TargetProgress,
  AiUsageSummary,
  ChurnSummary,
  AppealAnalytics,
  RubricVersion,
  BulkResult,
  SimilarCall,
  NotificationFeed,
  ReviewCall,
  ReviewQueueStats,
  ReviewSubmit,
  SecurityChecks,
  SSOConfig,
  SSOConfigSave,
  SSOSaveResult,
  EncryptionStatus,
  CSATCorrelation,
  CSATBand,
} from "./types";
import { translate, type Lang } from "./i18n";

export const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const V1 = `${API_BASE}/api/v1`;

const TOKEN_KEY = "kg_token";
const REFRESH_KEY = "kg_refresh";

export const tokenStore = {
  get: () => (typeof window === "undefined" ? null : localStorage.getItem(TOKEN_KEY)),
  getRefresh: () => (typeof window === "undefined" ? null : localStorage.getItem(REFRESH_KEY)),
  set: (access: string, refresh: string) => {
    localStorage.setItem(TOKEN_KEY, access);
    localStorage.setItem(REFRESH_KEY, refresh);
  },
  clear: () => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_KEY);
  },
};

/**
 * WebSocket URL'i uretir (http->ws, https->wss).
 *
 * Token query string'e konur: tarayicinin WebSocket API'si ozel HTTP basligi
 * gondermeye izin vermez, bu yuzden Authorization header kullanilamaz.
 * Token yoksa null doner — cagiran baglanmayi atlar.
 */
export function wsUrl(path: string): string | null {
  const token = tokenStore.get();
  if (!token) return null;
  const base = V1.replace(/^http/, "ws");
  return `${base}${path}?token=${encodeURIComponent(token)}`;
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

/**
 * Kancasız çeviri — `api.ts` bir React bileşeni değildir, `useT()` çağıramaz.
 *
 * B41: buradaki hata mesajları sabit Türkçeydi ve doğrudan kullanıcıya
 * gösteriliyordu (sayfalar `e.message`'ı basıyor), yani İngilizce arayüzde
 * de Türkçe çıkıyorlardı. Dil `kg_lang`'den okunur — `I18nProvider` da aynı
 * anahtarı yazar, dolayısıyla iki taraf aynı kaynağa bakar.
 */
function tr(key: string): string {
  let lang: Lang = "tr";
  try {
    const kayitli = localStorage.getItem("kg_lang");
    if (kayitli === "en" || kayitli === "tr") lang = kayitli;
  } catch { /* SSR ya da erisim yok: varsayilan dil */ }
  return translate(lang, key);
}

async function request<T>(path: string, init: RequestInit = {}, retry = true): Promise<T> {
  const token = tokenStore.get();
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const res = await fetch(`${V1}${path}`, { cache: "no-store", ...init, headers });

  if (res.status === 401 && retry) {
    // Access token süresi dolmuş olabilir; refresh dene
    const refreshed = await tryRefresh();
    if (refreshed) return request<T>(path, init, false);
  }
  if (res.status === 401) {
    tokenStore.clear();
    if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
      window.location.href = "/login";
    }
    throw new ApiError(401, "Oturum gerekli");
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(res.status, body.detail ?? `API ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

async function tryRefresh(): Promise<boolean> {
  const refresh = tokenStore.getRefresh();
  if (!refresh) return false;
  const res = await fetch(`${V1}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refresh }),
  });
  if (!res.ok) return false;
  const data = await res.json();
  tokenStore.set(data.access_token, data.refresh_token);
  return true;
}

const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const api = {
  // --- FAZ 3/5: kaliteci inceleme kuyrugu ---
  reviewNext: () => request<ReviewCall | null>("/review-queue/next"),
  reviewQueueStats: () => request<ReviewQueueStats>("/review-queue/stats"),
  reviewSubmit: (callId: number, body: ReviewSubmit) =>
    request<ReviewCall | null>(`/review-queue/${callId}/submit`, json(body)),
  securityChecks: () => request<SecurityChecks>("/enterprise/security-checks"),

  // --- S12: kurumsal kimlik dogrulama + sifreleme anahtari ---
  ssoConfig: () => request<SSOConfig>("/enterprise/sso/config"),
  ssoConfigSave: (body: SSOConfigSave) =>
    request<SSOSaveResult>("/enterprise/sso/config", { ...json(body), method: "PUT" }),
  encryptionStatus: () => request<EncryptionStatus>("/enterprise/encryption/status"),

  // --- Gercek musteri anketi (CSAT) ---
  csatCorrelation: () => request<CSATCorrelation>("/csat/correlation"),
  csatDistribution: () => request<{ bantlar: CSATBand[] }>("/csat/distribution"),
  csatWrite: (callId: number, puan: number, kaynak = "manuel", yorum = "") =>
    request<{ call_id: number; actual_csat: number }>(`/csat/${callId}`,
      json({ puan, kaynak, yorum })),

  // --- Auth ---
  login: async (email: string, password: string, tenantSlug = "demo") => {
    const data = await request<{ access_token: string; refresh_token: string }>(
      "/auth/login",
      json({ email, password, tenant_slug: tenantSlug }),
      false,
    );
    tokenStore.set(data.access_token, data.refresh_token);
  },
  demoLogin: async (role: string) => {
    const res = await fetch(`${V1}/auth/demo-login`, json({ role }));
    if (!res.ok) throw new ApiError(res.status, tr("err.demoLogin"));
    const data = await res.json();
    tokenStore.set(data.access_token, data.refresh_token);
  },
  me: () => request<Me>("/auth/me"),

  // --- Kurumsal onboarding / auth ---
  authConfig: async (): Promise<AuthConfig | null> => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/auth/config`);
      return res.ok ? await res.json() : null;
    } catch { return null; }
  },
  registerOrg: async (body: { org_name: string; admin_name: string; admin_email: string; password: string }) => {
    const res = await fetch(`${V1}/auth/register-org`, json(body));
    if (!res.ok) throw new ApiError(res.status, ((await res.json().catch(() => ({}))) as { detail?: string }).detail ?? tr("err.orgCreate"));
    const data = await res.json();
    tokenStore.set(data.access_token, data.refresh_token);
  },
  inviteInfo: async (token: string): Promise<InviteInfo> => {
    const res = await fetch(`${V1}/auth/invite/${encodeURIComponent(token)}`);
    return res.ok ? await res.json() : { valid: false, email: "", name: "", org_name: "" };
  },
  acceptInvite: async (token: string, password: string) => {
    const res = await fetch(`${V1}/auth/accept-invite`, json({ token, password }));
    if (!res.ok) throw new ApiError(res.status, ((await res.json().catch(() => ({}))) as { detail?: string }).detail ?? "Davet kabul edilemedi");
    const data = await res.json();
    tokenStore.set(data.access_token, data.refresh_token);
  },
  forgotPassword: (email: string, org_slug?: string): Promise<{ message: string }> =>
    fetch(`${V1}/auth/forgot-password`, json({ email, org_slug })).then((r) => r.json()),
  resetPassword: async (token: string, password: string) => {
    const res = await fetch(`${V1}/auth/reset-password`, json({ token, password }));
    if (!res.ok) throw new ApiError(res.status, ((await res.json().catch(() => ({}))) as { detail?: string }).detail ?? tr("err.passwordReset"));
    const data = await res.json();
    tokenStore.set(data.access_token, data.refresh_token);
  },
  changePassword: (old_password: string, new_password: string) =>
    request<{ ok: boolean }>("/auth/change-password", json({ old_password, new_password })),

  // --- Calls ---
  listCalls: (params: Record<string, string>) =>
    request<CallList>(`/calls?${new URLSearchParams(params)}`),
  getCall: (id: number | string, reveal = false) =>
    request<CallDetail>(`/calls/${id}${reveal ? "?reveal=true" : ""}`),
  rescoreCall: (id: number, full = false) =>
    request<CallListItem>(`/calls/${id}/rescore?full=${full}`, { method: "POST" }),
  deleteCall: (id: number) => request<void>(`/calls/${id}`, { method: "DELETE" }),
  toggleGolden: (id: number) => request<CallListItem>(`/calls/${id}/golden`, { method: "POST" }),
  setCallTags: (id: number, tags: string[]) =>
    request<CallListItem>(`/calls/${id}/tags`, { ...json({ tags }), method: "PUT" }),
  uploadCall: (file: File, agentName: string, campaignId?: number) => {
    const form = new FormData();
    form.append("file", file);
    if (agentName) form.append("agent_name", agentName);
    if (campaignId) form.append("campaign_id", String(campaignId));
    return request<CallListItem>("/calls/upload", { method: "POST", body: form });
  },

  // --- Transkript arama ---
  searchTranscripts: (params: Record<string, string>) =>
    request<TranscriptSearchResult>(`/calls/search?${new URLSearchParams(params)}`),

  // --- Stats ---
  overview: () => request<Overview>("/stats/overview"),

  // --- Agents ---
  listAgents: () => request<AgentSummary[]>("/agents"),
  getAgent: (id: number | string) => request<AgentScorecard>(`/agents/${id}`),
  coachingPlan: (agentId: number | string, days = 30) =>
    request<CoachingPlan>(`/agents/${agentId}/coaching-plan?days=${days}`),

  // --- Criteria ---
  listCriteria: () => request<Criterion[]>("/criteria"),
  createCriterion: (body: Partial<Criterion>) =>
    request<Criterion>("/criteria", json(body)),
  updateCriterion: (id: number, body: Partial<Criterion>) =>
    request<Criterion>(`/criteria/${id}`, { ...json(body), method: "PATCH" }),
  deleteCriterion: (id: number) => request<void>(`/criteria/${id}`, { method: "DELETE" }),
  simulateRubric: (criteria: SimulateCriterion[], days = 30, limit = 200) =>
    request<SimulateResult>("/criteria/simulate", json({ criteria, days, limit })),

  // --- Admin ---
  listCampaigns: () => request<Campaign[]>("/admin/campaigns"),
  createCampaign: (body: { name: string; channel: string; description: string }) =>
    request<Campaign>("/admin/campaigns", json(body)),
  deleteCampaign: (id: number) => request<void>(`/admin/campaigns/${id}`, { method: "DELETE" }),
  listBannedWords: () => request<BannedWord[]>("/admin/banned-words"),
  createBannedWord: (body: Partial<BannedWord>) =>
    request<BannedWord>("/admin/banned-words", json(body)),
  updateBannedWord: (id: number, body: Partial<BannedWord>) =>
    request<BannedWord>(`/admin/banned-words/${id}`, { ...json(body), method: "PATCH" }),
  deleteBannedWord: (id: number) =>
    request<void>(`/admin/banned-words/${id}`, { method: "DELETE" }),
  listTeams: () => request<Team[]>("/admin/teams"),
  listUsers: () => request<UserRow[]>("/admin/users"),
  inviteUser: (body: { email: string; name: string; role: string; team_id?: number | null; agent_id?: number | null }) =>
    request<InviteResult>("/admin/users/invite", json(body)),
  regenerateLink: (userId: number) =>
    request<InviteResult>(`/admin/users/${userId}/invite-link`, { method: "POST" }),
  deleteUser: (userId: number) => request<void>(`/admin/users/${userId}`, { method: "DELETE" }),
  createTeam: (body: { name: string; supervisor_id?: number | null }) =>
    request<Team>("/admin/teams", json(body)),
  deleteTeam: (id: number) => request<void>(`/admin/teams/${id}`, { method: "DELETE" }),
  listAgentsAdmin: () => request<AgentAdmin[]>("/admin/agents"),
  createAgentAdmin: (body: { name: string; team_id?: number | null }) =>
    request<AgentAdmin>("/admin/agents", json(body)),
  updateAgentAdmin: (id: number, body: { name: string; team_id?: number | null }) =>
    request<AgentAdmin>(`/admin/agents/${id}`, { ...json(body), method: "PATCH" }),
  deleteAgentAdmin: (id: number) => request<void>(`/admin/agents/${id}`, { method: "DELETE" }),
  seedHistory: () => request<{ created: number; message: string }>("/admin/seed-demo-history", { method: "POST" }),
  getSettings: () => request<TenantSettings>("/admin/settings"),
  updateSettings: (body: Partial<{ retention_days: number; auto_process: boolean; notify_events: string[] }>) =>
    request<TenantSettings>("/admin/settings", { ...json(body), method: "PUT" }),
  systemInfo: () => request<SystemInfo>("/admin/system-info"),
  onboardingStatus: () => request<OnboardingStatus>("/admin/onboarding-status"),
  // --- Coklu AI saglayici ---
  getAiConfig: () => request<AIConfig>("/admin/ai/config"),
  putAiConfig: (body: Record<string, unknown>) =>
    request<AIConfig>("/admin/ai/config", { ...json(body), method: "PUT" }),
  aiCatalog: () => request<AICatalog>("/admin/ai/catalog"),
  /** Canli model listesi — saglayicinin kendi API'sinden. */
  aiModels: (provider: string, kind = "llm", refresh = false) =>
    request<ModelListesi>(
      `/admin/ai/models?provider=${provider}&kind=${kind}&refresh=${refresh}`),
  aiTest: (provider?: string) => request<AITestResult>("/admin/ai/test", json({ provider })),
  ollamaModels: () => request<{ models: OllamaModel[]; error?: string }>("/admin/ai/ollama/models"),
  ollamaPull: (model: string) => request<{ started: boolean }>("/admin/ai/ollama/pull", json({ model })),
  ollamaPullStatus: () => request<Record<string, PullStatus>>("/admin/ai/ollama/pull-status"),

  // --- Workflow ---
  listAlerts: (onlyUnread = false) =>
    request<Alert[]>(`/alerts?only_unread=${onlyUnread}`),
  readAlert: (id: number) => request<void>(`/alerts/${id}/read`, { method: "POST" }),
  overrideScore: (scoreId: number, body: { override_score: number; override_reason: string }) =>
    request<void>(`/scores/${scoreId}/override`, json(body)),
  listAppeals: (status?: string) =>
    request<Appeal[]>(`/appeals${status ? `?status=${status}` : ""}`),
  createAppeal: (body: { call_id: number; reason: string }) =>
    request<Appeal>("/appeals", json(body)),
  resolveAppeal: (id: number, body: { decision: string; resolution_note: string }) =>
    request<Appeal>(`/appeals/${id}/resolve`, json(body)),
  listCoaching: (status?: string) =>
    request<CoachingTask[]>(`/coaching${status ? `?status=${status}` : ""}`),
  createCoaching: (body: { call_id: number; assignee_agent_id: number; note: string }) =>
    request<CoachingTask>("/coaching", json(body)),
  completeCoaching: (id: number, body: { agent_comment: string }) =>
    request<CoachingTask>(`/coaching/${id}/complete`, json(body)),
  calibration: () => request<CalibrationRow[]>("/calibration"),

  // --- Isleme kontrolu (agir STT/LLM isini elle baslatma) ---
  processingStatus: () => request<ProcessingStatus>("/admin/processing"),
  pauseProcessing: () => request<ProcessingStatus>("/admin/processing/pause", { method: "POST" }),
  resumeProcessing: () => request<ProcessingStatus>("/admin/processing/resume", { method: "POST" }),
  startProcessing: () => request<ProcessingStatus>("/admin/processing/start", { method: "POST" }),

  // --- Kalibrasyon oturumlari (insan<->insan uyum) ---
  listCalibrationSessions: (status?: string) =>
    request<CalibrationSession[]>(`/calibration-sessions${status ? `?status=${status}` : ""}`),
  createCalibrationSession: (body: { call_id: number; title?: string; scheduled_at?: string | null }) =>
    request<CalibrationSession>("/calibration-sessions", json(body)),
  submitEvaluation: (sessionId: number, body: {
    call_id: number; scores: { criterion_id: number; score: number; note?: string }[]; notes?: string;
  }) => request<unknown>(`/calibration-sessions/${sessionId}/evaluate`, json(body)),
  closeCalibrationSession: (sessionId: number) =>
    request<CalibrationReport>(`/calibration-sessions/${sessionId}/close`, { method: "POST" }),
  calibrationReport: (sessionId: number) =>
    request<CalibrationReport>(`/calibration-sessions/${sessionId}/report`),

  // --- CSV metadata esleştirme ---
  importMetadata: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<{ matched: number; updated: number; not_found_count: number; message: string }>(
      "/admin/import-metadata", { method: "POST", body: form },
    );
  },

  // --- Bilgi bankasi (RAG) ---
  listKnowledgeDocs: () => request<KnowledgeDoc[]>("/knowledge/docs"),
  uploadKnowledgeDoc: (file: File, title: string) => {
    const form = new FormData();
    form.append("file", file);
    if (title) form.append("title", title);
    return request<KnowledgeDoc>("/knowledge/docs", { method: "POST", body: form });
  },
  deleteKnowledgeDoc: (id: number) =>
    request<void>(`/knowledge/docs/${id}`, { method: "DELETE" }),
  searchKnowledge: (q: string) =>
    request<KnowledgeHit[]>(`/knowledge/search?q=${encodeURIComponent(q)}`),
  knowledgeStats: () => request<KnowledgeStats>("/knowledge/stats"),
  seedKnowledge: () => request<KnowledgeDoc>("/knowledge/seed-demo", { method: "POST" }),

  // --- Toplu yeniden puanlama ---
  rescoreBulk: (callIds?: number[]) =>
    request<{ queued: boolean; message: string }>("/calls/rescore-bulk", json({ call_ids: callIds ?? null })),

  // --- Supervisor / gamification ---
  leaderboard: (period: string, teamId?: number) =>
    request<LeaderboardRow[]>(`/leaderboard?period=${period}${teamId ? `&team_id=${teamId}` : ""}`),
  cockpit: (teamId?: number) =>
    request<SupervisorCockpit>(`/supervisor/cockpit${teamId ? `?team_id=${teamId}` : ""}`),
  topics: (days = 30, refresh = false) =>
    request<TopicsResult>(`/supervisor/topics?days=${days}&refresh=${refresh}`),

  // --- Chat ---
  ingestChat: (body: unknown) => request<CallListItem>("/chats", json(body)),

  // --- Analitik (Dalga 3a VoC + 3b dashboard) ---
  analyticsTimeseries: (metric = "score", days = 30, bucket = "day") =>
    request<TimeseriesResponse>(`/analytics/timeseries?metric=${metric}&days=${days}&bucket=${bucket}`),
  analyticsVoc: (days = 14) => request<VocResponse>(`/analytics/voc?days=${days}`),
  analyticsEmotions: (days = 30) =>
    request<{ emotions: Record<string, number>; churn: Record<string, number> }>(`/analytics/emotions?days=${days}`),
  analyticsCohort: (dimension = "team", days = 30) =>
    request<CohortRow[]>(`/analytics/cohort?dimension=${dimension}&days=${days}`),
  emergingTopics: (days = 7) => request<EmergingTopic[]>(`/analytics/emerging?days=${days}`),
  correlations: (days = 90) => request<CorrelationInsight[]>(`/analytics/correlations?days=${days}`),
  execSummary: (days = 30) => request<ExecSummary>(`/analytics/exec-summary?days=${days}`),
  listTargets: () => request<Target[]>("/targets"),
  createTarget: (body: TargetIn) => request<Target>("/targets", json(body)),
  deleteTarget: (id: number) => request<void>(`/targets/${id}`, { method: "DELETE" }),
  targetProgress: (days = 30) => request<TargetProgress[]>(`/targets/progress?days=${days}`),
  aiUsage: (days = 30) => request<AiUsageSummary>(`/admin/ai/usage?days=${days}`),
  churn: (days = 30) => request<ChurnSummary>(`/analytics/churn?days=${days}`),
  appealAnalytics: (days = 90) => request<AppealAnalytics>(`/analytics/appeals?days=${days}`),
  listRubricVersions: () => request<RubricVersion[]>("/criteria/versions"),
  saveRubricVersion: (note: string) => request<RubricVersion>("/criteria/versions", json({ note })),
  restoreRubricVersion: (id: number) => request<Criterion[]>(`/criteria/versions/${id}/restore`, { method: "POST" }),
  bulkCallAction: (ids: number[], action: string, tag?: string) =>
    request<BulkResult>("/calls/bulk", json({ ids, action, tag })),
  similarCalls: (id: number | string, limit = 8) => request<SimilarCall[]>(`/calls/${id}/similar?limit=${limit}`),
  notifications: () => request<NotificationFeed>("/notifications"),
  notificationsReadAll: () => request<void>("/notifications/read-all", { method: "POST" }),

  // --- QA inceleme & ornekleme (Dalga 2b) ---
  reviewStats: () => request<ReviewStats>("/review/stats"),
  myReviews: (onlyOpen = false) =>
    request<ReviewAssignment[]>(`/review/mine?only_open=${onlyOpen}`),
  createSample: (body: { reviewer_id: number; reason: string; count: number }) =>
    request<ReviewAssignment[]>("/review/sample", json(body)),
  completeReview: (id: number, evaluationId?: number) =>
    request<ReviewAssignment>(`/review/${id}/complete${evaluationId ? `?evaluation_id=${evaluationId}` : ""}`, { method: "POST" }),
  coachingEffectiveness: () => request<CoachingEffectiveness>("/review/coaching-effectiveness"),

  // --- Self-servis + gamification (Dalga 3c + 3d) ---
  myGamification: () => request<Gamification>("/me/gamification"),
  createSelfAssessment: (body: { call_id: number; self_score: number; note?: string }) =>
    request<SelfAssessment>("/me/self-assessment", json(body)),
  getSelfAssessment: (callId: number) =>
    request<SelfAssessment | null>(`/calls/${callId}/self-assessment`),
  listChallenges: () => request<Challenge[]>("/challenges"),
  createChallenge: (body: Partial<Challenge> & { title: string }) =>
    request<Challenge>("/challenges", json(body)),

  // --- Uyum paketleri (Dalga 4a) ---
  compliancePacks: () => request<CompliancePack[]>("/compliance-packs"),

  // --- Agent assist + vision (Dalga 5 + 6) ---
  assistSuggest: (partialText: string, packs?: string[]) =>
    request<AssistSuggestion[]>("/assist/suggest", json({ partial_text: partialText, packs: packs ?? null })),
  visionStatus: () => request<VisionStatus>("/vision/status"),
  visionAnalyze: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<VisionResult>("/vision/analyze", { method: "POST", body: form });
  },

  // --- Kurumsal: denetim gunlugu, guvenlik durusu, AI puan karti, ROI, marka ---
  auditLog: (params: Record<string, string>) =>
    request<AuditPage>(`/admin/audit?${new URLSearchParams(params)}`),
  securityPosture: () => request<SecurityPosture>("/enterprise/security-posture"),
  buildScorecard: (body: { prompt: string; channel: string; max_criteria: number }) =>
    request<ScorecardDraft>("/enterprise/scorecard/build", json(body)),
  saveScorecard: (body: { criteria: DraftCriterion[]; campaign_id?: number | null; replace_existing: boolean }) =>
    request<{ created: number; message: string }>("/enterprise/scorecard/save", json(body)),
  computeRoi: (body: RoiInputs) => request<RoiResult>("/enterprise/roi", json(body)),
  demoReset: () =>
    request<{ deleted: number; created: number; message: string }>("/enterprise/demo/reset", { method: "POST" }),
  getBranding: () => request<Branding>("/admin/branding"),
  updateBranding: (body: Partial<Branding>) =>
    request<Branding>("/admin/branding", { ...json(body), method: "PUT" }),
};

/** Giris ekrani icin auth'suz marka (public). */
export async function fetchPublicBranding(tenant = "demo"): Promise<Branding | null> {
  try {
    const res = await fetch(`${V1}/auth/branding?tenant=${encodeURIComponent(tenant)}`, { cache: "no-store" });
    if (!res.ok) return null;
    return (await res.json()) as Branding;
  } catch {
    return null;
  }
}

/** SSO baslat: tarayiciyi backend'in OIDC yonlendirmesine gonderir. */
export const ssoLoginUrl = () => `${V1}/auth/sso/login`;

// Ses <audio> Authorization header gonderemez; blob olarak cekip object URL veririz
export async function fetchAudioObjectUrl(id: number | string): Promise<string> {
  const token = tokenStore.get();
  const res = await fetch(`${V1}/calls/${id}/audio`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new ApiError(res.status, tr("err.audioLoad"));
  const blob = await res.blob();
  return URL.createObjectURL(blob);
}

export const exportCsvUrl = (params: Record<string, string>) =>
  `${V1}/calls/export.csv?${new URLSearchParams(params)}`;

export const reportUrls = {
  teamXlsx: (teamId?: number) => `${V1}/reports/team.xlsx${teamId ? `?team_id=${teamId}` : ""}`,
  agentPdf: (agentId: number) => `${V1}/reports/agent/${agentId}.pdf`,
};

// Yetkilendirilmis indirme (Authorization header ile) — dosyayi blob olarak indirir
export async function authedDownload(url: string, filename: string) {
  const token = tokenStore.get();
  const res = await fetch(url, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
  if (!res.ok) throw new ApiError(res.status, tr("err.download"));
  const blob = await res.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}

// ---- Sunum yardımcıları ----

/**
 * Etiket haritaları — metin DEĞİL, i18n ANAHTARI tutar.
 *
 * ## B41: neden değişti
 *
 * Önceki sürüm burada sabit Türkçe metin tutuyordu ve arayüz onları olduğu
 * gibi basıyordu. Ölçüldü: İngilizce arayüzde çağrı listesinde **"Kuyrukta"**,
 * arama sayfasında **"Sesli"** görünüyordu. Kokpit o an temiz görünüyordu
 * ama yalnızca işlenmiş çağrı olmadığı için — kategori etiketleri de aynı
 * şekilde sızacaktı.
 *
 * Roller için aynı sorun daha önce fark edilip `ROLE_LABEL_KEYS` ile
 * çözülmüş, kalan beş harita öyle bırakılmıştı: kural biliniyordu, yarısı
 * uygulanmıştı.
 *
 * ## Kullanım
 *
 * `t(CATEGORY_LABEL_KEYS[k] ?? "") || k`
 *
 * Sondaki `|| k` önemli: sözlükte olmayan bir anahtar gelirse boş hücre
 * değil ham değer görünsün. Boş hücre, veri yok mu çeviri yok mu ayırt
 * ettirmez.
 */
export const CATEGORY_LABEL_KEYS: Record<string, string> = {
  fatura: "cat.fatura", iptal: "cat.iptal", ariza: "cat.ariza",
  sikayet: "cat.sikayet", bilgi: "cat.bilgi", diger: "cat.diger",
};

// `pending` etiketi "Kuyrukta" idi ve yanıltıyordu: işleme DURAKLATILMIŞKEN
// çağrı bir kuyrukta değil, kullanıcının başlatmasını bekliyor. `/admin/
// processing` aynı anda `queued_now: 0` döndürüyordu.
export const STATUS_LABEL_KEYS: Record<string, string> = {
  pending: "callstatus.pending", transcribing: "callstatus.transcribing",
  scoring: "callstatus.scoring", done: "callstatus.done",
  failed: "callstatus.failed",
};

/** i18n anahtarlari — cevrilmis rol adi icin t(ROLE_LABEL_KEYS[role]) */
export const ROLE_LABEL_KEYS: Record<string, string> = {
  admin: "role.admin", supervisor: "role.supervisor",
  quality: "role.quality", agent: "role.agent",
};

export const CHANNEL_LABEL_KEYS: Record<string, string> = {
  voice: "chan.voice", chat: "chan.chat",
};

/** Duygu: metin i18n'den, renk sınıfı sabit (sınıf çeviriye tabi değil). */
export const SENTIMENT_LABEL_KEYS: Record<string, { key: string; cls: string }> = {
  olumlu: { key: "sent.olumlu", cls: "badge-good" },
  notr: { key: "sent.notr", cls: "badge-neutral" },
  olumsuz: { key: "sent.olumsuz", cls: "badge-critical" },
};

export const VIOLATION_LABEL_KEYS: Record<string, string> = {
  hakaret: "viol.hakaret", kucumseme: "viol.kucumseme", rakip: "viol.rakip",
  yasak_vaat: "viol.yasak_vaat", mevzuat: "viol.mevzuat",
  eskalasyon: "viol.eskalasyon", kvkk: "viol.kvkk", pci: "viol.pci",
  kayit_ifsa: "viol.kayit_ifsa", hitap: "viol.hitap",
};

export function fmtTs(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

export function fmtDuration(sec: number | null): string {
  return sec == null ? "—" : fmtTs(sec);
}

export function fmtDate(iso: string): string {
  return new Date(iso).toLocaleString("tr-TR", {
    day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

export type ScoreStatus = "good" | "warning" | "critical";

export function scoreStatus(score: number): ScoreStatus {
  if (score >= 80) return "good";
  if (score >= 60) return "warning";
  return "critical";
}

export function scoreStatus10(score: number): ScoreStatus {
  if (score >= 8) return "good";
  if (score >= 6) return "warning";
  return "critical";
}
