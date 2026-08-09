from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .models import CATEGORIES

# =============================================================
# LLM cikti semalari — LLM yaniti her zaman bunlara zorlanir
# =============================================================

def _fold_tr(value: str) -> str:
    # Buyuk noktali İ, Python'un lower()'inda "i" + U+0307 (birlesik nokta)
    # verir; bu da eslesmeleri kacirir. Once ASCII'ye indir, sonra kucult.
    value = value.replace("İ", "i").replace("I", "i").replace("ı", "i")
    return value.strip().lower().translate(str.maketrans("ıişğüöçâî", "iisguocai"))


class LLMRiskliAn(BaseModel):
    zaman: float = Field(description="Riskli anin saniye cinsinden zamani")
    aciklama: str
    onem: Literal["dusuk", "orta", "yuksek"] = "orta"

    @field_validator("onem", mode="before")
    @classmethod
    def _norm_onem(cls, v):
        if isinstance(v, str):
            v = _fold_tr(v)
            if v in ("dusuk", "orta", "yuksek"):
                return v
            if v in ("low", "medium", "high"):
                return {"low": "dusuk", "medium": "orta", "high": "yuksek"}[v]
        return "orta"

    @field_validator("zaman", mode="before")
    @classmethod
    def _norm_zaman(cls, v):
        try:
            return max(0.0, float(v))
        except (TypeError, ValueError):
            return 0.0


class LLMPuan(BaseModel):
    kriter_id: int
    puan: int = Field(ge=0, le=10)
    gerekce: str = ""
    kanit: str = ""
    kanit_zaman: float | None = None

    @field_validator("puan", mode="before")
    @classmethod
    def _clamp_puan(cls, v):
        try:
            return min(10, max(0, round(float(v))))
        except (TypeError, ValueError):
            raise ValueError("puan sayisal olmali")

    @field_validator("kanit_zaman", mode="before")
    @classmethod
    def _norm_kanit_zaman(cls, v):
        if v is None or v == "":
            return None
        try:
            return max(0.0, float(v))
        except (TypeError, ValueError):
            return None


SENTIMENTS = ["olumlu", "notr", "olumsuz"]

_SENTIMENT_ALIASES = {
    "pozitif": "olumlu",
    "positive": "olumlu",
    "negatif": "olumsuz",
    "negative": "olumsuz",
    "neutral": "notr",
    "noetr": "notr",
}


def _norm_sentiment(v) -> str:
    if isinstance(v, str):
        folded = _fold_tr(v)
        if folded in SENTIMENTS:
            return folded
        if folded in _SENTIMENT_ALIASES:
            return _SENTIMENT_ALIASES[folded]
    return "notr"


# 8 duygu — musterinin baskin duygusu (LLM analitik paketi)
EMOTIONS = [
    "ofke", "hayal_kirikligi", "endise", "memnuniyet",
    "notr", "saskinlik", "minnettarlik", "uzuntu",
]
_EMOTION_ALIASES = {
    "kizgin": "ofke", "kizginlik": "ofke", "sinir": "ofke", "anger": "ofke",
    "angry": "ofke", "hayalkirikligi": "hayal_kirikligi",
    "frustration": "hayal_kirikligi", "frustrated": "hayal_kirikligi",
    "kaygi": "endise", "kaygili": "endise", "anxiety": "endise", "worried": "endise",
    "endiseli": "endise", "mutlu": "memnuniyet", "memnun": "memnuniyet",
    "satisfaction": "memnuniyet", "happy": "memnuniyet", "notr": "notr",
    "neutral": "notr", "sasirmis": "saskinlik", "surprise": "saskinlik",
    "confused": "saskinlik", "tesekkur": "minnettarlik", "gratitude": "minnettarlik",
    "grateful": "minnettarlik", "uzgun": "uzuntu", "sadness": "uzuntu", "sad": "uzuntu",
}


def _norm_emotion(v) -> str:
    if isinstance(v, str):
        folded = _fold_tr(v).replace(" ", "_")
        if folded in EMOTIONS:
            return folded
        if folded in _EMOTION_ALIASES:
            return _EMOTION_ALIASES[folded]
    return "notr"


TRAJECTORIES = ["yukselen", "dusen", "sabit"]
_TRAJECTORY_ALIASES = {
    "artan": "yukselen", "iyilesen": "yukselen", "rising": "yukselen", "up": "yukselen",
    "kotulesen": "dusen", "azalan": "dusen", "falling": "dusen", "down": "dusen",
    "degismeyen": "sabit", "stable": "sabit", "flat": "sabit",
}


def _norm_trajectory(v) -> str:
    if isinstance(v, str):
        folded = _fold_tr(v)
        if folded in TRAJECTORIES:
            return folded
        if folded in _TRAJECTORY_ALIASES:
            return _TRAJECTORY_ALIASES[folded]
    return "sabit"


RISK_LEVELS = ["dusuk", "orta", "yuksek"]
_RISK_ALIASES = {"low": "dusuk", "medium": "orta", "high": "yuksek", "yok": "dusuk"}


def _norm_risk(v) -> str:
    if isinstance(v, str):
        folded = _fold_tr(v)
        if folded in RISK_LEVELS:
            return folded
        if folded in _RISK_ALIASES:
            return _RISK_ALIASES[folded]
    return "dusuk"


