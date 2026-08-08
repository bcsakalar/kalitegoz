"""Canli alarm WebSocket'i.

Kimlik dogrulama notu
---------------------
Tarayicidaki WebSocket API'si ozel HTTP basligi gondermeye izin vermez, bu
yuzden Bearer token query string ile alinir (`?token=...`). Bu yaygin ve kabul
gormus bir yontemdir ama bir bedeli vardir: URL'ler sunucu erisim loglarina
duz metin olarak dusebilir. Riski sinirlamak icin:
  - Yalnizca KISA omurlu ACCESS token kabul edilir (refresh token reddedilir),
  - Token her baglantida yeniden dogrulanir (REST ile ayni `decode_token`),
  - Yetki kapsami REST'teki /api/v1/alerts ile birebir aynidir.
"""

import logging

import jwt
from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Role, User
from ..security import decode_token
from ..services.events import Subscriber, hub

logger = logging.getLogger(__name__)

router = APIRouter(tags=["events"])

# WebSocket kapanis kodlari (RFC 6455 uygulama araligi).
#
# ONEMLI: accept() ONCESI close() cagrildiginda ASGI/uvicorn bunu handshake
# seviyesinde HTTP 403'e cevirir; bu kodlar istemciye ULASMAZ (canli dogrulandi,
# istemci "Handshake status 403" gorur). Yine de anlamli tutuluyorlar: sunucu
# loglarinda reddin sebebini ayirt ediyorlar ve accept() sonrasi kapatmaya
# gecilirse dogrudan gecerli olurlar. Istemci tarafi bu kodlara GUVENMEMELI —
# frontend/components/LiveAlertsProvider.tsx bu yuzden deneme sayisini sinirlar.
WS_UNAUTHORIZED = 4401
WS_FORBIDDEN = 4403


def _authenticate(token: str, db: Session) -> User | None:
    try:
        payload = decode_token(token, "access")
    except jwt.PyJWTError:
        return None
    user = db.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        return None
    if user.tenant_id != payload.get("tenant_id"):
        return None
    return user


@router.websocket("/api/v1/ws/alerts")
async def alerts_ws(
    websocket: WebSocket,
    token: str = Query(default=""),
    db: Session = Depends(get_db),
):
    user = _authenticate(token, db)
    if user is None:
        await websocket.close(code=WS_UNAUTHORIZED, reason="Gecersiz veya suresi dolmus token")
        return
    if user.role == Role.agent:
        # REST'te de require_staff temsilciyi disari alir; kapsam ayni kalmali.
        await websocket.close(code=WS_FORBIDDEN, reason="Bu akis icin personel yetkisi gerekli")
        return

    sub = Subscriber(
        tenant_id=user.tenant_id,
        team_id=user.team_id,
        is_supervisor=user.role == Role.supervisor,
    )
    await websocket.accept()
    await hub.register(websocket, sub)
    logger.info("Canli alarm baglantisi: user=%s tenant=%s", user.email, user.tenant_id)
    try:
        await websocket.send_json({"type": "ready"})
        while True:
            # Istemciden veri beklemiyoruz; bu cagri baglanti kopana kadar
            # bekler ve kopmayi WebSocketDisconnect olarak bildirir.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.warning("Canli alarm baglantisi hata ile kapandi: %s", exc)
    finally:
        await hub.unregister(websocket)
