"""B3 regresyonu: soz kesme sayaci — kim kesti, kac kez?

Kok neden: docs/v2/01-KOK-NEDEN.md §D. Sisen STT segment bitisleri her konusmaci
degisimini "bindirme" gosteriyordu; canli cagri #24'te temsilci_kesinti=4,
musteri_kesinti=4 uretilmisti ve sekizinin de gercek karsiligi yoktu.
"""

from __future__ import annotations

from app.services.metrics import compute_metrics
from app.services.stt import MIN_WORDS_PER_SEC, _clip_to_speech


def seg(speaker: str, start: float, end: float, text: str = "bir iki uc dort bes") -> dict:
    return {"speaker": speaker, "start": start, "end": end, "text": text}


# --- Soz kesme sayaci ------------------------------------------------------

def test_ardisik_replikler_soz_kesme_uretmez():
    """Bindirmesiz, ardisik konusma: kesme sayisi SIFIR olmali."""
    segs = [
        seg("temsilci", 1.0, 5.0),
        seg("musteri", 5.4, 9.0),
        seg("temsilci", 9.3, 13.0),
        seg("musteri", 13.4, 17.0),
    ]
    m = compute_metrics(segs, 18.0)
    assert m["temsilci_kesinti"] == 0
    assert m["musteri_kesinti"] == 0


def test_musteri_keserse_yalniz_musteriye_yazilir():
    """B3'un kalbi: kesen musteriyse temsilci CEZALANDIRILAMAZ."""
    segs = [
        seg("temsilci", 1.0, 8.0),
        seg("musteri", 6.0, 10.0),    # 2 sn bindirme, temsilci 5 sn'dir konusuyor
        seg("temsilci", 10.4, 16.0),
        seg("musteri", 14.0, 18.0),   # yine musteri kesiyor
    ]
    m = compute_metrics(segs, 19.0)
    assert m["musteri_kesinti"] == 2
    assert m["temsilci_kesinti"] == 0


def test_temsilci_keserse_temsilciye_yazilir():
    segs = [
        seg("musteri", 1.0, 8.0),
        seg("temsilci", 6.0, 10.0),
        seg("musteri", 10.4, 17.0),
        seg("temsilci", 15.0, 19.0),
    ]
    m = compute_metrics(segs, 20.0)
    assert m["temsilci_kesinti"] == 2
    assert m["musteri_kesinti"] == 0


def test_sinir_artefakti_soz_kesme_sayilmaz():
    """Kesilen replik henuz 1 sn olmadiysa bu bir soz kesme degil, hizalama hatasi."""
    segs = [
        seg("temsilci", 1.0, 5.0),
        seg("musteri", 1.3, 6.0),  # temsilci daha 0.3 sn'dir konusuyor
    ]
    m = compute_metrics(segs, 7.0)
    assert m["musteri_kesinti"] == 0


def test_kucuk_bindirme_dogal_kabul_edilir():
    segs = [
        seg("temsilci", 1.0, 5.0),
        seg("musteri", 4.9, 9.0),  # 0.1 sn — tolerans icinde
    ]
    m = compute_metrics(segs, 10.0)
    assert m["musteri_kesinti"] == 0


# --- STT segment kirpma (sismenin kaynagi) --------------------------------

class _FakeWord:
    def __init__(self, start, end):
        self.start, self.end = start, end


class _FakeSeg:
    def __init__(self, start, end, words=None):
        self.start, self.end, self.words = start, end, words


def test_kelime_zamani_varsa_gercek_bitis_alinir():
    """Sisen segment, son kelimenin bitisine cekilmeli."""
    s = _FakeSeg(25.9, 42.9, [_FakeWord(25.9, 26.6), _FakeWord(26.6, 27.3), _FakeWord(27.3, 28.1)])
    start, end = _clip_to_speech(s, "Hasan Yıldız 447821")
    assert start == 25.9
    assert end == 28.1  # 42.9 DEGIL


def test_kelime_zamani_yoksa_kelime_hizina_gore_kirpilir():
    """Canli olculen vaka: 3 kelime / 20.6 sn = 0.15 kelime/sn — fizik disi."""
    s = _FakeSeg(67.4, 88.0, words=None)
    start, end = _clip_to_speech(s, "Tamam, not aldım.")
    assert start == 67.4
    assert end < 70.0, f"Sisen segment kirpilmadi: {end}"
    assert 3 / (end - start) >= MIN_WORDS_PER_SEC


def test_makul_segment_bozulmaz():
    """Normal hizdaki bir segment kirpilmamali."""
    s = _FakeSeg(10.0, 14.0, words=None)
    start, end = _clip_to_speech(s, "Size nasıl yardımcı olabilirim efendim")
    assert (start, end) == (10.0, 14.0)
