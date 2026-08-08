"""Canli olay yayini: Celery worker -> Redis -> API WebSocket -> tarayici.

Neden Redis?
------------
Alarmlar Celery worker SURECINDE olusur (`app/tasks/pipeline.py`), WebSocket
baglantilari ise API surecinde durur. Bunlar AYRI container'lardir; surec ici
bir pub/sub (asyncio.Queue, in-memory liste vb.) worker'daki olayi API'ye asla
tasiyamaz. Redis zaten Celery broker'i olarak ayakta oldugu icin ek bagimlilik
getirmeden dogru koprudur.

Yayin best-effort'tur: Redis'e yazilamazsa alarm YINE DE veritabaninda durur
ve frontend'in mevcut polling'i onu gosterir. Canli itme bir iyilestirmedir,
dogruluk garantisi degil — bu yuzden publish hatalari pipeline'i dusurmez.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any

from ..config import settings

logger = logging.getLogger(__name__)

ALERT_CHANNEL = "kg:alerts"


# =====================================================================
# Yayin tarafi (senkron — Celery worker icinden cagrilir)
# =====================================================================
def publish_alert(payload: dict[str, Any]) -> bool:
    """Alarmi Redis kanalina yayinlar. Basarisizlik sessizce yutulur."""
    try:
        import redis as redis_lib

        r = redis_lib.from_url(settings.redis_url, socket_timeout=2)
        r.publish(ALERT_CHANNEL, json.dumps(payload, ensure_ascii=False, default=str))
        return True
    except Exception as exc:  # baglanti yok, redis kapali, serialize hatasi...
        logger.warning("Canli alarm yayinlanamadi (DB kaydi etkilenmez): %s", exc)
        return False


# =====================================================================
# Abone/dagitim tarafi (async — API surecinde)
# =====================================================================
@dataclass(frozen=True)
class Subscriber:
    """Bir WebSocket baglantisinin gorebilecegi alarm kapsami.

    Kapsam REST'teki `/api/v1/alerts` ile AYNI olmak zorundadir; aksi halde
    WebSocket bir yetki kacagi acar.
    """

    tenant_id: int
    team_id: int | None
    is_supervisor: bool

    def accepts(self, alert: dict[str, Any]) -> bool:
        if alert.get("tenant_id") != self.tenant_id:
            return False
        # Supervisor yalnizca kendi takimini + takimsiz (genel) alarmlari gorur.
        if self.is_supervisor and self.team_id is not None:
            team = alert.get("team_id")
            return team is None or team == self.team_id
        return True


class AlertHub:
    """Tek bir Redis aboneligini tum WebSocket baglantilarina dagitir.

    Her baglanti icin ayri abonelik acmak N katina cikan Redis baglantisi
    demekti; tek dinleyici + surec ici fan-out yeterli.
    """

    def __init__(self) -> None:
        self._conns: dict[Any, Subscriber] = {}
        self._task: asyncio.Task | None = None
        self._lock = asyncio.Lock()

    @property
    def connection_count(self) -> int:
        return len(self._conns)

    async def register(self, ws: Any, sub: Subscriber) -> None:
        async with self._lock:
            self._conns[ws] = sub
            if self._task is None or self._task.done():
                self._task = asyncio.create_task(self._listen())

    async def unregister(self, ws: Any) -> None:
        async with self._lock:
            self._conns.pop(ws, None)
            if not self._conns and self._task is not None:
                self._task.cancel()
                self._task = None

    async def broadcast(self, alert: dict[str, Any]) -> int:
        """Alarmi kapsamina uyan tum baglantilara gonderir; gonderi sayisini doner.

        Kopan baglantilar sessizce dusurulur — bir alicinin olmesi digerlerinin
        yayinini engellememeli.
        """
        sent = 0
        dead = []
        for ws, sub in list(self._conns.items()):
            if not sub.accepts(alert):
                continue
            try:
                await ws.send_json({"type": "alert", "data": alert})
                sent += 1
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self.unregister(ws)
        return sent

    async def _listen(self) -> None:
        """Redis kanalini dinler; kopmada geri cekilerek yeniden baglanir."""
        backoff = 1
        while True:
            try:
                import redis.asyncio as aioredis

                r = aioredis.from_url(settings.redis_url)
                pubsub = r.pubsub()
                await pubsub.subscribe(ALERT_CHANNEL)
                logger.info("Canli alarm dinleyicisi baglandi: %s", ALERT_CHANNEL)
                backoff = 1
                async for msg in pubsub.listen():
                    if msg.get("type") != "message":
                        continue
                    try:
                        await self.broadcast(json.loads(msg["data"]))
                    except json.JSONDecodeError:
                        logger.warning("Bozuk alarm mesaji atlandi")
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("Alarm dinleyicisi koptu (%s); %ds sonra yeniden", exc, backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30)


hub = AlertHub()
