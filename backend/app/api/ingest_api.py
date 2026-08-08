"""Push-ingest konnektor: harici sistemler (santral webhook, CRM, dialer) API
anahtariyla cagri ses+metadata POST eder.

Kimlik: X-Ingest-Key basligi (config.ingest_api_key). Tenant, gonderen sisteme
gore slug ile secilir. Boylece watch-folder disinda GERCEK ZAMANLI entegrasyon
mumkun olur — kurumsal santrallerin (Genesys/Avaya/3CX) webhook ciktisi buraya
baglanir.
"""

import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..config import settings
from ..db import SessionLocal
from ..models import Tenant
from ..schemas import CallListItem
from ..services.ingest import IngestError, ingest_audio

router = APIRouter(prefix="/api/v1/ingest", tags=["ingest"])

MAX_UPLOAD_BYTES = 200 * 1024 * 1024


def _check_key(x_ingest_key: str | None) -> None:
    if not settings.ingest_api_key:
        raise HTTPException(404, "Push-ingest kapali (INGEST_API_KEY tanimli degil)")
    if not x_ingest_key or x_ingest_key != settings.ingest_api_key:
        raise HTTPException(401, "Gecersiz ingest anahtari")


@router.get("/health")
def ingest_health():
    """Konnektor saglik/kesif — harici sistem entegrasyonu dogrular (anahtarsiz)."""
    return {"enabled": bool(settings.ingest_api_key), "endpoint": "/api/v1/ingest/call"}


@router.post("/call", response_model=CallListItem, status_code=201)
async def ingest_call(
    file: UploadFile = File(...),
    tenant_slug: str = Form(default="demo"),
    agent_name: str | None = Form(default=None),
    campaign_id: int | None = Form(default=None),
    customer_ref: str | None = Form(default=None),
    x_ingest_key: str | None = Header(default=None),
):
    """Harici sistemden cagri al (API anahtariyla). Cagri 'pending' olusur; agir
    isleme tenant'in isleme ayarina gore (otomatik/elle) baslar."""
    _check_key(x_ingest_key)
    if not file.filename:
        raise HTTPException(400, "Dosya adi bos")

    db: Session = SessionLocal()
    try:
        tenant = db.query(Tenant).filter(
            Tenant.slug == tenant_slug, Tenant.is_active.is_(True)).first()
        if tenant is None:
            raise HTTPException(404, f"Tenant bulunamadi: {tenant_slug}")

        size = 0
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    tmp.close()
                    Path(tmp.name).unlink(missing_ok=True)
                    raise HTTPException(413, "Dosya cok buyuk (limit 200 MB)")
                tmp.write(chunk)
            tmp_path = Path(tmp.name)
        try:
            call = ingest_audio(
                db, tenant.id, tmp_path, file.filename,
                agent_name=agent_name, campaign_id=campaign_id,
                customer_ref=customer_ref, move=True,
            )
        except IngestError as exc:
            tmp_path.unlink(missing_ok=True)
            raise HTTPException(400, str(exc))
        return call
    finally:
        db.close()
