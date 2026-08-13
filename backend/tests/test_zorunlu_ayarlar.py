"""B42/B43 — "zorunlu env eksikse aç ık Türkçe hatayla dur" kuralı yarım uygulanmıştı.

## Ne bulundu

`zorunlu_ayarlari_dogrula` beş alanı zorunlu ilan ediyordu:

    jwt_secret · session_secret · admin_password · database_url · redis_url

Kontrol `if not str(getattr(s, alan, "") or "").strip()` diyor — yani alanın
**boş** olmasını arıyor. Ama üçünün `Settings` içinde **dolu varsayılanı**
vardı:

| alan | eski varsayılan |
|---|---|
| `jwt_secret` | `kalitegoz-dev-secret-CHANGE-IN-PROD` |
| `database_url` | `postgresql+psycopg://kalitegoz:kalitegoz@postgres:5432/...` |
| `redis_url` | `redis://redis:6379/0` |

Dolu varsayılan, "boş mu?" kontrolünü **erişilemez** kılar. Yani kural
yazılıydı, listede duruyordu, ama üç alan için hiçbir zaman çalışamazdı.

Somut sonucu: `JWT_SECRET` tanımsızsa uygulama **bilinen bir imza
anahtarıyla** ayağa kalkıyordu. Üretim koruması yalnızca
`ENVIRONMENT=production` iken devreye giriyor ve varsayılan `development`.

## Neden testi yoktu

Fonksiyonun hiç regresyon vakası yoktu (B43). Kendi doğruluğunu iddia eden
ama sınanmayan bir koruma, korumadığını fark ettirmez.

## Bu testlerin savunduğu şey

1. Beş zorunlu alanın **hiçbirinin** dolu varsayılanı yok — yani kontrol
   her biri için gerçekten ateşlenebilir.
2. Eksik alan açık **Türkçe** mesajla ve çözüm adımıyla durduruyor.
3. Üretim ek kontrolleri (kısa JWT, demo modu, joker CORS) hata veriyor.
4. Geliştirmede bu ek kontroller çalışmıyor — yerel kurulum zorlaşmasın.
"""

from __future__ import annotations

import pytest

from app.config import _ZORUNLU, Settings, YapilandirmaHatasi, zorunlu_ayarlari_dogrula


def _tam(**kw) -> Settings:
    """Tum zorunlu alanlari dolu, gecerli bir ayar nesnesi."""
    temel = dict(
        jwt_secret="x" * 48,
        session_secret="y" * 48,
        admin_password="Parola1234",
        database_url="postgresql+psycopg://u:p@db:5432/k",
        redis_url="redis://redis:6379/0",
        environment="development",
    )
    temel.update(kw)
    return Settings(**temel)


# ------------------------------------------------------------------ B42

@pytest.mark.parametrize("alan, env, _", _ZORUNLU)
def test_zorunlu_alanin_DOLU_VARSAYILANI_olamaz(alan, env, _):
    """Dolu varsayilan, "bos mu?" kontrolunu ERISILEMEZ kilar.

    Bu testin yakaladigi hata sinifinin adi: kural yazili, kod uygulanmiyor.
    Biri ileride "yerelde kolay olsun" diye varsayilan koyarsa burada kirilir.
    """
    varsayilan = Settings.model_fields[alan].default
    assert not (varsayilan or "").strip(), (
        f"{env} icin dolu varsayilan var ({varsayilan!r}) — zorunluluk "
        "kontrolu bu alan icin hicbir zaman atesleyemez."
    )


@pytest.mark.parametrize("alan, env, _", _ZORUNLU)
def test_eksik_zorunlu_alan_UYGULAMAYI_durdurur(alan, env, _):
    with pytest.raises(YapilandirmaHatasi) as hata:
        zorunlu_ayarlari_dogrula(_tam(**{alan: ""}))
    metin = str(hata.value)
    assert env in metin, f"Hata mesaji hangi degiskenin eksik oldugunu soylemiyor: {metin}"


def test_hata_mesaji_TURKCE_ve_COZUM_soyluyor():
    """Kullanici hangi komutu calistiracagini bilmeli; "config error" yetmez."""
    with pytest.raises(YapilandirmaHatasi) as hata:
        zorunlu_ayarlari_dogrula(_tam(jwt_secret="", session_secret=""))
    metin = str(hata.value)
    assert "zorunlu yapilandirma eksik" in metin.lower()
    assert "generate-secrets.sh" in metin, "Cozum adimi yazilmamis"
    # Iki eksik alan da tek seferde listelenmeli — tek tek kesfettirmemeli
    assert "JWT_SECRET" in metin and "SESSION_SECRET" in metin


def test_tam_yapilandirma_GECER():
    zorunlu_ayarlari_dogrula(_tam())  # istisna atmamali


def test_bosluk_dolu_deger_DOLU_sayilmaz():
    """"   " bir deger degildir; strip() kontrolu bunu yakalamali."""
    with pytest.raises(YapilandirmaHatasi):
        zorunlu_ayarlari_dogrula(_tam(admin_password="   "))


# ------------------------------------------------------------------ üretim kapısı

def test_URETIMDE_kisa_jwt_reddedilir():
    with pytest.raises(YapilandirmaHatasi) as hata:
        zorunlu_ayarlari_dogrula(_tam(environment="production", jwt_secret="kisa"))
    assert "JWT_SECRET" in str(hata.value)


def test_URETIMDE_demo_modu_reddedilir():
    with pytest.raises(YapilandirmaHatasi) as hata:
        zorunlu_ayarlari_dogrula(_tam(environment="production", demo_mode=True))
    assert "DEMO_MODE" in str(hata.value)


def test_URETIMDE_joker_CORS_reddedilir():
    with pytest.raises(YapilandirmaHatasi) as hata:
        zorunlu_ayarlari_dogrula(_tam(environment="production", cors_origins="*"))
    assert "CORS_ORIGINS" in str(hata.value)


def test_GELISTIRMEDE_uretim_kurallari_uygulanmaz():
    """Yerel kurulum zorlasmamali: kisa sir + demo modu gelistirmede sorun degil."""
    zorunlu_ayarlari_dogrula(
        _tam(environment="development", jwt_secret="kisa-ama-yerel", demo_mode=True))


# ------------------------------------------------------------------ çağrılıyor mu

def test_dogrulama_UYGULAMA_ACILISINDA_cagriliyor():
    """Fonksiyon dogru olabilir ama cagrilmiyorsa hicbir sey korumaz.

    Bu depoda ayni kalip iki kez yasandi (B33, `hedefler()`), o yuzden
    cagrildigi kaynak duzeyinde kilitleniyor.
    """
    from pathlib import Path

    main = (Path(__file__).resolve().parents[1] / "app" / "main.py").read_text(encoding="utf-8")
    assert "zorunlu_ayarlari_dogrula(settings)" in main, (
        "Dogrulama main.py'de cagrilmiyor — koruma etkisiz.")
