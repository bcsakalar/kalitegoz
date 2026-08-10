"""KaliteGoz veri modeli.

v2 (kurumsal): multi-tenant + kullanici/takim/kampanya + uyum motoru
(yasakli kelime, sifirlayici ihlal, kalibrasyon/itiraz, kocluk, alarm).
Mevcut v1 tablolari (Call, Segment, Criterion, Score, Agent) korunur ve
tenant_id ile genisletilir.
"""

import enum
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

# =====================================================================
# Enum / sabitler
# =====================================================================


class Role(str, enum.Enum):
    admin = "admin"
    supervisor = "supervisor"
    quality = "quality"
    agent = "agent"


class Channel(str, enum.Enum):
    voice = "voice"
    chat = "chat"


class CallStatus(str, enum.Enum):
    pending = "pending"
    transcribing = "transcribing"
    scoring = "scoring"
    done = "done"
    failed = "failed"


class AppealStatus(str, enum.Enum):
    open = "open"
    accepted = "accepted"
    rejected = "rejected"


class TaskStatus(str, enum.Enum):
    open = "open"
    done = "done"


class ReviewStatus(str, enum.Enum):
    """Manuel QA inceleme atamasinin durumu."""
    assigned = "assigned"      # atandi, henuz bakilmadi
    in_review = "in_review"    # inceleniyor
    completed = "completed"    # tamamlandi (ManualEvaluation olusturuldu)


class ReviewReason(str, enum.Enum):
    """Bir cagri neden manuel incelemeye alindi? (FAZ 3.2 kuyruk kurallari)"""
    critical = "critical"                  # 1. sifirlayici ihlal — HER ZAMAN
    crisis = "crisis"                      # 2. kriz sinyali — HER ZAMAN
    low_confidence = "low_confidence"      # 3. guven < 0.70 veya yetersiz kanit
    low_score = "low_score"                # 4. toplam puan alt %10 diliminde
    emotion_mismatch = "emotion_mismatch"  # 5. duygu <-> puan uyumsuzlugu
    random = "random"                      # 6. rastgele ornek (kor kontrol grubu)
    new_agent = "new_agent"                # 7. yeni temsilci (ilk 30 gun)
    manual = "manual"                      # yonetici elle sectiyle


class QAState(str, enum.Enum):
    """Kalite kontrol durum makinesi (FAZ 3.1).

    Cagrinin ISLEME durumundan (CallStatus) AYRIDIR: CallStatus "ses cozuldu mu,
    puanlandi mi" sorusunu; QAState "bu puan gecerli mi, insan onayladi mi"
    sorusunu cevaplar.

        ai_puanlandi
          |-- risk kurali tetiklenmedi --> kesinlesti
          `-- risk kurali tetiklendi   --> insan_kuyrugunda
                                             |-- onaylandi/duzeltildi --> kesinlesti
                                             `-- temsilci itirazi -----> itiraz_incelemede
                                                                            `--> kesinlesti

    KESINLESMEYEN puan temsilci karnesinde ve liderlik tablosunda HAM PUAN
    OLARAK SAYILMAZ (ayri gosterilir: "onay bekliyor").
    """

    ai_scored = "ai_puanlandi"
    human_queue = "insan_kuyrugunda"
    appeal_review = "itiraz_incelemede"
    final = "kesinlesti"


class OverrideReasonCode(str, enum.Enum):
    """Kaliteci bir puani neden duzeltti? Sabit liste — serbest metin YERINE.

    Sabit kod sarttir: kalibrasyon analizi "hangi sebeple ne kadar duzeltiliyor"
    sorusunu ancak sayilabilir bir alanla cevaplayabilir. Serbest not AYRICA
    tutulur.
    """

    kanit_yanlis = "kanit_yanlis"                      # gosterilen kanit hatali
    baglam_kacirildi = "baglam_kacirildi"              # cagrinin baglami atlandi
    kriter_yanlis_yorumlandi = "kriter_yanlis_yorumlandi"
    stt_hatasi = "stt_hatasi"                          # transkript hatali
    rubrik_mugak = "rubrik_mugak"                      # kriter tanimi net degil
    diger = "diger"


class AlertType(str, enum.Enum):
    zeroing = "zeroing"          # sifirlayici ihlal
    crisis = "crisis"           # kriz cagrisi
    banned_word = "banned_word"  # yasakli kelime
    low_score = "low_score"     # dusuk puan
    score_drop = "score_drop"   # temsilci performansinda ani dusus (trend alarmi)


