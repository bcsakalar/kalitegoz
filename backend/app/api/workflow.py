"""Insan katmani is akislari: alarm, itiraz, kocluk gorevi, puan override, kalibrasyon."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import CurrentUser, get_current_user, require_roles, require_staff
from ..models import (
    Agent,
    Alert,
    Appeal,
    AppealStatus,
    Call,
    CoachingTask,
    QAState,
    Role,
    Score,
    TaskStatus,
)
from ..schemas import (
    AlertOut,
    AppealCreate,
    AppealOut,
    AppealResolve,
    CalibrationRow,
    CoachingTaskComplete,
    CoachingTaskCreate,
    CoachingTaskOut,
    ScoreOverride,
)
from ..services import audit, qa_workflow

router = APIRouter(prefix="/api/v1", tags=["workflow"])


# =====================================================================
# Alarmlar (supervisor/quality/admin gorur; supervisor kendi takimini)
# =====================================================================
@router.get("/alerts", response_model=list[AlertOut])
def list_alerts(only_unread: bool = False, db: Session = Depends(get_db),
                user: CurrentUser = Depends(require_staff)):
    q = db.query(Alert).filter(Alert.tenant_id == user.tenant_id)
    if user.role == Role.supervisor and user.team_id:
        q = q.filter((Alert.team_id == user.team_id) | (Alert.team_id.is_(None)))
    if only_unread:
        q = q.filter(Alert.is_read.is_(False))
    # Gecersizlesen alarmlar (yeniden puanlama sonrasi) kullaniciya GOSTERILMEZ
    q = q.filter(Alert.is_stale.is_(False))
    return q.order_by(Alert.created_at.desc()).limit(200).all()


@router.post("/alerts/{alert_id}/read", status_code=204)
def mark_alert_read(alert_id: int, db: Session = Depends(get_db),
                    user: CurrentUser = Depends(require_staff)):
    alert = db.query(Alert).filter(
        Alert.id == alert_id, Alert.tenant_id == user.tenant_id).first()
    if alert is None:
        raise HTTPException(404, "Alarm bulunamadi")
    alert.is_read = True
    db.commit()


# =====================================================================
# Puan override (kalite uzmani AI puanini duzeltir)
# =====================================================================
@router.post("/scores/{score_id}/override", status_code=204)
def override_score(score_id: int, body: ScoreOverride, request: Request,
                   db: Session = Depends(get_db),
                   user: CurrentUser = Depends(require_roles(Role.quality, Role.admin))):
    score = (
        db.query(Score).join(Call, Score.call_id == Call.id)
        .filter(Score.id == score_id, Call.tenant_id == user.tenant_id).first()
    )
    if score is None:
        raise HTTPException(404, "Puan bulunamadi")
    score.override_score = body.override_score
    score.override_reason = body.override_reason
    score.overridden_by = user.id
    score.overridden_at = datetime.utcnow()
    db.commit()
    audit.log(db, action="override_score", tenant_id=user.tenant_id, user_id=user.id,
              entity_type="score", entity_id=score.id,
              detail={"new": body.override_score, "reason": body.override_reason},
              ip=request.client.host if request.client else "")



def _record_appeal_as_calibration(db: Session, call, appeal, user_id: int) -> None:
    """Kabul edilen itirazi kalibrasyon ornegi olarak kaydet.

    Temsilci hakli cikti ise sistem (AI ya da kaliteci) yanilmis demektir; bu,
    prompt'a beslenecek en degerli sinyallerden biridir. En dusuk puanli kriter
    ornek olarak alinir — itirazin muhtemel konusu odur.
    """
    from ..models import Score, Segment
    from ..services import review_feedback

    dusuk = (
        db.query(Score)
        .filter(Score.call_id == call.id, Score.score.isnot(None))
        .order_by(Score.score.asc())
        .first()
    )
    if dusuk is None or dusuk.criterion_id is None:
        return
    segs = db.query(Segment).filter(Segment.call_id == call.id).order_by(Segment.idx).all()
    excerpt = " ".join(g.text for g in segs)[: review_feedback.EXCERPT_CHARS]
    hedef = min(10, (dusuk.override_score or dusuk.score or 0) + 2)
    review_feedback.record_correction(
        db, tenant_id=call.tenant_id, criterion_id=dusuk.criterion_id,
        call_id=call.id, excerpt=excerpt, ai_score=dusuk.score,
        human_score=hedef, reason_code="baglam_kacirildi",
        note=f"Temsilci itirazi kabul edildi: {appeal.reason[:200]}",
        user_id=user_id,
    )


# =====================================================================
# Itiraz akisi (temsilci acar, kalite uzmani karara baglar)
# =====================================================================
@router.post("/appeals", response_model=AppealOut, status_code=201)
def create_appeal(body: AppealCreate, db: Session = Depends(get_db),
                  user: CurrentUser = Depends(get_current_user)):
    if user.role != Role.agent:
        raise HTTPException(403, "Itirazi yalnizca temsilci acabilir")
    call = db.query(Call).filter(
        Call.id == body.call_id, Call.tenant_id == user.tenant_id).first()
    if call is None or call.agent_id != user.agent_id:
        raise HTTPException(404, "Cagri bulunamadi veya size ait degil")
    existing = db.query(Appeal).filter(
        Appeal.call_id == body.call_id, Appeal.status == AppealStatus.open).first()
    if existing:
        raise HTTPException(409, "Bu cagri icin zaten acik bir itiraz var")
    appeal = Appeal(tenant_id=user.tenant_id, call_id=body.call_id,
                    created_by=user.id, reason=body.reason)
    db.add(appeal)
    # FAZ 3.1: itiraz kesinlesmis bir puani bile yeniden acar; cagri
    # `itiraz_incelemede` durumuna gecer ve karneye ham puan olarak SAYILMAZ.
    qa_workflow.open_appeal(db, call, user_id=user.id, reason=body.reason)
    db.commit()
    db.refresh(appeal)
    return appeal


@router.get("/appeals", response_model=list[AppealOut])
def list_appeals(status: str | None = None, db: Session = Depends(get_db),
                 user: CurrentUser = Depends(get_current_user)):
    q = db.query(Appeal).filter(Appeal.tenant_id == user.tenant_id)
    if user.role == Role.agent:
        q = q.filter(Appeal.created_by == user.id)
    if status:
        q = q.filter(Appeal.status == status)
    return q.order_by(Appeal.created_at.desc()).all()


@router.post("/appeals/{appeal_id}/resolve", response_model=AppealOut)
def resolve_appeal(appeal_id: int, body: AppealResolve, request: Request,
                   db: Session = Depends(get_db),
                   user: CurrentUser = Depends(require_roles(Role.quality, Role.admin))):
    appeal = db.query(Appeal).filter(
        Appeal.id == appeal_id, Appeal.tenant_id == user.tenant_id).first()
    if appeal is None:
        raise HTTPException(404, "Itiraz bulunamadi")
    if appeal.status != AppealStatus.open:
        raise HTTPException(409, "Itiraz zaten karara baglanmis")
    if body.decision not in ("accepted", "rejected"):
        raise HTTPException(400, "Karar 'accepted' veya 'rejected' olmali")
    appeal.status = AppealStatus(body.decision)
    appeal.resolution_note = body.resolution_note
    appeal.resolver_id = user.id
    appeal.resolved_at = datetime.utcnow()

    call = db.get(Call, appeal.call_id)
    if call is not None:
        # Kabul edilen itiraz KALIBRASYON VERISIDIR: puan yanlisti demektir.
        if body.decision == "accepted":
            _record_appeal_as_calibration(db, call, appeal, user.id)
        qa_workflow.transition(
            db, call, QAState.final, user_id=user.id, reason="itiraz_sonuclandi",
            detail={"karar": body.decision, "appeal_id": appeal.id},
        )
    db.commit()
    db.refresh(appeal)
    audit.log(db, action="resolve_appeal", tenant_id=user.tenant_id, user_id=user.id,
              entity_type="appeal", entity_id=appeal.id, detail={"decision": body.decision},
              ip=request.client.host if request.client else "")
    return appeal


# =====================================================================
# Kocluk gorevi (supervisor atar, temsilci tamamlar)
# =====================================================================
@router.post("/coaching", response_model=CoachingTaskOut, status_code=201)
def create_coaching(body: CoachingTaskCreate, db: Session = Depends(get_db),
                    user: CurrentUser = Depends(require_roles(Role.supervisor, Role.admin))):
    call = db.query(Call).filter(
        Call.id == body.call_id, Call.tenant_id == user.tenant_id).first()
    if call is None:
        raise HTTPException(404, "Cagri bulunamadi")
    agent = db.query(Agent).filter(
        Agent.id == body.assignee_agent_id, Agent.tenant_id == user.tenant_id).first()
    if agent is None:
        raise HTTPException(404, "Temsilci bulunamadi")
    task = CoachingTask(tenant_id=user.tenant_id, call_id=body.call_id,
                        assigner_id=user.id, assignee_agent_id=body.assignee_agent_id,
                        note=body.note)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.get("/coaching", response_model=list[CoachingTaskOut])
def list_coaching(status: str | None = None, db: Session = Depends(get_db),
                  user: CurrentUser = Depends(get_current_user)):
    q = db.query(CoachingTask).filter(CoachingTask.tenant_id == user.tenant_id)
    if user.role == Role.agent:
        q = q.filter(CoachingTask.assignee_agent_id == (user.agent_id or -1))
    if status:
        q = q.filter(CoachingTask.status == status)
    return q.order_by(CoachingTask.created_at.desc()).all()


@router.post("/coaching/{task_id}/complete", response_model=CoachingTaskOut)
def complete_coaching(task_id: int, body: CoachingTaskComplete, db: Session = Depends(get_db),
                      user: CurrentUser = Depends(get_current_user)):
    task = db.query(CoachingTask).filter(
        CoachingTask.id == task_id, CoachingTask.tenant_id == user.tenant_id).first()
    if task is None:
        raise HTTPException(404, "Gorev bulunamadi")
    if user.role == Role.agent and task.assignee_agent_id != user.agent_id:
        raise HTTPException(403, "Bu gorev size ait degil")
    task.status = TaskStatus.done
    task.agent_comment = body.agent_comment
    task.completed_at = datetime.utcnow()
    db.commit()
    db.refresh(task)
    return task


# =====================================================================
# Kalibrasyon: AI puani vs insan override sapmasi (kriter bazli)
# =====================================================================
@router.get("/calibration", response_model=list[CalibrationRow])
def calibration(db: Session = Depends(get_db),
                user: CurrentUser = Depends(require_roles(Role.quality, Role.admin))):
    rows = (
        db.query(
            Score.criterion_name,
            func.avg(Score.score),
            func.avg(Score.override_score),
            func.count(Score.override_score),
        )
        .join(Call, Score.call_id == Call.id)
        .filter(Call.tenant_id == user.tenant_id, Score.override_score.isnot(None))
        .group_by(Score.criterion_name)
        .order_by(func.count(Score.override_score).desc())
        .all()
    )
    out = []
    for name, ai_avg, human_avg, cnt in rows:
        ai = round(ai_avg or 0, 2)
        human = round(human_avg or 0, 2)
        out.append(CalibrationRow(
            criterion_name=name, ai_avg=ai, human_avg=human,
            delta=round(human - ai, 2), override_count=cnt,
        ))
    return out
