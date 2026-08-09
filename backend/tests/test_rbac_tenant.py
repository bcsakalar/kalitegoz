"""RBAC + tenant izolasyonu testleri (TestClient uzerinden gercek endpoint'ler)."""

from tests.conftest import token_for


def test_requires_auth(seeded, client):
    assert client.get("/api/v1/calls").status_code == 401


def test_tenant_isolation_list(seeded, client):
    """Tenant B admin'i yalnizca kendi cagrilarini gorur, A'nınkileri gormez."""
    hdr = token_for(seeded["admin_b"], seeded["tenant_b"], "admin")
    r = client.get("/api/v1/calls", headers=hdr)
    assert r.status_code == 200
    ids = [c["id"] for c in r.json()["items"]]
    assert seeded["call_b"] in ids
    assert seeded["call_a"] not in ids


def test_tenant_isolation_detail_404(seeded, client):
    """Tenant B, Tenant A'nin cagri detayina erisemez (404)."""
    hdr = token_for(seeded["admin_b"], seeded["tenant_b"], "admin")
    r = client.get(f"/api/v1/calls/{seeded['call_a']}", headers=hdr)
    assert r.status_code == 404


def test_agent_sees_only_own_calls(seeded, client):
    """Temsilci yalnizca kendi cagrilarini gorur."""
    hdr = token_for(seeded["agent_user_a"], seeded["tenant_a"], "agent")
    r = client.get("/api/v1/calls", headers=hdr)
    assert r.status_code == 200
    ids = [c["id"] for c in r.json()["items"]]
    assert ids == [seeded["call_a"]]  # sadece kendi cagrisi


def test_supervisor_sees_only_own_team_calls(seeded, client):
    """Süpervizör yalnızca kendi takımının çağrılarını görür (başka takım görünmez)."""
    hdr = token_for(seeded["sup_user_a"], seeded["tenant_a"], "supervisor")
    r = client.get("/api/v1/calls", headers=hdr)
    assert r.status_code == 200
    ids = [c["id"] for c in r.json()["items"]]
    assert seeded["call_a"] in ids                  # kendi takimi
    assert seeded["call_other_team"] not in ids     # diger takim
    assert seeded["call_b"] not in ids              # diger tenant


def test_supervisor_cannot_open_other_team_call(seeded, client):
    """Süpervizör başka takımın çağrı detayına erişemez (404)."""
    hdr = token_for(seeded["sup_user_a"], seeded["tenant_a"], "supervisor")
    r = client.get(f"/api/v1/calls/{seeded['call_other_team']}", headers=hdr)
    assert r.status_code == 404


def test_admin_sees_all_teams(seeded, client):
    """Admin tenant'ın tüm takımlarını görür."""
    hdr = token_for(seeded["admin_a"], seeded["tenant_a"], "admin")
    ids = [c["id"] for c in client.get("/api/v1/calls", headers=hdr).json()["items"]]
    assert seeded["call_a"] in ids and seeded["call_other_team"] in ids


def test_audio_missing_returns_404_not_500(seeded, client):
    """audio_path bos olan kayit (chat/sentetik) 404 dondurmeli, 500 DEGIL.

    Path("") -> "." (mevcut bir klasor) oldugu icin naif exists() kontrolu
    True donuyor ve FileResponse klasore carpip 500 veriyordu.
    """
    hdr = token_for(seeded["admin_a"], seeded["tenant_a"], "admin")
    r = client.get(f"/api/v1/calls/{seeded['call_a']}/audio", headers=hdr)
    assert r.status_code == 404
    # FAZ 4.3: standart hata zarfi {"error": {"code","message_tr","details"}}
    assert r.json()["error"]["code"] == "bulunamadi"
    assert "ses" in r.json()["error"]["message_tr"].lower()


def test_agent_cannot_create_criterion(seeded, client):
    """RBAC: temsilci kriter olusturamaz (403)."""
    hdr = token_for(seeded["agent_user_a"], seeded["tenant_a"], "agent")
    r = client.post("/api/v1/criteria", headers=hdr,
                    json={"name": "Yeni", "description": "deneme"})
    assert r.status_code == 403


def test_admin_can_create_criterion_scoped_to_tenant(seeded, client):
    """Admin kriter olusturur; kriter kendi tenant'ina yazilir."""
    hdr = token_for(seeded["admin_a"], seeded["tenant_a"], "admin")
    r = client.post("/api/v1/criteria", headers=hdr,
                    json={"name": "Kapanis", "description": "veda", "group": "Kapanis"})
    assert r.status_code == 201
    # Tenant B bu kriteri gormez
    hdr_b = token_for(seeded["admin_b"], seeded["tenant_b"], "admin")
    names_b = [c["name"] for c in client.get("/api/v1/criteria", headers=hdr_b).json()]
    assert "Kapanis" not in names_b


def test_agent_cannot_access_admin_banned_words(seeded, client):
    hdr = token_for(seeded["agent_user_a"], seeded["tenant_a"], "agent")
    assert client.get("/api/v1/admin/banned-words", headers=hdr).status_code == 403


def test_cross_tenant_token_mismatch_rejected(seeded, client):
    """Kullanicinin tenant'i ile token tenant'i uyusmazsa 401."""
    bad = token_for(seeded["admin_a"], seeded["tenant_b"], "admin")  # yanlis tenant
    assert client.get("/api/v1/calls", headers=bad).status_code == 401
