"""normalize_tr / find_phrase testleri — B4'un kok nedenini kapatan katman."""

from __future__ import annotations

import pytest

from app.services.text_tr import (
    contains_verbatim,
    find_any,
    find_phrase,
    fold_tr,
    lower_tr,
    normalize_tr,
)


# --- Turkce kucuk harf tuzagi ---------------------------------------------

def test_lower_tr_buyuk_I_ve_noktali_I():
    assert lower_tr("IŞIK") == "ışık"
    assert lower_tr("İSTANBUL") == "istanbul"
    # Python'un lower()'i "İ" icin i + U+0307 uretir; bizimki uretmemeli
    assert "̇" not in lower_tr("İ")


def test_fold_tr_karsilastirma_icin_ascii():
    assert fold_tr("Görüşmemiz kayıt altına alınmaktadır") == "gorusmemiz kayit altina alinmaktadir"
    assert fold_tr("ÇÖĞÜŞI") == fold_tr("çöğüşı")


def test_normalize_tr_noktalama_ve_bosluk():
    assert normalize_tr("Merhaba,   dünya!!") == "merhaba dunya"


def test_normalize_tr_rakam_maskeleme():
    assert normalize_tr("musteri no 447821", mask_digits=True) == "musteri no #"
    assert normalize_tr("3 adet", mask_digits=True) == "3 adet"  # kisa sayi korunur


# --- B4: kelime siniri ve ek toleransi ------------------------------------

@pytest.mark.parametrize("cumle", [
    "Kesinlikle daha avantajlı bir paket sunabilirim.",
    "Kesinlikle haklısınız efendim.",
    "Kesin bir tarih veremiyorum.",
    "Kesintisiz hizmet veriyoruz.",
])
def test_b4_yasak_vaat_yanlis_pozitif_uretmez(cumle):
    """'kesin cozulur' yasak vaadi bu cumlelerin HICBIRIYLE eslesmemeli.

    Eski fuzzy eslesme 4'unun 4'unde de ESLESIYORDU ve bu, yuksek siddetli
    yasakli kelime oldugu icin CAGRIYI SIFIRLIYORDU.
    """
    assert find_phrase(cumle, "kesin çözülür") is None


@pytest.mark.parametrize("cumle", [
    "Bu sorun kesin çözülür, merak etmeyin.",
    "Sorununuz kesin çözülecek.",
])
def test_b4_gercek_yasak_vaat_yakalanir(cumle):
    hit = find_phrase(cumle, "kesin çözülür")
    assert hit is not None
    assert "kesin" in hit.quote.lower()


def test_ek_toleransi_kvkk_kaliplari():
    """Turkce cekim ekleri kaliplari kacirmamali."""
    metin = "Görüşmemiz kayıt altına alınmaktadır."
    assert find_phrase(metin, "kayıt alt") is not None
    assert find_phrase(metin, "kayıt altına") is not None


def test_ek_toleransi_kisa_kelimede_kapali():
    """Kisa kalip kelimeleri onek eslesmesi yapmamali (yanlis pozitif kaynagi)."""
    # "ve" kalibi "veremiyorum" ile ESLESMEMELI
    assert find_phrase("Kesin bir tarih veremiyorum.", "ve") is None


def test_araya_kelime_giremez():
    assert find_phrase("kayıt bugün altına alındı", "kayıt altına") is None


def test_alinti_ORIJINAL_metinden_kesilir():
    """Gosterilecek alinti ASCII'ye dusurulmus olamaz (prompt 'asla yapma' #7)."""
    metin = "Görüşmemiz kayıt altına alınmaktadır."
    hit = find_phrase(metin, "kayıt alt")
    assert hit is not None
    assert hit.quote == "kayıt altına"  # Turkce karakterler KORUNMUS
    assert metin[hit.start:hit.end] == hit.quote


def test_find_any_anlam_kumesi():
    metin = "Bu görüşme hizmet kalitesi için kaydedilmektedir."
    hit = find_any(metin, ("kayıt altına", "kayıt edil", "kaydedilmekte"))
    assert hit is not None
    assert hit.pattern == "kaydedilmekte"


# --- Katman C: kanit dogrulama --------------------------------------------

def test_contains_verbatim_gercek_alinti():
    t = "Netik İletişim'e hoş geldiniz, ben Mehmet. Size nasıl yardımcı olabilirim?"
    assert contains_verbatim(t, "ben Mehmet. Size nasıl yardımcı olabilirim?")


def test_contains_verbatim_uydurma_alinti_reddedilir():
    t = "Netik İletişim'e hoş geldiniz, ben Mehmet."
    assert not contains_verbatim(t, "Temsilci kurum adını hiç söylemedi efendim.")


def test_contains_verbatim_kirpilmis_alinti_kabul():
    t = "Görüşmemiz kayıt altına alınmaktadır ve verileriniz KVKK kapsamında işlenmektedir."
    assert contains_verbatim(t, "kayıt altına alınmaktadır ve verileriniz KVKK kapsamında")
