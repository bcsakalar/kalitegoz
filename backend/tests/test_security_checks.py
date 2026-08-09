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
