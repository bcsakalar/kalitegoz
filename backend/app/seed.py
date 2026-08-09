"""Baslangic verisi: demo tenant + organizasyon + rubrik + yasakli kelimeler.

Idempotent: demo tenant zaten varsa hicbir sey yapmaz. `make demo` bu tohum
uzerine sentetik cagri/chat verisi ekler.
"""

from sqlalchemy.orm import Session

from .models import (
    Agent,
    Badge,
    BannedWord,
    Campaign,
    Channel,
    Criterion,
    Role,
    Team,
    Tenant,
    User,
)
from .security import hash_password

DEMO_SLUG = "demo"
DEMO_PASSWORD = "demo1234"

# 12 temsilci, 2 takima bolunmus (satis / destek)
DEMO_AGENTS = [
    ("ayse.yilmaz", "Satış Ekibi"),
    ("mehmet.kaya", "Destek Ekibi"),
    ("zeynep.demir", "Satış Ekibi"),
    ("emre.sahin", "Destek Ekibi"),
    ("elif.arslan", "Satış Ekibi"),
    ("burak.ozturk", "Destek Ekibi"),
    ("selin.koc", "Satış Ekibi"),
    ("caner.aydin", "Destek Ekibi"),
    ("deniz.yildiz", "Satış Ekibi"),
    ("gizem.celik", "Destek Ekibi"),
    ("okan.dogan", "Satış Ekibi"),
    ("pelin.acar", "Destek Ekibi"),
]

