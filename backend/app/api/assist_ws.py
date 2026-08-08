"""Gercek zamanli agent assist WebSocket'i (Dalga 6 — streaming).

Mimari:
Tarayici, konusmayi canli metne cevirir (Web Speech API — tarayici-ici STT,
Turkce destekli, ek sunucu yuku yok) ve biriken kismi metni bu WebSocket'e
akitir. Sunucu her guncellemede assist motorunu calistirip onerileri geri
akitir. Boylece <1sn gecikmeyle canli sufle olur — agir bir streaming-STT
sunucu altyapisi gerekmeden.

Kimlik dogrulama: alerts WS'i ile ayni desen (token query string, kisa omurlu
access token). Assist tum personel + temsilciye acik (temsilci kendine sufle
alir); yalniz gecerli kullanici sart.
"""

import logging

import jwt
from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User
from ..security import decode_token
from ..services import assist

logger = logging.getLogger(__name__)

router = APIRouter(tags=["assist"])

WS_UNAUTHORIZED = 4401
# Cok sik guncellemede LLM'siz motor bile bosa calismasin diye: metin en az bu
# kadar UZADIYSA yeniden hesapla (throttle). Istemci de debounce yapar.
_MIN_DELTA_CHARS = 15


def _authenticate(token: str, db: Session) -> User | None:
    try:
        payload = decode_token(token, "access")
    except jwt.PyJWTError:
        return None
    user = db.get(User, int(payload["sub"]))
    if user is None or not user.is_active or user.tenant_id != payload.get("tenant_id"):
        return None
    return user


@router.websocket("/api/v1/ws/assist")
async def assist_ws(websocket: WebSocket, token: str = Query(default=""),
                    db: Session = Depends(get_db)):
    user = _authenticate(token, db)
    if user is None:
        await websocket.close(code=WS_UNAUTHORIZED, reason="Gecersiz token")
        return

    await websocket.accept()
    await websocket.send_json({"type": "ready"})
    last_len = 0
    try:
        while True:
            # Istemci {"text": "...", "packs": [...]} gonderir
            msg = await websocket.receive_json()
            text = (msg.get("text") or "").strip()
            packs = msg.get("packs") or None
            # Throttle: kayda deger uzama yoksa yeniden hesaplama
            if abs(len(text) - last_len) < _MIN_DELTA_CHARS and text:
                continue
            last_len = len(text)
            suggestions = assist.suggest(db, user.tenant_id, text, tuple(packs) if packs else None)
            await websocket.send_json({"type": "suggestions", "data": suggestions})
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.warning("Assist WS hata ile kapandi: %s", exc)
