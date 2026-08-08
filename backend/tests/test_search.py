"""Transkript arama: eslesme, konusmaci filtresi, tenant/rol kapsami."""

from app.models import Segment
from tests.conftest import TestingSession, token_for


def _add_segments(call_id: int, rows: list[tuple[str, str, float]]):
    db = TestingSession()
    try:
        for i, (speaker, text, ts) in enumerate(rows):
            db.add(Segment(call_id=call_id, idx=i, speaker=speaker,
                           start_sec=ts, end_sec=ts + 2, text=text))
        db.commit()
    finally:
        db.close()


def test_finds_phrase_with_timestamp(seeded, client):
    _add_segments(seeded["call_a"], [
        ("temsilci", "Merhaba, size nasıl yardımcı olabilirim?", 1),
        ("musteri", "Avukatıma danışacağım, bu iş böyle olmaz", 12.5),
    ])
    hdr = token_for(seeded["admin_a"], seeded["tenant_a"], "admin")
    r = client.get("/api/v1/calls/search?q=avukat", headers=hdr)
    assert r.status_code == 200
    body = r.json()
    assert body["total_hits"] == 1
    assert body["total_calls"] == 1
    hit = body["items"][0]
    assert hit["call_id"] == seeded["call_a"]
    assert hit["ts_sec"] == 12.5
    assert hit["speaker"] == "musteri"


def test_case_insensitive(seeded, client):
    _add_segments(seeded["call_a"], [("temsilci", "GARANTI EDERIM efendim", 3)])
    hdr = token_for(seeded["admin_a"], seeded["tenant_a"], "admin")
    assert client.get("/api/v1/calls/search?q=garanti", headers=hdr).json()["total_hits"] == 1


def test_speaker_filter(seeded, client):
    _add_segments(seeded["call_a"], [
        ("temsilci", "kesin çözülür merak etmeyin", 5),
        ("musteri", "kesin çözülür mü gerçekten?", 9),
    ])
    hdr = token_for(seeded["admin_a"], seeded["tenant_a"], "admin")
    both = client.get("/api/v1/calls/search?q=kesin çözülür", headers=hdr).json()
    assert both["total_hits"] == 2
    only_agent = client.get(
        "/api/v1/calls/search?q=kesin çözülür&speaker=temsilci", headers=hdr).json()
    assert only_agent["total_hits"] == 1
    assert only_agent["items"][0]["speaker"] == "temsilci"


def test_search_is_tenant_scoped(seeded, client):
    """Baska tenant'in transkripti aramada CIKMAMALI."""
    _add_segments(seeded["call_b"], [("musteri", "gizli tenant b ifadesi", 4)])
    hdr_a = token_for(seeded["admin_a"], seeded["tenant_a"], "admin")
    assert client.get("/api/v1/calls/search?q=gizli tenant b", headers=hdr_a).json()["total_hits"] == 0
    hdr_b = token_for(seeded["admin_b"], seeded["tenant_b"], "admin")
    assert client.get("/api/v1/calls/search?q=gizli tenant b", headers=hdr_b).json()["total_hits"] == 1


def test_agent_only_searches_own_calls(seeded, client):
    """Temsilci baska temsilcinin cagrisinda arama yapamaz."""
    _add_segments(seeded["call_other_team"], [("temsilci", "baska ekibin ifadesi", 2)])
    hdr = token_for(seeded["agent_user_a"], seeded["tenant_a"], "agent")
    assert client.get("/api/v1/calls/search?q=baska ekibin", headers=hdr).json()["total_hits"] == 0


def test_supervisor_search_limited_to_team(seeded, client):
    _add_segments(seeded["call_other_team"], [("temsilci", "diger takim cumlesi", 2)])
    hdr = token_for(seeded["sup_user_a"], seeded["tenant_a"], "supervisor")
    assert client.get("/api/v1/calls/search?q=diger takim", headers=hdr).json()["total_hits"] == 0


def test_short_query_rejected(seeded, client):
    hdr = token_for(seeded["admin_a"], seeded["tenant_a"], "admin")
    assert client.get("/api/v1/calls/search?q=a", headers=hdr).status_code == 422


def test_search_requires_auth(seeded, client):
    assert client.get("/api/v1/calls/search?q=test").status_code == 401
