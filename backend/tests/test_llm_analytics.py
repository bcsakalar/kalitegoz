"""LLM analitik paketi (Dalga 1): duygu/churn/CES/niyet normalize + uyumsuzluk.

LLM cagrilmaz — cikti semasi ve turetilmis mantik test edilir. Modelin
inandiriciligi degil, ciktisinin HER ZAMAN gecerli bir sekle zorlandigi ve
turetilen bayraklarin dogru oldugu dogrulanir.
"""

import pytest

from app.schemas import (
    EMOTIONS,
    LLMDegerlendirme,
    _norm_emotion,
    _norm_risk,
    _norm_trajectory,
)
from app.services.scoring import _detect_emotion_mismatch


def _eval(**kw):
    base = {"puanlar": [{"kriter_id": 1, "puan": 8}]}
    base.update(kw)
    return LLMDegerlendirme(**base)


class TestEmotionNormalization:
    @pytest.mark.parametrize("raw,expected", [
        ("ofke", "ofke"), ("Öfke", "ofke"), ("kizgin", "ofke"), ("angry", "ofke"),
        ("frustration", "hayal_kirikligi"), ("hayal kirikligi", "hayal_kirikligi"),
        ("happy", "memnuniyet"), ("memnun", "memnuniyet"),
        ("grateful", "minnettarlik"), ("sad", "uzuntu"), ("worried", "endise"),
    ])
    def test_aliases(self, raw, expected):
        assert _norm_emotion(raw) == expected

    def test_unknown_falls_back_to_neutral(self):
        assert _norm_emotion("bilinmeyen_sey") == "notr"
        assert _norm_emotion(None) == "notr"

    def test_all_canonical_emotions_pass_through(self):
        for e in EMOTIONS:
            assert _norm_emotion(e) == e


class TestTrajectoryAndRisk:
    @pytest.mark.parametrize("raw,expected", [
        ("yukselen", "yukselen"), ("rising", "yukselen"), ("iyilesen", "yukselen"),
        ("dusen", "dusen"), ("down", "dusen"), ("stable", "sabit"),
    ])
    def test_trajectory(self, raw, expected):
        assert _norm_trajectory(raw) == expected

    @pytest.mark.parametrize("raw,expected", [
        ("yuksek", "yuksek"), ("high", "yuksek"), ("orta", "orta"),
        ("low", "dusuk"), ("yok", "dusuk"), ("sacma", "dusuk"),
    ])
    def test_risk(self, raw, expected):
        assert _norm_risk(raw) == expected


class TestIntentTags:
    def test_normalized_and_deduped(self):
        r = _eval(niyet_etiketleri=["İptal Tehdidi", "iptal tehdidi", "Fatura-İtiraz"])
        # kucuk harf + bosluk->tire + tekillestirme
        assert r.niyet_etiketleri == ["iptal-tehdidi", "fatura-itiraz"]

    def test_capped_at_six(self):
        r = _eval(niyet_etiketleri=[f"etiket{i}" for i in range(10)])
        assert len(r.niyet_etiketleri) == 6

    def test_non_list_becomes_empty(self):
        assert _eval(niyet_etiketleri="tek").niyet_etiketleri == []

    def test_empty_strings_dropped(self):
        assert _eval(niyet_etiketleri=["", "  ", "gecerli"]).niyet_etiketleri == ["gecerli"]


class TestCESClamp:
    def test_clamped_to_range(self):
        assert _eval(musteri_efor=9).musteri_efor == 5.0
        assert _eval(musteri_efor=-3).musteri_efor == 1.0

    def test_garbage_defaults_to_mid(self):
        assert _eval(musteri_efor="cok").musteri_efor == 3.0


class TestEmotionMismatch:
    def test_angry_but_high_csat_is_mismatch(self):
        """Musteri ofkeli bitip CSAT 4.5 tahmin edildiyse AI kendiyle celisiyor."""
        assert _detect_emotion_mismatch("olumsuz", "ofke", 4.5) is True

    def test_happy_but_low_csat_is_mismatch(self):
        assert _detect_emotion_mismatch("olumlu", "memnuniyet", 1.5) is True

    def test_consistent_negative_is_not_mismatch(self):
        assert _detect_emotion_mismatch("olumsuz", "ofke", 1.5) is False

    def test_consistent_positive_is_not_mismatch(self):
        assert _detect_emotion_mismatch("olumlu", "memnuniyet", 4.5) is False

    def test_neutral_mid_is_not_mismatch(self):
        assert _detect_emotion_mismatch("notr", "notr", 3.0) is False

    def test_frustration_counts_as_negative_feeling(self):
        assert _detect_emotion_mismatch("notr", "hayal_kirikligi", 4.5) is True


class TestSchemaDefaults:
    def test_missing_fields_get_safe_defaults(self):
        """LLM yeni alanlari hic dondurmezse (eski model) sema patlamamali."""
        r = _eval()
        assert r.baskin_duygu == "notr"
        assert r.duygu_yorungesi == "sabit"
        assert r.churn_riski == "dusuk"
        assert r.musteri_efor == 3.0
        assert r.niyet_etiketleri == []
        assert r.sonraki_aksiyon == ""


# --- Uyum kontrolunun puanlamaya baglanmasi ---
#
# FAZ 2'de uyum kontrolu `compliance_packs`ten Katman A'ya (deterministic.py)
# tasindi. Fark sadece modul degil: compliance_packs YALNIZ alarm uretiyordu,
# puana hic dokunmuyordu — bu yuzden KVKK anonsu hic yapilmamis bir cagri 92
# puan alabiliyordu (B32). Katman A bulgusu ARTIK kriter puanini belirler.
#
# compliance_packs modulu canli asistan (assist.py) ve panel listesi
# (selfservice.py) icin duruyor; puanlama yolunda kullanilmiyor.
class TestUyumKontroluPuanlamayaBagli:
    def test_katman_a_scoring_e_bagli(self):
        """scoring modulu deterministik katmani import ediyor olmali (regresyon)."""
        from app.services import scoring
        assert hasattr(scoring, "deterministic")
        assert hasattr(scoring, "scoring_layers")

    def test_b32_kvkk_anonsu_yoksa_kriter_puani_sifir(self):
        """B32: eksik KVKK anonsu artik SADECE alarm degil, PUAN da uretir."""
        from dataclasses import dataclass

        from app.services import deterministic as det

        @dataclass
        class S:
            speaker: str
            text: str
            start_sec: float
            end_sec: float

        segs = [
            S("temsilci", "Netik İletişim, ben Ceyda, buyurun.", 1.0, 4.0),
            S("temsilci", "Adınızı ve müşteri numaranızı alabilir miyim?", 4.5, 8.0),
            S("musteri", "Okan Yılmaz, 771450.", 8.5, 11.0),
        ]
        f = det.check_kvkk(segs)
        assert f.decision == "not_met"
        assert f.score == 0, "Eksik anons puana yansimadi — B32 geri geldi"

    def test_canli_asistan_uyum_paketlerini_kullanmaya_devam_ediyor(self):
        from app.services import compliance_packs
        v = compliance_packs.evaluate("Buyurun, size nasil yardimci olabilirim?")
        assert any(x["type"] == "missing_required" for x in v)
        assert all(x["pack"] == "kvkk" for x in v)  # DEFAULT_ACTIVE
