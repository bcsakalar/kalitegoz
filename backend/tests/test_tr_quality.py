"""B16 — AI ciktisi Turkce kalite denetimi."""

from __future__ import annotations

import pytest

from app.services import tr_quality as tq


def test_ascii_turkce_yakalanir():
    """Ekranda gorulen gercek ornek."""
    assert tq.ascii_turkce_mi(
        "Temsilci agir yasakli ifade kullandi ve musteri cagriyi kapatti icin ozur diledi."
    )


def test_dogru_turkce_gecer():
    assert not tq.ascii_turkce_mi(
        "Temsilci ağır yasaklı ifade kullandı ve müşteri çağrıyı kapattığı için özür diledi."
    )


def test_kisa_metin_yanlis_alarm_vermez():
    """'Tamam.' gibi kisa cumlelerde diakritik olmamasi normaldir."""
    assert not tq.ascii_turkce_mi("Takip gerekmiyor.")
    assert not tq.ascii_turkce_mi("Tamam.")


def test_ingilizce_alinti_yanlis_alarm_vermez():
    """Diakritik yok ama Turkce parmak izi de yok."""
    assert not tq.ascii_turkce_mi(
        "The customer requested a refund and the agent processed it immediately today."
    )


def test_denetle_sorunlu_alanlari_dondurur():
    sorunlu = tq.denetle({
        "ozet": "Musteri fatura icin aradi ve temsilci dogru bilgi verdi ancak cozum olmadi.",
        "aksiyon": "Takip gerekmiyor.",
        "koclu": "Temsilci müşteriyi dinledi ve çözüm üretti; başarılı bir çağrıydı.",
    })
    assert sorunlu == ["ozet"]


def test_duzeltme_istegi_alan_adlarini_icerir():
    metin = tq.duzeltme_istegi(["ozet", "gelisim_onerisi"])
    assert "ozet" in metin and "gelisim_onerisi" in metin
    assert "ç" in metin and "ğ" in metin


def test_diakritik_orani():
    assert tq.diakritik_orani("çğıöşü") == 1.0
    assert tq.diakritik_orani("abc") == 0.0
