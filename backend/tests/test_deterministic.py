"""KATMAN A testleri — B1, B2, B4, B29, B32 regresyonlari.

Her test, altin setteki bir senaryonun deterministik karsiligidir.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.services import deterministic as det

BRANDS = ("Netik İletişim", "Netik")


@dataclass
class Seg:
    speaker: str
    text: str
    start_sec: float
    end_sec: float


@dataclass
class BW:
    term: str
    category: str = "hakaret"
    severity: str = "yuksek"
    match_type: str = "fuzzy"
    is_active: bool = True


def segs(*rows) -> list[Seg]:
    """rows: (speaker, text) — zamanlar otomatik ardisik."""
    out, t = [], 1.0
    for speaker, text in rows:
        dur = max(1.2, len(text.split()) / 2.5)
        out.append(Seg(speaker, text, round(t, 2), round(t + dur, 2)))
        t += dur + 0.35
    return out


# =========================================================================
# B1 — Acilis
# =========================================================================

def test_b1_kurum_ve_isim_varsa_tam_puan():
    s = segs(
        ("temsilci", "Netik İletişim'e hoş geldiniz, ben Mehmet."),
        ("musteri", "İyi günler."),
    )
    f = det.check_acilis(s, brand_names=BRANDS)
    assert f.decision == "met"
    assert f.score == 10
    assert "Mehmet" in f.evidence_quote or "Netik" in f.evidence_quote


def test_b1_kurum_adi_cumle_ORTASINDA_da_sayilir():
    """tuzak-01: konum degil VARLIK aranir."""
    s = segs(("temsilci", "İyi günler, ben Mert; Netik İletişim müşteri hizmetlerinden."))
    f = det.check_acilis(s, brand_names=BRANDS)
    assert f.decision == "met"
    assert f.score == 10


def test_b1_isim_yoksa_kismen():
    s = segs(("temsilci", "Netik İletişim'e hoş geldiniz, buyurun."))
    f = det.check_acilis(s, brand_names=BRANDS)
    assert f.decision == "partially_met"
    assert 5 <= f.score <= 7


def test_b1_hicbiri_yoksa_karsilanmadi():
    s = segs(("temsilci", "Alo, buyurun."))
    f = det.check_acilis(s, brand_names=BRANDS)
    assert f.decision == "not_met"
    assert f.score <= 2


# =========================================================================
# B2 — KVKK anlam kumesi
# =========================================================================

def test_b2_standart_kalip_disinda_anons_kabul_edilir():
    """reg-b2: 'kayit altina' kalibinin hicbiri gecmiyor ama anons TAM."""
    s = segs(
        ("temsilci", "Netik İletişim, ben Selin. Bilginiz olsun, bu konuşma hizmet kalitesi için kaydediliyor."),
        ("temsilci", "Paylaşacağınız bilgiler kişisel verilerin korunması mevzuatı çerçevesinde saklanır."),
    )
    f = det.check_kvkk(s)
    assert f.decision == "met", f.rationale_tr
    assert f.score == 10


def test_b2_anons_iki_replige_bolunmus_olabilir():
    """tuzak-04: kayit bildirimi ve aydinlatma AYRI repliklerde."""
    s = segs(
        ("temsilci", "Netik İletişim, ben Yiğit."),
        ("musteri", "İyi günler."),
        ("temsilci", "Bu görüşme hizmet kalitesi amacıyla kaydedilmektedir."),
        ("temsilci", "Ayrıca paylaşacağınız kişisel veriler mevzuata uygun şekilde işlenecektir."),
    )
    f = det.check_kvkk(s)
    assert f.decision == "met"


def test_b32_anons_hic_yoksa_karsilanmadi():
    """reg-b32: anons yok -> puan 0, sifirlamayi TETIKLEMELI."""
    s = segs(
        ("temsilci", "Netik İletişim, ben Ceyda, buyurun."),
        ("temsilci", "Adınızı ve müşteri numaranızı alabilir miyim?"),
        ("musteri", "Okan Yılmaz, 771450."),
    )
    f = det.check_kvkk(s)
    assert f.decision == "not_met"
    assert f.score == 0


def test_kvkk_sadece_kayit_bildirimi_kismen():
    s = segs(("temsilci", "Görüşmemiz kayıt altına alınmaktadır."))
    f = det.check_kvkk(s)
    assert f.decision == "partially_met"


# =========================================================================
# B29 — Konusmaci bilinmiyorsa CEZA YOK
# =========================================================================

@pytest.mark.parametrize("fn", [det.check_kvkk, det.check_kimlik, det.check_kapanis])
def test_b29_konusmaci_bilinmiyorsa_yetersiz_kanit(fn):
    """Mono kayit + diarizasyon yok -> 'ihlal' DENEMEZ, 'yetersiz kanit' der."""
    s = segs(
        ("bilinmeyen", "Netik İletişim, ben Tolga. Görüşmemiz kayıt altına alınmaktadır."),
        ("bilinmeyen", "İnternetim iki gündür yavaş."),
    )
    f = fn(s)
    assert f.decision == "insufficient_evidence"
    assert f.score is None
    assert not f.is_conclusive


def test_b29_acilis_da_yetersiz_kanit_der():
    s = segs(("bilinmeyen", "Netik İletişim, ben Tolga."))
    f = det.check_acilis(s, brand_names=BRANDS)
    assert f.decision == "insufficient_evidence"


# =========================================================================
# B4 — Yasakli kelime yanlis pozitifi
# =========================================================================

def test_b4_kibar_ifade_yasakli_sayilmaz():
    """'Kesinlikle haklisiniz efendim' cagriyi SIFIRLAYAMAZ."""
    s = segs(
        ("temsilci", "Kesinlikle haklısınız, bu süre kabul edilebilir değil."),
        ("temsilci", "Kesin bir tarih veremiyorum ama bugün dönüş yapılacak."),
    )
    f = det.check_uslup(s, [BW("kesin çözülür", category="yasak_vaat")])
    assert f.decision == "met"
    assert f.score == 10


def test_b4_gercek_yasak_vaat_yakalanir():
    s = segs(("temsilci", "Merak etmeyin, bu sorun kesin çözülür, garanti veriyorum."))
    f = det.check_uslup(s, [BW("kesin çözülür", category="yasak_vaat")])
    assert f.decision == "not_met"
    assert f.score == 0
    assert "kesin çözülür" in f.evidence_quote


def test_musterinin_kufru_temsilciyi_cezalandirmaz():
    """tuzak-03: 'sacmalamayin', 'aptal' MUSTERI replikinde."""
    s = segs(
        ("musteri", "Ne adı be, saçmalamayın, aptal sistem!"),
        ("temsilci", "Sizi anlıyorum, sinirlenmenizde haklısınız."),
    )
    f = det.check_uslup(s, [BW("saçmalama"), BW("aptal")])
    assert f.decision == "met"
    assert f.score == 10
    assert f.details["musteri_ihlali"] == 2


def test_temsilcinin_hakareti_sifirlar():
    s = segs(
        ("musteri", "Bu ne biçim hizmet!"),
        ("temsilci", "Aptalca konuşmayı bırakın da derdinizi anlatın."),
    )
    f = det.check_uslup(s, [BW("aptalca")])
    assert f.decision == "not_met"
    assert f.score == 0
    assert f.details["agir"] is True


# =========================================================================
# Kimlik ve kapanis
# =========================================================================

def test_kimlik_dogrulama_basta_tam_puan():
    s = segs(
        ("temsilci", "Adınızı ve müşteri numaranızı alabilir miyim?"),
        ("musteri", "Ayşe Kaya, 448120."),
        ("temsilci", "Teşekkürler Ayşe Hanım."),
        ("musteri", "Faturamla ilgili arıyorum."),
        ("temsilci", "Hemen bakıyorum efendim."),
    )
    f = det.check_kimlik(s)
    assert f.decision == "met"
    assert f.score == 10


def test_kimlik_dogrulama_hic_yoksa():
    s = segs(
        ("temsilci", "Netik İletişim, ben Nazlı."),
        ("musteri", "Tüm ek paketleri iptal edin."),
        ("temsilci", "Hemen iptal ediyorum."),
    )
    f = det.check_kimlik(s)
    assert f.decision == "not_met"
    assert f.score == 0


def test_kapanis_tam():
    s = segs(
        ("temsilci", "İşleminiz tamamlandı."),
        ("temsilci", "Başka yardımcı olabileceğim bir konu var mı?"),
        ("musteri", "Yok, teşekkürler."),
        ("temsilci", "Aradığınız için teşekkür ederim, iyi günler dilerim."),
    )
    f = det.check_kapanis(s)
    assert f.decision == "met"
    assert f.score == 10


def test_kapanis_eksik():
    """orta-01: veda var ama 'baska yardim' sorulmadi."""
    s = segs(
        ("temsilci", "Kredi kartı bilgilerinizi internet şubesinden tanımlayabilirsiniz."),
        ("musteri", "Tamam anladım."),
        ("temsilci", "İyi günler."),
    )
    f = det.check_kapanis(s)
    assert f.decision == "partially_met"
    assert f.score <= 6


def test_run_all_tum_kontrolleri_dondurur():
    s = segs(("temsilci", "Netik İletişim, ben Ali."))
    out = det.run_all(s, brand_names=BRANDS, banned=[])
    assert set(out) == set(det.CHECK_KEYS)


def test_check_key_for_ad_bazli_eslesme():
    class C:
        name = "KVKK / Aydinlatma"
        check_key = None
    assert det.check_key_for(C()) == "kvkk_anons"

    class D:
        name = "Cozum / Yonlendirme"
        check_key = None
    assert det.check_key_for(D()) is None


# =========================================================================
# Aktif Dinleme deterministik tavani
# =========================================================================

def test_kesme_yoksa_tavan_uygulanmaz():
    tavan, _ = det.listening_ceiling({"temsilci_kesinti": 0})
    assert tavan is None


def test_iki_kesme_tavani_7():
    tavan, gerekce = det.listening_ceiling({"temsilci_kesinti": 2})
    assert tavan == 7
    assert "2 kez" in gerekce


def test_dort_kesme_tavani_4():
    tavan, _ = det.listening_ceiling({"temsilci_kesinti": 4})
    assert tavan == 4


def test_cok_kesme_tavani_2():
    tavan, _ = det.listening_ceiling({"temsilci_kesinti": 9})
    assert tavan == 2


def test_metrik_yoksa_tavan_yok():
    assert det.listening_ceiling(None)[0] is None
    assert det.listening_ceiling({})[0] is None


def test_musteri_kesmesi_tavani_ETKILEMEZ():
    """B3'un kalici korumasi: musterinin kesmesi temsilciyi sinirlayamaz."""
    tavan, _ = det.listening_ceiling({"temsilci_kesinti": 0, "musteri_kesinti": 9})
    assert tavan is None
