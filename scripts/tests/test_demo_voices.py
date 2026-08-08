"""Demo seslendirme testleri: ses/metin tutarliligi ve konusmaci varyantlari.

Bu testler AG ERISIMI GEREKTIRMEZ — edge-tts cagrilmaz, yalnizca cinsiyet
atama mantigi ve varyant uretimi dogrulanir. Gercek ses uretimi
`--tts-engine edge` ile elle dogrulanir (bkz. run.md).
"""

import importlib.util
import random
import re
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

from tts_engines import (  # noqa: E402
    EDGE_VOICES,
    MIN_PITCH_GAP,
    PIPER_PITCH,
    speaker_variant,
)


def _load_demo():
    spec = importlib.util.spec_from_file_location("gd", SCRIPTS / "generate_demo.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


gd = _load_demo()

HONORIFIC = re.compile(r"([A-Za-zÇĞİÖŞÜçğıöşü]{2,})\s+(Bey|Hanım)")


class TestAgentGender:
    def test_roster_female(self):
        for name in gd.FEMALE_AGENTS:
            assert gd.agent_gender(name) == "kadin", name

    def test_roster_male(self):
        for name in gd.MALE_AGENTS:
            assert gd.agent_gender(name) == "erkek", name

    def test_roster_wins_over_lexicon_for_unisex_name(self):
        """'deniz' sozlukte unisex; kadro kadin diyorsa kadin olmali."""
        assert "deniz.yildiz" in gd.FEMALE_AGENTS
        assert gd.agent_gender("deniz.yildiz") == "kadin"

    def test_unknown_agent_falls_back_to_lexicon(self):
        assert gd.agent_gender("fatma.ozkan") == "kadin"
        assert gd.agent_gender("hasan.tekin") == "erkek"

    def test_every_dialog_agent_is_in_roster(self):
        """Kadro disi temsilci sessizce 'erkek' olur — bunu erken yakala."""
        roster = gd.FEMALE_AGENTS | gd.MALE_AGENTS
        for d in gd.DIALOGS:
            assert d["agent"] in roster, f"kadroda yok: {d['agent']}"


class TestCustomerGender:
    def test_honorific_drives_customer_voice(self):
        rng = random.Random(0)
        turns = [{"k": "t", "m": "Fatma Hanım, faturanızı kontrol ediyorum."},
                 {"k": "m", "m": "Teşekkürler."}]
        assert gd.customer_gender(turns, rng) == "kadin"

    def test_customer_addressing_agent_is_ignored(self):
        """'Ayse Hanim' diyen MUSTERI ise, bu temsilciye hitaptir —
        musterinin cinsiyeti hakkinda bilgi vermez."""
        rng = random.Random(0)
        turns = [{"k": "t", "m": "Merhaba, ben Ayşe."},
                 {"k": "m", "m": "Ayşe Hanım, faturamda sorun var."}]
        results = {gd.customer_gender(turns, random.Random(s)) for s in range(20)}
        # Hitap yok sayildigi icin rastgeleye duser: her iki sonuc da cikmali
        assert results == {"kadin", "erkek"}

    def test_falls_back_to_random_without_honorific(self):
        turns = [{"k": "t", "m": "Size nasıl yardımcı olabilirim?"},
                 {"k": "m", "m": "İnternetim çalışmıyor."}]
        results = {gd.customer_gender(turns, random.Random(s)) for s in range(20)}
        assert results == {"kadin", "erkek"}

    def test_no_dialog_contradicts_its_honorific(self):
        """REGRESYON: eskiden musteri 'temsilcinin ziddi' atanirdi ve 12
        cagrinin 7'sinde ses hitapla celisiyordu ('Fatma Hanim' erkek sesle)."""
        rng = random.Random(42)
        for d in gd.DIALOGS:
            agent_text = " ".join(t["m"] for t in d["turns"] if t["k"] == "t")
            m = HONORIFIC.search(agent_text)
            if not m:
                continue
            expected = "erkek" if m.group(2) == "Bey" else "kadin"
            assert gd.customer_gender(d["turns"], rng) == expected, \
                f"{d['agent']}: '{m.group(0)}' hitabi ile ses celisiyor"

    def test_gender_mix_stays_balanced(self):
        """Zorlama 'zit cinsiyet' kuralini kaldirdik; karisim yine de dengeli
        kalmali (tek cinsiyete cokerse demo inandiriciligini kaybeder)."""
        rng = random.Random(42)
        voices = []
        for d in gd.DIALOGS:
            voices.append(gd.agent_gender(d["agent"]))
            voices.append(gd.customer_gender(d["turns"], rng))
        female = voices.count("kadin")
        assert 0.3 <= female / len(voices) <= 0.7, f"dengesiz: {female}/{len(voices)}"


class TestSpeakerVariant:
    def test_deterministic(self):
        assert speaker_variant("ayse.yilmaz") == speaker_variant("ayse.yilmaz")

    def test_differs_between_speakers(self):
        """Ayni cinsiyetteki temsilciler ayni sesle cikmamali."""
        variants = {speaker_variant(a) for a in gd.FEMALE_AGENTS}
        assert len(variants) > 1

    def test_empty_speaker_is_neutral(self):
        assert speaker_variant("") == (0, 0)

    def test_offsets_stay_narrow(self):
        """Genis kaydirma formant bozar — tam da kacindigimiz sey."""
        for a in gd.FEMALE_AGENTS | gd.MALE_AGENTS:
            rate, pitch = speaker_variant(a)
            assert -10 <= rate <= 10
            assert -20 <= pitch <= 20


class TestWithinCallSeparation:
    """Ayni cagrida ayni cinsiyetten iki kisi ayirt edilebilmeli."""

    def test_avoid_pitch_pushes_result_away(self):
        for spk in ["musteri-01", "musteri-07", "x", "zeynep.demir"]:
            for avoid in (-16, -8, 0, 8, 16):
                _, pitch = speaker_variant(spk, avoid_pitch=avoid)
                assert abs(pitch - avoid) >= MIN_PITCH_GAP, (spk, avoid, pitch)

    def test_avoid_pitch_is_deterministic(self):
        assert speaker_variant("musteri-03", 0) == speaker_variant("musteri-03", 0)

    def test_no_op_when_already_far(self):
        """Zaten uzaksa varyant DEGISMEMELI (gereksiz kayma yok)."""
        base = speaker_variant("musteri-01")          # (-6, -16)
        far = base[1] + 2 * MIN_PITCH_GAP
        assert speaker_variant("musteri-01", far) == base

    def test_same_gender_calls_get_separated_speakers(self):
        """REGRESYON: erkek temsilci + erkek musteri ayni tonda cikmasin."""
        rng = random.Random(42)
        for i, d in enumerate(gd.DIALOGS, 1):
            tg = gd.agent_gender(d["agent"])
            mg = gd.customer_gender(d["turns"], rng)
            if tg != mg:
                continue
            a_pitch = speaker_variant(d["agent"])[1]
            m_pitch = speaker_variant(f"musteri-{i:02d}", avoid_pitch=a_pitch)[1]
            assert abs(a_pitch - m_pitch) >= MIN_PITCH_GAP, \
                f"{d['agent']} cagri {i}: temsilci ve musteri ayni tonda ({tg})"


class TestEdgeVoices:
    def test_both_genders_mapped(self):
        assert set(EDGE_VOICES) == {"kadin", "erkek"}

    def test_voices_are_distinct_speakers(self):
        """Ayni modelin pitch'lenmis hali DEGIL, iki ayri konusmaci olmali."""
        assert EDGE_VOICES["kadin"] != EDGE_VOICES["erkek"]
        assert EDGE_VOICES["kadin"] == "tr-TR-EmelNeural"
        assert EDGE_VOICES["erkek"] == "tr-TR-AhmetNeural"


class TestPiperFallbackLimits:
    """dfki bir ERKEK sesidir (olculen F0 ~108 Hz) — bu bir sinir, hata degil.

    Bu testler sinirin BILINCLI oldugunu sabitler. Eski kod dfki'yi kadin sanip
    1.06 ile carpiyordu; sonuc ~114 Hz, yani hala erkek — demoda "iki konusmaci
    da erkek" duyulmasinin sebebi tam olarak buydu.
    """

    def test_female_factor_does_not_pretend_to_reach_female_range(self):
        """1.75+ bir faktor kadin araligina cikarirdi ama tempoyu %75 hizlandirip
        konusmayi anlasilmaz yapardi. Boyle bir deger BILEREK secilmemeli."""
        assert PIPER_PITCH["kadin"] < 1.3, (
            "Piper resample tabanli: buyuk faktor tempoyu da bozar. "
            "Gercek cinsiyet icin edge-tts kullanilmali."
        )

    def test_factors_stay_within_intelligible_tempo(self):
        """Tempo kaymasi +/-%20'yi asarsa konusma bozulur."""
        for gender, f in PIPER_PITCH.items():
            assert 0.8 <= f <= 1.2, f"{gender}: {f} tempoyu asiri bozar"

    def test_two_speakers_still_differ(self):
        """Cinsiyet veremesek de iki konusmaci ayirt edilebilmeli."""
        assert PIPER_PITCH["kadin"] != PIPER_PITCH["erkek"]
        ratio = PIPER_PITCH["kadin"] / PIPER_PITCH["erkek"]
        assert ratio >= 1.15, "iki konusmaci arasindaki fark duyulmayacak kadar kucuk"
