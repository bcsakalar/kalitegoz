"""Kalibrasyon oturumlari + manuel degerlendirme (uzmanlar arasi uyum).

Akis:
1. Kalite uzmani/admin bir cagri icin oturum acar.
2. Birden fazla uzman BAGIMSIZ puanlar (birbirini goremez — yanlilik olmasin).
3. Oturum kapatilir -> uyum raporu: kriter bazinda kim kac verdi, en cok
   ayrisilan kriter hangisi, hedef (%85) tutturuldu mu, AI ne demisti.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session, joinedload

from ..db import get_db
from ..deps import CurrentUser, require_roles, require_staff
from ..models import (
    CalibrationSession,
    Call,
    Criterion,
    ManualEvaluation,
    Role,
    Score,
    User,
)
from ..schemas import (
    CalibrationReport,
    CalibrationSessionCreate,
    CalibrationSessionOut,
    ManualEvaluationCreate,
    ManualEvaluationOut,
)
from ..services import audit, calibration

router = APIRouter(prefix="/api/v1/calibration-sessions", tags=["calibration"])

# Kalibrasyon yapabilenler: kalite uzmani, supervizor, admin
_staff_roles = require_roles(Role.quality, Role.admin, Role.supervisor)


def _session_or_404(db: Session, user: CurrentUser, session_id: int) -> CalibrationSession:
    s = (
        db.query(CalibrationSession)
        .filter(
            CalibrationSession.id == session_id,
            CalibrationSession.tenant_id == user.tenant_id,
        )
        .first()
    )
    if s is None:
        raise HTTPException(404, "Kalibrasyon oturumu bulunamadi")
    return s


def _to_out(db: Session, s: CalibrationSession, user: CurrentUser) -> CalibrationSessionOut:
    mine = (
        db.query(ManualEvaluation.id)
        .filter(
            ManualEvaluation.session_id == s.id,
            ManualEvaluation.evaluator_id == user.id,
        )
        .first()
    )
    return CalibrationSessionOut(
        id=s.id, call_id=s.call_id, title=s.title, status=s.status,
        created_by=s.created_by, scheduled_at=s.scheduled_at,
        created_at=s.created_at, closed_at=s.closed_at,
        evaluation_count=db.query(ManualEvaluation.id).filter(
            ManualEvaluation.session_id == s.id).count(),
        my_evaluation_id=mine[0] if mine else None,
    )


@router.post("", response_model=CalibrationSessionOut, status_code=201)
def create_session(body: CalibrationSessionCreate, db: Session = Depends(get_db),
                   user: CurrentUser = Depends(_staff_roles)):
    call = db.query(Call).filter(
        Call.id == body.call_id, Call.tenant_id == user.tenant_id).first()
    if call is None:
        raise HTTPException(404, "Cagri bulunamadi")
    s = CalibrationSession(
        tenant_id=user.tenant_id, call_id=body.call_id, created_by=user.id,
        title=body.title or f"Kalibrasyon — {call.filename}",
        scheduled_at=body.scheduled_at,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return _to_out(db, s, user)


@router.get("", response_model=list[CalibrationSessionOut])
def list_sessions(status: str | None = None, db: Session = Depends(get_db),
                  user: CurrentUser = Depends(require_staff)):
    q = db.query(CalibrationSession).filter(CalibrationSession.tenant_id == user.tenant_id)
    if status:
        q = q.filter(CalibrationSession.status == status)
    return [
        _to_out(db, s, user)
        for s in q.order_by(CalibrationSession.created_at.desc()).limit(100).all()
    ]


@router.post("/{session_id}/evaluate", response_model=ManualEvaluationOut, status_code=201)
def submit_evaluation(session_id: int, body: ManualEvaluationCreate, request: Request,
                      db: Session = Depends(get_db),
                      user: CurrentUser = Depends(_staff_roles)):
    """Oturuma BAGIMSIZ degerlendirme gonder. Kapali oturuma puan eklenemez."""
    s = _session_or_404(db, user, session_id)
    if s.status != "open":
        raise HTTPException(409, "Oturum kapali — puan eklenemez")
    exists = db.query(ManualEvaluation.id).filter(
        ManualEvaluation.session_id == session_id,
        ManualEvaluation.evaluator_id == user.id,
    ).first()
    if exists:
        raise HTTPException(409, "Bu oturumda zaten puanladiniz")

    crits = {
        c.id: c for c in db.query(Criterion).filter(Criterion.tenant_id == user.tenant_id).all()
    }
    scores = []
    for sc in body.scores:
        c = crits.get(sc.criterion_id)
        if c is None:
            raise HTTPException(400, f"Gecersiz kriter: {sc.criterion_id}")
        scores.append({
            "criterion_id": c.id, "criterion_name": c.name,
            "score": sc.score, "note": sc.note,
        })

    total = calibration.compute_total(scores, {c.id: c.weight for c in crits.values()})
    ev = ManualEvaluation(
        tenant_id=user.tenant_id, call_id=s.call_id, session_id=session_id,
        evaluator_id=user.id, scores=scores, total_score=total, notes=body.notes,
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)
    audit.log(db, action="manual_evaluation", tenant_id=user.tenant_id, user_id=user.id,
              entity_type="call", entity_id=s.call_id,
              detail={"session_id": session_id, "total": total},
              ip=request.client.host if request.client else "")
    return ev


@router.post("/{session_id}/close", response_model=CalibrationReport)
def close_session(session_id: int, db: Session = Depends(get_db),
                  user: CurrentUser = Depends(_staff_roles)):
    """Oturumu kapat ve uyum raporunu dondur."""
    s = _session_or_404(db, user, session_id)
    if s.status == "open":
        s.status = "closed"
        s.closed_at = datetime.utcnow()
        db.commit()
    return _report(db, user, s)


@router.get("/{session_id}/report", response_model=CalibrationReport)
def get_report(session_id: int, db: Session = Depends(get_db),
               user: CurrentUser = Depends(require_staff)):
    """Uyum raporu. Oturum ACIKKEN puanlar gizlidir (yanlilik olmasin)."""
    s = _session_or_404(db, user, session_id)
    if s.status == "open":
        raise HTTPException(
            409,
            "Oturum devam ediyor — uyum raporu, yanlilik olmamasi icin oturum "
            "kapandiginda acilir.",
        )
    return _report(db, user, s)


def _report(db: Session, user: CurrentUser, s: CalibrationSession) -> CalibrationReport:
    evals = (
        db.query(ManualEvaluation)
        .options(joinedload(ManualEvaluation.session))
        .filter(ManualEvaluation.session_id == s.id)
        .all()
    )
    names = {
        u.id: u.name for u in db.query(User).filter(
            User.id.in_([e.evaluator_id for e in evals] or [-1])).all()
    }
    payload = [
        {
            "evaluator_id": e.evaluator_id,
            "evaluator_name": names.get(e.evaluator_id, f"#{e.evaluator_id}"),
            "scores": e.scores or [],
        }
        for e in evals
    ]

    # AI'nin ayni cagriya verdigi puanlar (karsilastirma icin)
    ai_rows = db.query(Score).filter(Score.call_id == s.call_id).all()
    ai_scores = {r.criterion_id: r.score for r in ai_rows if r.criterion_id}
    call = db.get(Call, s.call_id)

    result = calibration.compute_agreement(payload, ai_scores)
    human_totals = [e.total_score for e in evals]

    return CalibrationReport(
        session_id=s.id, call_id=s.call_id, status=s.status,
        agreement_pct=result["agreement_pct"],
        evaluator_count=result["evaluator_count"],
        meets_target=result["meets_target"],
        target=calibration.TARGET_AGREEMENT,
        most_divergent=result["most_divergent"],
        criteria=result["criteria"],
        ai_total=call.total_score if call else None,
        human_avg_total=round(sum(human_totals) / len(human_totals), 1) if human_totals else None,
    )
