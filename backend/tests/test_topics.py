"""Konu kesfi: kumeleme mantigi ve tenant kapsami."""

from datetime import datetime, timedelta

from app.models import Call, CallStatus, Channel
from app.services import knowledge, topics
from tests.conftest import TestingSession


def test_cluster_groups_similar_vectors():
    """Benzer vektorler ayni kumeye, farkli olanlar ayri kumeye gitmeli."""
    vectors = [
        [1.0, 0.0],   # A grubu
        [0.99, 0.1],  # A grubu (benzer)
        [0.0, 1.0],   # B grubu
        [0.1, 0.99],  # B grubu (benzer)
    ]
    clusters = topics._cluster(vectors, threshold=0.9)
    assert len(clusters) == 2
    sizes = sorted(len(c) for c in clusters)
    assert sizes == [2, 2]


def test_cluster_separates_dissimilar():
    """Dik (benzemez) vektorler ayri kumelerde olmali."""
    clusters = topics._cluster([[1.0, 0.0], [0.0, 1.0]], threshold=0.7)
    assert len(clusters) == 2


def test_cluster_single_group_when_all_similar():
    clusters = topics._cluster([[1.0, 0.0], [0.98, 0.02], [0.99, 0.01]], threshold=0.9)
    assert len(clusters) == 1
    assert len(clusters[0]) == 3


def test_cluster_empty():
    assert topics._cluster([], 0.7) == []


def _add_call(db, tenant_id, agent_id, summary, days_ago=1, score=80.0):
    c = Call(
        tenant_id=tenant_id, filename="x.wav", audio_path="", channel=Channel.voice,
        agent_id=agent_id, status=CallStatus.done, total_score=score,
        category="fatura", summary=summary,
        created_at=datetime.utcnow() - timedelta(days=days_ago),
    )
    db.add(c)
    return c


def test_discover_returns_empty_without_enough_calls(seeded):
    db = TestingSession()
    try:
        assert topics.discover(db, seeded["tenant_a"], days=30) == []
    finally:
        db.close()


def test_discover_is_tenant_scoped(seeded, monkeypatch):
    """Baska tenant'in cagrilari tema kesfine KARISMAMALI."""
    db = TestingSession()
    try:
        for i in range(3):
            _add_call(db, seeded["tenant_b"], seeded["agent_b"], f"tenant b ozeti {i}")
        db.commit()

        # embedding + LLM sahtelenir; tenant A'da cagri yok => bos donmeli
        monkeypatch.setattr(knowledge, "embed", lambda texts, ts=None: [[1.0, 0.0]] * len(texts))
        assert topics.discover(db, seeded["tenant_a"], days=30) == []
    finally:
        db.close()


def test_discover_clusters_and_falls_back_when_llm_fails(seeded, monkeypatch):
    """LLM tema adlandiramazsa kume yine doner (kategori bazli yedek baslik)."""
    db = TestingSession()
    try:
        for i in range(4):
            _add_call(db, seeded["tenant_a"], seeded["agent_a"], f"cift ucretlendirme sikayeti {i}")
        db.commit()

        monkeypatch.setattr(knowledge, "embed", lambda texts, ts=None: [[1.0, 0.0]] * len(texts))

        def boom(*a, **k):
            raise RuntimeError("LLM yok")

        monkeypatch.setattr(topics, "generate_json", boom)

        result = topics.discover(db, seeded["tenant_a"], days=30)
        assert len(result) == 1, "hepsi ayni vektor -> tek kume"
        t = result[0]
        assert t["cagri_sayisi"] == 4
        assert t["ortalama_puan"] == 80.0
        assert t["kategoriler"] == {"fatura": 4}
        assert "fatura" in t["baslik"], "LLM yoksa kategori bazli baslik"
        assert len(t["ornek_cagrilar"]) == 3
    finally:
        db.close()


def test_discover_skips_when_embedding_unavailable(seeded, monkeypatch):
    """Embedding servisi yoksa tema kesfi sessizce bos doner (pipeline dusmez)."""
    db = TestingSession()
    try:
        for i in range(3):
            _add_call(db, seeded["tenant_a"], seeded["agent_a"], f"ozet {i}")
        db.commit()

        def boom(texts, ts=None):
            raise knowledge.KnowledgeError("embedding servisi kapali")

        monkeypatch.setattr(knowledge, "embed", boom)
        assert topics.discover(db, seeded["tenant_a"], days=30) == []
    finally:
        db.close()