class LLMKanit(BaseModel):
    """Bir kriter kararinin dayanagi. Alinti BIREBIR transkriptten olmali —
    Katman C bunu normalize transkriptte arar, bulunamazsa kanit REDDEDILIR."""

    speaker: Literal["agent", "customer", "temsilci", "musteri"] = "temsilci"
    start_sec: float = 0.0
    quote: str = ""

    @field_validator("speaker", mode="before")
    @classmethod
    def _norm_speaker(cls, v):
        m = {"agent": "temsilci", "customer": "musteri"}
        if isinstance(v, str):
            return m.get(_fold_tr(v), _fold_tr(v) if _fold_tr(v) in ("temsilci", "musteri") else "temsilci")
        return "temsilci"

    @field_validator("start_sec", mode="before")
    @classmethod
    def _norm_start(cls, v):
        try:
            return max(0.0, float(v))
        except (TypeError, ValueError):
            return 0.0


class LLMKriterKarari(BaseModel):
    """KATMAN B ciktisi — kriter basina KANIT ZORUNLU karar.

    Altin kural: kanit yoksa CEZA YOK. `kanitlar` bos veya alinti dogrulanamazsa
    karar `insufficient_evidence` olur ve kriter puani ORTALAMAYA KATILMAZ;
    cagri insan kuyruguna duser. Bu kural B1, B2, B5'i kokten cozer.
    """

    # LLM'e kriterler HARF kimlikle sunulur (sayisal sira bias yaratiyor —
    # arXiv 2506.22316). kriter_id sunucu tarafinda harf haritasindan doldurulur.
    kriter_harf: str = ""
    kriter_id: int | None = None
    karar: Literal["met", "partially_met", "not_met", "not_applicable",
                   "insufficient_evidence"] = "insufficient_evidence"
    puan: int | None = Field(default=None, ge=0, le=10)
    kanitlar: list[LLMKanit] = []
    gerekce: str = ""
    guven: float = Field(default=0.5, ge=0.0, le=1.0)

    @field_validator("karar", mode="before")
    @classmethod
    def _norm_karar(cls, v):
        if not isinstance(v, str):
            return "insufficient_evidence"
        f = _fold_tr(v).replace(" ", "_").replace("-", "_")
        aliases = {
            "karsilandi": "met", "kismen_karsilandi": "partially_met",
            "karsilanmadi": "not_met", "uygulanamaz": "not_applicable",
            "yetersiz_kanit": "insufficient_evidence",
        }
        f = aliases.get(f, f)
        valid = {"met", "partially_met", "not_met", "not_applicable", "insufficient_evidence"}
        return f if f in valid else "insufficient_evidence"

    @field_validator("puan", mode="before")
    @classmethod
    def _clamp(cls, v):
        if v is None or v == "":
            return None
        try:
            return min(10, max(0, round(float(v))))
        except (TypeError, ValueError):
            return None

    @field_validator("guven", mode="before")
    @classmethod
    def _norm_guven(cls, v):
        try:
            return min(1.0, max(0.0, float(v)))
        except (TypeError, ValueError):
            return 0.5


class LLMKriterGrubu(BaseModel):
    """Bir kriter grubunun (3-4 kriter) degerlendirme ciktisi.

    Tek dev prompt'ta 12 kriter degerlendirmek yasak (prompt "asla yapma" #3);
    kriterler gruplara bolunur, her grup AYRI LLM cagrisidir.
    """

    kararlar: list[LLMKriterKarari] = []


class LLMCagriAnalizi(BaseModel):
    """Puanlamadan AYRI, cagri geneli analiz (ozet, duygu, koclu, niyet).

    Kriter puanlariyla ayni cagriya sikistirilmaz — modelin dikkati bolunuyordu.
    """

    kategori: str = "diger"
    ozet: str = ""
    musteri_duygu_baslangic: str = "notr"
    musteri_duygu_bitis: str = "notr"
    gelisim_onerisi: str = ""
    tahmini_csat: float = 3.0
    baskin_duygu: str = "notr"
    duygu_yorungesi: str = "sabit"
    sonraki_aksiyon: str = ""
    churn_riski: str = "dusuk"
    musteri_efor: float = 3.0
    niyet_etiketleri: list[str] = []
    riskli_anlar: list[LLMRiskliAn] = []

    @field_validator("kategori", mode="before")
    @classmethod
    def _norm_kategori(cls, v):
        if isinstance(v, str):
            folded = _fold_tr(v)
            if folded in CATEGORIES:
                return folded
        return "diger"

    @field_validator("musteri_duygu_baslangic", "musteri_duygu_bitis", mode="before")
    @classmethod
    def _norm_duygu2(cls, v):
        if isinstance(v, str):
            f = _fold_tr(v)
            if f in ("olumlu", "notr", "olumsuz"):
                return f
            return {"positive": "olumlu", "neutral": "notr", "negative": "olumsuz"}.get(f, "notr")
        return "notr"

    @field_validator("churn_riski", mode="before")
    @classmethod
    def _norm_churn2(cls, v):
        if isinstance(v, str):
            f = _fold_tr(v)
            if f in ("dusuk", "orta", "yuksek"):
                return f
        return "dusuk"

    @field_validator("duygu_yorungesi", mode="before")
    @classmethod
    def _norm_yorunge2(cls, v):
        if isinstance(v, str):
            f = _fold_tr(v)
            if f in ("yukselen", "dusen", "sabit"):
                return f
        return "sabit"

    @field_validator("tahmini_csat", "musteri_efor", mode="before")
    @classmethod
    def _norm_1_5(cls, v):
        try:
            return min(5.0, max(1.0, float(v)))
        except (TypeError, ValueError):
            return 3.0