CATEGORIES = ["fatura", "iptal", "ariza", "sikayet", "bilgi", "diger"]

# Kriter gruplari (rubrik editorunde secilir)
CRITERION_GROUPS = [
    "Acilis",
    "Ihtiyac Analizi",
    "Cozum",
    "Kapanis",
    "Uyum",
    "Iletisim Kalitesi",
    "Kriz Yonetimi",
]

BANNED_CATEGORIES = ["hakaret", "kucumseme", "rakip", "yasak_vaat", "mevzuat"]


# =====================================================================
# Organizasyon: Tenant / Kullanici / Takim / Kampanya
# =====================================================================


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    retention_days: Mapped[int] = mapped_column(Integer, default=365)
    # Isleme duraklatildiysa yeni cagrilar "pending" olarak birikir, STT/LLM
    # calismaz. Yonetim > Isleme ekranindan elle baslatilir. Boylece agir is
    # (CPU/RAM) makinenin uygun oldugu zamanda calistirilir.
    processing_paused: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Beyaz etiket (white-label): tenant kendi markasini gorur. Bos ise config
    # varsayilanlari (brand_name/brand_color) kullanilir.
    brand_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    brand_color: Mapped[str | None] = mapped_column(String(9), nullable=True)  # #RRGGBB
    logo_data_url: Mapped[str | None] = mapped_column(Text, nullable=True)      # data: URI
    # Kurum-bazli esnek ayarlar (panelden yonetilir): notify_events, auto_process vb.
    settings: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Team(Base):
    __tablename__ = "teams"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_team_tenant_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(128))
    supervisor_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Campaign(Base):
    """Kuyruk / kampanya — kendi rubrigi ve kanali olabilir."""

    __tablename__ = "campaigns"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_campaign_tenant_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(128))
    channel: Mapped[Channel] = mapped_column(
        SAEnum(Channel, native_enum=False, length=10), default=Channel.voice
    )
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("tenant_id", "email", name="uq_user_tenant_email"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    email: Mapped[str] = mapped_column(String(256), index=True)
    name: Mapped[str] = mapped_column(String(128))
    password_hash: Mapped[str] = mapped_column(String(256))
    role: Mapped[Role] = mapped_column(SAEnum(Role, native_enum=False, length=16))
    team_id: Mapped[int | None] = mapped_column(
        ForeignKey("teams.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # agent rolundeki kullaniciyi Agent kaydina baglar (kendi cagrilarini gorur)
    agent_id: Mapped[int | None] = mapped_column(
        ForeignKey("agents.id", ondelete="SET NULL"), nullable=True, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Davet edilen kullanici parolasini belirleyene kadar False -> giris engellenir.
    # Seed/elle olusturulan kullanicilar True (parolasi hazir).
    password_set: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# =====================================================================
# Temsilci / Cagri / Segment
# =====================================================================


class Agent(Base):
    __tablename__ = "agents"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_agent_tenant_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(128), index=True)
    team_id: Mapped[int | None] = mapped_column(
        ForeignKey("teams.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    calls: Mapped[list["Call"]] = relationship(back_populates="agent")


class Call(Base):
    __tablename__ = "calls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    filename: Mapped[str] = mapped_column(String(512))
    audio_path: Mapped[str] = mapped_column(String(1024))
    channel: Mapped[Channel] = mapped_column(
        SAEnum(Channel, native_enum=False, length=10), default=Channel.voice, index=True
    )
    # Musteri referansi (CRM ID / musteri no / telefon hash). Verilirse GERCEK FCR
    # hesaplanir: ayni musteri FCR_WINDOW_DAYS icinde tekrar aradiysa ilk temas
    # cozum saglamamis demektir. Verilmezse FCR tahmini kullanilir.
    customer_ref: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    # Bu cagri, ayni musterinin yakin zamandaki onceki cagrisinin TEKRARI mi?
    is_repeat: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    repeat_of_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    agent_id: Mapped[int | None] = mapped_column(
        ForeignKey("agents.id", ondelete="SET NULL"), nullable=True, index=True
    )
    campaign_id: Mapped[int | None] = mapped_column(
        ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[CallStatus] = mapped_column(
        SAEnum(CallStatus, native_enum=False, length=20),
        default=CallStatus.pending,
        index=True,
    )
    duration_sec: Mapped[float | None] = mapped_column(Float, nullable=True)
    category: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    total_score: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)
    # Sifirlayici ihlal tetiklendiyse puan 0'a cekilir ve bu bayrak set edilir.
    # zeroed=True ise gerekce ve kanit ZORUNLUDUR — kanitsiz sifirlama sistem
    # hatasi olarak firlatilir (B5). Onceden gerekce yalnizca alarm metninde
    # yasiyordu; alarm silinince "neden 0?" sorusu cevapsiz kaliyordu.
    zeroed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    zeroing_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    zeroing_evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    zeroing_evidence_ts: Mapped[float | None] = mapped_column(Float, nullable=True)
    zeroing_criterion_id: Mapped[int | None] = mapped_column(
        ForeignKey("criteria.id", ondelete="SET NULL"), nullable=True
    )
    # --- FAZ 4.3: veri modeli ---
    # Insan-okur kisa referans (#0024). Dosya adi BIRINCIL KIMLIK OLMAKTAN CIKAR:
    # "deniz.yildiz_sikayet_05_v2.wav" bir kimlik degil, bir dosya adidir.
    @property
    def ref(self) -> str:
        return f"#{self.id:04d}"

    # Idempotent isleme: ayni ses dosyasi iki kez yuklenirse hash ile tespit
    # edilir ve TEKRAR ISLENMEZ (LLM/STT maliyeti bosa gitmez).
    audio_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    # --- FAZ 3: iki asamali kalite kontrol ---
    # values_callable ZORUNLU: SQLAlchemy varsayilan olarak enum'un ADINI yazar
    # ("final"), ama migration ve API enum DEGERINI kullaniyor ("kesinlesti").
    # Bu ikisi ayrisirsa DB'den okurken LookupError alinir — nitekim alindi.
    qa_state: Mapped[QAState] = mapped_column(
        SAEnum(QAState, native_enum=False, length=20,
               values_callable=lambda e: [m.value for m in e]),
        default=QAState.ai_scored, index=True,
    )
    # Hangi kuyruk kurallari tetiklendi (ReviewReason degerleri)
    queue_reasons: Mapped[list] = mapped_column(JSON, default=list)
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finalized_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    @property
    def score_is_final(self) -> bool:
        """Puan liderlik tablosuna ve karneye girebilir mi?"""
        return self.qa_state == QAState.final
    is_crisis: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    predicted_csat: Mapped[float | None] = mapped_column(Float, nullable=True)  # 1-5 LLM tahmini

    # --- Gercek musteri anketi (CSAT) ---
    #
    # `predicted_csat` bir TAHMINDIR ve tek basina hicbir sey kanitlamaz: onu
    # ureten model ile onu degerlendiren rubrik ayni tarafin urunu. Urunun
    # "kaliteli cagri" tanimini DISARIDAN dogrulayan tek veri, musterinin
    # kendi verdigi puandir.
    #
    # Bu alanlar dolduruldugunda kalite puani <-> gercek CSAT korelasyonu
    # olculebilir hale gelir. Korelasyon zayif cikarsa sorgulanmasi gereken
    # sey model degil, RUBRIGIN KENDISIDIR — ve dogrusu budur.
    actual_csat: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)
    # anket | manuel | ice_aktarma — puanin nereden geldigi denetlenebilsin
    csat_source: Mapped[str | None] = mapped_column(String(16), nullable=True)
    csat_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    csat_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    risky_moments: Mapped[list] = mapped_column(JSON, default=list)
    metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    sentiment_start: Mapped[str | None] = mapped_column(String(16), nullable=True)
    sentiment_end: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # --- LLM analitik paketi (Dalga 1) ---
    # Musterinin baskin duygusu (8 duygudan biri): ofke, hayal_kirikligi, endise,
    # memnuniyet, notr, saskinlik, minnettarlik, uzuntu
    emotion: Mapped[str | None] = mapped_column(String(24), nullable=True, index=True)
    # Duygu yorungesi: yukselen | dusen | sabit — cagri boyunca tonun seyri
    sentiment_trajectory: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # Duygu-sonuc uyumsuzlugu: musteri ofkeli bitip CSAT yuksek tahmin edildiyse
    # (veya tersi) bu bayrak set edilir — insan gozden gecirmesi gerekebilir
    emotion_mismatch: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    # Sonraki en iyi aksiyon (uretken oneri): "iade baslat", "ust birime aktar"...
    next_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Musteri kayip (churn) riski: dusuk | orta | yuksek
    churn_risk: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    # Musteri Efor Skoru (CES) 1-5: musteri sorununu cozmek icin ne kadar ugrasti
    # (1 = cok kolay, 5 = cok zor) — dusuk efor daha iyi deneyim
    customer_effort: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Otomatik niyet/konu etiketleri (ince taneli): ["iptal-tehdidi", "fatura-itiraz"]
    intent_tags: Mapped[list] = mapped_column(JSON, default=list)
    coaching: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Manuel etiketleme + "altin/ornek cagri" (egitim kutuphanesi)
    is_golden: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Cagri ozeti/transkript embedding'i (JSON) — semantik "benzer cagri" aramasi icin
    embedding: Mapped[list | None] = mapped_column(JSON, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    agent: Mapped[Agent | None] = relationship(back_populates="calls")
    campaign: Mapped["Campaign | None"] = relationship()
    segments: Mapped[list["Segment"]] = relationship(
        back_populates="call", cascade="all, delete-orphan", order_by="Segment.idx"
    )
    scores: Mapped[list["Score"]] = relationship(
        back_populates="call", cascade="all, delete-orphan"
    )
    violations: Mapped[list["Violation"]] = relationship(
        cascade="all, delete-orphan"
    )


class Segment(Base):
    """Voice'ta STT segmenti, chat'te mesaj — ayni pipeline/puanlama akisi."""

    __tablename__ = "segments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    call_id: Mapped[int] = mapped_column(
        ForeignKey("calls.id", ondelete="CASCADE"), index=True
    )
    idx: Mapped[int] = mapped_column(Integer)
    speaker: Mapped[str] = mapped_column(String(16))  # musteri | temsilci | bilinmeyen
    start_sec: Mapped[float] = mapped_column(Float)
    end_sec: Mapped[float] = mapped_column(Float)
    text: Mapped[str] = mapped_column(Text)

    call: Mapped[Call] = relationship(back_populates="segments")


# =====================================================================
# Rubrik & Puan
# =====================================================================


class Criterion(Base):
    __tablename__ = "criteria"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    # campaign_id NULL => tum kampanyalarda gecerli (global kriter)
    campaign_id: Mapped[int | None] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(256))
    description: Mapped[str] = mapped_column(Text)
    group: Mapped[str] = mapped_column(String(64), default="Iletisim Kalitesi")
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    min_score: Mapped[int] = mapped_column(Integer, default=0)
    max_score: Mapped[int] = mapped_column(Integer, default=10)
    # Sifirlayici (kritik) kriter: bu kriter esik altinda kalirsa tum cagri 0
    is_critical: Mapped[bool] = mapped_column(Boolean, default=False)
    critical_threshold: Mapped[int] = mapped_column(Integer, default=3)
    # Kanal kapsami: voice | chat | all
    channel_scope: Mapped[str] = mapped_column(String(10), default="all")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # --- FAZ 2: uc katmanli puanlama ---
    # deterministic : Katman A kodla cozer, LLM'e SORULMAZ
    # llm_evidence  : Katman B kanit zorunlu LLM degerlendirmesi
    # human_only    : oznel kriter, AI puanlamaz -> dogrudan kaliteciye
    evaluation_mode: Mapped[str] = mapped_column(String(16), default="llm_evidence")
    # evaluation_mode='deterministic' ise hangi kontrol (deterministic.CHECK_KEYS)
    check_key: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # Mugak sifat yasak: "10 puan neye benzer / 0 puan neye benzer" capasi
    anchor_10: Mapped[str] = mapped_column(Text, default="")
    anchor_0: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Score(Base):
    __tablename__ = "scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    call_id: Mapped[int] = mapped_column(
        ForeignKey("calls.id", ondelete="CASCADE"), index=True
    )
    criterion_id: Mapped[int | None] = mapped_column(
        ForeignKey("criteria.id", ondelete="SET NULL"), nullable=True
    )
    criterion_name: Mapped[str] = mapped_column(String(256))
    criterion_group: Mapped[str] = mapped_column(String(64), default="")
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    # 0-10 AI puani. NULL = 'insufficient_evidence' — kanit bulunamadi, kriter
    # puanlanmadi ve ORTALAMAYA KATILMAZ. Kanitsiz ceza vermek yasak (B28).
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rationale: Mapped[str] = mapped_column(Text, default="")
    evidence: Mapped[str] = mapped_column(Text, default="")
    evidence_ts: Mapped[float | None] = mapped_column(Float, nullable=True)
    # --- FAZ 2: kanit zorunlulugu ve izlenebilirlik ---
    # met | partially_met | not_met | not_applicable | insufficient_evidence
    decision: Mapped[str] = mapped_column(String(24), default="met")
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    # Katman C: alinti transkriptte GERCEKTEN bulundu mu?
    evidence_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    # A = deterministik kod, B = kanit zorunlu LLM
    source_layer: Mapped[str] = mapped_column(String(1), default="B")
    # Puanin hangi rubrik surumuyle uretildigi (rubrik degisince gecmis bozulmaz)
    rubric_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("rubric_versions.id", ondelete="SET NULL"), nullable=True
    )
    # Insan override (kalite uzmani AI puanini degistirebilir)
    override_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    # FAZ 3: sabit gerekce kodu — kalibrasyon analizi serbest metni sayamaz
    override_reason_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # Kaliteci bu kriteri ONAYLADI mi (puani degistirmeden)? Onay da veridir:
    # overturn orani = duzeltilen / INCELENEN; onaysiz paydayi bilemeyiz.
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reviewed_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    overridden_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    overridden_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    call: Mapped[Call] = relationship(back_populates="scores")

    @property
    def effective_score(self) -> int:
        return self.override_score if self.override_score is not None else self.score


# =====================================================================
# Uyum motoru: yasakli kelime + ihlal kayitlari
# =====================================================================


class BannedWord(Base):
    __tablename__ = "banned_words"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    term: Mapped[str] = mapped_column(String(128), index=True)
    category: Mapped[str] = mapped_column(String(32), default="hakaret")
    severity: Mapped[str] = mapped_column(String(16), default="orta")  # dusuk|orta|yuksek
    match_type: Mapped[str] = mapped_column(String(16), default="fuzzy")  # exact|fuzzy|regex
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Violation(Base):
    """Bir cagrida tespit edilen ihlal (yasakli kelime, sifirlayici vb.)."""

    __tablename__ = "violations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    call_id: Mapped[int] = mapped_column(
        ForeignKey("calls.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(32))  # banned_word | zeroing | crisis
    category: Mapped[str] = mapped_column(String(32), default="")
    severity: Mapped[str] = mapped_column(String(16), default="orta")
    term: Mapped[str] = mapped_column(String(256), default="")
    speaker: Mapped[str] = mapped_column(String(16), default="")  # kim soyledi
    evidence: Mapped[str] = mapped_column(Text, default="")
    ts_sec: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# =====================================================================
# Insan katmani: itiraz, kocluk gorevi, alarm, rozet
# =====================================================================


class Appeal(Base):
    __tablename__ = "appeals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    call_id: Mapped[int] = mapped_column(
        ForeignKey("calls.id", ondelete="CASCADE"), index=True
    )
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[AppealStatus] = mapped_column(
        SAEnum(AppealStatus, native_enum=False, length=16), default=AppealStatus.open, index=True
    )
    resolver_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class CalibrationExample(Base):
    """Kaliteci duzeltmesinden ogrenilen ornek (FAZ 3.4 geri besleme dongusu).

    Her duzeltme buraya yazilir. Bir kriterde yeterli ornek birikince o kriterin
    Katman B prompt'una **few-shot ornek** olarak enjekte edilir.

    ONEMLI — ne YAPILMAZ: duzeltmeler gizlice agirliklara islenip gecmis puanlar
    geriye donuk degistirilmez. Rubrik DEGISMEZ, yalnizca ornek eklenir; her
    kalibrasyon etkisi surumlenir (`prompt_version`) ve raporlanir.

    FAZ 2 olcumu, kappa acikinin tamamen dort oznel kriterde toplandigini
    gosterdi (Aktif Dinleme +0.86, Ihtiyac +0.73, Cozum +0.73 sapma). Bu tablo
    o acigin kapatilma mekanizmasidir.
    """

    __tablename__ = "calibration_examples"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    criterion_id: Mapped[int] = mapped_column(
        ForeignKey("criteria.id", ondelete="CASCADE"), index=True
    )
    call_id: Mapped[int | None] = mapped_column(
        ForeignKey("calls.id", ondelete="SET NULL"), nullable=True
    )
    # Prompt'a girecek kisa transkript parcasi (tam cagri degil — token bütçesi)
    excerpt: Mapped[str] = mapped_column(Text, default="")
    ai_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    human_score: Mapped[int] = mapped_column(Integer)
    reason_code: Mapped[str] = mapped_column(String(32), default="diger")
    note: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # Kalibrasyon yoneticisi bir ornegi devre disi birakabilir (hatali ornek
    # prompt'u zehirler); silmek yerine pasiflestirilir — denetim izi kalir.
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class CoachingTask(Base):
    __tablename__ = "coaching_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    call_id: Mapped[int] = mapped_column(ForeignKey("calls.id", ondelete="CASCADE"))
    assigner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    assignee_agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), index=True)
    note: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[TaskStatus] = mapped_column(
        SAEnum(TaskStatus, native_enum=False, length=16), default=TaskStatus.open, index=True
    )
    agent_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    call_id: Mapped[int | None] = mapped_column(
        ForeignKey("calls.id", ondelete="CASCADE"), nullable=True
    )
    team_id: Mapped[int | None] = mapped_column(
        ForeignKey("teams.id", ondelete="SET NULL"), nullable=True, index=True
    )
    type: Mapped[AlertType] = mapped_column(SAEnum(AlertType, native_enum=False, length=16))
    severity: Mapped[str] = mapped_column(String(16), default="orta")
    message: Mapped[str] = mapped_column(Text)
    # --- FAZ 4.2: alarm sablonunun ZORUNLU alanlari (B4) ---
    # Sablon motoru bu alanlari doldurmadan alarm uretemez; onceden alarm
    # metni tek bir serbest string'ti ve "tespit edilen ifade" ile "gosterilen
    # alinti" birbirini tutmuyordu.
    title_tr: Mapped[str] = mapped_column(String(200), default="")
    explanation_tr: Mapped[str] = mapped_column(Text, default="")
    evidence_quote: Mapped[str] = mapped_column(Text, default="")
    evidence_timestamp: Mapped[float | None] = mapped_column(Float, nullable=True)
    suggested_action_tr: Mapped[str] = mapped_column(Text, default="")
    # --- Dedup (B12) ---
    # (call_id, rule_id, evidence_hash) uclusunde tekillik. Ayni ihlal ayni
    # cagrida TEK alarm uretir; tekrarlar occurrence_count ile sayilir.
    rule_id: Mapped[str] = mapped_column(String(64), default="", index=True)
    evidence_hash: Mapped[str] = mapped_column(String(40), default="", index=True)
    occurrence_count: Mapped[int] = mapped_column(Integer, default=1)
    # --- Yasam dongusu: yeni -> okundu -> aksiyon_alindi | gecersiz_isaretlendi ---
    lifecycle: Mapped[str] = mapped_column(String(24), default="yeni", index=True)
    lifecycle_note: Mapped[str] = mapped_column(Text, default="")
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    # Cagri yeniden puanlandiginda onceki alarmlar GECERSIZLESIR (B31).
    # Silinmez — denetim izi ve kalibrasyon sinyali olarak saklanir, ama
    # kullaniciya gosterilmez. Onceden eski/hatali alarm ekranda asili kaliyordu.
    is_stale: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class Badge(Base):
    __tablename__ = "badges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    code: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text, default="")
    icon: Mapped[str] = mapped_column(String(16), default="🏅")


