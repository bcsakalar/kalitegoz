"""Derin analitik: zaman serisi, VoC trend, duygu dagilimi, kohort (Dalga 3a+3b)."""

from datetime import datetime, timedelta

from app.models import Call, CallStatus, Channel
from app.services import analytics
from tests.conftest import TestingSession

_seq = 0


def _call(db, tenant_id, agent_id, *, score=80, csat=4.0, days_ago=0, category="fatura",
          emotion="notr", churn="dusuk", tags=None, crisis=False):
    global _seq
    _seq += 1
    c = Call(
        tenant_id=tenant_id, agent_id=agent_id, filename=f"a{_seq}.wav", audio_path="",
        channel=Channel.voice, status=CallStatus.done, total_score=score,
        predicted_csat=csat, category=category, emotion=emotion, churn_risk=churn,
        intent_tags=tags or [], is_crisis=crisis,
        created_at=datetime.utcnow() - timedelta(days=days_ago),
    )
    db.add(c)
    db.flush()
    return c


class TestTimeseries:
    def test_daily_buckets_average(self, seeded):
        db = TestingSession()
        try:
            t, a = seeded["tenant_a"], seeded["agent_a"]
            _call(db, t, a, score=60, days_ago=1)
            _call(db, t, a, score=80, days_ago=1)  # ayni gun -> ortalama 70
            _call(db, t, a, score=90, days_ago=0)
            db.commit()
            # B10: donus artik {noktalar, grafik_cizilebilir, tekil_deger, ...}
            ts = analytics.metric_timeseries(db, t, "score", days=7, bucket="day")
            by_date = {r["date"]: r for r in ts["noktalar"]}
            yday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
            assert by_date[yday]["avg"] == 70.0
            assert by_date[yday]["count"] == 2
        finally:
            db.close()

    def test_week_bucket(self, seeded):
        db = TestingSession()
        try:
            t, a = seeded["tenant_a"], seeded["agent_a"]
            _call(db, t, a, days_ago=0)
            _call(db, t, a, days_ago=2)
            db.commit()
            ts = analytics.metric_timeseries(db, t, "score", days=30, bucket="week")
            assert len(ts["noktalar"]) >= 1
            assert all("date" in r and "avg" in r for r in ts["noktalar"])
            # B10: 2 nokta ile cizgi grafik cizilmez
            assert ts["grafik_cizilebilir"] is False
            assert ts["tekil_deger"] is not None
        finally:
            db.close()


class TestVoC:
    def test_category_increase_detected(self, seeded):
        db = TestingSession()
        try:
            t, a = seeded["tenant_a"], seeded["agent_a"]
            # onceki pencere (14-28 gun once): 2 iptal
            _call(db, t, a, category="iptal", days_ago=20)
            _call(db, t, a, category="iptal", days_ago=18)
            # son pencere (0-14 gun): 4 iptal -> %100 artis
            for d in (1, 3, 5, 7):
                _call(db, t, a, category="iptal", days_ago=d)
            db.commit()
            _voc = analytics.category_trends(db, t, days=14)
            trends = (_voc['kategoriler']['satirlar']
                      + _voc['etiketler']['satirlar'])
            iptal = next(x for x in trends if x["kind"] == "category" and x["label"] == "iptal")
            assert iptal["recent"] == 4
            assert iptal["prior"] == 2
            assert iptal["change_pct"] == 100.0
        finally:
            db.close()

    def test_intent_tags_trended(self, seeded):
        db = TestingSession()
        try:
            t, a = seeded["tenant_a"], seeded["agent_a"]
            _call(db, t, a, tags=["iptal-tehdidi"], days_ago=2)
            _call(db, t, a, tags=["iptal-tehdidi"], days_ago=4)
            db.commit()
            _voc = analytics.category_trends(db, t, days=14)
            trends = (_voc['kategoriler']['satirlar']
                      + _voc['etiketler']['satirlar'])
            intent = [x for x in trends if x["kind"] == "intent"]
            assert any(x["label"] == "iptal-tehdidi" and x["recent"] == 2 for x in intent)
        finally:
            db.close()


class TestEmotionAndChurn:
    def test_emotion_distribution(self, seeded):
        db = TestingSession()
        try:
            t, a = seeded["tenant_a"], seeded["agent_a"]
            _call(db, t, a, emotion="ofke")
            _call(db, t, a, emotion="ofke")
            _call(db, t, a, emotion="memnuniyet")
            db.commit()
            dist = analytics.emotion_distribution(db, t)
            assert dist.get("ofke") == 2
            assert dist.get("memnuniyet") == 1
        finally:
            db.close()

    def test_churn_summary(self, seeded):
        db = TestingSession()
        try:
            t, a = seeded["tenant_a"], seeded["agent_a"]
            _call(db, t, a, churn="yuksek")
            _call(db, t, a, churn="orta")
            db.commit()
            churn = analytics.churn_summary(db, t)
            assert churn["yuksek"] == 1 and churn["orta"] == 1
        finally:
            db.close()


class TestCohort:
    def test_team_cohort_isolated_by_tenant(self, seeded):
        db = TestingSession()
        try:
            t, a = seeded["tenant_a"], seeded["agent_a"]
            _call(db, t, a, score=90)
            _call(db, seeded["tenant_b"], seeded["agent_b"], score=10)  # baska tenant
            db.commit()
            cohorts = analytics.cohort_compare(db, t, "team")
            # tenant_b'nin dusuk puani buraya sizmamali
            for c in cohorts:
                assert (c["avg_score"] or 100) > 50
        finally:
            db.close()
