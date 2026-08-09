"""FAZ 6.3 — Satış demosu verisi.

`make demo` bunu çağırır. Amaç: **satış görüşmesinde anlatılacak bir hikâye.**

## Neden sentetik puanlı veri, gerçek işleme değil?

200 çağrıyı gerçekten işlemek (STT + LLM) yerel donanımda saatler sürer ve
demo öncesi kimse bunu bekleyemez. Bu betik puanları **doğrudan** yazar —
ama motorun ürettiğiyle aynı şekle sahip: kanıt, karar, güven, katman,
sıfırlama gerekçesi, QA durumu.

Gerçek uçtan uca işleme ayrı komutla yapılır (`scripts/load-examples.ps1`).

## Hikâye

Demo verisi **zaman içinde iyileşme** gösterir: ilk hafta ortalama ~72,
son hafta ~88. Koçluk görevleri araya serpiştirilir ve koçluk alan
temsilcilerin puanı sonrasında yükselir — satışta anlatılacak şey budur.

Puan dağılımı **çan eğrisidir**, mükemmel değil: birkaç sıfırlayıcı ihlal,
birkaç kriz, gerçekçi bir dağılım.

Demo verisi `is_demo` yerine ayrı bir kiracı ile ayrılır — böylece
`make demo-reset` gerçek veriye dokunmadan temizler.
"""

from __future__ import annotations

import argparse
import random
import sys
from datetime import datetime, timedelta

sys.path.insert(0, "/srv")

from app.db import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    Agent, Alert, Call, CallStatus, Channel, CoachingTask, Criterion, QAState,
    Score, Segment, TaskStatus, Team, Tenant, User, Violation,
)
from app.security import hash_password  # noqa: E402
from app.services import alert_engine  # noqa: E402

# Windows konsolu varsayilan olarak cp1254 kullanir ve "≥", "→" gibi
# karakterlerde COKER (UnicodeEncodeError). Betigin ciktisi Turkce oldugu
# icin bu kacinilmaz; cozum ciktiyi UTF-8'e sabitlemek.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


DEMO_SLUG = "demo"
GUN = 30
HEDEF_CAGRI = 220

TEMSILCILER = [
    "ayse.yilmaz", "mehmet.kaya", "zeynep.demir", "can.ozturk", "elif.sahin",
    "burak.celik", "deniz.yildiz", "gizem.arslan", "pelin.acar", "onur.kurt",
    "seda.gunes", "kerem.aydin",
]

KATEGORI = ["fatura", "iptal", "ariza", "sikayet", "bilgi"]
DUYGU = ["ofke", "hayal_kirikligi", "endise", "memnuniyet", "notr", "minnettarlik"]

OZETLER = {
    "fatura": "Müşteri faturasındaki tanımadığı kalemi sordu; temsilci kalemi açıkladı ve iadeyi başlattı.",
    "iptal": "Müşteri iptal talebinde bulundu; temsilci ihtiyacı analiz edip uygun tarifeye geçiş önerdi.",
    "ariza": "Müşteri internet arızası bildirdi; temsilci hattı test edip profili yeniledi, sorun çözüldü.",
    "sikayet": "Müşteri gecikmiş teknisyen randevusundan şikâyetçi oldu; temsilci özür dileyip kaydı öncelikli açtı.",
    "bilgi": "Müşteri yurt dışı kullanım koşullarını sordu; temsilci paket seçeneklerini açıkladı.",
}

KOCLUK = [
    ("Aktif dinleme", "Müşterinin sözünü kesmeden dinleyip anladığını özetleyerek teyit et."),
    ("Kapanış disiplini", "Her çağrıyı 'başka bir konuda yardımcı olabilir miyim?' ile kapat."),
    ("İhtiyaç analizi", "Çözüm önermeden önce müşterinin gerçek ihtiyacını netleştiren soru sor."),
]


def _kalite_egrisi(gun_once: int, rng: random.Random) -> float:
    """Zaman içinde iyileşme: 30 gün önce ~72, bugün ~88 + gürültü.

    Satışta anlatılacak hikâye bu; düz bir dağılım "koçluk işe yarıyor"
    demez.
    """
    ilerleme = (GUN - gun_once) / GUN          # 0 (eski) → 1 (yeni)
    taban = 72 + ilerleme * 16
    return max(0, min(100, rng.gauss(taban, 7)))