class LLMDegerlendirme(BaseModel):
    """Tek atis (veya reduce asamasi) puanlama ciktisi."""

    kategori: str = "diger"
    ozet: str = ""
    musteri_duygu_baslangic: str = "notr"
    musteri_duygu_bitis: str = "notr"
    gelisim_onerisi: str = ""
    tahmini_csat: float = 3.0  # LLM'in musteri memnuniyeti tahmini (1-5)
    puanlar: list[LLMPuan]
    riskli_anlar: list[LLMRiskliAn] = []
    # --- LLM analitik paketi (Dalga 1) ---
    baskin_duygu: str = "notr"                 # 8 duygudan biri
    duygu_yorungesi: str = "sabit"             # yukselen|dusen|sabit
    sonraki_aksiyon: str = ""                   # uretken oneri
    churn_riski: str = "dusuk"                  # dusuk|orta|yuksek
    musteri_efor: float = 3.0                   # CES 1-5 (1 kolay, 5 zor)
    niyet_etiketleri: list[str] = []            # ince niyet/konu etiketleri

    @field_validator("kategori", mode="before")
    @classmethod
    def _norm_kategori(cls, v):
        if isinstance(v, str):
            folded = _fold_tr(v)
            if folded in CATEGORIES:
                return folded
        return "diger"

    @field_validator("musteri_duygu_baslangic", "musteri_duygu_bitis", mode="before")
    @classmethod
    def _norm_duygu(cls, v):
        return _norm_sentiment(v)

    @field_validator("baskin_duygu", mode="before")
    @classmethod
    def _norm_baskin_duygu(cls, v):
        return _norm_emotion(v)

    @field_validator("duygu_yorungesi", mode="before")
    @classmethod
    def _norm_yorunge(cls, v):
        return _norm_trajectory(v)

    @field_validator("churn_riski", mode="before")
    @classmethod
    def _norm_churn(cls, v):
        return _norm_risk(v)

    @field_validator("musteri_efor", mode="before")
    @classmethod
    def _norm_efor(cls, v):
        try:
            return min(5.0, max(1.0, float(v)))
        except (TypeError, ValueError):
            return 3.0

    @field_validator("niyet_etiketleri", mode="before")
    @classmethod
    def _norm_etiketler(cls, v):
        if not isinstance(v, list):
            return []
        out = []
        for t in v:
            if isinstance(t, str) and t.strip():
                # normalize: kucuk harf, bosluk -> tire, en fazla 6 etiket
                tag = _fold_tr(t).replace(" ", "-")[:40]
                if tag and tag not in out:
                    out.append(tag)
        return out[:6]

    @field_validator("tahmini_csat", mode="before")
    @classmethod
    def _norm_csat(cls, v):
        try:
            return min(5.0, max(1.0, float(v)))
        except (TypeError, ValueError):
            return 3.0


class LLMGozlem(BaseModel):
    """Map asamasinda chunk basina kriter gozlemi."""

    kriter_id: int
    gozlem: str = ""
    kanit: str = ""
    kanit_zaman: float | None = None

    @field_validator("kanit_zaman", mode="before")
    @classmethod
    def _norm_ts(cls, v):
        if v is None or v == "":
            return None
        try:
            return max(0.0, float(v))
        except (TypeError, ValueError):
            return None


class LLMChunkAnaliz(BaseModel):
    gozlemler: list[LLMGozlem] = []
    riskli_anlar: list[LLMRiskliAn] = []


class LLMKonuAnalizi(BaseModel):
    """Kume icin tema adi + kok neden + aksiyon (konu kesfi)."""

    baslik: str = "Adsiz tema"
    kok_neden: str = ""
    aksiyon: str = ""


# =============================================================
# Chat kanali ingest
# =============================================================


class ChatMessageIn(BaseModel):
    speaker: str  # musteri | temsilci
    ts_sec: float = 0.0  # gorusme baslangicindan saniye
    text: str


class ChatIngest(BaseModel):
    filename: str = "chat.json"
    agent_name: str | None = None
    campaign_id: int | None = None
    messages: list[ChatMessageIn] = Field(min_length=1)


# =============================================================
# API request/response semalari
# =============================================================


class AgentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str


class SegmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    idx: int
    speaker: str
    start_sec: float
    end_sec: float
    text: str


class ScoreOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    criterion_id: int | None
    criterion_name: str
    criterion_group: str
    weight: float
    score: int
    rationale: str
    evidence: str
    evidence_ts: float | None
    override_score: int | None
    override_reason: str | None
    effective_score: int


class CampaignOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    channel: str
    description: str


class CallListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    filename: str
    channel: str
    status: str
    duration_sec: float | None
    category: str | None
    total_score: float | None
    zeroed: bool
    is_crisis: bool
    predicted_csat: float | None
    customer_ref: str | None
    is_repeat: bool
    repeat_of_id: int | None
    # LLM analitik paketi (listede filtre/rozet icin kompakt alanlar)
    emotion: str | None = None
    churn_risk: str | None = None
    emotion_mismatch: bool = False
    intent_tags: list = []
    is_golden: bool = False
    tags: list = []
    created_at: datetime
    processed_at: datetime | None
    agent: AgentOut | None
    campaign: CampaignOut | None


class CallList(BaseModel):
    items: list[CallListItem]
    total: int
    page: int
    page_size: int


class ViolationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    kind: str
    category: str
    severity: str
    term: str
    speaker: str
    evidence: str
    ts_sec: float | None


class CallDetail(CallListItem):
    summary: str | None
    risky_moments: list
    metrics: dict | None
    sentiment_start: str | None
    sentiment_end: str | None
    sentiment_trajectory: str | None = None
    next_action: str | None = None
    customer_effort: float | None = None
    coaching: str | None
    error: str | None
    segments: list[SegmentOut]
    scores: list[ScoreOut]
    violations: list[ViolationOut]
    # PII maskelendi mi? (True ise transkript/ozet KVKK maskesiyle donduruldu;
    # admin/kalite `?reveal=true` ile ham veriyi gorebilir)
    pii_masked: bool = False


class CriterionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: str
    group: str
    weight: float
    min_score: int
    max_score: int
    is_critical: bool
    critical_threshold: int
    channel_scope: str
    campaign_id: int | None
    is_active: bool


class CriterionCreate(BaseModel):
    name: str = Field(min_length=2, max_length=256)
    description: str = Field(min_length=2)
    group: str = "Iletisim Kalitesi"
    weight: float = Field(default=1.0, ge=0.1, le=10)
    min_score: int = Field(default=0, ge=0, le=10)
    max_score: int = Field(default=10, ge=0, le=10)
    is_critical: bool = False
    critical_threshold: int = Field(default=3, ge=0, le=10)
    channel_scope: str = "all"
    campaign_id: int | None = None
    is_active: bool = True


class CriterionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=256)
    description: str | None = Field(default=None, min_length=2)
    group: str | None = None
    weight: float | None = Field(default=None, ge=0.1, le=10)
    min_score: int | None = Field(default=None, ge=0, le=10)
    max_score: int | None = Field(default=None, ge=0, le=10)
    is_critical: bool | None = None
    critical_threshold: int | None = Field(default=None, ge=0, le=10)
    channel_scope: str | None = None
    campaign_id: int | None = None
    is_active: bool | None = None


class AgentSummary(BaseModel):
    id: int
    name: str
    call_count: int
    avg_score: float | None
    last_call_at: datetime | None


class TrendPoint(BaseModel):
    date: str
    avg_score: float
    call_count: int


class CriterionAvg(BaseModel):
    criterion_name: str
    avg_score: float
    count: int


class AgentDetail(BaseModel):
    id: int
    name: str
    call_count: int
    avg_score: float | None
    trend: list[TrendPoint]
    criteria: list[CriterionAvg]
    recent_calls: list[CallListItem]


class Overview(BaseModel):
    total_calls: int
    done_calls: int
    processing_calls: int
    failed_calls: int
    avg_score: float | None
    low_score_calls: int  # < 60 puan
    zeroed_calls: int
    crisis_calls: int
    avg_csat: float | None
    category_dist: dict[str, int]
    trend: list[TrendPoint]


# =============================================================
# Auth
# =============================================================


class LoginRequest(BaseModel):
    email: str
    password: str
    tenant_slug: str = "demo"


class DemoLoginRequest(BaseModel):
    role: str  # admin | supervisor | quality | agent
    tenant_slug: str = "demo"


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class MeOut(BaseModel):
    id: int
    email: str
    name: str
    role: str
    tenant_id: int
    tenant_name: str
    team_id: int | None
    agent_id: int | None


# =============================================================
# Organizasyon / admin
# =============================================================


class TeamOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    supervisor_id: int | None


class CampaignCreate(BaseModel):
    name: str = Field(min_length=2, max_length=128)
    channel: str = "voice"
    description: str = ""


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    name: str
    role: str
    team_id: int | None
    agent_id: int | None
    is_active: bool
    password_set: bool = True  # False => davet bekliyor (parola belirlenmedi)


class UserCreate(BaseModel):
    email: str
    name: str = Field(min_length=2, max_length=128)
    password: str = Field(min_length=6, max_length=128)
    role: str
    team_id: int | None = None
    agent_id: int | None = None


# =============================================================
# Kurumsal onboarding: kurum olusturma, davet, parola akislari
# =============================================================
class RegisterOrgRequest(BaseModel):
    org_name: str = Field(min_length=2, max_length=200)
    admin_name: str = Field(min_length=2, max_length=128)
    admin_email: str
    password: str = Field(min_length=8, max_length=128)


class AuthConfigOut(BaseModel):
    sso_enabled: bool
    demo_mode: bool
    needs_setup: bool           # gercek (demo disi) kurum yok -> kurulum ekrani goster
    org_slug: str | None = None  # girisin varsayilan hedefi (on-prem tek kurum)
    org_name: str | None = None


class InviteUserRequest(BaseModel):
    email: str
    name: str = Field(min_length=2, max_length=128)
    role: str
    team_id: int | None = None
    agent_id: int | None = None


