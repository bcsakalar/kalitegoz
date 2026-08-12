"""Canlı model kataloğu ve sağlayıcı hata mesajları.

## Neden bu dosya var

Panelde model alanı boştu ve sağlayıcı seçimi 4 elle yazılmış model
öneriyordu. Kullanıcı sordu: *"çoklu model desteği çalışıyor di mi ... bütün
modellerini çek."*

Liste artık sağlayıcının kendi API'sinden geliyor. Bu, ağ bağımlılığı
demektir — ve ağ bağımlılığı olan kod **sessizce boş liste döndürmemelidir**.

## Neyi garanti eder

1. Ağ çöktüğünde yedek liste + **sebebi** döner, boş sessizlik değil.
2. Sağlayıcının o yüzeyi hiç sunmadığı durum ayrı ve açık.
3. Hata metni kullanıcıya **ne yapacağını** söyler; ham istisna değil.
4. Gemini'nin 400/API_KEY_INVALID'i "geçersiz anahtar" diye tanınır —
   yalnızca 401'e bakan kontrol onu kaçırıyordu (ölçüldü).
5. Ollama model türü `capabilities`'ten okunur, ad kalıbından değil.
"""

from unittest.mock import patch

import httpx
import pytest

from app.services import model_catalog


def _hata(kod: int, govde: str = "") -> httpx.HTTPStatusError:
    istek = httpx.Request("GET", "https://ornek.test/v1/models")
    yanit = httpx.Response(kod, text=govde, request=istek)
    return httpx.HTTPStatusError(f"{kod}", request=istek, response=yanit)


# ------------------------------------------------------------------ hata metni

@pytest.mark.parametrize("kod, beklenen_parca", [
    (401, "geçersiz"),
    (403, "geçersiz"),
    (429, "hız sınırı"),
    (404, "Model adını"),
])
def test_HTTP_kodlari_ne_yapilacagini_soyler(kod, beklenen_parca):
    metin = model_catalog.hata_mesaji("openai", _hata(kod))
    assert beklenen_parca in metin, f"{kod} icin yararsiz mesaj: {metin}"
    assert "developer.mozilla.org" not in metin, "Ham istisna metni sizmis"


def test_GEMINI_400_gecersiz_anahtar_olarak_taninir():
    """Olculdu: Gemini gecersiz anahtara 401 degil 400 donuyor.

    Yalnizca 401/403'e bakan kontrol, kullanicinin en sik yapacagi hatayi
    (yanlis anahtar) "bilinmeyen 400" diye gosteriyordu.
    """
    govde = '{"error":{"code":400,"message":"API key not valid",' \
            '"status":"INVALID_ARGUMENT","details":[{"reason":"API_KEY_INVALID"}]}}'
    metin = model_catalog.hata_mesaji("gemini", _hata(400, govde))
    assert "geçersiz" in metin, f"Gemini 400 taninmadi: {metin}"


def test_400_ama_anahtar_hatasi_DEGILSE_uydurulmaz():
    """Her 400'u 'anahtarin yanlis' diye gostermek yanlis yonlendirir."""
    metin = model_catalog.hata_mesaji("gemini", _hata(400, '{"error":"model too long"}'))
    assert "geçersiz ya da yetkisiz" not in metin
    assert "400" in metin


def test_AG_hatasinda_yedek_listenin_ESKI_olabilecegi_soylenir():
    metin = model_catalog.hata_mesaji("openrouter", httpx.ConnectError("baglanti yok"))
    assert "yedek" in metin and "eski" in metin


# ------------------------------------------------------------------ liste davranışı

def test_ag_coktugunde_YEDEK_liste_ve_sebep_doner():
    """Bos liste + bos hata, kullaniciya 'anahtarim mi yanlis?' dedirtir."""
    with patch.object(model_catalog, "_openai", side_effect=httpx.ConnectError("yok")):
        sonuc = model_catalog.listele("openai", "llm", api_key="k", tazele=True)
    assert sonuc.kaynak == "yedek"
    assert sonuc.modeller, "Yedek liste bos — panel hicbir sey gosteremez"
    assert sonuc.hata, "Yedege dusuldu ama sebebi yazilmamis"


