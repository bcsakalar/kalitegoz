"""QA ornekleme/atama (2b) + kocluk etkinlik dongusu (2c) testleri."""

import random
from datetime import datetime, timedelta

from app.models import (
    Call,
    CallStatus,
    Channel,
    CoachingTask,
    ReviewReason,
    ReviewStatus,
    TaskStatus,
)
from app.services import coaching_effect, sampling
from tests.conftest import TestingSession

_seq = 0


def _mk_call(db, tenant_id, agent_id, score=80, created=None, **kw):
    global _seq
    _seq += 1
    c = Call(
        tenant_id=tenant_id, agent_id=agent_id, filename=f"c{_seq}.wav", audio_path="",
        channel=Channel.voice, status=CallStatus.done, total_score=score,
        created_at=created or datetime.utcnow(), **kw,
    )
    db.add(c)
    db.flush()
    return c


# ---------------------------------------------------------------------------
# 2b — QA ornekleme & atama
# ---------------------------------------------------------------------------
class TestSampling:
    def test_random_sample_assigns_requested_count(self, seeded):
        db = TestingSession()
        try:
            t, agent, rev = seeded["tenant_a"], seeded["agent_a"], seeded["sup_user_a"]
            for _ in range(10):
                _mk_call(db, t, agent)
            db.commit()
            out = sampling.sample_and_assign(db, t, rev, ReviewReason.random, 4, rng=random.Random(1))
            assert len(out) == 4
            assert all(a.status == ReviewStatus.assigned for a in out)
        finally:
            db.close()

    def test_no_duplicate_assignment_to_same_reviewer(self, seeded):
        db = TestingSession()
        try:
            t, agent, rev = seeded["tenant_a"], seeded["agent_a"], seeded["sup_user_a"]
            for _ in range(5):
                _mk_call(db, t, agent)
            db.commit()
            # Havuzu tuket: cok buyuk sayilarla iki kez ornekle
            first = sampling.sample_and_assign(db, t, rev, ReviewReason.random, 100, rng=random.Random(1))
            second = sampling.sample_and_assign(db, t, rev, ReviewReason.random, 100, rng=random.Random(2))
            # Ikinci turda atanacak yeni cagri kalmamali (hepsi tuketildi)
            assert len(second) == 0
            # Ve hicbir cagri iki kez atanmamis olmali
            call_ids = [a.call_id for a in first]
            assert len(call_ids) == len(set(call_ids))
        finally:
            db.close()

    def test_low_confidence_filters_emotion_mismatch(self, seeded):
        db = TestingSession()
        try:
            t, agent, rev = seeded["tenant_a"], seeded["agent_a"], seeded["sup_user_a"]
            _mk_call(db, t, agent, emotion_mismatch=False)
            _mk_call(db, t, agent, emotion_mismatch=True)
            _mk_call(db, t, agent, emotion_mismatch=True)
            db.commit()
            out = sampling.sample_and_assign(db, t, rev, ReviewReason.low_confidence, 10)
            assert len(out) == 2
        finally:
            db.close()

    def test_critical_filters_zeroed_or_crisis(self, seeded):
        db = TestingSession()
        try:
            t, agent, rev = seeded["tenant_a"], seeded["agent_a"], seeded["sup_user_a"]
            _mk_call(db, t, agent, zeroed=False, is_crisis=False)
            _mk_call(db, t, agent, zeroed=True)
            _mk_call(db, t, agent, is_crisis=True)
            db.commit()
            out = sampling.sample_and_assign(db, t, rev, ReviewReason.critical, 10)
            assert len(out) == 2
        finally:
            db.close()

    def test_requesting_more_than_available_returns_available(self, seeded):
        db = TestingSession()
        try:
            t, agent, rev = seeded["tenant_a"], seeded["agent_a"], seeded["sup_user_a"]
            _mk_call(db, t, agent)
            db.commit()
            out = sampling.sample_and_assign(db, t, rev, ReviewReason.random, 50)
            # seeded zaten 1 done cagri iceriyor (call_a) + bizimki = en fazla mevcut
            assert 1 <= len(out) <= 3
        finally:
            db.close()

    def test_stats_reports_completion_rate(self, seeded):
        db = TestingSession()
        try:
            t, agent, rev = seeded["tenant_a"], seeded["agent_a"], seeded["sup_user_a"]
            for _ in range(3):
                _mk_call(db, t, agent)
            db.commit()
            out = sampling.sample_and_assign(db, t, rev, ReviewReason.random, 4, rng=random.Random(1))
            sampling.complete_assignment(db, out[0])
            stats = sampling.review_stats(db, t)
            assert stats["total"] == len(out)
            assert stats["counts"]["completed"] == 1
        finally:
            db.close()

    def test_tenant_isolation(self, seeded):
        db = TestingSession()
        try:
            # tenant_b'nin cagrisi tenant_a havuzuna girmemeli
            out = sampling.sample_and_assign(
                db, seeded["tenant_a"], seeded["sup_user_a"], ReviewReason.random, 10)
            # tenant_a'da yalnizca seed'in call_a + call_other_team'i var (2 done)
            for a in out:
                call = db.get(Call, a.call_id)
                assert call.tenant_id == seeded["tenant_a"]
        finally:
            db.close()


# ---------------------------------------------------------------------------
# 2c — Kocluk etkinlik dongusu
# ---------------------------------------------------------------------------
class TestCoachingEffectiveness:
    def _coaching(self, db, tenant_id, agent_id, ref, call_id):
        task = CoachingTask(
            tenant_id=tenant_id, call_id=call_id, assigner_id=1, assignee_agent_id=agent_id,
            note="test", status=TaskStatus.done, created_at=ref, completed_at=ref,
        )
        db.add(task)
        db.flush()
        return task

    def test_measures_improvement(self, seeded):
        db = TestingSession()
        try:
            t, agent = seeded["tenant_a"], seeded["agent_a"]
            ref = datetime.utcnow() - timedelta(days=1)
            for _ in range(4):
                _mk_call(db, t, agent, score=60, created=ref - timedelta(days=3))
            for _ in range(4):
                _mk_call(db, t, agent, score=85, created=ref + timedelta(days=3))
            self._coaching(db, t, agent, ref, seeded["call_a"])
            db.commit()
            rep = coaching_effect.effectiveness_report(db, t)
            assert rep["measurable_count"] == 1
            assert rep["improved_count"] == 1
            assert rep["effects"][0]["improved"] is True
            assert rep["effects"][0]["delta"] > 0
        finally:
            db.close()

    def test_insufficient_data_not_measurable(self, seeded):
        db = TestingSession()
        try:
            t, agent = seeded["tenant_a"], seeded["agent_a"]
            ref = datetime.utcnow() - timedelta(days=1)
            _mk_call(db, t, agent, score=60, created=ref - timedelta(days=3))
            for _ in range(4):
                _mk_call(db, t, agent, score=85, created=ref + timedelta(days=3))
            self._coaching(db, t, agent, ref, seeded["call_a"])
            db.commit()
            rep = coaching_effect.effectiveness_report(db, t)
            assert rep["measurable_count"] == 0
        finally:
            db.close()

    def test_no_completed_coaching_empty_report(self, seeded):
        db = TestingSession()
        try:
            rep = coaching_effect.effectiveness_report(db, seeded["tenant_a"])
            assert rep["measurable_count"] == 0
            assert rep["effects"] == []
        finally:
            db.close()
