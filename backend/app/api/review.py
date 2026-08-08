"""QA ornekleme & inceleme atamasi + kocluk etkinlik API'si (Dalga 2b + 2c)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import CurrentUser, require_staff
from ..models import (
    ManualEvaluation,
    ReviewAssignment,
    ReviewReason,
    ReviewStatus,
    Role,
    User,
)
from ..schemas import (
    CoachingEffectivenessOut,
    ReviewAssignmentOut,
    ReviewStatsOut,
    SampleRequest,
)
from ..services import coaching_effect, sampling

router = APIRouter(prefix="/api/v1/review", tags=["review"])


# ---------------------------------------------------------------------------
# QA ornekleme & atama (Dalga 2b)
# ---------------------------------------------------------------------------
@router.post("/sample", response_model=list[ReviewAssignmentOut])
def create_sample(body: SampleRequest, db: Session = Depends(get_db),
                  user: CurrentUser = Depends(require_staff)):
    """Stratejiye gore cagri ornekleyip bir uzmana atar (admin/supervisor/quality)."""
    if user.role == Role.agent:
        raise HTTPException(403, "Temsilci inceleme atayamaz")
    # Reviewer ayni tenant'ta personel olmali
    reviewer = db.get(User, body.reviewer_id)
    if reviewer is None or reviewer.tenant_id != user.tenant_id or reviewer.role == Role.agent:
        raise HTTPException(400, "Gecersiz inceleyici (ayni tenant'ta personel olmali)")
    assignments = sampling.sample_and_assign(
        db, tenant_id=user.tenant_id, reviewer_id=body.reviewer_id,
        reason=ReviewReason(body.reason), count=body.count, assigner_id=user.id,
    )
    return assignments


@router.get("/mine", response_model=list[ReviewAssignmentOut])
def my_reviews(only_open: bool = False, db: Session = Depends(get_db),
               user: CurrentUser = Depends(require_staff)):
    """Bana atanmis incelemeler."""
    q = db.query(ReviewAssignment).filter(
        ReviewAssignment.tenant_id == user.tenant_id,
        ReviewAssignment.reviewer_id == user.id,
    )
    if only_open:
        q = q.filter(ReviewAssignment.status != ReviewStatus.completed)
    return q.order_by(ReviewAssignment.created_at.desc()).limit(200).all()


@router.get("/stats", response_model=ReviewStatsOut)
def stats(db: Session = Depends(get_db), user: CurrentUser = Depends(require_staff)):
    return sampling.review_stats(db, user.tenant_id)


@router.post("/{assignment_id}/complete", response_model=ReviewAssignmentOut)
def complete(assignment_id: int, evaluation_id: int | None = None,
             db: Session = Depends(get_db), user: CurrentUser = Depends(require_staff)):
    """Incelemeyi tamamla (opsiyonel olarak bir ManualEvaluation'a bagla)."""
    a = db.query(ReviewAssignment).filter(
        ReviewAssignment.id == assignment_id,
        ReviewAssignment.tenant_id == user.tenant_id,
    ).first()
    if a is None:
        raise HTTPException(404, "Inceleme atamasi bulunamadi")
    if a.reviewer_id != user.id and user.role not in (Role.admin, Role.supervisor):
        raise HTTPException(403, "Yalnizca atanan uzman veya yonetici tamamlayabilir")
    ev = None
    if evaluation_id is not None:
        ev = db.get(ManualEvaluation, evaluation_id)
        if ev is None or ev.tenant_id != user.tenant_id:
            raise HTTPException(400, "Gecersiz degerlendirme")
    sampling.complete_assignment(db, a, ev)
    db.refresh(a)
    return a


# ---------------------------------------------------------------------------
# Kocluk etkinlik dongusu (Dalga 2c)
# ---------------------------------------------------------------------------
@router.get("/coaching-effectiveness", response_model=CoachingEffectivenessOut)
def coaching_effectiveness(db: Session = Depends(get_db),
                           user: CurrentUser = Depends(require_staff)):
    """Kocluk gercekten ise yariyor mu? Kocluk oncesi/sonrasi puan degisimi."""
    return coaching_effect.effectiveness_report(db, user.tenant_id)
