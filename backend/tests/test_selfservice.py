"""Self-servis, gamification, uyum paketleri, bildirim testleri (3c/3d/4a/4b)."""

from datetime import datetime, timedelta

from app.models import Call, CallStatus, Challenge, Channel
from app.services import compliance_packs, gamification, notifications
from tests.conftest import TestingSession

_seq = 0


def _call(db, t, a, *, score=90, days_ago=0, zeroed=False):
    global _seq
    _seq += 1
    c = Call(tenant_id=t, agent_id=a, filename=f"g{_seq}.wav", audio_path="",
             channel=Channel.voice, status=CallStatus.done, total_score=score,
             zeroed=zeroed, created_at=datetime.utcnow() - timedelta(days=days_ago))
    db.add(c)
    db.flush()
    return c


# ---------------------------------------------------------------------------
# 3d — Gamification
# ---------------------------------------------------------------------------
class TestGamification:
    def test_points_zero_without_calls(self):
        assert gamification.points(None, 0, 0) == 0

    def test_points_reward_quality_and_volume(self):
        low = gamification.points(70.0, 5, 0)
        high = gamification.points(90.0, 5, 0)
        assert high > low
        # kriz yonetimi bonus ekler
        assert gamification.points(90.0, 5, 3) > gamification.points(90.0, 5, 0)

    def test_streak_counts_consecutive_good(self, seeded):
        db = TestingSession()
        try:
            t, a = seeded["tenant_a"], seeded["agent_a"]
            db.query(Call).filter(Call.agent_id == a).delete()  # seed cagrilarini temizle
            # en yeni -> en eski: 85, 90, 88, sonra 50 (seri kirilir)
            _call(db, t, a, score=50, days_ago=4)
            _call(db, t, a, score=88, days_ago=3)
            _call(db, t, a, score=90, days_ago=2)
            _call(db, t, a, score=85, days_ago=1)
            db.commit()
            assert gamification.current_streak(db, a) == 3
        finally:
            db.close()

    def test_streak_broken_at_top_is_zero(self, seeded):
        db = TestingSession()
        try:
            t, a = seeded["tenant_a"], seeded["agent_a"]
            db.query(Call).filter(Call.agent_id == a).delete()
            _call(db, t, a, score=90, days_ago=2)
            _call(db, t, a, score=40, days_ago=1)  # en yeni dusuk
            db.commit()
            assert gamification.current_streak(db, a) == 0
        finally:
            db.close()

    def test_challenge_progress_score_above(self, seeded):
        db = TestingSession()
        try:
            t, a = seeded["tenant_a"], seeded["agent_a"]
            for s in (90, 95, 70):
                _call(db, t, a, score=s)
            ch = Challenge(tenant_id=t, title="10 cagrida 85+", metric="score_above",
                           threshold=85.0, target=10, starts_at=datetime.utcnow() - timedelta(days=1))
            db.add(ch)
            db.commit()
            prog = gamification.active_challenges(db, t, a)
            c = next(x for x in prog if x["id"] == ch.id)
            assert c["progress"] == 2  # 90 ve 95
            assert c["completed"] is False
        finally:
            db.close()

    def test_challenge_team_scoped(self, seeded):
        db = TestingSession()
        try:
            t = seeded["tenant_a"]
            ch = Challenge(tenant_id=t, title="Takim ozel", metric="call_count",
                           target=1, team_id=seeded["team2"],
                           starts_at=datetime.utcnow() - timedelta(days=1))
            db.add(ch)
            db.commit()
            # team1 temsilcisi bu challenge'i gormemeli
            got = gamification.active_challenges(db, t, seeded["agent_a"], team_id=seeded["team1"])
            assert all(x["id"] != ch.id for x in got)
            # team2 gormeli
            got2 = gamification.active_challenges(db, t, seeded["agent_a"], team_id=seeded["team2"])
            assert any(x["id"] == ch.id for x in got2)
        finally:
            db.close()


# ---------------------------------------------------------------------------
# 4a — Uyum paketleri
# ---------------------------------------------------------------------------
class TestCompliancePacks:
    def test_kvkk_missing_disclosure_flagged(self):
        text = "Merhaba, size nasil yardimci olabilirim? Faturanizi kontrol ediyorum."
        v = compliance_packs.evaluate(text, ("kvkk",))
        keys = {x["rule"] for x in v}
        assert "kayit_bildirimi" in keys
        assert "aydinlatma" in keys

    def test_kvkk_satisfied_no_violation(self):
        text = ("Gorusmemiz kalite icin kayit altina alinmaktadir ve kisisel "
                "verileriniz KVKK kapsaminda islenmektedir. Buyurun.")
        v = compliance_packs.evaluate(text, ("kvkk",))
        assert v == []

    def test_pci_forbidden_present(self):
        text = "Lutfen bana kart numaranizi soyleyin ve guvenlik kodunu okuyun."
        v = compliance_packs.evaluate(text, ("pci",))
        assert any(x["type"] == "forbidden_present" for x in v)

    def test_unknown_pack_skipped(self):
        assert compliance_packs.evaluate("herhangi", ("yokboyle",)) == []

    def test_default_active_is_kvkk_only(self):
        v_default = compliance_packs.evaluate("bos metin")
        v_kvkk = compliance_packs.evaluate("bos metin", ("kvkk",))
        assert v_default == v_kvkk

    def test_list_packs_has_builtin(self):
        keys = {p["key"] for p in compliance_packs.list_packs()}
        assert {"kvkk", "pci"} <= keys

    def test_turkish_i_folding_matches(self):
        """Buyuk İ ile yazilmis KVKK metni de eslesmeli (fold hatasi regresyonu)."""
        text = "Görüşmemiz KAYIT ALTINA alınmaktadır. KİŞİSEL VERİLERİNİZ KVKK kapsamındadır."
        v = compliance_packs.evaluate(text, ("kvkk",))
        assert v == []


# ---------------------------------------------------------------------------
# 4b — Slack/Teams bildirimi
# ---------------------------------------------------------------------------
class TestNotifications:
    def test_event_not_in_list_skipped(self, monkeypatch):
        monkeypatch.setattr("app.config.settings.notify_events", "crisis")
        monkeypatch.setattr("app.config.settings.slack_webhook_url", "http://x")
        # low_score listede degil -> gonderilmez
        assert notifications.notify("low_score", {"message": "x"}) == 0

    def test_no_url_sends_nothing(self, monkeypatch):
        monkeypatch.setattr("app.config.settings.notify_events", "crisis")
        monkeypatch.setattr("app.config.settings.slack_webhook_url", "")
        monkeypatch.setattr("app.config.settings.teams_webhook_url", "")
        assert notifications.notify("crisis", {"message": "x"}) == 0

    def test_format_text_includes_agent_and_message(self):
        text = notifications._format_text("crisis", {"agent": "ayse", "message": "kriz var", "call_id": 5})
        assert "ayse" in text and "kriz var" in text and "5" in text
