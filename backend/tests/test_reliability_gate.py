"""Olculmus guvenilirlik kapisi — sistem sinirini bilir ve yonetir.

FAZ 3 olcumu, dort oznel kriterde AI'nin uzmanla uyumunun rastlantidan zor
ayirt edildigini gosterdi (kappa 0.03-0.21). Bu bir kusur degil, YONETILMESI
gereken bir sinirdir: o kriterlerde guven skoru tavanlanir ve cagri insan
onayina duser.
"""

from __future__ import annotations

import pytest

from app.services import calibration_scale as cs


@pytest.mark.parametrize("kriter", [
    "KVKK / Aydinlatma", "Yasakli Kelime / Uslup", "Acilis", "Kapanis",
])
def test_guvenilir_kriterlerde_tavan_yok(kriter):
    assert cs.confidence_cap(kriter, "B") is None


@pytest.mark.parametrize("kriter", [
    "Aktif Dinleme", "Ihtiyac Analizi", "Cozum / Yonlendirme",
    "Bilgi Dogrulugu", "Script Uyumu",
])
def test_guvenilmez_kriterlerde_guven_tavanlanir(kriter):
    cap = cs.confidence_cap(kriter, "B")
    assert cap is not None
    assert cap < 0.70, "Tavan, insan kuyrugu esiginin (0.70) ALTINDA olmali"


def test_deterministik_karar_tavanlanmaz():
    """Katman A kararlarinin olculen kappa'si 0.90+; sinirlamak yanlis olur."""
    assert cs.confidence_cap("Aktif Dinleme", "A") is None


def test_bilinmeyen_kriter_serbest():
    assert cs.confidence_cap("Yeni Ozel Kriter", "B") is None


def test_tavan_insan_incelemesini_GARANTI_eder():
    """Tavan, qa_workflow kural 3'un esigini kesin olarak tetiklemeli."""
    from app.services.qa_workflow import DEFAULTS

    assert cs.UNRELIABLE_CONFIDENCE_CAP < DEFAULTS["confidence_threshold"]
