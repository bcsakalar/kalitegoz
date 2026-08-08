"""Turkce ad/hitap -> cinsiyet cikarimi testleri."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tr_gender import (  # noqa: E402
    FEMALE_NAMES,
    MALE_NAMES,
    UNISEX_NAMES,
    gender_from_honorific,
    gender_from_name,
    infer_speaker_gender,
)


class TestGenderFromName:
    @pytest.mark.parametrize("name", ["ayse", "Ayşe", "ayse.yilmaz", "Ayşe Yılmaz",
                                      "zeynep.demir", "ELIF", "Fatma"])
    def test_female(self, name):
        assert gender_from_name(name) == "kadin"

    @pytest.mark.parametrize("name", ["mehmet", "Mehmet Kaya", "mehmet.kaya",
                                      "emre.sahin", "Hasan", "BURAK"])
    def test_male(self, name):
        assert gender_from_name(name) == "erkek"

    def test_turkish_dotted_i_normalizes(self):
        # 'İ' ve 'I' ASCII katlamasindan sonra 'i' olmali
        assert gender_from_name("İrem") == "kadin"
        assert gender_from_name("Ilknur") == "kadin"

    @pytest.mark.parametrize("name", ["deniz", "Deniz Yıldız", "Özgür", "Şafak"])
    def test_unisex_returns_none(self, name):
        """Unisex adlarda sessizce tahmin etmektense belirsiz demek dogru."""
        assert gender_from_name(name) is None

    @pytest.mark.parametrize("name", ["", "   ", "xyzqwe", "Zzz Zzz"])
    def test_unknown_returns_none(self, name):
        assert gender_from_name(name) is None


class TestGenderFromHonorific:
    def test_bey_is_male(self):
        assert gender_from_honorific("Teşekkürler Mehmet Bey, iyi günler.") == "erkek"

    def test_hanim_is_female(self):
        assert gender_from_honorific("Fatma Hanım, faturanızı kontrol ettim.") == "kadin"

    def test_hanim_without_turkish_chars(self):
        assert gender_from_honorific("Fatma Hanim, buyurun.") == "kadin"

    def test_first_honorific_wins(self):
        assert gender_from_honorific("Ayten Hanım ... Mehmet Bey") == "kadin"

    def test_no_honorific(self):
        assert gender_from_honorific("Merhaba, size nasıl yardımcı olabilirim?") is None

    def test_bare_word_bey_is_not_honorific(self):
        """'Bey' tek basina gecerse (ad olmadan) hitap sayilmaz."""
        assert gender_from_honorific("Bey efendi geldi") is None


class TestInferSpeakerGender:
    def test_honorific_beats_name(self):
        """Hitap ad sozlugunden GUCLU sinyaldir: metin kime hitap ettigini soyler."""
        assert infer_speaker_gender(text="Mehmet Bey", name="ayse") == "erkek"

    def test_falls_back_to_name(self):
        assert infer_speaker_gender(text="merhaba", name="zeynep.demir") == "kadin"

    def test_falls_back_to_default(self):
        assert infer_speaker_gender(text="merhaba", name="xyz", default="kadin") == "kadin"

    def test_returns_none_when_nothing_known(self):
        assert infer_speaker_gender(text="merhaba", name="xyz") is None


class TestLexiconHygiene:
    def test_no_accidental_overlap_outside_unisex(self):
        """Bir ad iki listede birden ise unisex olarak isaretli olmali."""
        assert (FEMALE_NAMES & MALE_NAMES) <= UNISEX_NAMES

    def test_lexicon_is_ascii_folded(self):
        """Sozluk anahtarlari normalize edilmis olmali; yoksa eslesme kacar."""
        for name in FEMALE_NAMES | MALE_NAMES:
            assert name.isascii() and name.islower(), f"normalize degil: {name!r}"
