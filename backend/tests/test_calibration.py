"""Kalibrasyon oturumu: uyum hesabi, gizlilik kurali, RBAC."""

from app.services import calibration
from tests.conftest import TestingSession, token_for


# =====================================================================
# Uyum hesabi (saf fonksiyon)
# =====================================================================


def _ev(name, pairs):
    return {
        "evaluator_id": hash(name) % 1000,
        "evaluator_name": name,
        "scores": [{"criterion_id": c, "criterion_name": f"K{c}", "score": s} for c, s in pairs],
    }


def test_full_agreement_is_100():
    evals = [_ev("A", [(1, 8), (2, 6)]), _ev("B", [(1, 8), (2, 6)])]
    r = calibration.compute_agreement(evals)
    assert r["agreement_pct"] == 100.0
    assert r["meets_target"] is True
    assert r["most_divergent"] is None


def test_within_tolerance_counts_as_agreed():
    """7 ile 8 arasindaki fark pratikte anlamsiz -> uyumlu sayilir."""
    evals = [_ev("A", [(1, 7)]), _ev("B", [(1, 8)])]
    assert calibration.compute_agreement(evals)["agreement_pct"] == 100.0


def test_big_spread_is_disagreement():
    """4 ile 9 arasindaki fark ciddi -> uyumsuz."""
    evals = [_ev("A", [(1, 4)]), _ev("B", [(1, 9)])]
    r = calibration.compute_agreement(evals)
    assert r["agreement_pct"] == 0.0
    assert r["meets_target"] is False
    assert r["most_divergent"] == "K1"
    assert r["criteria"][0]["spread"] == 5


def test_partial_agreement_and_most_divergent():
    """En cok ayrisilan kriter raporun basinda olmali (rubrikte duzeltilecek olan)."""
    evals = [
        _ev("A", [(1, 8), (2, 3), (3, 7)]),
        _ev("B", [(1, 8), (2, 9), (3, 7)]),
    ]
    r = calibration.compute_agreement(evals)
    assert r["agreement_pct"] == round(2 / 3 * 100, 1)
    assert r["most_divergent"] == "K2"
    assert r["criteria"][0]["criterion_name"] == "K2"  # en buyuk spread basta


def test_single_evaluator_has_no_agreement():
    r = calibration.compute_agreement([_ev("A", [(1, 8)])])
    assert r["agreement_pct"] is None
    assert r["evaluator_count"] == 1


def test_ai_score_included_in_report():
    evals = [_ev("A", [(1, 8)]), _ev("B", [(1, 8)])]
    r = calibration.compute_agreement(evals, ai_scores={1: 5})
    assert r["criteria"][0]["ai_score"] == 5


def test_compute_total_weighted():
    scores = [{"criterion_id": 1, "score": 10}, {"criterion_id": 2, "score": 0}]
    # esit agirlik -> %50
    assert calibration.compute_total(scores, {1: 1.0, 2: 1.0}) == 50.0
    # 1. kriter 3x agirlikli -> %75
    assert calibration.compute_total(scores, {1: 3.0, 2: 1.0}) == 75.0


# =====================================================================
# API akisi
# =====================================================================


def _criterion_id(tenant_id):
    from app.models import Criterion

    db = TestingSession()
    try:
        return db.query(Criterion).filter(Criterion.tenant_id == tenant_id).first().id
    finally:
        db.close()


def test_session_flow_and_report(seeded, client):
    hdr = token_for(seeded["admin_a"], seeded["tenant_a"], "admin")
    cid = _criterion_id(seeded["tenant_a"])

    r = client.post("/api/v1/calibration-sessions", headers=hdr,
                    json={"call_id": seeded["call_a"], "title": "Haftalık kalibrasyon"})
    assert r.status_code == 201
    sid = r.json()["id"]
    assert r.json()["status"] == "open"

    r = client.post(f"/api/v1/calibration-sessions/{sid}/evaluate", headers=hdr,
                    json={"call_id": seeded["call_a"], "scores": [{"criterion_id": cid, "score": 8}]})
    assert r.status_code == 201
    assert r.json()["total_score"] == 80.0

    # Acik oturumda rapor GIZLI olmali
    assert client.get(f"/api/v1/calibration-sessions/{sid}/report", headers=hdr).status_code == 409

    r = client.post(f"/api/v1/calibration-sessions/{sid}/close", headers=hdr)
    assert r.status_code == 200
    assert r.json()["status"] == "closed"

    # Kapandiktan sonra rapor acilir
    assert client.get(f"/api/v1/calibration-sessions/{sid}/report", headers=hdr).status_code == 200


def test_cannot_evaluate_twice(seeded, client):
    hdr = token_for(seeded["admin_a"], seeded["tenant_a"], "admin")
    cid = _criterion_id(seeded["tenant_a"])
    sid = client.post("/api/v1/calibration-sessions", headers=hdr,
                      json={"call_id": seeded["call_a"]}).json()["id"]
    body = {"call_id": seeded["call_a"], "scores": [{"criterion_id": cid, "score": 7}]}
    assert client.post(f"/api/v1/calibration-sessions/{sid}/evaluate", headers=hdr, json=body).status_code == 201
    assert client.post(f"/api/v1/calibration-sessions/{sid}/evaluate", headers=hdr, json=body).status_code == 409


def test_cannot_evaluate_closed_session(seeded, client):
    hdr = token_for(seeded["admin_a"], seeded["tenant_a"], "admin")
    cid = _criterion_id(seeded["tenant_a"])
    sid = client.post("/api/v1/calibration-sessions", headers=hdr,
                      json={"call_id": seeded["call_a"]}).json()["id"]
    client.post(f"/api/v1/calibration-sessions/{sid}/close", headers=hdr)
    r = client.post(f"/api/v1/calibration-sessions/{sid}/evaluate", headers=hdr,
                    json={"call_id": seeded["call_a"], "scores": [{"criterion_id": cid, "score": 7}]})
    assert r.status_code == 409


def test_invalid_criterion_rejected(seeded, client):
    hdr = token_for(seeded["admin_a"], seeded["tenant_a"], "admin")
    sid = client.post("/api/v1/calibration-sessions", headers=hdr,
                      json={"call_id": seeded["call_a"]}).json()["id"]
    r = client.post(f"/api/v1/calibration-sessions/{sid}/evaluate", headers=hdr,
                    json={"call_id": seeded["call_a"], "scores": [{"criterion_id": 99999, "score": 7}]})
    assert r.status_code == 400


def test_agent_cannot_create_session(seeded, client):
    hdr = token_for(seeded["agent_user_a"], seeded["tenant_a"], "agent")
    assert client.post("/api/v1/calibration-sessions", headers=hdr,
                       json={"call_id": seeded["call_a"]}).status_code == 403


def test_session_is_tenant_scoped(seeded, client):
    hdr_a = token_for(seeded["admin_a"], seeded["tenant_a"], "admin")
    sid = client.post("/api/v1/calibration-sessions", headers=hdr_a,
                      json={"call_id": seeded["call_a"]}).json()["id"]
    hdr_b = token_for(seeded["admin_b"], seeded["tenant_b"], "admin")
    assert client.post(f"/api/v1/calibration-sessions/{sid}/close", headers=hdr_b).status_code == 404


def test_cannot_open_session_for_other_tenant_call(seeded, client):
    hdr_b = token_for(seeded["admin_b"], seeded["tenant_b"], "admin")
    r = client.post("/api/v1/calibration-sessions", headers=hdr_b,
                    json={"call_id": seeded["call_a"]})
    assert r.status_code == 404