class InviteResultOut(BaseModel):
    user: UserOut
    invite_url: str
    emailed: bool                # SMTP ile gonderildi mi (false ise link'i admin paylasir)


class InviteInfoOut(BaseModel):
    valid: bool
    email: str = ""
    name: str = ""
    org_name: str = ""


class AcceptInviteRequest(BaseModel):
    token: str
    password: str = Field(min_length=8, max_length=128)


class ForgotPasswordRequest(BaseModel):
    email: str
    org_slug: str | None = None


class ResetPasswordRequest(BaseModel):
    token: str
    password: str = Field(min_length=8, max_length=128)


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(min_length=8, max_length=128)


class ResetResultOut(BaseModel):
    message: str
    # SMTP yoksa admin panelinden tetiklenen sifirlamada link doner; self-servis
    # "parolami unuttum"da guvenlik geregi link DONMEZ (bilgi sizmasin).
    reset_url: str | None = None


class TeamCreate(BaseModel):
    name: str = Field(min_length=2, max_length=128)
    supervisor_id: int | None = None


class AgentAdminCreate(BaseModel):
    name: str = Field(min_length=2, max_length=128)
    team_id: int | None = None


class AgentAdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    team_id: int | None


# --- Kurum ayarlari / sistem bilgisi / onboarding durumu ---
class TenantSettingsOut(BaseModel):
    org_name: str
    retention_days: int
    auto_process: bool           # yeni cagrilar otomatik islensin mi
    notify_events: list[str]     # zeroing, crisis, banned_word, low_score, score_drop
    brand_name: str | None = None
    brand_color: str | None = None


class TenantSettingsUpdate(BaseModel):
    retention_days: int | None = Field(default=None, ge=1, le=3650)
    auto_process: bool | None = None
    notify_events: list[str] | None = None


class SystemInfoOut(BaseModel):
    """Salt-okunur sistem yapilandirmasi (.env kaynakli) — panelde gosterilir."""
    llm_provider: str
    llm_model: str
    whisper_model: str
    whisper_device: str
    vision_enabled: bool
    rag_enabled: bool
    sso_enabled: bool
    demo_mode: bool
    pii_masking: bool
    smtp_configured: bool


class OnboardingStatusOut(BaseModel):
    brand_set: bool
    has_teams: bool
    has_agents: bool
    has_users: bool          # admin disinda kullanici davet edilmis mi
    has_rubric: bool
    has_calls: bool
    has_knowledge: bool
    complete: bool


# --- Dalga 1: etiket/altin cagri · rubrik playground · AI kocluk · yukselen konu ---
class TagsUpdate(BaseModel):
    tags: list[str] = Field(default_factory=list)


class SimulateCriterion(BaseModel):
    criterion_id: int
    weight: float = 1.0
    is_critical: bool = False
    critical_threshold: int = 3
    is_active: bool = True


class SimulateRequest(BaseModel):
    criteria: list[SimulateCriterion]
    days: int = Field(default=30, ge=1, le=365)
    limit: int = Field(default=200, ge=1, le=1000)


class SimulateChange(BaseModel):
    id: int
    filename: str
    before: float
    after: float
    delta: float


class SimulateResult(BaseModel):
    call_count: int
    avg_before: float
    avg_after: float
    zeroed_before: int
    zeroed_after: int
    biggest_changes: list[SimulateChange]


class WeakCriterion(BaseModel):
    name: str
    avg: float


class CoachingPlanOut(BaseModel):
    agent_id: int
    agent_name: str
    call_count: int
    weak_criteria: list[WeakCriterion]
    focus: list[str]
    plan: str


class EmergingTopic(BaseModel):
    label: str
    kind: str          # kategori | niyet
    now_count: int
    prev_count: int
    change_pct: float


# =============================================================
# Dalga 2: korelasyon, yonetici ozeti, hedefler, AI kullanim
# =============================================================


class CorrelationInsight(BaseModel):
    factor: str
    label: str
    # B8: n<30 ise katsayi GOSTERILMEZ -> None. Arayuz sayi yerine `insight`
    # metnini gosterir ("egilim gozlemi, henuz anlamli degil").
    corr: float | None = None
    n: int
    direction: str        # positive | negative | unknown
    strength: str         # zayif | orta | guclu | belirsiz
    insight: str
    significant: bool = True


class ExecSummary(BaseModel):
    period_days: int
    call_count: int
    avg_score: float | None
    headline: str
    wins: list[str]
    risks: list[str]
    actions: list[str]
    generated_at: datetime


class TargetIn(BaseModel):
    scope: str = "tenant"     # tenant | team | agent
    scope_id: int | None = None
    metric: str = "quality"   # quality | csat | fcr | zeroed_rate
    target_value: float


class TargetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    scope: str
    scope_id: int | None
    metric: str
    target_value: float


class TargetProgress(BaseModel):
    id: int
    scope: str
    scope_id: int | None
    scope_name: str
    metric: str
    target_value: float
    actual: float | None
    met: bool
    call_count: int


class AiUsageRow(BaseModel):
    kind: str
    provider: str
    calls: int
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    avg_latency_ms: int


