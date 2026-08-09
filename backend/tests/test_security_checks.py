"""B25 — guvenlik sayfasi GERCEK kontrollerden okumali, bayraktan degil."""

from __future__ import annotations

import pytest

from app.services import crypto, security_checks, sso

from .conftest import TestingSession


@pytest.fixture
def db(seeded):
    s = TestingSession()
    try:
        yield s
    finally:
        s.close()


# =========================================================================
# Diskte sifreleme — gercek sifrele/coz/butunluk testi
# =========================================================================

def test_anahtar_yoksa_sifreleme_KAPALI_der(monkeypatch):
    """Sessizce duz metin yazip 'sifreli' demek guvenlik sayfasini yalanci yapar."""
    monkeypatch.delenv(crypto.ENV_KEY, raising=False)
    assert crypto.is_enabled() is False
    ok, mesaj = crypto.self_test()
    assert ok is False
    assert crypto.ENV_KEY in mesaj


def test_kisa_anahtar_kabul_edilmez(monkeypatch):
    monkeypatch.setenv(crypto.ENV_KEY, "kisa")
    assert crypto.is_enabled() is False


def test_anahtar_varsa_sifreleme_gercekten_calisir(monkeypatch):
    monkeypatch.setenv(crypto.ENV_KEY, "x" * 40)
    ok, mesaj = crypto.self_test()
    assert ok is True, mesaj


def test_sifreli_metin_duz_metinden_farkli(monkeypatch):
    monkeypatch.setenv(crypto.ENV_KEY, "y" * 40)
    duz = "TCKN 12345678901"
    sifreli = crypto.encrypt_text(duz)
    assert sifreli != duz
    assert duz not in sifreli
    assert sifreli.startswith(crypto.PREFIX)
    assert crypto.decrypt_text(sifreli) == duz


def test_butunluk_bozulursa_okuma_REDDEDILIR(monkeypatch):
    monkeypatch.setenv(crypto.ENV_KEY, "z" * 40)
    sifreli = crypto.encrypt_text("hassas veri")
    with pytest.raises(crypto.CryptoError):
        crypto.decrypt_text(sifreli[:-4] + "AAAA")


def test_sifrelenmemis_eski_veri_okunabilir(monkeypatch):
    """Kademeli gecis: mevcut duz veriler bozulmadan okunmali."""
    monkeypatch.setenv(crypto.ENV_KEY, "q" * 40)
    assert crypto.decrypt_text("eski duz metin") == "eski duz metin"


def test_anahtar_yokken_sifreli_veri_okunamaz(monkeypatch):
    monkeypatch.setenv(crypto.ENV_KEY, "w" * 40)
    sifreli = crypto.encrypt_text("veri")
    monkeypatch.delenv(crypto.ENV_KEY)
    with pytest.raises(crypto.CryptoError):
        crypto.decrypt_text(sifreli)


# =========================================================================
# SSO — gercek discovery kontrolu
# =========================================================================

def test_sso_yapilandirilmamissa_kapali(monkeypatch):
    for k in ("OIDC_ISSUER", "OIDC_CLIENT_ID", "OIDC_CLIENT_SECRET"):
        monkeypatch.delenv(k, raising=False)
    durum, mesaj, _ = sso.check(force=True)
    assert durum == "kapali"
    assert "yapılandırılmamış" in mesaj


def test_sso_yapilandirilmis_ama_ULASILAMIYORSA_uyari(monkeypatch):
    """Ayar var ama saglayici erisilemiyorsa 'acik' demek YANILTICIDIR."""
    monkeypatch.setenv("OIDC_ISSUER", "http://127.0.0.1:9/realms/yok")
    monkeypatch.setenv("OIDC_CLIENT_ID", "kalitegoz")
    monkeypatch.setenv("OIDC_CLIENT_SECRET", "gizli")
    durum, mesaj, detay = sso.check(force=True)
    assert durum == "uyari"
    assert detay["reachable"] is False


# =========================================================================
# Toplu kontrol
# =========================================================================

def test_tum_kontroller_kanit_ve_yol_gosterir(db, seeded):
    rapor = security_checks.run_all(db, seeded["tenant_a"])
    assert rapor["toplam"] >= 8
    for k in rapor["kontroller"]:
        assert k["durum"] in ("ok", "uyari", "kapali")
        assert k["kanit"], f"{k['anahtar']} kanit uretmedi"
        if k["durum"] != "ok":
            assert k["nasil_acilir"], f"{k['anahtar']} kapali ama yol gostermiyor"


def test_pii_maskeleme_ORNEK_veriyle_dogrulanir(db, seeded):
    rapor = security_checks.run_all(db, seeded["tenant_a"])
    pii = next(k for k in rapor["kontroller"] if k["anahtar"] == "pii_masking")
    assert "12345678901" not in pii["kanit"], "Kontrol kaniti PII sizdiriyor"


def test_rbac_kontrolu_gercek_dagilimi_okur(db, seeded):
    rapor = security_checks.run_all(db, seeded["tenant_a"])
    rbac = next(k for k in rapor["kontroller"] if k["anahtar"] == "rbac")
    assert rbac["detay"]["dagilim"], "Rol dagilimi bos — kontrol gercek veri okumuyor"


