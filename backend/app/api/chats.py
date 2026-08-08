"""Chat / yazisma kanali ingest — JSON mesaj listesi puanlamaya alinir."""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import CurrentUser, require_staff
from ..schemas import CallListItem, ChatIngest
from ..services import audit
from ..services.ingest import ingest_chat

router = APIRouter(prefix="/api/v1/chats", tags=["chats"])


@router.post("", response_model=CallListItem, status_code=201)
def create_chat(body: ChatIngest, request: Request, db: Session = Depends(get_db),
                user: CurrentUser = Depends(require_staff)):
    valid_speakers = {"musteri", "temsilci"}
    if not any(m.speaker in valid_speakers for m in body.messages):
        raise HTTPException(400, "En az bir gecerli mesaj (musteri/temsilci) gerekli")
    call = ingest_chat(
        db, user.tenant_id, body.filename,
        [m.model_dump() for m in body.messages],
        agent_name=body.agent_name, campaign_id=body.campaign_id,
    )
    audit.log(db, action="ingest_chat", tenant_id=user.tenant_id, user_id=user.id,
              entity_type="call", entity_id=call.id,
              ip=request.client.host if request.client else "")
    return call