class AiUsageSummary(BaseModel):
    period_days: int
    total_calls: int
    total_tokens: int
    total_cost_usd: float
    ok_rate: float
    by_kind: list[AiUsageRow]
    by_provider: list[AiUsageRow]


# --- Dalga 3: churn/retention, itiraz analitigi ---


class ChurnCall(BaseModel):
    id: int
    filename: str
    agent_name: str | None
    category: str | None
    churn_risk: str
    total_score: float | None
    predicted_csat: float | None
    created_at: datetime


class ChurnSummary(BaseModel):
    period_days: int
    high: int
    medium: int
    low: int
    total_scored: int
    high_rate: float          # yuksek riskli oran (%)
    retention_list: list[ChurnCall]


class AppealAnalytics(BaseModel):
    period_days: int
    total: int
    open: int
    accepted: int
    rejected: int
    overturn_rate: float      # kabul / (kabul+ret) — insan AI'yi ne siklikta duzeltiyor
    avg_resolution_days: float | None


# --- Dalga 5: rubrik versiyon, bulk aksiyon, benzer cagrilar ---


class RubricVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    note: str
    criteria_count: int
    created_by: int | None
    created_at: datetime


class RubricVersionCreate(BaseModel):
    note: str = ""


class BulkCallAction(BaseModel):
    ids: list[int]
    action: str               # golden_on | golden_off | tag_add | tag_remove | delete
    tag: str | None = None


class BulkResult(BaseModel):
    affected: int
    action: str


class SimilarCall(BaseModel):
    id: int
    filename: str
    agent_name: str | None
    category: str | None
    total_score: float | None
    similarity: float         # 0..1 (ortak etiket/kategori orani)
    shared_tags: list[str]


# --- Dalga 6: bildirim merkezi ---


class NotificationItem(BaseModel):
    kind: str                 # alert | review | coaching | appeal
    ref_id: int               # kaynak kaydin id'si (alert/review/task/appeal)
    title: str
    message: str
    link: str                 # frontend rotasi
    severity: str             # dusuk | orta | yuksek
    created_at: datetime


class NotificationFeed(BaseModel):
    unread_count: int
    items: list[NotificationItem]


# =============================================================
# Yasakli kelime
# =============================================================


class BannedWordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    term: str
    category: str
    severity: str
    match_type: str
    is_active: bool


class BannedWordCreate(BaseModel):
    term: str = Field(min_length=1, max_length=128)
    category: str = "hakaret"
    severity: str = "orta"
    match_type: str = "fuzzy"
    is_active: bool = True


class BannedWordUpdate(BaseModel):
    term: str | None = Field(default=None, min_length=1, max_length=128)
    category: str | None = None
    severity: str | None = None
    match_type: str | None = None
    is_active: bool | None = None


# =============================================================
# Alarm / itiraz / kocluk / override
# =============================================================


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    call_id: int | None
    type: str
    severity: str
    message: str
    is_read: bool
    created_at: datetime


class AppealCreate(BaseModel):
    call_id: int
    reason: str = Field(min_length=3)


class AppealResolve(BaseModel):
    decision: str  # accepted | rejected
    resolution_note: str = ""


class AppealOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    call_id: int
    created_by: int
    reason: str
    status: str
    resolution_note: str | None
    created_at: datetime
    resolved_at: datetime | None


class CoachingTaskCreate(BaseModel):
    call_id: int
    assignee_agent_id: int
    note: str = ""


class CoachingTaskComplete(BaseModel):
    agent_comment: str = ""


class CoachingTaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    call_id: int
    assignee_agent_id: int
    note: str
    status: str
    agent_comment: str | None
    created_at: datetime
    completed_at: datetime | None


class ScoreOverride(BaseModel):
    override_score: int = Field(ge=0, le=10)
    override_reason: str = Field(min_length=3)


# =============================================================
# Kalibrasyon oturumu + manuel degerlendirme (inter-rater reliability)
# =============================================================


class EvalScoreIn(BaseModel):
    criterion_id: int
    score: int = Field(ge=0, le=10)
    note: str = ""


class ManualEvaluationCreate(BaseModel):
    call_id: int
    session_id: int | None = None  # kalibrasyon oturumu icindeyse
    scores: list[EvalScoreIn] = Field(min_length=1)
    notes: str = ""


class ManualEvaluationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    call_id: int
    session_id: int | None
    evaluator_id: int
    scores: list
    total_score: float
    notes: str
    created_at: datetime


class CalibrationSessionCreate(BaseModel):
    call_id: int
    title: str = ""
    scheduled_at: datetime | None = None


class CalibrationSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    call_id: int
    title: str
    status: str
    created_by: int
    scheduled_at: datetime | None = None
    created_at: datetime
    closed_at: datetime | None
    evaluation_count: int = 0
    my_evaluation_id: int | None = None  # bu kullanici puanladi mi?


class CalibrationCriterionRow(BaseModel):
    criterion_id: int
    criterion_name: str
    scores: list[dict]
    min: int
    max: int
    spread: int
    avg: float
    agreed: bool
    ai_score: int | None


class CalibrationReport(BaseModel):
    session_id: int
    call_id: int
    status: str
    agreement_pct: float | None
    evaluator_count: int
    meets_target: bool | None
    target: float
    most_divergent: str | None
    criteria: list[CalibrationCriterionRow]
    ai_total: float | None
    human_avg_total: float | None


