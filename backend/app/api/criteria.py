from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ..db import get_db
from ..deps import CurrentUser, get_current_user, require_staff
from ..models import Call, CallStatus, Criterion, RubricVersion, Score
from ..schemas import (
    CriterionCreate, CriterionOut, CriterionUpdate,
    RubricVersionCreate, RubricVersionOut,
    SimulateChange, SimulateRequest, SimulateResult,
)
from ..services import audit

router = APIRouter(prefix="/api/v1/criteria", tags=["criteria"])

# Snapshot'a alinan kriter alanlari (geri yukleme bu alanlari yazar)
_SNAP_FIELDS = ("name", "description", "group", "weight", "is_critical",
                "critical_threshold", "channel_scope", "campaign_id", "is_active")


def _snapshot(db: Session, tenant_id: int) -> list[dict]:
    rows = db.query(Criterion).filter(Criterion.tenant_id == tenant_id).order_by(Criterion.id).all()
    return [{f: getattr(c, f) for f in _SNAP_FIELDS} for c in rows]


@router.get("/versions", response_model=list[RubricVersionOut])
def list_versions(db: Session = Depends(get_db), user: CurrentUser = Depends(require_staff)):
    return (db.query(RubricVersion).filter(RubricVersion.tenant_id == user.tenant_id)
            .order_by(RubricVersion.created_at.desc()).limit(50).all())


@router.post("/versions", response_model=RubricVersionOut, status_code=201)
def save_version(body: RubricVersionCreate, db: Session = Depends(get_db),
                 user: CurrentUser = Depends(require_staff)):
    """Mevcut rubrigin anlik goruntusunu kaydet (degisiklik oncesi/sonrasi guvenlik agi)."""
    snap = _snapshot(db, user.tenant_id)
    v = RubricVersion(tenant_id=user.tenant_id, note=(body.note or "")[:200],
                      snapshot=snap, criteria_count=len(snap), created_by=user.id)
    db.add(v); db.commit(); db.refresh(v)
    audit.log(db, action="rubric_version_save", tenant_id=user.tenant_id, user_id=user.id,
              entity_type="rubric_version", entity_id=v.id)
    return v


@router.post("/versions/{version_id}/restore", response_model=list[CriterionOut])
def restore_version(version_id: int, db: Session = Depends(get_db),
                    user: CurrentUser = Depends(require_staff)):
    """Bir versiyonu geri yukle: mevcut kriterleri siler, snapshot'takileri yeniden yazar.
    Geri yukleme oncesi otomatik bir 'geri-yukleme oncesi' versiyonu kaydeder."""
    v = db.query(RubricVersion).filter(RubricVersion.id == version_id,
                                       RubricVersion.tenant_id == user.tenant_id).first()
    if v is None:
        raise HTTPException(404, "Versiyon bulunamadi")
    # Guvenlik agi: geri yuklemeden once mevcut hali sakla
    cur = _snapshot(db, user.tenant_id)
    db.add(RubricVersion(tenant_id=user.tenant_id, note="[otomatik] geri yukleme oncesi",
                         snapshot=cur, criteria_count=len(cur), created_by=user.id))
    db.query(Criterion).filter(Criterion.tenant_id == user.tenant_id).delete()
    db.flush()
    for item in v.snapshot:
        db.add(Criterion(tenant_id=user.tenant_id, **{f: item.get(f) for f in _SNAP_FIELDS}))
    db.flush()
    # Gecmis puanlarin criterion_id'si (SET NULL ile) kopmasin: isimle yeniden bagla
    name_to_id = {c.name: c.id for c in
                  db.query(Criterion).filter(Criterion.tenant_id == user.tenant_id).all()}
    tenant_call_ids = select(Call.id).where(Call.tenant_id == user.tenant_id)
    for s in db.query(Score).filter(Score.call_id.in_(tenant_call_ids)).all():
        new_id = name_to_id.get(s.criterion_name)
        if new_id is not None:
            s.criterion_id = new_id
    db.commit()
    audit.log(db, action="rubric_version_restore", tenant_id=user.tenant_id, user_id=user.id,
              entity_type="rubric_version", entity_id=v.id)
    return db.query(Criterion).filter(Criterion.tenant_id == user.tenant_id).order_by(Criterion.id).all()


