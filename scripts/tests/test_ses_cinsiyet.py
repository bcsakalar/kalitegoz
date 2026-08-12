"""Demo çağrılarında ses cinsiyeti metinle tutarlı olmalı.

## Neden bu test var

Kullanıcı sordu: "kadın isimli olanlar kadın sesli, erkek isimli olanlar
erkek sesli değil mi?" Ölçünce **iki gerçek hata** çıktı:

1. **`13-dusuk-yanlis-bilgi`** — müşteri kendini "Gizem Çelik" diye
   tanıtıyor ama **erkek sesi** atanmıştı. Sebep: `customer_gender` yalnızca
   temsilcinin hitabına ("X Hanım/Bey") bakıyordu; temsilci hiç hitap
   etmediğinde cinsiyet **rastgele** seçiliyordu. Oysa müşteri kimlik
   doğrulamada adını söylüyor.

2. **`18-sifirlayici-hakaret`** — temsilci "Beyefendi saçmalamayın" diyor ama
   müşteriye **kadın sesi** atanmıştı. Sebep: hitap deseni "AD + Bey/Hanım"
   arıyordu; **yalın** hitap ("Beyefendi", "Hanımefendi") tanınmıyordu.

İkisi de sessiz hatalardı: ses üretilir, dosya yazılır, hiçbir uyarı çıkmaz.
Ancak kulakla ya da bu testle fark edilir.

## Kural

Cinsiyet sırası: **hitap → müşterinin kendi adı → rastgele**. Rastgeleye
düşmek yalnızca ikisi de yoksa kabul edilir.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parents[1]
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

from demo_dialogs import DEMO_CALLS  # noqa: E402
from generate_demo import (  # noqa: E402
    FEMALE_AGENTS,
    MALE_AGENTS,
    _musteri_adi,
    customer_gender,
)
from tr_gender import gender_from_honorific, gender_from_name  # noqa: E402

TOHUM = 20260810  # seed_demo_calls.py ile ayni


def _rng():
    return random.Random(TOHUM)


# ---------------------------------------------------------------- hitap

@pytest.mark.parametrize("metin, beklenen", [
    ("Teşekkürler Serkan Bey, faturanız hazır.", "erkek"),
    ("Fatma Hanım, kaydınızı açtım.", "kadin"),
    # Yalin hitap — ONCEDEN TANINMIYORDU
    ("Beyefendi saçmalamayın, sistemde ne varsa onu söylüyorum.", "erkek"),
    ("Hanımefendi bir dakika bekler misiniz?", "kadin"),
    ("Hanimefendi buyurun.", "kadin"),
    ("Merhaba, nasıl yardımcı olabilirim?", None),
])
def test_hitaptan_cinsiyet(metin, beklenen):
    assert gender_from_honorific(metin) == beklenen


# ---------------------------------------------------------------- temsilci

def test_her_temsilci_kadroda_TANIMLI():
    """Kadroda olmayan temsilciye sessizce 'erkek' atanır — bu gizli bir hatadır."""
    eksik = {
        d["agent"] for d in DEMO_CALLS
        if d["agent"] not in FEMALE_AGENTS and d["agent"] not in MALE_AGENTS
    }
    assert not eksik, f"Kadroda tanımsız temsilci: {sorted(eksik)}"


def test_temsilci_sesi_ADIYLA_tutarli():
    """ayse -> kadın, mehmet -> erkek. Kadro sözlükle çelişmemeli."""
    celiski = []
    for ad in sorted(FEMALE_AGENTS | MALE_AGENTS):
        ilk = ad.split(".")[0]
        sozluk = gender_from_name(ilk)
        kadro = "kadin" if ad in FEMALE_AGENTS else "erkek"
        if sozluk is not None and sozluk != kadro:
            celiski.append(f"{ad}: kadro={kadro} sozluk={sozluk}")
    assert not celiski, "Kadro ile ad sözlüğü çelişiyor:\n" + "\n".join(celiski)


# ---------------------------------------------------------------- müşteri

def test_musteri_sesi_KENDI_ADIYLA_tutarli():
    """Müşteri adını söylüyorsa ses o ada uymalı — rastgeleye düşmemeli.

    `13-dusuk-yanlis-bilgi` bu testte kırmızıydı: "Gizem Çelik" -> erkek sesi.
    """
    rng = _rng()
    uyusmaz = []
    for d in DEMO_CALLS:
        ses = customer_gender(d["turns"], rng)
        ad = _musteri_adi(d["turns"])
        beklenen = gender_from_name(ad) if ad else None
        if beklenen is not None and beklenen != ses:
            uyusmaz.append(f"{d['id']}: '{ad}' -> {beklenen} beklenirken {ses} atandı")
    assert not uyusmaz, "Müşteri sesi adıyla uyuşmuyor:\n" + "\n".join(uyusmaz)


def test_musteri_sesi_HITAPLA_tutarli():
    """Temsilci 'X Bey' / 'Beyefendi' diyorsa ses erkek olmalı.

    `18-sifirlayici-hakaret` bu testte kırmızıydı: "Beyefendi" -> kadın sesi.
    """
    rng = _rng()
    uyusmaz = []
    for d in DEMO_CALLS:
        ses = customer_gender(d["turns"], rng)
        t_metin = " ".join(x["m"] for x in d["turns"] if x["k"] == "t")
        hitap = gender_from_honorific(t_metin)
        if hitap is not None and hitap != ses:
            uyusmaz.append(f"{d['id']}: hitap={hitap} ama ses={ses}")
    assert not uyusmaz, "Müşteri sesi hitapla uyuşmuyor:\n" + "\n".join(uyusmaz)


def test_cinsiyet_atamasi_DETERMINISTIK():
    """Aynı tohumla iki koşum aynı sesi vermeli — kurulumlar arası tutarlılık."""
    a = [customer_gender(d["turns"], _rng()) for d in DEMO_CALLS]
    b = [customer_gender(d["turns"], _rng()) for d in DEMO_CALLS]
    assert a == b


def test_rastgeleye_dusen_cagri_SAYISI_sinirli():
    """Hitap da ad da yoksa rastgele atanır; bu bir kaçış yolu olmamalı.

    20 çağrının en fazla 2'sinde bilgi eksik olabilir. Daha fazlası,
    senaryoların kimlik doğrulama adımını atladığı anlamına gelir.
    """
    bilgisiz = []
    for d in DEMO_CALLS:
        t_metin = " ".join(x["m"] for x in d["turns"] if x["k"] == "t")
        if gender_from_honorific(t_metin) is None and not gender_from_name(_musteri_adi(d["turns"])):
            bilgisiz.append(d["id"])
    assert len(bilgisiz) <= 2, (
        f"Çok fazla çağrıda müşteri cinsiyeti bilinmiyor ({len(bilgisiz)}): {bilgisiz}"
    )


# ---------------------------------------------------------------- dağılım

def test_ses_karisimi_TEK_TARAFLI_degil():
    """Hem temsilci hem müşteri tarafında iki cinsiyet de bulunmalı.

    Hepsi aynı cinsiyet olursa demo, konuşmacı ayrımını göstermez.
    """
    rng = _rng()
    t = {("kadin" if d["agent"] in FEMALE_AGENTS else "erkek") for d in DEMO_CALLS}
    m = {customer_gender(d["turns"], rng) for d in DEMO_CALLS}
    assert t == {"kadin", "erkek"}, f"Temsilci sesleri tek taraflı: {t}"
    assert m == {"kadin", "erkek"}, f"Müşteri sesleri tek taraflı: {m}"


def test_musteri_TEMSILCIYE_hitap_ederse_kendi_adi_sayilmaz():
    """"Ayşe Hanım, faturamda sorun var." diyen müşteri KENDİNİ tanıtmıyor.

    İlk düzeltmemde bu ayrımı atlamıştım: "Ad Soyad," deseni "Ad Unvan,"
    biçimini de yakalıyordu ve temsilciye hitap eden müşteriye deterministik
    olarak o unvanın cinsiyeti atanıyordu.

    Mevcut bir test (`test_demo_voices.py`) bunu yakaladı — yeni bir kural
    eklerken eski testleri koşmanın karşılığı budur.
    """
    turns = [
        {"k": "t", "m": "Merhaba, ben Ayşe."},
        {"k": "m", "m": "Ayşe Hanım, faturamda sorun var."},
    ]
    assert _musteri_adi(turns) == "", "Hitap, müşterinin kendi adı sanıldı"


def test_musteri_gercekten_tanitirsa_ad_ALINIR():
    """Kontrol testi: filtre fazla geniş olmasın."""
    turns = [
        {"k": "t", "m": "Adınızı alabilir miyim?"},
        {"k": "m", "m": "Serkan Aydın, müşteri numaram dört beş altı."},
    ]
    assert _musteri_adi(turns) == "Serkan"