# =============================================================
# Bilgi bankasi (RAG)
# =============================================================


class KnowledgeDocOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    source_filename: str
    chunk_count: int
    created_at: datetime


class KnowledgeSearchHit(BaseModel):
    doc_id: int
    doc_title: str
    idx: int
    content: str
    similarity: float


class BulkRescoreRequest(BaseModel):
    call_ids: list[int] | None = None  # bos => tenant'in tum tamamlanmis cagrilari


# =============================================================
# Isleme kontrolu (agir STT/LLM isini elle baslatma)
# =============================================================


# =============================================================
# Transkript arama (speech analytics: "su ifade gecen tum cagrilar")
# =============================================================


class TranscriptHit(BaseModel):
    call_id: int
    filename: str
    channel: str
    agent_name: str | None
    category: str | None
    total_score: float | None
    created_at: datetime
    speaker: str
    ts_sec: float
    text: str          # eslesen cumle/mesaj (tam)
    match_count: int   # bu cagrida toplam kac eslesme var


class TranscriptSearchResult(BaseModel):
    query: str
    total_hits: int      # toplam eslesen cumle
    total_calls: int     # kac farkli cagrida gectigi
    items: list[TranscriptHit]


class ProcessingStatus(BaseModel):
    paused: bool
    pending_calls: int      # kuyruga alinmayi bekleyen (pending)
    failed_calls: int       # hata almis, yeniden denenebilir
    running_calls: int      # su an transcribing/scoring
    done_calls: int
    queued_now: int = 0     # "baslat" sonucu kuyruga atilan sayisi


# =============================================================
# Gamification / kokpit
# =============================================================


class BadgeOut(BaseModel):
    code: str
    name: str
    icon: str
    description: str
    period: str


class LeaderboardRow(BaseModel):
    agent_id: int
    agent_name: str
    team_name: str | None
    avg_score: float
    call_count: int
    crisis_handled: int
    points: float
    # B7: az orneklemli temsilci siralamada yildizli gosterilir ve ust siralara
    # cikamaz. 5 cagrida 95 tutan, 200 cagrida 91 tutandan iyi DEGILDIR.
    ranked: bool = True
    sample_warning: str = ""


class AgentScorecard(BaseModel):
    id: int
    name: str
    team_name: str | None
    call_count: int
    avg_score: float | None
    avg_csat: float | None
    zeroed_count: int
    crisis_count: int
    trend: list[TrendPoint]
    criteria: list[CriterionAvg]
    badges: list[BadgeOut]
    recent_calls: list[CallListItem]
    weekly_coaching: str


class CalibrationRow(BaseModel):
    criterion_name: str
    ai_avg: float
    human_avg: float
    delta: float
    override_count: int


class SupervisorCockpit(BaseModel):
    team_id: int | None
    avg_score: float | None
    avg_csat: float | None
    crisis_calls: int
    zeroed_calls: int
    avg_handle_sec: float | None
    fcr_estimate: float | None
    # True: musteri referansi + tekrar arama ile hesaplanan GERCEK FCR
    # False: kriz yok + puan>=70 varsayimiyla TAHMINI FCR
    fcr_is_real: bool = False
    repeat_calls: int = 0  # ayni musterinin 7 gun icinde tekrar aramasi
    unread_alerts: int
    violation_dist: dict[str, int]
    agents: list[LeaderboardRow]


# =============================================================
# QA ornekleme & inceleme atamasi (Dalga 2b)
# =============================================================
class ReviewAssignmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    call_id: int
    reviewer_id: int
    reason: str
    status: str
    created_at: datetime
    completed_at: datetime | None


class SampleRequest(BaseModel):
    reviewer_id: int
    reason: Literal["random", "low_confidence", "critical", "manual"] = "random"
    count: int = Field(default=5, ge=1, le=100)


class ReviewStatsOut(BaseModel):
    counts: dict[str, int]
    total: int
    completion_rate: float


# =============================================================
# Kocluk etkinlik dongusu (Dalga 2c)
# =============================================================
class CoachingEffect(BaseModel):
    task_id: int
    agent_id: int
    agent_name: str
    ref_date: str
    before_avg: float
    after_avg: float
    delta: float
    before_n: int
    after_n: int
    improved: bool


class CoachingEffectivenessOut(BaseModel):
    # B13: "olculemedi" ile "sonuc kotu" ayri seylerdir. Olculemiyorsa sayi
    # yerine None doner ve arayuz `aciklama`yi gosterir.
    olculebilir: bool = False
    aciklama: str = ""
    measurable_count: int
    total_completed: int
    improved_count: int | None = None
    improved_rate: float | None = None
    avg_delta: float | None = None
    window_days: int
    min_calls: int = 3
    effects: list[CoachingEffect]


# =============================================================
# Self-servis + gamification (Dalga 3c + 3d)
# =============================================================
class SelfAssessmentCreate(BaseModel):
    call_id: int
    self_score: float = Field(ge=0, le=100)
    note: str | None = None


class SelfAssessmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    call_id: int
    agent_id: int
    self_score: float
    note: str | None
    created_at: datetime


class ChallengeOut(BaseModel):
    id: int
    title: str
    description: str
    metric: str
    target: int
    progress: int
    completed: bool
    reward_points: int
    ends_at: str | None


