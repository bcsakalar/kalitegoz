"""Canli alarm (WebSocket + Redis pub/sub) testleri.

Redis GEREKMEZ: hub'in `broadcast()` metodu dogrudan cagrilir. Redis dinleyicisi
yalnizca `broadcast`'i besleyen bir tasima katmanidir; kapsam/yetki mantigi
burada test edilir.
"""

import asyncio

import pytest

from app.services.events import AlertHub, Subscriber, publish_alert


class FakeWS:
    """send_json'u kaydeden minimal WebSocket taklidi."""

    def __init__(self, fail: bool = False):
        self.sent: list[dict] = []
        self.fail = fail

    async def send_json(self, data):
        if self.fail:
            raise RuntimeError("baglanti koptu")
        self.sent.append(data)


def alert(tenant_id=1, team_id=None, **kw):
    return {"id": 1, "tenant_id": tenant_id, "team_id": team_id,
            "type": "kritik_ihlal", "severity": "yuksek",
            "message": "test", "is_read": False, **kw}


# =====================================================================
# Kapsam (yetki) — REST /api/v1/alerts ile AYNI olmali
# =====================================================================
class TestSubscriberScope:
    def test_tenant_isolation(self):
        """BASKA tenant'in alarmi asla gorulmemeli."""
        sub = Subscriber(tenant_id=1, team_id=None, is_supervisor=False)
        assert sub.accepts(alert(tenant_id=1))
        assert not sub.accepts(alert(tenant_id=2))

    def test_supervisor_sees_only_own_team(self):
        sub = Subscriber(tenant_id=1, team_id=10, is_supervisor=True)
        assert sub.accepts(alert(team_id=10))
        assert not sub.accepts(alert(team_id=99))

    def test_supervisor_sees_teamless_alerts(self):
        """Takimsiz (genel) alarmlar REST'te de supervisor'a gorunur."""
        sub = Subscriber(tenant_id=1, team_id=10, is_supervisor=True)
        assert sub.accepts(alert(team_id=None))

    def test_supervisor_without_team_sees_all_in_tenant(self):
        sub = Subscriber(tenant_id=1, team_id=None, is_supervisor=True)
        assert sub.accepts(alert(team_id=99))

    def test_admin_sees_all_teams_in_tenant(self):
        sub = Subscriber(tenant_id=1, team_id=10, is_supervisor=False)
        assert sub.accepts(alert(team_id=99))
        assert not sub.accepts(alert(tenant_id=2, team_id=99))

    def test_tenant_check_precedes_team_check(self):
        """Ayni team_id baska tenant'ta da olabilir — tenant once bakilmali."""
        sub = Subscriber(tenant_id=1, team_id=10, is_supervisor=True)
        assert not sub.accepts(alert(tenant_id=2, team_id=10))


# =====================================================================
# Dagitim
# =====================================================================
class TestAlertHub:
    """Not: pytest-asyncio eklemek yerine asyncio.run() kullaniliyor —
    test ortamina yeni bagimlilik getirmemek icin."""

    def test_broadcast_only_to_matching_scope(self):
        async def go():
            hub = AlertHub()
            a, b = FakeWS(), FakeWS()
            await hub.register(a, Subscriber(1, 10, True))
            await hub.register(b, Subscriber(1, 99, True))
            hub._task.cancel()  # Redis dinleyicisi bu testte gereksiz
            sent = await hub.broadcast(alert(team_id=10))
            return sent, a, b

        sent, a, b = asyncio.run(go())
        assert sent == 1
        assert len(a.sent) == 1 and a.sent[0]["type"] == "alert"
        assert b.sent == []

    def test_dead_connection_does_not_block_others(self):
        """Bir alicinin kopmasi digerlerinin yayinini engellememeli."""
        async def go():
            hub = AlertHub()
            dead, alive = FakeWS(fail=True), FakeWS()
            await hub.register(dead, Subscriber(1, None, False))
            await hub.register(alive, Subscriber(1, None, False))
            hub._task.cancel()
            sent = await hub.broadcast(alert())
            return sent, alive, hub.connection_count

        sent, alive, remaining = asyncio.run(go())
        assert sent == 1
        assert len(alive.sent) == 1
        assert remaining == 1  # kopan otomatik dusuruldu

    def test_unregister_removes_connection(self):
        async def go():
            hub = AlertHub()
            ws = FakeWS()
            await hub.register(ws, Subscriber(1, None, False))
            hub._task.cancel()
            before = hub.connection_count
            await hub.unregister(ws)
            return before, hub.connection_count

        before, after = asyncio.run(go())
        assert (before, after) == (1, 0)

    def test_listener_stops_when_last_client_leaves(self):
        """Bosta Redis aboneligi tutmak kaynak israfi olurdu."""
        async def go():
            hub = AlertHub()
            ws = FakeWS()
            await hub.register(ws, Subscriber(1, None, False))
            started = hub._task is not None
            await hub.unregister(ws)
            return started, hub._task

        started, task = asyncio.run(go())
        assert started is True
        assert task is None


# =====================================================================
# Yayin dayanikliligi
# =====================================================================
class TestPublishResilience:
    def test_publish_failure_is_swallowed(self, monkeypatch):
        """Redis kapaliysa alarm YINE DE DB'de durur; pipeline dusmemeli."""
        monkeypatch.setattr(
            "app.config.settings.redis_url", "redis://nonexistent-host:6379/0"
        )
        assert publish_alert({"id": 1}) is False  # istisna firlatmadi


# =====================================================================
# WebSocket endpoint kimlik dogrulama
# =====================================================================
class TestWebSocketAuth:
    """Baglantinin REDDEDILDIGI dogrulanir, kapanis KODU degil.

    Sunucu yetkisiz baglantiyi accept() etmeden kapatir; ASGI bunu handshake
    seviyesinde HTTP 403'e cevirir ve 4401/4403 kodlari gercek istemciye
    ULASMAZ (canli dogrulandi: websocket-client "Handshake status 403" gordu).
    TestClient kodu yine de yuzeye cikarir — ona gore assert etmek, uretimde
    var olmayan bir davranisi test etmek olurdu.
    """

    def _rejected(self, client, url) -> bool:
        from starlette.websockets import WebSocketDisconnect
        try:
            with client.websocket_connect(url):
                return False  # baglanti kuruldu -> kacak
        except WebSocketDisconnect:
            return True

    def test_rejects_missing_token(self, client):
        assert self._rejected(client, "/api/v1/ws/alerts")

    def test_rejects_garbage_token(self, client):
        assert self._rejected(client, "/api/v1/ws/alerts?token=abc.def.ghi")

    def test_rejects_refresh_token(self, client):
        """Refresh token uzun omurludur; URL'de tasinmasi riskli — reddedilmeli."""
        from app.security import create_refresh_token
        tok = create_refresh_token(1, 1)
        assert self._rejected(client, f"/api/v1/ws/alerts?token={tok}")
