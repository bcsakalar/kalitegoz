"""FCR: tekrar arama tespiti ve gercek/tahmini FCR hesabi."""

from datetime import datetime, timedelta

from app.models import Call, CallStatus, Channel
from app.services import fcr
from tests.conftest import TestingSession


def _call(db, tenant_id, agent_id, *, ref=None, days_ago=0, score=85.0, crisis=False):
    c = Call(
        tenant_id=tenant_id, filename=f"c{days_ago}.wav", audio_path="",
        channel=Channel.voice, agent_id=agent_id, status=CallStatus.done,
        total_score=score, is_crisis=crisis, customer_ref=ref,
        created_at=datetime.utcnow() - timedelta(days=days_ago),
    )
    db.add(c)
    db.flush()
    return c


def test_detects_repeat_within_window(seeded):
    db = TestingSession()
    try:
        _call(db, seeded["tenant_a"], seeded["agent_a"], ref="MUS-1", days_ago=3)
        today = _call(db, seeded["tenant_a"], seeded["agent_a"], ref="MUS-1", days_ago=0)
        db.commit()
        prev = fcr.detect_repeat(db, today)
        assert prev is not None, "3 gun onceki cagri tekrar olarak bulunmali"
    finally:
        db.close()


def test_no_repeat_outside_window(seeded):
    """Pencere disindaki (>7 gun) cagri tekrar SAYILMAZ."""
    db = TestingSession()
    try:
        _call(db, seeded["tenant_a"], seeded["agent_a"], ref="MUS-2", days_ago=30)
        today = _call(db, seeded["tenant_a"], seeded["agent_a"], ref="MUS-2", days_ago=0)
        db.commit()
        assert fcr.detect_repeat(db, today) is None
    finally:
        db.close()


def test_different_customer_is_not_repeat(seeded):
    db = TestingSession()
    try:
        _call(db, seeded["tenant_a"], seeded["agent_a"], ref="MUS-A", days_ago=2)
        other = _call(db, seeded["tenant_a"], seeded["agent_a"], ref="MUS-B", days_ago=0)
        db.commit()
        assert fcr.detect_repeat(db, other) is None
    finally:
        db.close()


def test_no_customer_ref_means_no_repeat_detection(seeded):
    db = TestingSession()
    try:
        c = _call(db, seeded["tenant_a"], seeded["agent_a"], ref=None)
        db.commit()
        assert fcr.detect_repeat(db, c) is None
    finally:
        db.close()


def test_repeat_detection_is_tenant_scoped(seeded):
    """Baska tenant'in ayni musteri referansi tekrar sayilmamali."""
    db = TestingSession()
    try:
        _call(db, seeded["tenant_b"], seeded["agent_b"], ref="ORTAK-REF", days_ago=1)
        mine = _call(db, seeded["tenant_a"], seeded["agent_a"], ref="ORTAK-REF", days_ago=0)
        db.commit()
        assert fcr.detect_repeat(db, mine) is None
    finally:
        db.close()


def test_apply_repeat_flags_sets_fields(seeded):
    db = TestingSession()
    try:
        first = _call(db, seeded["tenant_a"], seeded["agent_a"], ref="MUS-9", days_ago=2)
        second = _call(db, seeded["tenant_a"], seeded["agent_a"], ref="MUS-9", days_ago=0)
        db.commit()
        fcr.apply_repeat_flags(db, second)
        db.commit()
        assert second.is_repeat is True
        assert second.repeat_of_id == first.id
    finally:
        db.close()


def test_real_fcr_when_enough_identified_calls(seeded):
    """10+ musteri referansli cagri varsa GERCEK FCR hesaplanir."""
    db = TestingSession()
    try:
        # 10 farkli musteri; 2'si tekrar aramis => FCR %80
        for i in range(10):
            c = _call(db, seeded["tenant_a"], seeded["agent_a"], ref=f"M{i}", days_ago=1)
            if i < 2:
                c.is_repeat = True
        db.commit()
        pct, is_real = fcr.compute_fcr(db, seeded["tenant_a"])
        assert is_real is True, "gercek FCR moduna gecmeliydi"
        assert pct == 80.0
    finally:
        db.close()


def test_estimated_fcr_without_customer_refs(seeded):
    """Musteri referansi yoksa TAHMINI moda duser."""
    db = TestingSession()
    try:
        _call(db, seeded["tenant_a"], seeded["agent_a"], score=90.0)
        _call(db, seeded["tenant_a"], seeded["agent_a"], score=40.0)  # dusuk -> cozulmemis
        db.commit()
        pct, is_real = fcr.compute_fcr(db, seeded["tenant_a"])
        assert is_real is False
        assert pct is not None
    finally:
        db.close()