class GamificationOut(BaseModel):
    points: int
    streak: int
    challenges: list[ChallengeOut]


class ChallengeCreate(BaseModel):
    title: str = Field(min_length=2, max_length=128)
    description: str = ""
    metric: Literal["score_above", "call_count", "avg_score", "zero_violations"] = "score_above"
    threshold: float = 85.0
    target: int = Field(default=10, ge=1)
    reward_points: int = Field(default=100, ge=0)
    team_id: int | None = None
    ends_at: datetime | None = None


# =============================================================
# Uyum paketleri (Dalga 4a)
# =============================================================
class ComplianceRuleOut(BaseModel):
    key: str
    description: str
    severity: str
    kind: str


class CompliancePackOut(BaseModel):
    key: str
    name: str
    description: str
    rules: list[ComplianceRuleOut]


# =============================================================
# Vision + Agent Assist (Dalga 5 + 6)
# =============================================================
class VisionResultOut(BaseModel):
    aciklama: str
    belge_turu: str
    kvkk_riski: str
    hassas_veri: list[str]
    ozet_not: str


class AssistRequest(BaseModel):
    partial_text: str = Field(min_length=1, max_length=20000)
    packs: list[str] | None = None


class AssistSuggestion(BaseModel):
    kind: str
    severity: str
    text: str
    detail: str = ""


# =============================================================
# Kurumsal: denetim gunlugu, guvenlik durusu, AI rubrik uretici,
# ROI, beyaz etiket (Dalga 13 — satilabilir MVP katmani)
# =============================================================
class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int | None
    user_name: str | None = None
    action: str
    entity_type: str
    entity_id: int | None
    detail: dict | None
    ip: str
    created_at: datetime


class AuditLogPage(BaseModel):
    items: list[AuditLogOut]
    total: int
    page: int
    page_size: int


class SecurityPosture(BaseModel):
    """Satis/uyum icin 'guvenlik durusu' ozeti — landing/güvenlik sayfasinda gosterilir."""
    deployment: str            # "on-premise" | "cloud"
    llm_provider: str          # ollama (yerel) | gemini (harici)
    data_leaves_premises: bool  # yerel LLM ise False
    pii_masking_enabled: bool
    audit_log_enabled: bool
    sso_enabled: bool
    rbac_roles: list[str]
    retention_days: int
    encryption_at_rest: bool
    multi_tenant_isolation: bool
    kvkk_pack_active: bool
    audit_events_30d: int


class ScorecardBuildRequest(BaseModel):
    """Dogal dil aciklamasindan rubrik uretimi (no-code puan karti)."""
    prompt: str = Field(min_length=10, max_length=4000)
    channel: Literal["voice", "chat", "all"] = "all"
    max_criteria: int = Field(default=8, ge=3, le=15)


class DraftCriterion(BaseModel):
    name: str
    description: str
    group: str
    weight: float
    is_critical: bool = False
    critical_threshold: int = 3
    channel_scope: str = "all"


class ScorecardDraft(BaseModel):
    criteria: list[DraftCriterion]
    note: str = ""


class ScorecardSaveRequest(BaseModel):
    criteria: list[DraftCriterion] = Field(min_length=1)
    campaign_id: int | None = None
    replace_existing: bool = False


class RoiInputs(BaseModel):
    # B14: lisans maliyeti girdiye eklendi — onsuz "geri odeme suresi"
    # hesaplanamaz ve ROI ekrani yarim kalir.
    platform_monthly_cost: float = Field(default=0.0, ge=0)
    agents: int = Field(default=50, ge=1)
    calls_per_agent_day: int = Field(default=40, ge=1)
    minutes_per_manual_review: int = Field(default=8, ge=1)
    qa_hourly_cost: float = Field(default=120.0, ge=0)     # kalite uzmani saatlik maliyet (TL)
    manual_coverage_pct: float = Field(default=3.0, ge=0, le=100)  # elle % kac cagri incelenir
    working_days_month: int = Field(default=22, ge=1, le=31)


class RoiResult(BaseModel):
    total_calls_month: int
    manual_reviews_month: int
    ai_coverage_pct: float           # KaliteGoz ile kapsam (%100)
    manual_hours_month: float
    manual_cost_month: float
    ai_equiv_hours_saved: float      # %100 kapsami elle yapmak kac saat surerdi
    ai_equiv_cost: float
    coverage_multiplier: float       # kapsam kac kat artti
    est_monthly_saving: float
    est_annual_saving: float
    payback_note: str
    # B14: ekranin gostermesi gereken somut sonuclar
    payback_months: float | None = None
    # hesaplanabilir | maliyet_girilmedi | maliyet_tasarrufuyla_amorti_olmaz
    payback_durumu: str = "maliyet_girilmedi"
    net_monthly_benefit: float = 0.0
    coverage_gain_pct: float = 0.0           # %3 -> %100 farki
    formuller: list[dict] = []               # formuller ekranda ACIK olmali


class BrandingOut(BaseModel):
    brand_name: str
    brand_color: str
    logo_data_url: str | None = None


class BrandingUpdate(BaseModel):
    brand_name: str | None = Field(default=None, min_length=1, max_length=80)
    brand_color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    logo_data_url: str | None = None  # data:image/...;base64,... (<= ~200 KB)
