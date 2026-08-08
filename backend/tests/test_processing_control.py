"""Isleme kontrolu: duraklatilmisken agir is (STT/LLM) kuyruga ATILMAMALI."""

from app.models import Tenant
from tests.conftest import TestingSession, token_for


def _set_paused(tenant_id: int, paused: bool):
    db = TestingSession()
    try:
        t = db.get(Tenant, tenant_id)
        t.processing_paused = paused
        db.commit()
    finally:
        db.close()


def test_status_reports_paused_and_counts(seeded, client):
    _set_paused(seeded["tenant_a"], True)
    hdr = token_for(seeded["admin_a"], seeded["tenant_a"], "admin")
    r = client.get("/api/v1/admin/processing", headers=hdr)
    assert r.status_code == 200
    body = r.json()
    assert body["paused"] is True
    assert body["done_calls"] >= 1  # conftest'te tamamlanmis cagri var


def test_pause_and_resume(seeded, client):
    hdr = token_for(seeded["admin_a"], seeded["tenant_a"], "admin")
    assert client.post("/api/v1/admin/processing/pause", headers=hdr).json()["paused"] is True
    assert client.post("/api/v1/admin/processing/resume", headers=hdr).json()["paused"] is False


def test_ingest_chat_does_not_enqueue_when_paused(seeded, client, monkeypatch):
    """Duraklatilmisken chat kaydedilir ama Celery'ye gonderilmez."""
    from app.tasks import pipeline

    sent: list[int] = []
    monkeypatch.setattr(pipeline.process_chat, "delay", lambda cid: sent.append(cid))

    _set_paused(seeded["tenant_a"], True)
    hdr = token_for(seeded["admin_a"], seeded["tenant_a"], "admin")
    r = client.post("/api/v1/chats", headers=hdr, json={
        "filename": "t.json", "agent_name": "agent.a",
        "messages": [{"speaker": "temsilci", "ts_sec": 1, "text": "merhaba"}],
    })
    assert r.status_code == 201
    assert r.json()["status"] == "pending"
    assert sent == [], "duraklatilmisken kuyruga is atilmamali"


def test_ingest_chat_enqueues_when_not_paused(seeded, client, monkeypatch):
    from app.tasks import pipeline

    sent: list[int] = []
    monkeypatch.setattr(pipeline.process_chat, "delay", lambda cid: sent.append(cid))

    _set_paused(seeded["tenant_a"], False)
    hdr = token_for(seeded["admin_a"], seeded["tenant_a"], "admin")
    r = client.post("/api/v1/chats", headers=hdr, json={
        "filename": "t2.json", "agent_name": "agent.a",
        "messages": [{"speaker": "temsilci", "ts_sec": 1, "text": "merhaba"}],
    })
    assert r.status_code == 201
    assert len(sent) == 1


def test_start_processing_enqueues_pending(seeded, client, monkeypatch):
    """'Islemeyi baslat' bekleyen cagrilari kuyruga atar."""
    from app.models import Call, CallStatus, Channel
    from app.tasks import pipeline

    voice_sent: list[int] = []
    monkeypatch.setattr(pipeline.process_call, "delay", lambda cid: voice_sent.append(cid))
    monkeypatch.setattr(pipeline.process_chat, "delay", lambda cid: None)

    db = TestingSession()
    try:
        db.add(Call(tenant_id=seeded["tenant_a"], filename="bekleyen.wav", audio_path="",
                    channel=Channel.voice, agent_id=seeded["agent_a"], status=CallStatus.pending))
        db.commit()
    finally:
        db.close()

    hdr = token_for(seeded["admin_a"], seeded["tenant_a"], "admin")
    r = client.post("/api/v1/admin/processing/start", headers=hdr)
    assert r.status_code == 200
    assert r.json()["queued_now"] >= 1
    assert len(voice_sent) >= 1


def test_agent_cannot_control_processing(seeded, client):
    hdr = token_for(seeded["agent_user_a"], seeded["tenant_a"], "agent")
    assert client.post("/api/v1/admin/processing/start", headers=hdr).status_code == 403
    assert client.get("/api/v1/admin/processing", headers=hdr).status_code == 403