def test_DESTEKLENMEYEN_yuzey_sebebiyle_doner():
    """OpenRouter gomme sunmuyor; bos liste bunu soylemez."""
    sonuc = model_catalog.listele("openrouter", "embed", tazele=True)
    assert sonuc.modeller == []
    assert "gömme" in sonuc.hata.lower() or "embedding" in sonuc.hata.lower(), (
        f"Desteklenmeyen yuzey sessizce bos dondu: {sonuc.hata!r}")


def test_bilinmeyen_saglayici_REDDEDILIR():
    sonuc = model_catalog.listele("uydurma", "llm")
    assert sonuc.modeller == []
    assert "Bilinmeyen" in sonuc.hata


# ------------------------------------------------------------------ tür sınıflandırma

@pytest.mark.parametrize("yetenekler, beklenen", [
    (["embedding"], "embed"),
    (["vision", "completion"], "vision"),
    (["completion", "tools"], "llm"),
])
def test_ollama_turu_SAGLAYICININ_meta_verisinden_okunur(yetenekler, beklenen):
    """Ad kalibi yanlis siniflandiriyordu: `bge-m3` bir gomme modeli ama
    adinda 'embed' gecmedigi icin LLM sayilmisti."""
    assert model_catalog._ollama_turu({"name": "bge-m3", "capabilities": yetenekler}) == beklenen


def test_capabilities_YOKSA_ad_kalibina_dusulur():
    """Eski Ollama surumleri `capabilities` dondurmuyor; liste bos kalmamali."""
    assert model_catalog._ollama_turu({"name": "nomic-embed-text"}) == "embed"


# ------------------------------------------------------------------ önbellek

def test_onbellek_ikinci_cagrida_AGA_gitmez():
    """15 dk onbellek: panel her acilista saglayiciyi dovmemeli."""
    sahte = [{"id": "m1", "ad": "m1", "tur": "llm", "kurulu": False}]
    with patch.object(model_catalog, "_openrouter", return_value=sahte) as f:
        model_catalog.listele("openrouter", "llm", tazele=True)
        model_catalog.listele("openrouter", "llm")
    assert f.call_count == 1, "Onbellek calismiyor — her acilista aga gidiliyor"


def test_TAZELE_onbellegi_atlar():
    """Panelde 'yenile' baglantisi gercekten yenilemeli."""
    sahte = [{"id": "m1", "ad": "m1", "tur": "llm", "kurulu": False}]
    with patch.object(model_catalog, "_openrouter", return_value=sahte) as f:
        model_catalog.listele("openrouter", "llm", tazele=True)
        model_catalog.listele("openrouter", "llm", tazele=True)
    assert f.call_count == 2, "'yenile' onbellegi atlamiyor"


# ------------------------------------------------------------------ sözleşme

def test_modeller_ARAYUZUN_bekledigi_alanlari_tasir():
    """Bilgi alanlari SAYI olmali; sunucu Turkce metin uretirse EN arayuzde
    satirlar karma dilde gorunuyordu."""
    sahte = [{"id": "a", "ad": "a", "tur": "llm", "baglam": 32768,
              "fiyat_m": 0.15, "ucretsiz": False, "kurulu": False}]
    with patch.object(model_catalog, "_openrouter", return_value=sahte):
        sonuc = model_catalog.listele("openrouter", "llm", tazele=True)
    m = sonuc.modeller[0]
    for alan in ("id", "ad", "tur", "kurulu"):
        assert alan in m, f"Model kaydinda '{alan}' yok"
    assert "aciklama" not in m, "Sunucu hazir metin uretiyor — bicimleme arayuzun isi"