DEFAULT_CRITERIA: list[dict] = [
    # --- UYUM (Compliance) -------------------------------------------------
    {
        "name": "KVKK / Aydinlatma",
        "group": "Uyum",
        "description": (
            "Gorusmenin kayit altina alindigi VE kisisel verilerin islendigi "
            "ayri ayri bildirildi mi? Aydinlatma Tebligi m.5/1 uyarinca anons "
            "cagri basinda sozlu yapilir; birebir ayni cumle beklenmez, ANLAM "
            "esleşmesi aranir."
        ),
        "anchor_10": "Hem kayit bildirimi hem kisisel veri aydinlatmasi acikca yapildi.",
        "anchor_0": "Ikisi de yapilmadi.",
        "weight": 1.5,
        "is_critical": True,
        "critical_threshold": 3,
        "evaluation_mode": "deterministic",
        "check_key": "kvkk_anons",
    },
    {
        "name": "Kimlik Dogrulama",
        "group": "Uyum",
        "description": (
            "Islem yapilmadan ONCE musteri kimligi (ad-soyad + musteri/hizmet no) "
            "teyit edildi mi?"
        ),
        "anchor_10": "Cagrinin ilk ucte birinde ad ve musteri numarasi istendi.",
        "anchor_0": "Hicbir dogrulama yapilmadan islem gerceklestirildi.",
        "weight": 1.5,
        "is_critical": True,
        "critical_threshold": 3,
        "evaluation_mode": "deterministic",
        "check_key": "kimlik_dogrulama",
    },
    {
        "name": "Script Uyumu",
        "group": "Uyum",
        "description": (
            "Kurumun zorunlu akisi izlendi mi: bilgilendirme, dogrulama, islem "
            "ozeti, teyit. Eksik her zorunlu adim puan dusurur."
        ),
        "anchor_10": "Zorunlu adimlarin tamami sirasiyla uygulandi.",
        "anchor_0": "Akis tamamen atlandi.",
        "weight": 1.0,
    },
    # --- ILETISIM (Communication) ------------------------------------------
    {
        "name": "Acilis",
        "group": "Iletisim",
        "description": (
            "Temsilci kurum adini VE kendi adini bildirdi mi? Kurum adinin cumle "
            "basinda olmasi gerekmez; VARLIGI aranir."
        ),
        "anchor_10": "Kurum adi ve temsilci adi acilista birlikte soylendi.",
        "anchor_0": "Ne kurum adi ne temsilci adi soylendi ('Alo, buyurun').",
        "weight": 1.0,
        "evaluation_mode": "deterministic",
        "check_key": "acilis",
    },
    {
        "name": "Yasakli Kelime / Uslup",
        "group": "Iletisim",
        "description": (
            "Temsilci kaba, kucumseyici, suclayici ifade veya yasak vaat kullandi "
            "mi? MUSTERININ kufru temsilciyi CEZALANDIRMAZ."
        ),
        "anchor_10": "Cagri boyunca profesyonel ve nazik uslup.",
        "anchor_0": "Temsilci hakaret etti veya agir yasak vaat verdi.",
        "weight": 1.5,
        "evaluation_mode": "deterministic",
        "check_key": "yasakli_kelime",
    },
    {
        "name": "Kapanis",
        "group": "Iletisim",
        "description": (
            "'Baska bir konuda yardimci olabilir miyim?' soruldu mu ve uygun veda "
            "cumlesi kuruldu mu?"
        ),
        "anchor_10": "Ek yardim soruldu ve veda edildi.",
        "anchor_0": "Cagri kapanis kalibi olmadan sonlandirildi.",
        "weight": 1.0,
        "evaluation_mode": "deterministic",
        "check_key": "kapanis",
    },
    {
        "name": "Aktif Dinleme",
        "group": "Iletisim",
        "description": (
            "Temsilci musteriyi kesmeden dinledi mi, anladigini teyit etti mi? "
            "YALNIZCA TEMSILCININ soz kesmesi puan kirar; musteri keserse kirmaz."
        ),
        "anchor_10": "Kesmeden dinledi, anladigini kendi cumleleriyle ozetleyip teyit etti.",
        "anchor_0": "Musteriyi surekli kesti, ayni seyi tekrar sordurdu.",
        "weight": 1.0,
    },
    # --- YETKINLIK (Competence) --------------------------------------------
    {
        "name": "Bilgi Dogrulugu",
        "group": "Yetkinlik",
        "description": (
            "Verilen bilgi (sure, ucret, sart, prosedur) sirket bilgi bankasindaki "
            "resmi dokumanlarla ortusuyor mu? Prompt'ta 'SIRKET BILGI BANKASI' "
            "bolumu varsa oradaki pasajlari esas al. MUSTERININ ANLAMAMASI "
            "temsilcinin hatasi degildir."
        ),
        "anchor_10": "Verilen her bilgi dogru ve dokumanla ortusuyor.",
        "anchor_0": "Musteriye acikca yanlis bilgi verildi.",
        "weight": 2.0,
    },
    {
        "name": "Ihtiyac Analizi",
        "group": "Yetkinlik",
        "description": (
            "Temsilci musterinin gercek ihtiyacini dogru soru sorarak netlestirdi mi?"
        ),
        "anchor_10": "Cozum onerilmeden once ihtiyaci netlestiren sorular soruldu.",
        "anchor_0": "Hic soru sorulmadan, ihtiyaca uymayan cozum dayatildi.",
        "weight": 1.0,
    },
    # --- MUSTERI ODAGI (Customer focus) ------------------------------------
    {
        "name": "Cozum / Yonlendirme",
        "group": "Musteri Odagi",
        "description": (
            "Musterinin sorunu cozuldu mu veya dogru birime net sekilde "
            "yonlendirildi mi? Somut adim, sure ve beklenti verildi mi?"
        ),
        "anchor_10": "Sorun cagri icinde cozuldu; somut adim ve sure bildirildi.",
        "anchor_0": "Sorun cozulmedi, sonraki adim da verilmedi.",
        "weight": 2.0,
    },
]

