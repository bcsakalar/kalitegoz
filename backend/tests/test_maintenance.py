"""Bakim gorevleri: trend anomali alarmi, rozet dagitimi, retention."""

from datetime import datetime, timedelta

import pytest

from app.models import Agent, AgentBadge, Alert, AlertType, Badge, Call, CallStatus, Channel
from tests.conftest import TestingSession, engine


@pytest.fixture
def patch_session(monkeypatch):
    """Bakim gorevleri kendi SessionLocal'ini acar; test DB'sine yonlendir."""
    from app.tasks import maintenance

    monkeypatch.setattr(maintenance, "SessionLocal", TestingSession)
    return maintenance


def _call(db, tenant_id, agent_id, *, score, days_ago, zeroed=False, crisis=False,
          s_start=None, s_end=None, ref=None, repeat=False):
    c = Call(
        tenant_id=tenant_id, filename="x.wav", audio_path="", channel=Channel.voice,
        agent_id=agent_id, status=CallStatus.done, total_score=score,
        zeroed=zeroed, is_crisis=crisis, sentiment_start=s_start, sentiment_end=s_end,
        customer_ref=ref, is_repeat=repeat,
        created_at=datetime.utcnow() - timedelta(days=days_ago),
    )
    db.add(c)
    return c


# =====================================================================
# Trend anomali alarmi
# =====================================================================


def test_detects_score_drop(seeded, patch_session):
    """Son hafta belirgin dustuyse alarm uretilmeli."""
    db = TestingSession()
    try:
        # Onceki 3 hafta: ~90 puan
        for i in range(6):
            _call(db, seeded["tenant_a"], seeded["agent_a"], score=90, days_ago=10 + i)
        # Son hafta: ~70 puan (20 puan dusus)
        for i in range(6):
            _call(db, seeded["tenant_a"], seeded["agent_a"], score=70, days_ago=i)
        db.commit()
    finally:
        db.close()

    result = patch_session.detect_anomalies()
    assert result.get("a") == 1

    db = TestingSession()
    try:
        alert = db.query(Alert).filter(Alert.type == AlertType.score_drop).first()
        assert alert is not None
        assert "agent.a" in alert.message
    finally:
        db.close()


def test_no_alert_for_stable_performance(seeded, patch_session):
    db = TestingSession()
    try:
        for i in range(6):
            _call(db, seeded["tenant_a"], seeded["agent_a"], score=85, days_ago=10 + i)
        for i in range(6):
            _call(db, seeded["tenant_a"], seeded["agent_a"], score=84, days_ago=i)
        db.commit()
    finally:
        db.close()

    patch_session.detect_anomalies()
    db = TestingSession()
    try:
        assert db.query(Alert).filter(Alert.type == AlertType.score_drop).count() == 0
    finally:
        db.close()


def test_no_alert_without_enough_calls(seeded, patch_session):
    """Az veriyle (istatistiksel gurultu) alarm uretilmemeli."""
    db = TestingSession()
    try:
        _call(db, seeded["tenant_a"], seeded["agent_a"], score=95, days_ago=12)
        _call(db, seeded["tenant_a"], seeded["agent_a"], score=40, days_ago=1)
        db.commit()
    finally:
        db.close()

    patch_session.detect_anomalies()
    db = TestingSession()
    try:
        assert db.query(Alert).filter(Alert.type == AlertType.score_drop).count() == 0
    finally:
        db.close()


def test_anomaly_alert_not_duplicated(seeded, patch_session):
    """Ayni temsilci icin hafta icinde tekrar alarm uretilmemeli (spam onleme)."""
    db = TestingSession()
    try:
        for i in range(6):
            _call(db, seeded["tenant_a"], seeded["agent_a"], score=90, days_ago=10 + i)
        for i in range(6):
            _call(db, seeded["tenant_a"], seeded["agent_a"], score=70, days_ago=i)
        db.commit()
    finally:
        db.close()

    patch_session.detect_anomalies()
    patch_session.detect_anomalies()  # ikinci kez

    db = TestingSession()
    try:
        assert db.query(Alert).filter(Alert.type == AlertType.score_drop).count() == 1
    finally:
        db.close()


# =====================================================================
# Rozet dagitimi
# =====================================================================


