"""Kocluk etkinlik dongusu: kocluk gercekten ise yariyor mu?

Sektorde 'closed-loop coaching': bir temsilciye kocluk atanir, sonra o
temsilcinin puani gercekten arttri mi diye OLCULUR. Kocluk tarihinden onceki
ve sonraki pencerede temsilcinin ortalama puani karsilastirilir.

Bu saf analitiktir — yeni model gerektirmez; mevcut CoachingTask + Call
verisinden hesaplanir. Boylece "hangi kocluk konulari/koclar ise yariyor"
gorulur ve kocluk yatirimni yonlendirir.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import Agent, Call, CallStatus, CoachingTask, TaskStatus, User

# Kocluk tarihinin oncesi/sonrasi kac gunluk pencere karsilastirilir
WINDOW_DAYS = 14
# Anlamli karsilastirma icin her pencerede en az bu kadar cagri olmali
MIN_CALLS = 3


def _avg_score(db: Session, agent_id: int, start, end) -> tuple[float | None, int]:
    avg, n = db.query(func.avg(Call.total_score), func.count(Call.id)).filter(
        Call.agent_id == agent_id,
        Call.status == CallStatus.done,
        Call.total_score.isnot(None),
        Call.created_at >= start,
        Call.created_at < end,
    ).one()
    return (float(avg) if avg is not None else None), int(n)


def task_effect(db: Session, task: CoachingTask) -> dict | None:
    """Tek bir tamamlanmis kocluk gorevinin etkisini olcer.

    Kocluk tamamlanma tarihini referans alir (yoksa olusturma tarihi):
    [ref - WINDOW, ref) vs [ref, ref + WINDOW) ortalama puan farki.
    Yeterli veri yoksa None doner.
    """
    ref = task.completed_at or task.created_at
    before_avg, before_n = _avg_score(db, task.assignee_agent_id, ref - timedelta(days=WINDOW_DAYS), ref)
    after_avg, after_n = _avg_score(db, task.assignee_agent_id, ref, ref + timedelta(days=WINDOW_DAYS))
    if before_n < MIN_CALLS or after_n < MIN_CALLS or before_avg is None or after_avg is None:
        return None
    return {
        "task_id": task.id,
        "agent_id": task.assignee_agent_id,
        "ref_date": ref.isoformat(),
        "before_avg": round(before_avg, 1),
        "after_avg": round(after_avg, 1),
        "delta": round(after_avg - before_avg, 1),
        "before_n": before_n,
        "after_n": after_n,
        "improved": after_avg > before_avg,
    }


def effectiveness_report(db: Session, tenant_id: int) -> dict:
    """Tenant genelinde kocluk etkinligi ozeti.

    - Olculebilir (yeterli veri olan) tamamlanmis kocluklarin etki listesi
    - Genel: kac kocluk ise yaradi, ortalama puan degisimi
    - Temsilci bazli ozet
    """
    tasks = (
        db.query(CoachingTask)
        .filter(
            CoachingTask.tenant_id == tenant_id,
            CoachingTask.status == TaskStatus.done,
        )
        .all()
    )
    effects = [e for t in tasks if (e := task_effect(db, t)) is not None]

    agent_names = {
        a.id: a.name for a in db.query(Agent).filter(Agent.tenant_id == tenant_id).all()
    }
    for e in effects:
        e["agent_name"] = agent_names.get(e["agent_id"], f"#{e['agent_id']}")

    measurable = len(effects)
    improved = sum(1 for e in effects if e["improved"])

    # B13: OLCULEBILIR KOCLUK YOKSA SIFIR GOSTERME.
    #
    # Panel "0 olculebilir kocluk / %0 iyilesme / Veri yok" gosteriyordu.
    # "%0 iyilesme" bir SONUCTUR ve "kocluk ise yaramiyor" demektir; oysa
    # gercek durum "henuz olculemedi"dir. Ikisini ayirmak zorunludur.
    olculebilir_mi = measurable > 0
    if not olculebilir_mi:
        gerekli = (
            f"Ilk olcum icin kocluk sonrasi en az {WINDOW_DAYS} gun gecmeli ve "
            f"temsilcinin oncesi/sonrasi pencerelerinde en az {MIN_CALLS}'er "
            "puanlanmis cagrisi olmali."
        )
        if not tasks:
            aciklama = "Henuz tamamlanmis kocluk gorevi yok. " + gerekli
        else:
            aciklama = (
                f"{len(tasks)} kocluk tamamlandi ancak henuz hicbiri olculebilir "
                f"degil. {gerekli}"
            )
    else:
        aciklama = ""

    return {
        "olculebilir": olculebilir_mi,
        "aciklama": aciklama,
        "measurable_count": measurable,
        "total_completed": len(tasks),
        # Olculemiyorsa SAYI URETME — None, "veri yok" demektir; 0 ise "sonuc kotu".
        "improved_count": improved if olculebilir_mi else None,
        "improved_rate": round(100 * improved / measurable, 1) if olculebilir_mi else None,
        "avg_delta": (round(sum(e["delta"] for e in effects) / measurable, 1)
                      if olculebilir_mi else None),
        "window_days": WINDOW_DAYS,
        "min_calls": MIN_CALLS,
        "effects": sorted(effects, key=lambda e: e["delta"], reverse=True),
    }
