"""Vision (Dalga 5) + Agent Assist (Dalga 6) API."""

import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..deps import CurrentUser, get_current_user, require_staff
from ..schemas import AssistRequest, AssistSuggestion, VisionResultOut
from ..services import assist

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["vision-assist"])

MAX_IMAGE_BYTES = 8 * 1024 * 1024  # 8 MB
_ALLOWED_MIME = {"image/png", "image/jpeg", "image/webp"}


# ---------------------------------------------------------------------------
# 5 — Vision: gorsel denetimi
# ---------------------------------------------------------------------------
@router.get("/vision/status")
def vision_status(db: Session = Depends(get_db), user: CurrentUser = Depends(require_staff)):
    """Vision acik mi + hangi saglayici/model kullanilacak (kurum ayarindan)."""
    from ..models import Tenant
    from ..services import ai_config
    t = db.get(Tenant, user.tenant_id)
    cfg = ai_config.resolve(t.settings if t else None, "vision")
    return {"enabled": settings.vision_enabled, "provider": cfg.provider, "model": cfg.model}


@router.post("/vision/analyze", response_model=VisionResultOut)
async def vision_analyze(file: UploadFile = File(...), db: Session = Depends(get_db),
                         user: CurrentUser = Depends(require_staff)):
    """Yuklenen gorseli denetle (fatura/ekran goruntusu/KVKK riski).

    VISION_ENABLED kapaliysa 503 doner; model cekilmemisse net hata verir.
    Lazy import: vision modulu (ve dolayli httpx cagrilari) yalnizca gerektiginde.
    """
    if not settings.vision_enabled:
        raise HTTPException(503, "Vision kapali (VISION_ENABLED=false). Acmak icin "
                                 "ortam degiskenini ayarlayin ve modeli cekin.")
    if file.content_type not in _ALLOWED_MIME:
        raise HTTPException(400, f"Desteklenmeyen tur: {file.content_type}. "
                                 f"PNG/JPEG/WebP kabul edilir.")
    data = await file.read()
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(413, "Gorsel 8 MB sinirini asiyor")

    from ..models import Tenant
    from ..services import vision
    t = db.get(Tenant, user.tenant_id)
    try:
        result = vision.analyze_image(data, file.content_type, t.settings if t else None)
    except vision.VisionError as exc:
        raise HTTPException(502, str(exc))
    return result


# ---------------------------------------------------------------------------
# 6 — Agent Assist: kismi metne gore canli sufle
# ---------------------------------------------------------------------------
@router.post("/assist/suggest", response_model=list[AssistSuggestion])
def assist_suggest(body: AssistRequest, db: Session = Depends(get_db),
                   user: CurrentUser = Depends(get_current_user)):
    """Kismi transkript metnine gore sufle: uyum hatirlatmasi + bilgi + aksiyon.

    Hizli ve deterministik (LLM'siz de calisir). Streaming STT eklendiginde
    bu endpoint her kismi metin guncellemesinde cagrilir.
    """
    packs = tuple(body.packs) if body.packs else None
    return assist.suggest(db, user.tenant_id, body.partial_text, packs)