def temizle(db, tenant: Tenant) -> int:
    n = db.query(Call).filter(Call.tenant_id == tenant.id).delete()
    db.query(CoachingTask).filter(CoachingTask.tenant_id == tenant.id).delete()
    db.commit()
    return n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--calls", type=int, default=HEDEF_CAGRI)
    ap.add_argument("--reset", action="store_true", help="Yalniz temizle, uretme")
    args = ap.parse_args()

    db = SessionLocal()
    tenant = db.query(Tenant).filter(Tenant.slug == DEMO_SLUG).first()
    if tenant is None:
        print(f"'{DEMO_SLUG}' kiracisi yok — once `docker compose up -d` ile seed calistirin.")
        return 1

    silinen = temizle(db, tenant)
    print(f"{silinen} eski demo cagrisi temizlendi")
    if args.reset:
        print("Demo verisi sifirlandi.")
        return 0

    criteria = (
        db.query(Criterion)
        .filter(Criterion.tenant_id == tenant.id, Criterion.is_active.is_(True))
        .order_by(Criterion.id)
        .all()
    )
    if not criteria:
        print("Rubrik bos — kriter olmadan demo uretilemez.")
        return 1

    team = db.query(Team).filter(Team.tenant_id == tenant.id).first()
    agents = {a.name: a for a in db.query(Agent).filter(Agent.tenant_id == tenant.id)}
    for ad in TEMSILCILER:
        if ad not in agents:
            a = Agent(tenant_id=tenant.id, name=ad, team_id=team.id if team else None)
            db.add(a)
            db.flush()
            agents[ad] = a

    # Koçluk alan temsilciler: puanları koçluktan SONRA belirgin yükselecek
    rng = random.Random(2026)
    koclananlar = set(rng.sample(TEMSILCILER, 4))
    koclu_gunu = 16  # ~yarida kocluk verildi

    simdi = datetime.utcnow()
    kritikler = [c for c in criteria if c.is_critical]
    uretilen = zeroed = kriz = kuyrukta = 0

    for i in range(args.calls):
        gun_once = rng.randint(0, GUN - 1)
        ad = TEMSILCILER[i % len(TEMSILCILER)]
        agent = agents[ad]
        tarih = simdi - timedelta(days=gun_once, hours=rng.randint(8, 18))

        taban = _kalite_egrisi(gun_once, rng)
        # Koçluk etkisi: koçluk sonrası (gun_once < koclu_gunu) +9 puan
        if ad in koclananlar and gun_once < koclu_gunu:
            taban = min(100, taban + 9)

        kategori = rng.choice(KATEGORI)
        sifirla = rng.random() < 0.045
        krizli = rng.random() < 0.06

        call = Call(
            tenant_id=tenant.id, agent_id=agent.id,
            filename=f"{ad}_{kategori}_{i:03d}.wav",
            audio_path=f"demo://{i}", channel=Channel.voice,
            status=CallStatus.done,
            duration_sec=round(rng.uniform(75, 420), 1),
            category=kategori,
            summary=OZETLER[kategori],
            predicted_csat=round(max(1, min(5, taban / 20 + rng.gauss(0, 0.4))), 1),
            customer_effort=round(rng.uniform(1, 5), 1),
            emotion=rng.choice(DUYGU),
            sentiment_start="olumsuz" if kategori in ("sikayet", "ariza") else "notr",
            sentiment_end="olumlu" if taban >= 80 else "notr",
            sentiment_trajectory="yukselen" if taban >= 80 else "sabit",
            churn_risk="yuksek" if krizli else ("orta" if taban < 70 else "dusuk"),
            is_crisis=krizli,
            intent_tags=[f"{kategori}-talebi"],
            coaching=("Müşteriyi kesmeden dinleyip anladığını özetle."
                      if taban < 80 else "Çağrı akışı örnek nitelikte; bu tempoyu koru."),
            next_action="takip gerekmiyor" if taban >= 80 else "48 saat içinde takip araması yap",
            created_at=tarih, processed_at=tarih,
        )
        db.add(call)
        db.flush()

        # Kriter puanlari — toplam `taban` etrafinda dagilir
        toplam_agirlik = sum(c.weight for c in criteria)
        for c in criteria:
            puan = round(max(0, min(10, rng.gauss(taban / 10, 1.1))))
            karar = "met" if puan >= 8 else ("partially_met" if puan >= 5 else "not_met")
            db.add(Score(
                call_id=call.id, criterion_id=c.id, criterion_name=c.name,
                criterion_group=c.group, weight=c.weight, score=puan,
                rationale=f"{c.name} kriteri çağrı akışında değerlendirildi.",
                evidence=OZETLER[kategori][:90],
                evidence_ts=round(rng.uniform(2, 60), 1),
                decision=karar, confidence=round(rng.uniform(0.75, 0.98), 2),
                evidence_verified=True,
                source_layer="A" if c.check_key else "B",
            ))

        if sifirla and kritikler:
            k = rng.choice(kritikler)
            call.total_score = 0.0
            call.zeroed = True
            call.zeroing_reason = f"{k.name}: zorunlu adım uygulanmadı."
            call.zeroing_evidence = "Temsilcinin repliklerinde ilgili ifade bulunamadı."
            call.zeroing_criterion_id = k.id
            zeroed += 1
            db.add(Violation(
                tenant_id=tenant.id, call_id=call.id, kind="compliance",
                category="uyum", severity="yuksek", term=k.name,
                speaker="temsilci", evidence=call.zeroing_evidence,
            ))
            alert_engine.emit(db, tenant.id, agent.team_id, alert_engine.zeroing_alert(
                call.id, k.name, call.zeroing_reason, call.zeroing_evidence, 12.0))
        else:
            call.total_score = round(taban, 1)

        if krizli:
            kriz += 1
            db.add(Violation(
                tenant_id=tenant.id, call_id=call.id, kind="crisis",
                category="eskalasyon", severity="yuksek", term="",
                speaker="musteri", evidence="Bu işi avukatıma vereceğim.",
                ts_sec=48.0,
            ))
            alert_engine.emit(db, tenant.id, agent.team_id, alert_engine.crisis_alert(
                call.id, "Bu işi avukatıma vereceğim.", 48.0))

        # QA durumu: riskli olanlar kuyrukta, digerleri kesinlesmis
        if call.zeroed or krizli:
            call.qa_state = QAState.human_queue
            call.queue_reasons = ["critical"] if call.zeroed else ["crisis"]
            kuyrukta += 1
        else:
            call.qa_state = QAState.final
            call.finalized_at = tarih

        uretilen += 1
        if i % 50 == 0:
            db.flush()

    # Kocluk gorevleri — etkisi olculebilsin diye koclanan temsilcilere
    supervisor = db.query(User).filter(
        User.tenant_id == tenant.id, User.role.in_(["supervisor", "admin"])).first()
    for ad in koclananlar:
        konu, aciklama = rng.choice(KOCLUK)
        # Kocluk gorevi bir CAGRIYA baglidir; o temsilcinin dusuk puanli bir
        # cagrisi secilir — "neden kocluk verildi" izlenebilir olsun.
        dayanak = (
            db.query(Call)
            .filter(Call.tenant_id == tenant.id, Call.agent_id == agents[ad].id)
            .order_by(Call.total_score.asc())
            .first()
        )
        if dayanak is None or supervisor is None:
            continue
        db.add(CoachingTask(
            tenant_id=tenant.id, call_id=dayanak.id,
            assigner_id=supervisor.id, assignee_agent_id=agents[ad].id,
            note=f"{konu}: {aciklama}", status=TaskStatus.done,
            created_at=simdi - timedelta(days=koclu_gunu + 1),
            completed_at=simdi - timedelta(days=koclu_gunu),
        ))

    db.commit()

    ortalama = (
        db.query(Call).filter(Call.tenant_id == tenant.id, Call.total_score.isnot(None)).count()
    )
    print(f"""
Demo verisi hazir:
  cagri           : {uretilen}
  temsilci        : {len(TEMSILCILER)}
  gun araligi     : {GUN}
  sifirlayici     : {zeroed}
  kriz            : {kriz}
  inceleme kuyrugu: {kuyrukta}
  kocluk gorevi   : {len(koclananlar)} (etkisi olculebilir)
  hikaye          : ilk hafta ~72 -> son hafta ~88 ortalama
  puanli kayit    : {ortalama}
""")
    db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