# Demo bilgi bankasi — 'yanlis bilgi veren temsilci' senaryosunun yakalanmasi icin
# resmi prosedur metni. `make demo` bunu otomatik indeksler.
DEMO_KNOWLEDGE_DOC = {
    "title": "Iade, Cayma ve Kargo Prosedürü (Resmî)",
    "filename": "iade_prosedur.md",
    "content": """# Netix İletişim — İade, Cayma ve Kargo Prosedürü

## 1. Cayma hakkı ve iade süresi
Mesafeli satış sözleşmesi kapsamında satın alınan tüm cihazlarda (modem, router,
akıllı cihaz) müşterinin cayma hakkı süresi **14 (on dört) gündür**. Bu süre
cihazın müşteriye teslim edildiği tarihte başlar. 14 günü aşan taleplerde cayma
hakkı kullanılamaz; talep istisnai onay sürecine gönderilir.

**Önemli:** Temsilciler hiçbir koşulda 14 günden farklı bir iade süresi (örneğin
30 gün) beyan edemez.

## 2. İade kargo ücreti
Cayma hakkı kapsamındaki iadelerde kargo ücreti **şirketimize aittir; müşteriden
kargo ücreti tahsil edilmez**. Müşteriye anlaşmalı kargo firması için ücretsiz
iade kodu SMS ile gönderilir. Müşteriden iade kargo ücreti talep etmek yasaktır.

## 3. Ambalajı açılmış ürünler
Ambalajı açılmış olması tek başına iadeye engel **değildir**. Cihaz, kullanım
hatası kaynaklı fiziksel hasar içermiyorsa ve tüm aksesuarları eksiksizse iade
kabul edilir.

## 4. İade süreci ve süreler
1. Müşteri talebi kaydedilir, iade kodu SMS ile gönderilir (aynı gün).
2. Müşteri cihazı ücretsiz kargo ile gönderir.
3. Cihaz depoya ulaştıktan sonra kontrol **3 iş günü** içinde tamamlanır.
4. Ücret iadesi, kontrolün ardından **7 iş günü** içinde ödeme yöntemine yapılır.

## 5. Taahhüt ve cayma bedeli
Taahhütlü aboneliklerde taahhüt süresi dolmadan iptal edilirse kalan aya göre
cayma bedeli yansıtılır. Taahhüdü biten aboneliklerde cayma bedeli **alınmaz**.
Hat dondurma alternatifi en fazla **6 ay** için sunulabilir; aylık hat koruma
ücreti **15 TL**'dir.
""",
}

DEFAULT_BANNED_WORDS: list[dict] = [
    {"term": "saçmalama", "category": "hakaret", "severity": "yuksek", "match_type": "fuzzy"},
    {"term": "aptal", "category": "hakaret", "severity": "yuksek", "match_type": "fuzzy"},
    {"term": "salak", "category": "hakaret", "severity": "yuksek", "match_type": "fuzzy"},
    {"term": "anlamıyorsun", "category": "kucumseme", "severity": "orta", "match_type": "fuzzy"},
    {"term": "işim gücüm var", "category": "kucumseme", "severity": "orta", "match_type": "fuzzy"},
    {"term": "kesin çözülür", "category": "yasak_vaat", "severity": "orta", "match_type": "fuzzy"},
    {"term": "garanti ederim", "category": "yasak_vaat", "severity": "orta", "match_type": "fuzzy"},
    {"term": "yüzde yüz", "category": "yasak_vaat", "severity": "dusuk", "match_type": "fuzzy"},
]

DEFAULT_BADGES: list[dict] = [
    {"code": "crisis_master", "name": "Kriz Ustası", "icon": "🛡️",
     "description": "Kriz cagrilarinda yuksek puan tutturan temsilci"},
    {"code": "zero_violation", "name": "Sıfır İhlal Ayı", "icon": "✨",
     "description": "Bir ay boyunca hic sifirlayici ihlal yasamayan temsilci"},
    {"code": "fastest_solution", "name": "En Hızlı Çözüm", "icon": "⚡",
     "description": "En yuksek ilk temasta cozum oranina sahip temsilci"},
    {"code": "empathy_champ", "name": "Empati Şampiyonu", "icon": "💗",
     "description": "Musteri duygusunu en cok iyilestiren temsilci"},
]


