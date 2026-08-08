"""Kurumsal/satis katmani: guvenlik durusu, AI puan karti uretici, ROI, demo reset."""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..deps import CurrentUser, require_admin, require_staff
from ..models import AuditLog, Call, Criterion, Role, Tenant
from ..schemas import (
    RoiInputs,
    RoiResult,
    ScorecardBuildRequest,
    ScorecardDraft,
    ScorecardSaveRequest,
    SecurityPosture,
)
from ..services import audit, roi, scorecard_builder
from ..services.compliance_packs import DEFAULT_ACTIVE
from ..services.llm import LLMError

router = APIRouter(prefix="/api/v1/enterprise", tags=["enterprise"])


# =====================================================================
# Guvenlik durusu — landing/güvenlik sayfasi (on-prem/KVKK satis silahi)
# =====================================================================
@router.get("/security-posture", response_model=SecurityPosture)
def security_posture(db: Session = Depends(get_db), user: CurrentUser = Depends(require_staff)):
    tenant = db.get(Tenant, user.tenant_id)
    local_llm = settings.llm_provider == "ollama"
    since = datetime.utcnow() - timedelta(days=30)
    audit_30d = (
        db.query(func.count(AuditLog.id))
        .filter(AuditLog.tenant_id == user.tenant_id, AuditLog.created_at >= since)
        .scalar() or 0
    )
    return SecurityPosture(
        deployment="on-premise" if local_llm else "cloud-hybrid",
        llm_provider=settings.llm_provider,
        data_leaves_premises=not local_llm,
        pii_masking_enabled=settings.pii_masking_enabled,
        audit_log_enabled=True,
        sso_enabled=settings.sso_enabled,
        rbac_roles=[r.value for r in Role],
        retention_days=tenant.retention_days if tenant else 365,
        encryption_at_rest=settings.encryption_at_rest,
        multi_tenant_isolation=True,
        kvkk_pack_active="kvkk" in DEFAULT_ACTIVE,
        audit_events_30d=int(audit_30d),
    )


# =====================================================================
# No-code AI puan karti (scorecard) uretici
# =====================================================================
@router.post("/scorecard/build", response_model=ScorecardDraft)
def build_scorecard(body: ScorecardBuildRequest, request: Request,
                    db: Session = Depends(get_db),
                    user: CurrentUser = Depends(require_admin)):
    """Dogal dil aciklamasindan rubrik TASLAGI uretir (kaydetmez). Kurumun AI
    saglayicisini (Ollama/Gemini/OpenAI/OpenRouter) kullanir."""
    from ..models import Tenant
    from ..services import ai_config
    tenant = db.get(Tenant, user.tenant_id)
    try:
        with ai_config.use_llm(tenant.settings if tenant else None, user.tenant_id, "scorecard"):
            draft = scorecard_builder.build(body.prompt, body.channel, body.max_criteria)
    except LLMError as exc:
        raise HTTPException(502, f"Puan karti uretilemedi (LLM): {exc}")
    audit.log(db, action="scorecard_build", tenant_id=user.tenant_id, user_id=user.id,
              detail={"prompt": body.prompt[:200], "count": len(draft.criteria)},
              ip=request.client.host if request.client else "")
    return draft


@router.post("/scorecard/save")
def save_scorecard(body: ScorecardSaveRequest, request: Request,
                   db: Session = Depends(get_db),
                   user: CurrentUser = Depends(require_admin)):
    """Taslak kriterleri kalici rubrik olarak kaydeder."""
    if body.replace_existing:
        q = db.query(Criterion).filter(
            Criterion.tenant_id == user.tenant_id, Criterion.is_active.is_(True))
        if body.campaign_id is not None:
            q = q.filter(Criterion.campaign_id == body.campaign_id)
        else:
            q = q.filter(Criterion.campaign_id.is_(None))
        for c in q.all():
            c.is_active = False

    created = 0
    for d in body.criteria:
        db.add(Criterion(
            tenant_id=user.tenant_id, campaign_id=body.campaign_id,
            name=d.name, description=d.description, group=d.group,
            weight=d.weight, min_score=0, max_score=10,
            is_critical=d.is_critical, critical_threshold=d.critical_threshold,
            channel_scope=d.channel_scope, is_active=True,
        ))
        created += 1
    db.commit()
    audit.log(db, action="scorecard_save", tenant_id=user.tenant_id, user_id=user.id,
              detail={"created": created, "campaign_id": body.campaign_id,
                      "replaced": body.replace_existing},
              ip=request.client.host if request.client else "")
    return {"created": created, "message": f"{created} kriter kaydedildi"}


# =====================================================================
# Yonetici ROI hesaplayici
# =====================================================================
@router.post("/roi", response_model=RoiResult)
def compute_roi(body: RoiInputs, user: CurrentUser = Depends(require_staff)):
    return roi.compute(body)


# =====================================================================
# Demo: tek tik "sifirla & yeniden doldur" (yalnizca demo modunda)
# =====================================================================
@router.post("/demo/reset")
def demo_reset(request: Request, db: Session = Depends(get_db),
               user: CurrentUser = Depends(require_admin)):
    """Bu tenant'in cagrilarini siler ve 8 haftalik sentetik gecmisi yeniden yukler.

    Yalnizca DEMO_MODE=true iken calisir. Prospect'e temiz, dolu bir sistem
    gostermek icin — uretim verisine dokunmaz (tenant kapsamli).
    """
    if not settings.demo_mode:
        raise HTTPException(403, "Demo modu kapali")
    deleted = db.query(Call).filter(Call.tenant_id == user.tenant_id).delete()
    db.commit()
    from ..seed import seed_demo_history

    created = seed_demo_history(db, user.tenant_id)
    audit.log(db, action="demo_reset", tenant_id=user.tenant_id, user_id=user.id,
              detail={"deleted": deleted, "created": created},
              ip=request.client.host if request.client else "")
    return {"deleted": deleted, "created": created,
            "message": f"{deleted} cagri silindi, {created} sentetik cagri yuklendi"}
