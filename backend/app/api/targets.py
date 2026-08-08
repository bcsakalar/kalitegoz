"""Kalite hedefleri: kurum/takim/temsilci icin metrik esikleri + gerceklesme takibi.

Yonetici olculebilir hedef koyar (or. 'Destek ekibi kalite >= 80'); kokpit ve
karne 'hedefe karsi gercek'i gosterir. Hedefin altindakiler kirmizi vurgulanir.
"""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import Integer, cast, func
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import CurrentUser, require_staff
from ..models import Agent, Call, CallStatus, Role, Target, Team
from ..schemas import TargetIn, TargetOut, TargetProgress

router = APIRouter(prefix="/api/v1/targets", tags=["targets"])

_METRICS = {"quality", "csat", "fcr", "zeroed_rate"}
_SCOPES = {"tenant", "team", "agent"}


@router.get("", response_model=list[TargetOut])
def list_targets(db: Session = Depends(get_db), user: CurrentUser = Depends(require_staff)):
    return (db.query(Target).filter(Target.tenant_id == user.tenant_id)
            .order_by(Target.scope, Target.id).all())


@router.post("", response_model=TargetOut, status_code=201)
def create_target(body: TargetIn, db: Session = Depends(get_db),
                  user: CurrentUser = Depends(require_staff)):
    if body.scope not in _SCOPES:
        raise HTTPException(422, "Gecersiz kapsam")
    if body.metric not in _METRICS:
        raise HTTPException(422, "Gecersiz metrik")
    if body.scope != "tenant" and body.scope_id is None:
        raise HTTPException(422, "Takim/temsilci hedefi icin scope_id gerekli")
    # Ayni kapsam+metrik varsa guncelle (idempotent his)
    existing = (db.query(Target).filter(
        Target.tenant_id == user.tenant_id, Target.scope == body.scope,
        Target.scope_id == body.scope_id, Target.metric == body.metric).first())
    if existing:
        existing.target_value = body.target_value
        db.commit(); db.refresh(existing)
        return existing
    t = Target(tenant_id=user.tenant_id, scope=body.scope, scope_id=body.scope_id,
               metric=body.metric, target_value=body.target_value)
    db.add(t); db.commit(); db.refresh(t)
    return t


@router.delete("/{target_id}", status_code=204)
def delete_target(target_id: int, db: Session = Depends(get_db),
                  user: CurrentUser = Depends(require_staff)):
    t = db.query(Target).filter(Target.id == target_id,
                                Target.tenant_id == user.tenant_id).first()
    if t is None:
        raise HTTPException(404, "Hedef bulunamadi")
    db.delete(t); db.commit()


def _actual(db: Session, tenant_id: int, scope: str, scope_id: int | None,
            metric: str, since: datetime) -> tuple[float | None, int]:
    q = db.query(Call).filter(Call.tenant_id == tenant_id, Call.status == CallStatus.done,
                              Call.created_at >= since)
    if scope == "agent":
        q = q.filter(Call.agent_id == scope_id)
    elif scope == "team":
        q = q.filter(Call.agent_id.in_(
            db.query(Agent.id).filter(Agent.tenant_id == tenant_id, Agent.team_id == scope_id)))
    n = q.count()
    if n == 0:
        return None, 0
    if metric == "quality":
        v = q.with_entities(func.avg(Call.total_score)).scalar()
    elif metric == "csat":
        v = q.with_entities(func.avg(Call.predicted_csat)).scalar()
    elif metric == "zeroed_rate":
        z = q.with_entities(func.sum(cast(Call.zeroed, Integer))).scalar() or 0
        v = z / n * 100.0
    else:  # fcr — tekrar arama orani uzerinden kaba tahmin
        rep = q.with_entities(func.sum(cast(Call.is_repeat, Integer))).scalar() or 0
        v = (1 - rep / n) * 100.0
    return (round(float(v), 1) if v is not None else None), n


@router.get("/progress", response_model=list[TargetProgress])
def progress(days: int = 30, db: Session = Depends(get_db),
             user: CurrentUser = Depends(require_staff)):
    since = datetime.utcnow() - timedelta(days=days)
    targets = db.query(Target).filter(Target.tenant_id == user.tenant_id).all()
    team_names = {t.id: t.name for t in db.query(Team).filter(Team.tenant_id == user.tenant_id)}
    agent_names = {a.id: a.name for a in db.query(Agent).filter(Agent.tenant_id == user.tenant_id)}
    out: list[TargetProgress] = []
    for t in targets:
        # Supervisor yalnizca kendi takimini/temsilcilerini gorur
        if user.role == Role.supervisor and user.team_id:
            if t.scope == "team" and t.scope_id != user.team_id:
                continue
            if t.scope == "agent" and t.scope_id not in agent_names:
                continue
        actual, n = _actual(db, user.tenant_id, t.scope, t.scope_id, t.metric, since)
        name = ("Kurum geneli" if t.scope == "tenant"
                else team_names.get(t.scope_id, "?") if t.scope == "team"
                else agent_names.get(t.scope_id, "?"))
        # zeroed_rate icin dusuk iyi; digerlerinde yuksek iyi
        met = False
        if actual is not None:
            met = actual <= t.target_value if t.metric == "zeroed_rate" else actual >= t.target_value
        out.append(TargetProgress(id=t.id, scope=t.scope, scope_id=t.scope_id, scope_name=name,
                                  metric=t.metric, target_value=t.target_value,
                                  actual=actual, met=met, call_count=n))
    return out
