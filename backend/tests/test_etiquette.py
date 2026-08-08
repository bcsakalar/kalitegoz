"""Hitap & nezaket kural motoru (Turkce): sen/siz, argo, Bey/Hanim."""

from types import SimpleNamespace

from app.services import etiquette


def _seg(speaker, text, ts=1.0):
    return SimpleNamespace(speaker=speaker, text=text, start_sec=ts, end_sec=ts + 2)


def test_detects_informal_sen_pronoun():
    segs = [_seg("temsilci", "Sen bu formu doldurman lazım", 5)]
    r = etiquette.analyze(segs)
    assert r["sen_kullanimi"] == 1
    f = r["bulgular"][0]
    assert f["tur"] == "informal_sen"
    assert f["onem"] == "yuksek"
    assert f["zaman"] == 5


def test_detects_informal_verb_suffix():
    """'yapabilirsin' gibi 2. tekil sahis cekimi yakalanmali."""
    r = etiquette.analyze([_seg("temsilci", "İnternetten de yapabilirsin bunu")])
    assert r["sen_kullanimi"] == 1


def test_formal_siz_is_clean():
    segs = [_seg("temsilci", "Siz bu formu doldurabilirsiniz efendim")]
    r = etiquette.analyze(segs)
    assert r["sen_kullanimi"] == 0


def test_customer_informal_speech_not_charged_to_agent():
    """Musteri 'sen' derse temsilci SUCLANMAZ."""
    segs = [_seg("musteri", "Sen bana yardım edemiyorsun")]
    r = etiquette.analyze(segs)
    assert r["sen_kullanimi"] == 0
    assert r["bulgular"] == []


def test_detects_slang():
    r = etiquette.analyze([_seg("temsilci", "Tabii canım, hemen bakıyorum")])
    assert r["argo_kullanimi"] == 1
    assert r["bulgular"][0]["tur"] == "slang"


def test_counts_courtesy_phrases():
    segs = [
        _seg("temsilci", "Rica ederim efendim"),
        _seg("temsilci", "Teşekkür ederim, buyurun"),
    ]
    r = etiquette.analyze(segs)
    assert r["nezaket_sayisi"] >= 3


def test_counts_honorifics():
    r = etiquette.analyze([_seg("temsilci", "Tabii Mehmet Bey, hemen yapıyorum")])
    assert r["hitap_sayisi"] == 1


def test_name_with_honorific_is_not_flagged():
    """'Ahmet Bey' dogru kullanim -> bare_name bulgusu OLMAMALI."""
    r = etiquette.analyze([_seg("temsilci", "Anladım Ahmet Bey, hemen bakıyorum")])
    assert not any(f["tur"] == "bare_name" for f in r["bulgular"])


def test_empty_segments():
    r = etiquette.analyze([])
    assert r["bulgular"] == []
    assert r["sen_kullanimi"] == 0


def test_hint_mentions_sen_violation():
    r = etiquette.analyze([_seg("temsilci", "Sen bilmiyorsun galiba")])
    h = etiquette.hint(r)
    assert "SEN" in h
    assert "siz" in h.lower()


def test_hint_empty_when_nothing_found():
    r = etiquette.analyze([_seg("temsilci", "merhaba")])
    assert etiquette.hint(r) == ""


def test_works_with_dict_segments():
    """Dict formatinda segment de kabul edilmeli (chat ingest yolu)."""
    r = etiquette.analyze([{"speaker": "temsilci", "text": "Sen yapabilirsin", "start_sec": 3}])
    assert r["sen_kullanimi"] == 1
    assert r["bulgular"][0]["zaman"] == 3
