"""FAZ 4 DoD — kokpit ilk yükleme < 2 sn (1000 çağrılık veriyle ölçülmüş).

Sentetik yük üretir (LLM/STT yok — yalnız DB satırı), sonra kokpit ve analitik
uçlarını ölçer. Yük ayrı bir `__perf__` kiracısına yazılır; gerçek veriye
dokunmaz ve koşum sonunda silinir.

Kullanım (container içinde):
    python scripts/perf_check.py [--calls 1000]
"""

from __future__ import annotations

import argparse
import random
import statistics
import sys
import time
from datetime import datetime, timedelta

sys.path.insert(0, "/srv")

from app.db import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    Agent, Alert, AlertType, Call, CallStatus, Channel, QAState, Score, Team, Tenant, Violation,
)

PERF_TENANT = "__perf__"
HEDEF_SN = 2.0


def hazirla(db, n: int) -> tuple[Tenant, list[Agent]]:
    t = db.query(Tenant).filter(Tenant.name == PERF_TENANT).first()
    if t is not None:
        db.query(Call).filter(Call.tenant_id == t.id).delete()
        db.query(Agent).filter(Agent.tenant_id == t.id).delete()
        db.commit()
    else:
        t = Tenant(name=PERF_TENANT, slug="perf")
        db.add(t)
        db.flush()

    team = db.query(Team).filter(Team.tenant_id == t.id).first()
    if team is None:
        team = Team(tenant_id=t.id, name="Perf Takimi")
        db.add(team)
        db.flush()

    agents = [Agent(tenant_id=t.id, name=f"perf.agent{i}", team_id=team.id) for i in range(12)]
    db.add_all(agents)
    db.flush()

    rng = random.Random(42)
    simdi = datetime.utcnow()
    for i in range(n):
        a = agents[i % len(agents)]
        c = Call(
            tenant_id=t.id, agent_id=a.id, filename=f"perf{i}.wav",
            audio_path=f"perf://{i}", channel=Channel.voice,
            status=CallStatus.done, qa_state=QAState.final,
            total_score=round(rng.uniform(45, 99), 1),
            predicted_csat=round(rng.uniform(1, 5), 1),
            customer_effort=round(rng.uniform(1, 5), 1),
            duration_sec=rng.uniform(60, 400),
            category=rng.choice(["fatura", "iptal", "ariza", "sikayet", "bilgi"]),
            emotion=rng.choice(["ofke", "notr", "memnuniyet", "endise"]),
            churn_risk=rng.choice(["dusuk", "orta", "yuksek"]),
            is_crisis=rng.random() < 0.05,
            zeroed=rng.random() < 0.04,
            intent_tags=[rng.choice(["fatura-itiraz", "teknik-ariza", "iptal-tehdidi"])],
            metrics={"temsilci_konusma_orani": rng.uniform(40, 70),
                     "temsilci_kesinti": rng.randint(0, 4),
                     "sessizlik_sn": rng.uniform(1, 30)},
            created_at=simdi - timedelta(days=rng.randint(0, 60)),
            finalized_at=simdi,
        )
        db.add(c)
        if i % 200 == 0:
            db.flush()
    db.commit()
    return t, agents


def olc(ad: str, fn, tekrar: int = 5) -> dict:
    sureler = []
    for _ in range(tekrar):
        t0 = time.perf_counter()
        fn()
        sureler.append(time.perf_counter() - t0)
    return {
        "ad": ad,
        "medyan_sn": round(statistics.median(sureler), 3),
        "en_kotu_sn": round(max(sureler), 3),
        "hedef_saglandi": max(sureler) < HEDEF_SN,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--calls", type=int, default=1000)
    ap.add_argument("--keep", action="store_true", help="Perf verisini silme")
    args = ap.parse_args()

    db = SessionLocal()
    print(f"{args.calls} cagrilik sentetik yuk hazirlaniyor...", flush=True)
    t0 = time.perf_counter()
    tenant, agents = hazirla(db, args.calls)
    print(f"  hazirlandi ({time.perf_counter() - t0:.1f} sn)", flush=True)

    from app.api import supervisor
    from app.services import analytics, coaching_effect

    sonuclar = [
        olc("kokpit: liderlik tablosu",
            lambda: supervisor._leaderboard_rows(db, tenant.id, None, None)),
        olc("analitik: zaman serisi (30 gun)",
            lambda: analytics.metric_timeseries(db, tenant.id, "score", days=30)),
        olc("analitik: VoC trendi",
            lambda: analytics.category_trends(db, tenant.id, days=14)),
        olc("analitik: duygu dagilimi",
            lambda: analytics.emotion_distribution(db, tenant.id)),
        olc("analitik: kohort karsilastirma",
            lambda: analytics.cohort_compare(db, tenant.id, "team")),
        olc("kocluk etkinligi",
            lambda: coaching_effect.effectiveness_report(db, tenant.id)),
    ]

    print("\n" + "=" * 62)
    print(f"KOKPIT PERFORMANSI ({args.calls} cagri, hedef < {HEDEF_SN} sn)")
    print("=" * 62)
    print(f"{'sorgu':<34}{'medyan':>9}{'en kotu':>10}{'durum':>9}")
    hepsi_ok = True
    for s in sonuclar:
        durum = "OK" if s["hedef_saglandi"] else "YAVAS"
        hepsi_ok &= s["hedef_saglandi"]
        print(f"{s['ad']:<34}{s['medyan_sn']:>9.3f}{s['en_kotu_sn']:>10.3f}{durum:>9}")

    toplam = sum(s["medyan_sn"] for s in sonuclar)
    print("-" * 62)
    print(f"{'kokpit toplami (tum sorgular)':<34}{toplam:>9.3f}"
          f"{'':>10}{'OK' if toplam < HEDEF_SN else 'YAVAS':>9}")

    if not args.keep:
        db.query(Call).filter(Call.tenant_id == tenant.id).delete()
        db.query(Agent).filter(Agent.tenant_id == tenant.id).delete()
        db.commit()
        print("\nPerf verisi temizlendi.")
    db.close()
    return 0 if (hepsi_ok and toplam < HEDEF_SN) else 1


if __name__ == "__main__":
    raise SystemExit(main())