def test_kiraci_izolasyonu_diger_kiracilari_saymaz(db, seeded):
    """seeded fixture'inda iki kiraci var; kontrol ayrimi gormeli."""
    rapor = security_checks.run_all(db, seeded["tenant_a"])
    izo = next(k for k in rapor["kontroller"] if k["anahtar"] == "tenant_isolation")
    assert izo["detay"]["diger_kiracilar"] >= 1


def test_kritik_acik_maddeler_raporlanir(db, seeded, monkeypatch):
    monkeypatch.delenv(crypto.ENV_KEY, raising=False)
    rapor = security_checks.run_all(db, seeded["tenant_a"])
    assert "encryption_at_rest" in rapor["kritik_acik"]


# =========================================================================
# S12 — anahtar kaynagi, rotasyon, SSO yonetim ekrani
# =========================================================================

def test_anahtar_DOSYADAN_okunabilir(monkeypatch, tmp_path):
    """.env bir anahtar kaynagi DEGILDIR; Docker secret dosyadan mount edilir."""
    f = tmp_path / "master.key"
    f.write_text("d" * 40, encoding="utf-8")
    monkeypatch.delenv(crypto.ENV_KEY, raising=False)
    monkeypatch.setenv(crypto.KEY_FILE_ENV, str(f))

    assert crypto.is_enabled() is True
    assert crypto.key_status()["kaynak"] == "dosya"
    assert crypto.self_test()[0] is True


def test_dosya_ortam_degiskenini_EZER(monkeypatch, tmp_path):
    f = tmp_path / "master.key"
    f.write_text("f" * 40, encoding="utf-8")
    monkeypatch.setenv(crypto.ENV_KEY, "e" * 40)
    monkeypatch.setenv(crypto.KEY_FILE_ENV, str(f))

    sifreli = crypto.encrypt_text("hassas")
    # Dosya anahtariyla sifrelendiyse, YALNIZ ortam degiskeniyle cozulemez
    monkeypatch.delenv(crypto.KEY_FILE_ENV)
    with pytest.raises(crypto.CryptoError):
        crypto.decrypt_text(sifreli)


def test_ROTASYON_eski_anahtarla_yazilani_okur(monkeypatch, tmp_path):
    """Rotasyon tek seferde bitmez; eski anahtarla yazilan veri okunabilmeli."""
    eski = tmp_path / "eski.key"
    yeni = tmp_path / "yeni.key"
    eski.write_text("1" * 40, encoding="utf-8")
    yeni.write_text("2" * 40, encoding="utf-8")

    monkeypatch.delenv(crypto.ENV_KEY, raising=False)
    monkeypatch.setenv(crypto.KEY_FILE_ENV, str(eski))
    sifreli = crypto.encrypt_text("rotasyon oncesi yazilmis veri")

    # Rotasyon: yeni anahtar aktif, eski hala tanimli
    monkeypatch.setenv(crypto.KEY_FILE_ENV, str(yeni))
    monkeypatch.setenv(crypto.OLD_KEYS_ENV, str(eski))
    assert crypto.decrypt_text(sifreli) == "rotasyon oncesi yazilmis veri"


def test_eski_anahtar_tanimli_degilse_okunamaz(monkeypatch, tmp_path):
    eski = tmp_path / "eski.key"
    yeni = tmp_path / "yeni.key"
    eski.write_text("3" * 40, encoding="utf-8")
    yeni.write_text("4" * 40, encoding="utf-8")

    monkeypatch.delenv(crypto.ENV_KEY, raising=False)
    monkeypatch.setenv(crypto.KEY_FILE_ENV, str(eski))
    sifreli = crypto.encrypt_text("veri")

    monkeypatch.setenv(crypto.KEY_FILE_ENV, str(yeni))
    monkeypatch.delenv(crypto.OLD_KEYS_ENV, raising=False)
    with pytest.raises(crypto.CryptoError) as exc:
        crypto.decrypt_text(sifreli)
    assert crypto.OLD_KEYS_ENV in str(exc.value)


def test_sso_veritabani_ayari_ortami_EZER(monkeypatch):
    monkeypatch.setenv("OIDC_ISSUER", "https://env.example/realms/a")
    monkeypatch.setenv("OIDC_CLIENT_ID", "env-client")
    monkeypatch.setenv("OIDC_CLIENT_SECRET", "env-secret")

    sso.set_db_config({
        "issuer": "https://panel.example/realms/b",
        "client_id": "panel-client",
        "client_secret": "panel-secret",
        "redirect_uri": "",
    })
    try:
        c = sso.config()
        assert c["issuer"] == "https://panel.example/realms/b"
        assert sso.kaynak() == "yonetim_ekrani"
    finally:
        sso.set_db_config({})


def test_sso_ayar_yoksa_ortama_duser(monkeypatch):
    sso.set_db_config({})
    monkeypatch.setenv("OIDC_ISSUER", "https://env.example/realms/a")
    assert sso.config()["issuer"] == "https://env.example/realms/a"
    assert sso.kaynak() == "ortam_degiskeni"
