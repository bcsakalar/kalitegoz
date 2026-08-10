"""B35 — Ölçüm araçlarının iç kiracıları giriş ekranına sızmamalı.

## Ne oldu

`make eval` izole bir `__golden__` kiracısı kurar; performans ölçümü de
`__perf__`. Bunlar ölçüm araçlarının çalışma alanıdır, birer müşteri değil.

`onboarding.primary_tenant` "demo olmayan ilk aktif kiracı" diye baktığı için
`__golden__`'ı **gerçek kurum** sandı. Sonuç zinciri:

    /auth/config  ->  org_slug: "golden"
    tarayici      ->  POST /auth/login {tenant_slug: "golden"}
    kullanicilar  ->  "demo" kiracisinda
    sonuc         ->  HER GIRIS 401

Yani `make eval` koşulan bir makinede **arayüze hiç girilemiyordu**. Hata
arayüz ekran görüntüsü alınırken ortaya çıktı: 15 sayfanın 15'i de giriş
ekranı olarak kaydedilmişti.

## Neden bu test var

Bu hatanın iki özelliği onu tehlikeli yapıyor:

1. **Sessiz.** Hiçbir yerde hata logu yok; sadece giriş çalışmıyor.
2. **Ortama bağlı.** Geliştirici makinesinde `make eval` koşulmuşsa çıkıyor,
   koşulmamışsa çıkmıyor. Yani "bende çalışıyor" denen türden.

Kural: **çift alt çizgiyle başlayan kiracı adı = iç kiracı**, kullanıcıya
asla kurum olarak sunulmaz.
"""

from app.models import Tenant
from app.services import onboarding
from tests.conftest import TestingSession


def _kiraci_ekle(ad: str, slug: str) -> int:
    db = TestingSession()
    try:
        t = Tenant(name=ad, slug=slug)
        db.add(t)
        db.commit()
        return t.id
    finally:
        db.close()


def test_golden_kiracisi_KURUM_sayilmaz(seeded):
    """make eval kosulduktan sonra giris ekrani hala dogru kurumu gostermeli."""
    _kiraci_ekle("__golden__", "golden")
    db = TestingSession()
    try:
        pt = onboarding.primary_tenant(db)
    finally:
        db.close()

    assert pt is not None
    assert pt.slug != "golden", "Altin set kiracisi giris hedefi oldu — her giris 401 alir"
    assert not pt.name.startswith("__")


def test_perf_kiracisi_KURUM_sayilmaz(seeded):
    _kiraci_ekle("__perf__", "perf")
    db = TestingSession()
    try:
        pt = onboarding.primary_tenant(db)
    finally:
        db.close()

    assert pt.slug != "perf"


def test_cift_alt_cizgili_her_kiraci_ic_sayilir(seeded):
    """Kural ada bagli: ileride eklenecek __baska__ kiraci da otomatik haric."""
    _kiraci_ekle("__yeni_olcum_araci__", "yeni-olcum")
    db = TestingSession()
    try:
        pt = onboarding.primary_tenant(db)
    finally:
        db.close()

    assert not pt.name.startswith("__")


def test_gercek_kurum_HALA_secilir(seeded):
    """Filtre fazla genis olmasin: gercek kurumlar secilebilir kalmali.

    `seeded` zaten "a" ve "b" kiracilarini kuruyor ve `primary_tenant` id
    sirasina gore ilkini secer. Testin korudugu sey hangi kurumun secildigi
    degil, SECILEN SEYIN GERCEK BIR KURUM OLMASI.
    """
    _kiraci_ekle("__golden__", "golden")
    _kiraci_ekle("Netix İletişim A.Ş.", "netix")
    db = TestingSession()
    try:
        pt = onboarding.primary_tenant(db)
        gercek_var = onboarding.has_real_org(db)
        # Netix, gercek kurum listesinde YER ALMALI (filtre onu de elememeli)
        adaylar = {t.slug for t in onboarding._gercek_kurum_sorgusu(db).all()}
    finally:
        db.close()

    assert gercek_var is True
    assert pt.slug != "golden"
    assert not pt.name.startswith("__")
    assert "netix" in adaylar, "Gercek kurum filtreden dustu"
    assert "golden" not in adaylar


def test_yalniz_ic_kiraci_varsa_KURULUM_ekrani_gosterilir(seeded):
    """__golden__ tek basina 'kurum kuruldu' anlamina gelmemeli."""
    _kiraci_ekle("__golden__", "golden")
    db = TestingSession()
    try:
        # seeded fixture "a" ve "b" kiracilarini kuruyor; onlari devre disi birak
        for t in db.query(Tenant).filter(Tenant.slug.in_(["a", "b"])).all():
            t.is_active = False
        db.commit()
        assert onboarding.has_real_org(db) is False, (
            "Yalnizca ic kiracilar varken sistem 'gercek kurum var' dedi")
    finally:
        db.close()


def test_auth_config_ic_kiraci_dondurmez(seeded, client):
    """Uctan uca: giris ekraninin cektigi yapilandirma ic kiraci gostermemeli."""
    _kiraci_ekle("__golden__", "golden")
    r = client.get("/api/v1/auth/config")
    assert r.status_code == 200
    slug = r.json().get("org_slug")
    assert slug != "golden", "Giris ekrani altin set kiracisini hedef gosterdi"
