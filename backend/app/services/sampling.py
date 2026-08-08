"""QA ornekleme & atama: cagrilarin bir kismini insana inceletme.

Sektorde 'QA sampling': %100 AI puanliyor ama insan da bir ornekleme uzerinden
denetler. Uc secim stratejisi:
  - random         : kalite guvence icin tarafsiz rastgele ornek
  - low_confidence : AI'nin kendiyle celistigi (duygu-sonuc uyumsuzlugu) cagrilar
  - critical       : sifirlayici ihlal / kriz — insan teyidi sart

Atama, ManualEvaluation ile birlesir: uzman inceleyip puanladiginda atama
'completed' olur ve kalibrasyon/uyum olcumune veri saglar.
"""

from __future__ import annotations

import random
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import (
    Call,
    CallStatus,
    ManualEvaluation,
    ReviewAssignment,
    ReviewReason,
    ReviewStatus,
)


def _already_assigned_call_ids(db: Session, tenant_id: int, reviewer_id: int) -> set[int]:
    rows = db.execute(
        select(ReviewAssignment.call_id).where(
            ReviewAssignment.tenant_id == tenant_id,
            ReviewAssignment.reviewer_id == reviewer_id,
        )
    ).scalars().all()
    return set(rows)


def eligible_calls(db: Session, tenant_id: int, reason: ReviewReason):
    """Verilen stratejiye gore incelemeye UYGUN (done) cagrilari dondurur."""
    q = db.query(Call).filter(
        Call.tenant_id == tenant_id,
        Call.status == CallStatus.done,
    )
    if reason == ReviewReason.low_confidence:
        q = q.filter(Call.emotion_mismatch.is_(True))
    elif reason == ReviewReason.critical:
        q = q.filter((Call.zeroed.is_(True)) | (Call.is_crisis.is_(True)))
    # random ve manual: tum done cagrilar uygun
    return q


def sample_and_assign(
    db: Session,
    tenant_id: int,
    reviewer_id: int,
    reason: ReviewReason,
    count: int,
    assigner_id: int | None = None,
    rng: random.Random | None = None,
) -> list[ReviewAssignment]:
    """Stratejiye gore `count` cagri secip reviewer'a atar.

    - Zaten bu reviewer'a atanmis cagrilar TEKRAR atanmaz (mukerrer onleme).
    - random stratejisinde secim rastgele; digerlerinde en yeni cagrilar oncelikli.
    - Uygun cagri sayisi count'tan azsa, bulunan kadarini atar (hata degil).
    """
    rng = rng or random.Random()
    existing = _already_assigned_call_ids(db, tenant_id, reviewer_id)
    pool = [c for c in eligible_calls(db, tenant_id, reason).all() if c.id not in existing]

    if reason == ReviewReason.random:
        rng.shuffle(pool)
    else:
        pool.sort(key=lambda c: c.created_at or datetime.min, reverse=True)

    chosen = pool[: max(0, count)]
    assignments = []
    for call in chosen:
        a = ReviewAssignment(
            tenant_id=tenant_id,
            call_id=call.id,
            reviewer_id=reviewer_id,
            assigner_id=assigner_id,
            reason=reason,
            status=ReviewStatus.assigned,
        )
        db.add(a)
        assignments.append(a)
    db.commit()
    for a in assignments:
        db.refresh(a)
    return assignments


def complete_assignment(
    db: Session, assignment: ReviewAssignment, evaluation: ManualEvaluation | None = None
) -> None:
    assignment.status = ReviewStatus.completed
    assignment.completed_at = datetime.utcnow()
    if evaluation is not None:
        assignment.evaluation_id = evaluation.id
    db.commit()


def review_stats(db: Session, tenant_id: int) -> dict:
    """Inceleme kuyrugu ozeti: durum bazli sayimlar + tamamlanma orani."""
    rows = db.execute(
        select(ReviewAssignment.status, func.count(ReviewAssignment.id))
        .where(ReviewAssignment.tenant_id == tenant_id)
        .group_by(ReviewAssignment.status)
    ).all()
    counts = {status.value: 0 for status in ReviewStatus}
    for status, n in rows:
        key = status.value if hasattr(status, "value") else str(status)
        counts[key] = n
    total = sum(counts.values())
    done = counts.get("completed", 0)
    return {
        "counts": counts,
        "total": total,
        "completion_rate": round(100 * done / total, 1) if total else 0.0,
    }
