"""Temsilci self-servis + gamification + uyum paketleri API (3c, 3d, 4a)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import CurrentUser, get_current_user, require_staff
from ..models import Call, Challenge, Role, SelfAssessment
from ..schemas import (
    ChallengeCreate,
    ChallengeOut,
    CompliancePackOut,
    GamificationOut,
    SelfAssessmentCreate,
    SelfAssessmentOut,
)
from ..services import compliance_packs, gamification

router = APIRouter(prefix="/api/v1", tags=["selfservice"])


# ---------------------------------------------------------------------------
# 3c — Temsilci self-servis: kendi karnesi + oz-degerlendirme
# ---------------------------------------------------------------------------
@router.get("/me/gamification", response_model=GamificationOut)
def my_gamification(db: Session = Depends(get_db),
                    user: CurrentUser = Depends(get_current_user)):
    """Temsilcinin kendi puani, serisi ve aktif challenge'lari."""
    if user.agent_id is None:
        raise HTTPException(400, "Bu kullanici bir temsilciye bagli degil")
    return gamification.agent_gamification(db, user.tenant_id, user.agent_id, user.team_id)


@router.post("/me/self-assessment", response_model=SelfAssessmentOut, status_code=201)
def create_self_assessment(body: SelfAssessmentCreate, db: Session = Depends(get_db),
                           user: CurrentUser = Depends(get_current_user)):
    """Temsilci kendi cagrisini degerlendirir (QA'dan once/bagimsiz)."""
    if user.agent_id is None:
        raise HTTPException(400, "Yalnizca temsilci oz-degerlendirme yapabilir")
    call = db.query(Call).filter(
        Call.id == body.call_id, Call.tenant_id == user.tenant_id).first()
    if call is None:
        raise HTTPException(404, "Cagri bulunamadi")
    if call.agent_id != user.agent_id:
        raise HTTPException(403, "Yalnizca kendi cagrinizi degerlendirebilirsiniz")
    existing = db.query(SelfAssessment).filter(
        SelfAssessment.call_id == body.call_id,
        SelfAssessment.agent_id == user.agent_id).first()
    if existing:
        raise HTTPException(409, "Bu cagri icin zaten oz-degerlendirme yaptiniz")
    sa = SelfAssessment(
        tenant_id=user.tenant_id, call_id=body.call_id, agent_id=user.agent_id,
        self_score=body.self_score, note=body.note,
    )
    db.add(sa)
    db.commit()
    db.refresh(sa)
    return sa


@router.get("/calls/{call_id}/self-assessment", response_model=SelfAssessmentOut | None)
def get_self_assessment(call_id: int, db: Session = Depends(get_db),
                        user: CurrentUser = Depends(get_current_user)):
    q = db.query(SelfAssessment).filter(
        SelfAssessment.call_id == call_id, SelfAssessment.tenant_id == user.tenant_id)
    if user.role == Role.agent and user.agent_id is not None:
        q = q.filter(SelfAssessment.agent_id == user.agent_id)
    return q.first()


# ---------------------------------------------------------------------------
# 3d — Gamification yonetimi (challenge tanimlama)
# ---------------------------------------------------------------------------
@router.get("/challenges", response_model=list[ChallengeOut])
def list_challenges(db: Session = Depends(get_db),
                    user: CurrentUser = Depends(get_current_user)):
    """Aktif challenge'lar + (temsilciyse) kendi ilerlemesi."""
    agent_id = user.agent_id or -1
    return gamification.active_challenges(db, user.tenant_id, agent_id, user.team_id)


@router.post("/challenges", response_model=ChallengeOut, status_code=201)
def create_challenge(body: ChallengeCreate, db: Session = Depends(get_db),
                     user: CurrentUser = Depends(require_staff)):
    """Yeni challenge tanimla (admin/supervisor/quality)."""
    if user.role == Role.agent:
        raise HTTPException(403, "Temsilci challenge olusturamaz")
    ch = Challenge(
        tenant_id=user.tenant_id, title=body.title, description=body.description,
        metric=body.metric, threshold=body.threshold, target=body.target,
        reward_points=body.reward_points, team_id=body.team_id, ends_at=body.ends_at,
    )
    db.add(ch)
    db.commit()
    db.refresh(ch)
    # Yeni challenge'in ilerleme alaniyla donmesi icin servis uzerinden dondur
    progress = gamification._challenge_progress(db, ch, user.agent_id or -1)
    return {
        "id": ch.id, "title": ch.title, "description": ch.description,
        "metric": ch.metric, "target": ch.target, "progress": progress,
        "completed": progress >= ch.target, "reward_points": ch.reward_points,
        "ends_at": ch.ends_at.isoformat() if ch.ends_at else None,
    }


# ---------------------------------------------------------------------------
# 4a — Uyum paketleri
# ---------------------------------------------------------------------------
@router.get("/compliance-packs", response_model=list[CompliancePackOut])
def compliance_pack_list(user: CurrentUser = Depends(require_staff)):
    """Built-in uyum paketlerini (KVKK/PCI/…) ve kurallarini listeler."""
    return compliance_packs.list_packs()