class AgentBadge(Base):
    __tablename__ = "agent_badges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), index=True)
    badge_id: Mapped[int] = mapped_column(ForeignKey("badges.id", ondelete="CASCADE"))
    period: Mapped[str] = mapped_column(String(16), default="")  # 2026-W28 vb.
    awarded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Challenge(Base):
    """Gamification: sureli hedef (challenge). Orn. 'Bu hafta 10 cagrida 85+ puan'.

    İlerleme cagri verisinden hesaplanir (metric + threshold + target). Boylece
    ayri ilerleme kaydi tutmaya gerek kalmaz — her zaman guncel.
    """

    __tablename__ = "challenges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text, default="")
    # Olculen metrik: 'score_above' (puan esigi ustu cagri sayisi), 'call_count',
    # 'avg_score' (donem ortalamasi), 'zero_violations' (ihlalsiz cagri).
    metric: Mapped[str] = mapped_column(String(24), default="score_above")
    threshold: Mapped[float] = mapped_column(Float, default=85.0)  # metrik esigi
    target: Mapped[int] = mapped_column(Integer, default=10)       # hedef adet/deger
    reward_points: Mapped[int] = mapped_column(Integer, default=100)
    starts_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    # Belirli bir takima ozel mi? (None = tum tenant)
    team_id: Mapped[int | None] = mapped_column(
        ForeignKey("teams.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SelfAssessment(Base):
    """Temsilcinin kendi cagrisini QA'dan ONCE degerlendirmesi (self-servis).

    Sektorde buyuyen pratik: temsilci kendini puanlar, sonra AI/uzman puaniyla
    kiyaslanir. Fark buyukse ozel farkindalik gerekir; kucukse temsilci kendi
    kalitesini iyi biliyor demektir. Itiraz oranini da dusurur.
    """

    __tablename__ = "self_assessments"
    __table_args__ = (
        UniqueConstraint("call_id", "agent_id", name="uq_self_call_agent"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    call_id: Mapped[int] = mapped_column(ForeignKey("calls.id", ondelete="CASCADE"), index=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), index=True)
    self_score: Mapped[float] = mapped_column(Float)  # 0-100 temsilcinin kendine verdigi
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# =====================================================================
# KVKK / audit
# =====================================================================


class CalibrationSession(Base):
    """Kalibrasyon oturumu: AYNI cagriyi birden fazla uzman BAGIMSIZ puanlar.

    Sektor pratigi: kalite uzmanlari haftalik kalibrasyon yapar; hedef
    inter-rater reliability (uzmanlar arasi uyum) >= %85. Uyum dusukse sorun
    uzmanda degil RUBRIKTE'dir (kriter aciklamasi mugalak demektir).

    Oturum acikken uzmanlar birbirinin puanini GOREMEZ (yanlilik olmasin);
    kapandiginda karsilastirma raporu acilir.
    """

    __tablename__ = "calibration_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    call_id: Mapped[int] = mapped_column(ForeignKey("calls.id", ondelete="CASCADE"), index=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(256), default="")
    status: Mapped[str] = mapped_column(String(16), default="open", index=True)  # open|closed
    # Planlanan tarih (opsiyonel): ileri tarihli/tekrarli kalibrasyon takvimi icin
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    evaluations: Mapped[list["ManualEvaluation"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class ManualEvaluation(Base):
    """Bir uzmanin BAGIMSIZ (AI'dan etkilenmemis) degerlendirmesi.

    Iki kullanim:
    1. Kalibrasyon oturumu icinde (session_id dolu) — uzmanlar arasi uyum olcumu.
    2. Tek basina manuel degerlendirme (session_id bos) — AI'yi tamamen atlayip
       sifirdan insan puanlamasi.
    """

    __tablename__ = "manual_evaluations"
    __table_args__ = (
        # Bir uzman ayni oturumda iki kez puanlayamaz
        UniqueConstraint("session_id", "evaluator_id", name="uq_eval_session_evaluator"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    call_id: Mapped[int] = mapped_column(ForeignKey("calls.id", ondelete="CASCADE"), index=True)
    session_id: Mapped[int | None] = mapped_column(
        ForeignKey("calibration_sessions.id", ondelete="CASCADE"), nullable=True, index=True
    )
    evaluator_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    # [{"criterion_id": 1, "criterion_name": "Acilis", "score": 8, "note": "..."}]
    scores: Mapped[list] = mapped_column(JSON, default=list)
    total_score: Mapped[float] = mapped_column(Float, default=0.0)  # 0-100 agirlikli
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    session: Mapped["CalibrationSession | None"] = relationship(back_populates="evaluations")


class KnowledgeDoc(Base):
    """Sirket bilgi bankasi dokumani (urun/prosedur/SSS)."""

    __tablename__ = "knowledge_docs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(256))
    source_filename: Mapped[str] = mapped_column(String(512), default="")
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    chunks: Mapped[list["KnowledgeChunk"]] = relationship(
        back_populates="doc", cascade="all, delete-orphan"
    )


class KnowledgeChunk(Base):
    """Dokuman parcasi + embedding (pgvector). RAG ile bilgi dogrulugu kontrolu."""

    __tablename__ = "knowledge_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    doc_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_docs.id", ondelete="CASCADE"), index=True
    )
    idx: Mapped[int] = mapped_column(Integer, default=0)
    content: Mapped[str] = mapped_column(Text)
    # Embedding pgvector Vector kolonu olarak migration ile eklenir; SQLAlchemy
    # tarafinda saglayici-bagimsiz kalmak icin JSON olarak da tutulabilir.
    # Uygulama pgvector varsa vektor aramasi, yoksa Python kosinus benzerligi yapar.
    embedding: Mapped[list | None] = mapped_column(JSON, nullable=True)

    doc: Mapped[KnowledgeDoc] = relationship(back_populates="chunks")


class ReviewAssignment(Base):
    """Bir cagrinin belirli bir uzmana manuel QA incelemesi icin atanmasi.

    Sektorde 'QA sampling & assignment': tum cagrilar AI ile puanlanir ama bir
    kismi (rastgele ornek + riskli olanlar) insana da inceletilir. Bu, AI'nin
    kalibrasyonunu korur ve kritik kararlarda insan teyidi saglar.
    """

    __tablename__ = "review_assignments"
    __table_args__ = (
        # Ayni cagri ayni uzmana iki kez atanmasin
        UniqueConstraint("call_id", "reviewer_id", name="uq_review_call_reviewer"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    call_id: Mapped[int] = mapped_column(ForeignKey("calls.id", ondelete="CASCADE"), index=True)
    reviewer_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    assigner_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reason: Mapped[ReviewReason] = mapped_column(
        SAEnum(ReviewReason, native_enum=False, length=16), default=ReviewReason.manual
    )
    status: Mapped[ReviewStatus] = mapped_column(
        SAEnum(ReviewStatus, native_enum=False, length=16),
        default=ReviewStatus.assigned, index=True,
    )
    # Tamamlandiginda olusan manuel degerlendirmeye baglanti (opsiyonel)
    evaluation_id: Mapped[int | None] = mapped_column(
        ForeignKey("manual_evaluations.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    call: Mapped["Call"] = relationship()
    reviewer: Mapped["User"] = relationship(foreign_keys=[reviewer_id])


class AuditLog(Base):
    """Append-only denetim gunlugu — kim, ne zaman, neyi yapti."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(64), index=True)  # login, view_call, override, ...
    entity_type: Mapped[str] = mapped_column(String(64), default="")
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ip: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class AuthToken(Base):
    """Tek kullanimlik token: kullanici daveti (parola belirleme) veya parola sifirlama.

    Kurumsal onboarding: admin bir kullaniciyi davet eder -> 'invite' token uretilir,
    e-posta ile (SMTP varsa) veya panelde link olarak paylasilir; kullanici linke
    tiklayip parolasini belirler. Parola unutulunca 'reset' token'i ayni akisla calisir.
    """

    __tablename__ = "auth_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    purpose: Mapped[str] = mapped_column(String(16))  # invite | reset
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AiUsage(Base):
    """Her LLM/embedding/vision cagrisinin kaydi — saglayici, model, token, sure.

    Kurum panelinden 'bu ay AI ne kadar kullanildi / tahmini maliyet' gorunur.
    Ollama (yerel) icin maliyet 0; bulut saglayicilarda token * birim fiyat.
    """

    __tablename__ = "ai_usage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True)
    provider: Mapped[str] = mapped_column(String(32), index=True)  # ollama|gemini|openai|openrouter
    model: Mapped[str] = mapped_column(String(96), default="")
    kind: Mapped[str] = mapped_column(String(24), index=True)  # scoring|topics|coaching|summary|vision|embed
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    ok: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class RubricVersion(Base):
    """Rubrik anlik goruntusu (versiyon): kim, ne zaman, hangi kriter yapilandirmasi.

    Kalite yonetimi rubrigi degistirmeden once/sonra kaydeder; gerektiginde geri
    yukler. Denetim + geri alma (governance) icin.
    """

    __tablename__ = "rubric_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True)
    note: Mapped[str] = mapped_column(String(200), default="")
    snapshot: Mapped[list] = mapped_column(JSON, default=list)  # [{name,group,weight,is_critical,...}]
    criteria_count: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class Target(Base):
    """Kalite hedefi: kurum/takim/temsilci icin bir metrik esigi ( or. kalite>=80).

    Kokpit ve karnede 'hedefe karsi gercek' gosterilir; hedefin altindakiler
    kirmizi vurgulanir. Yoneticinin ekibi olculebilir hedefe baglamasini saglar.
    """

    __tablename__ = "targets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(Integer, index=True)
    scope: Mapped[str] = mapped_column(String(16), default="tenant")  # tenant|team|agent
    scope_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # team_id/agent_id, tenant icin None
    metric: Mapped[str] = mapped_column(String(24), default="quality")  # quality|csat|fcr|zeroed_rate
    target_value: Mapped[float] = mapped_column(Float, default=80.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