def seed_all(db: Session) -> Tenant:
    """Demo tenant + organizasyon + rubrik. Idempotent."""
    tenant = db.query(Tenant).filter(Tenant.slug == DEMO_SLUG).first()
    if tenant is not None:
        return tenant

    # processing_paused=True: agir STT/LLM isi (CPU/RAM yogun) kendiliginden
    # baslamasin. Cagrilar "pending" birikir; kullanici makinesi musaitken
    # Yonetim > Isleme ekranindan "Islemeyi baslat" der.
    tenant = Tenant(name="Demo Çağrı Merkezi", slug=DEMO_SLUG, retention_days=365,
                    processing_paused=True)
    db.add(tenant)
    db.flush()

    # Takimlar
    teams = {}
    for tname in ("Satış Ekibi", "Destek Ekibi"):
        team = Team(tenant_id=tenant.id, name=tname)
        db.add(team)
        db.flush()
        teams[tname] = team

    # Kampanyalar (kuyruklar)
    for cname, desc in (
        ("Satış Hattı", "Yeni satis ve tarife gorusmeleri"),
        ("Destek Hattı", "Ariza, fatura, sikayet ve bilgi gorusmeleri"),
    ):
        db.add(Campaign(tenant_id=tenant.id, name=cname, channel=Channel.voice, description=desc))

    # Personel kullanicilari
    db.add(User(tenant_id=tenant.id, email="admin@demo.local", name="Sistem Yöneticisi",
                password_hash=hash_password(DEMO_PASSWORD), role=Role.admin))
    db.add(User(tenant_id=tenant.id, email="kalite@demo.local", name="Kalite Uzmanı",
                password_hash=hash_password(DEMO_PASSWORD), role=Role.quality))
    for tname, team in teams.items():
        sup = User(
            tenant_id=tenant.id,
            email=f"sef.{'satis' if 'Satış' in tname else 'destek'}@demo.local",
            name=f"{tname} Şefi",
            password_hash=hash_password(DEMO_PASSWORD),
            role=Role.supervisor,
            team_id=team.id,
        )
        db.add(sup)
        db.flush()
        team.supervisor_id = sup.id

    # Temsilciler + agent-rol kullanicilari
    for agent_name, team_name in DEMO_AGENTS:
        agent = Agent(tenant_id=tenant.id, name=agent_name, team_id=teams[team_name].id)
        db.add(agent)
        db.flush()
        db.add(User(
            tenant_id=tenant.id,
            email=f"{agent_name}@demo.local",
            name=agent_name.replace(".", " ").title(),
            password_hash=hash_password(DEMO_PASSWORD),
            role=Role.agent,
            team_id=teams[team_name].id,
            agent_id=agent.id,
        ))

    # Rubrik
    for item in DEFAULT_CRITERIA:
        db.add(Criterion(tenant_id=tenant.id, **item))

    # Yasakli kelimeler
    for bw in DEFAULT_BANNED_WORDS:
        db.add(BannedWord(tenant_id=tenant.id, **bw))

    # Rozetler
    for b in DEFAULT_BADGES:
        db.add(Badge(tenant_id=tenant.id, **b))

    db.commit()
    return tenant


# Geriye donuk uyumluluk (main.py eski adi cagirabilir)
def seed_criteria(db: Session) -> None:
    seed_all(db)