@router.get("", response_model=list[CriterionOut])
def list_criteria(
    include_inactive: bool = True,
    campaign_id: int | None = None,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    q = db.query(Criterion).filter(Criterion.tenant_id == user.tenant_id)
    if not include_inactive:
        q = q.filter(Criterion.is_active.is_(True))
    if campaign_id is not None:
        q = q.filter(Criterion.campaign_id == campaign_id)
    return q.order_by(Criterion.id).all()


@router.post("/simulate", response_model=SimulateResult)
def simulate(body: SimulateRequest, db: Session = Depends(get_db),
             user: CurrentUser = Depends(require_staff)):
    """Rubrik degisikligini KAYDETMEDEN gecmis cagrilarda dener. 'before' mevcut
    config, 'after' onerilen config ile kayitli puan satirlarindan yeniden hesaplanir
    (LLM'siz, aninda). Kalite yoneticisi karar riskini gormeden alir."""
    current = {
        c.id: {"weight": c.weight, "is_critical": c.is_critical,
               "critical_threshold": c.critical_threshold, "is_active": c.is_active}
        for c in db.query(Criterion).filter(Criterion.tenant_id == user.tenant_id).all()
    }
    proposed = {
        sc.criterion_id: {"weight": sc.weight, "is_critical": sc.is_critical,
                          "critical_threshold": sc.critical_threshold, "is_active": sc.is_active}
        for sc in body.criteria
    }

    since = datetime.utcnow() - timedelta(days=body.days)
    calls = (
        db.query(Call).options(joinedload(Call.scores))
        .filter(Call.tenant_id == user.tenant_id, Call.status == CallStatus.done,
                Call.total_score.isnot(None), Call.created_at >= since)
        .order_by(Call.created_at.desc()).limit(body.limit).all()
    )

    def _score(scores, cfg_map: dict) -> float | None:
        num = den = 0.0
        zeroed = False
        for r in scores:
            cfg = cfg_map.get(r.criterion_id)
            if not cfg or not cfg["is_active"]:
                continue
            eff = r.override_score if r.override_score is not None else r.score
            num += eff * cfg["weight"]
            den += cfg["weight"]
            if cfg["is_critical"] and eff < cfg["critical_threshold"]:
                zeroed = True
        if den == 0:
            return None
        return 0.0 if zeroed else round(num / (den * 10) * 100, 1)

    befores: list[float] = []
    afters: list[float] = []
    changes: list[SimulateChange] = []
    zb = za = 0
    for c in calls:
        b = _score(c.scores, current)
        a = _score(c.scores, proposed)
        if b is None or a is None:
            continue
        befores.append(b)
        afters.append(a)
        zb += 1 if b == 0 else 0
        za += 1 if a == 0 else 0
        changes.append(SimulateChange(id=c.id, filename=c.filename, before=b, after=a,
                                      delta=round(a - b, 1)))

    n = len(befores)
    changes.sort(key=lambda x: abs(x.delta), reverse=True)
    return SimulateResult(
        call_count=n,
        avg_before=round(sum(befores) / n, 1) if n else 0.0,
        avg_after=round(sum(afters) / n, 1) if n else 0.0,
        zeroed_before=zb, zeroed_after=za,
        biggest_changes=changes[:15],
    )


@router.post("", response_model=CriterionOut, status_code=201)
def create_criterion(body: CriterionCreate, db: Session = Depends(get_db),
                     user: CurrentUser = Depends(require_staff)):
    crit = Criterion(tenant_id=user.tenant_id, **body.model_dump())
    db.add(crit)
    db.commit()
    db.refresh(crit)
    return crit


@router.patch("/{criterion_id}", response_model=CriterionOut)
def update_criterion(criterion_id: int, body: CriterionUpdate, db: Session = Depends(get_db),
                     user: CurrentUser = Depends(require_staff)):
    crit = (
        db.query(Criterion)
        .filter(Criterion.id == criterion_id, Criterion.tenant_id == user.tenant_id)
        .first()
    )
    if crit is None:
        raise HTTPException(404, "Kriter bulunamadi")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(crit, field, value)
    db.commit()
    db.refresh(crit)
    return crit


@router.delete("/{criterion_id}", status_code=204)
def delete_criterion(criterion_id: int, db: Session = Depends(get_db),
                     user: CurrentUser = Depends(require_staff)):
    crit = (
        db.query(Criterion)
        .filter(Criterion.id == criterion_id, Criterion.tenant_id == user.tenant_id)
        .first()
    )
    if crit is None:
        raise HTTPException(404, "Kriter bulunamadi")
    db.delete(crit)
    db.commit()