def _seed_badges(tenant_id: int):
    db = TestingSession()
    try:
        for code, name in (
            ("zero_violation", "Sıfır İhlal"), ("crisis_master", "Kriz Ustası"),
            ("empathy_champ", "Empati Şampiyonu"), ("fastest_solution", "En Hızlı Çözüm"),
        ):
            db.add(Badge(tenant_id=tenant_id, code=code, name=name, description="", icon="🏅"))
        db.commit()
    finally:
        db.close()


def test_awards_zero_violation_badge(seeded, patch_session):
    _seed_badges(seeded["tenant_a"])
    db = TestingSession()
    try:
        for i in range(6):
            _call(db, seeded["tenant_a"], seeded["agent_a"], score=85, days_ago=i, zeroed=False)
        db.commit()
    finally:
        db.close()

    patch_session.award_badges()
    db = TestingSession()
    try:
        codes = [
            b.code for b in db.query(Badge).join(AgentBadge, AgentBadge.badge_id == Badge.id)
            .filter(AgentBadge.agent_id == seeded["agent_a"]).all()
        ]
        assert "zero_violation" in codes
    finally:
        db.close()


def test_no_zero_violation_badge_when_violation_exists(seeded, patch_session):
    _seed_badges(seeded["tenant_a"])
    db = TestingSession()
    try:
        for i in range(5):
            _call(db, seeded["tenant_a"], seeded["agent_a"], score=85, days_ago=i)
        _call(db, seeded["tenant_a"], seeded["agent_a"], score=0, days_ago=1, zeroed=True)
        db.commit()
    finally:
        db.close()

    patch_session.award_badges()
    db = TestingSession()
    try:
        codes = [
            b.code for b in db.query(Badge).join(AgentBadge, AgentBadge.badge_id == Badge.id)
            .filter(AgentBadge.agent_id == seeded["agent_a"]).all()
        ]
        assert "zero_violation" not in codes
    finally:
        db.close()


def test_awards_crisis_master(seeded, patch_session):
    _seed_badges(seeded["tenant_a"])
    db = TestingSession()
    try:
        for i in range(3):
            _call(db, seeded["tenant_a"], seeded["agent_a"], score=88, days_ago=i, crisis=True)
        for i in range(3):
            _call(db, seeded["tenant_a"], seeded["agent_a"], score=80, days_ago=i)
        db.commit()
    finally:
        db.close()

    patch_session.award_badges()
    db = TestingSession()
    try:
        codes = [
            b.code for b in db.query(Badge).join(AgentBadge, AgentBadge.badge_id == Badge.id)
            .filter(AgentBadge.agent_id == seeded["agent_a"]).all()
        ]
        assert "crisis_master" in codes
    finally:
        db.close()


def test_badges_not_duplicated_in_same_period(seeded, patch_session):
    _seed_badges(seeded["tenant_a"])
    db = TestingSession()
    try:
        for i in range(6):
            _call(db, seeded["tenant_a"], seeded["agent_a"], score=85, days_ago=i)
        db.commit()
    finally:
        db.close()

    patch_session.award_badges()
    patch_session.award_badges()  # ayni hafta tekrar

    db = TestingSession()
    try:
        n = db.query(AgentBadge).filter(AgentBadge.agent_id == seeded["agent_a"]).count()
        assert n == 1, "ayni donemde ayni rozet tekrar verilmemeli"
    finally:
        db.close()


# =====================================================================
# Retention
# =====================================================================


def test_retention_deletes_old_calls(seeded, patch_session):
    """Saklama suresi dolan cagrilar silinmeli, yeniler kalmali."""
    from app.models import Tenant

    db = TestingSession()
    try:
        t = db.get(Tenant, seeded["tenant_a"])
        t.retention_days = 30
        _call(db, seeded["tenant_a"], seeded["agent_a"], score=80, days_ago=100)  # eski
        _call(db, seeded["tenant_a"], seeded["agent_a"], score=80, days_ago=5)    # yeni
        db.commit()
        before = db.query(Call).filter(Call.tenant_id == seeded["tenant_a"]).count()
    finally:
        db.close()

    patch_session.apply_retention()

    db = TestingSession()
    try:
        after = db.query(Call).filter(Call.tenant_id == seeded["tenant_a"]).count()
        assert after < before, "eski cagri silinmeliydi"
        remaining = db.query(Call).filter(Call.tenant_id == seeded["tenant_a"]).all()
        cutoff = datetime.utcnow() - timedelta(days=30)
        assert all(c.created_at >= cutoff for c in remaining)
    finally:
        db.close()