def seed_demo_history(db: Session, tenant_id: int, weeks: int = 8) -> int:
    """Dashboard demo aninda dolu gorunsun diye 8 haftalik sentetik puanli cagri uret.

    Gercek STT/LLM'den gecmez; dogrudan puanlanmis Call+Score kayitlari yazar
    (status=done, gecmis tarihli). Idempotent: 'gecmis_' onekli cagri varsa atlar.
    """
    import random
    from datetime import datetime, timedelta

    from .models import Call, CallStatus, Channel, Criterion, Score

    existing = db.query(Call).filter(
        Call.tenant_id == tenant_id, Call.filename.like("gecmis_%")
    ).first()
    if existing:
        return 0

    rng = random.Random(2026)
    agents = db.query(Agent).filter(Agent.tenant_id == tenant_id).all()
    criteria = db.query(Criterion).filter(
        Criterion.tenant_id == tenant_id, Criterion.is_active.is_(True)
    ).order_by(Criterion.id).all()
    campaigns = db.query(Campaign).filter(Campaign.tenant_id == tenant_id).all()
    if not agents or not criteria:
        return 0

    categories = ["fatura", "iptal", "ariza", "sikayet", "bilgi"]
    sentiments = ["olumlu", "notr", "olumsuz"]
    # Her temsilciye bir yetenek taban puani (5.5-9.0 arasi)
    skill = {a.id: rng.uniform(5.5, 9.0) for a in agents}
    total_weight = sum(c.weight for c in criteria)
    created = 0

    for week in range(weeks):
        for agent in agents:
            n_calls = rng.randint(2, 5)
            for _ in range(n_calls):
                days_ago = week * 7 + rng.randint(0, 6)
                when = datetime.utcnow() - timedelta(
                    days=days_ago, hours=rng.randint(0, 8), minutes=rng.randint(0, 59)
                )
                channel = Channel.chat if rng.random() < 0.3 else Channel.voice
                campaign = rng.choice(campaigns) if campaigns else None
                base = skill[agent.id] + rng.uniform(-1.5, 1.5)

                per_scores = []
                for c in criteria:
                    val = int(max(0, min(10, round(base + rng.uniform(-2, 2)))))
                    per_scores.append((c, val))

                # Nadiren sifirlayici ihlal (KVKK/kimlik kritik esik alti)
                zeroed = False
                for c, val in per_scores:
                    if c.is_critical and rng.random() < 0.04:
                        zeroed = True
                is_crisis = rng.random() < 0.06
                raw = sum(v * c.weight for c, v in per_scores)
                total = 0.0 if zeroed else round(raw / (total_weight * 10) * 100, 1)
                csat = 1.0 if zeroed else round(min(5, max(1, total / 20 + rng.uniform(-0.4, 0.4))), 1)
                sent_end = "olumsuz" if total < 55 else ("olumlu" if total >= 78 else "notr")

                call = Call(
                    tenant_id=tenant_id,
                    # Uzanti YOK: bu kayitlarin gercek ses/metin dosyasi yoktur,
                    # yalnizca dashboard'u doldurmak icin uretilmis sentetik satirlardir.
                    # ".wav" demek kullaniciyi "neden dinleyemiyorum?" diye yaniltiyordu.
                    filename=f"[sentetik] {agent.name} · {days_ago} gun once #{rng.randint(1000,9999)}",
                    audio_path="",
                    channel=channel,
                    agent_id=agent.id,
                    campaign_id=campaign.id if campaign else None,
                    status=CallStatus.done,
                    duration_sec=rng.uniform(90, 600),
                    category=rng.choice(categories),
                    total_score=total,
                    zeroed=zeroed,
                    is_crisis=is_crisis,
                    predicted_csat=csat,
                    summary="Sentetik gecmis demo cagrisi (dashboard doldurma).",
                    sentiment_start=rng.choice(sentiments),
                    sentiment_end=sent_end,
                    created_at=when,
                    processed_at=when,
                )
                db.add(call)
                db.flush()
                for c, val in per_scores:
                    db.add(Score(
                        call_id=call.id, criterion_id=c.id, criterion_name=c.name,
                        criterion_group=c.group, weight=c.weight, score=val,
                        rationale="Sentetik gecmis puan.", evidence="",
                    ))
                created += 1
        db.commit()
    return created
