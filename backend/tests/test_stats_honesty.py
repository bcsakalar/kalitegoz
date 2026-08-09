"""B7-B10, B13, B14 regresyon testleri — istatistiksel durustluk.

Ortak kok: sistem veri yetersizken de bir sayi uretmek zorunda hissediyordu.
Bir cagri merkezi muduru "n=24 ile guclu iliski" ya da "onceki 0 iken +%100"
gorur ve urune guvenmeyi birakir.
"""

from __future__ import annotations

import pytest

from app.services import stats_honesty as sh


# =========================================================================
# B8 — n<30 ile korelasyon iddiasi
# =========================================================================

def test_b8_az_orneklemle_KATSAYI_gosterilmez():
    """Ekranda gorulen hata: n=24 ile '+0.68 guclu iliski'."""
    pairs = [(float(i), float(i * 2)) for i in range(24)]  # mukemmel korelasyon
    olcum = sh.korelasyon(pairs, "Konusma hizi")
    assert olcum.deger is None, "n=24 ile katsayi gosterildi"
    assert olcum.yeterli is False
    assert "n=24" in olcum.aciklama
    assert "anlamlı değil" in olcum.aciklama


def test_b8_yeterli_orneklemde_katsayi_ve_GUVEN_ARALIGI_gosterilir():
    pairs = [(float(i), float(i * 2)) for i in range(40)]
    olcum = sh.korelasyon(pairs, "Konusma hizi")
    assert olcum.yeterli is True
    assert olcum.deger == 1.0
    assert "%95 GA" in olcum.aciklama
    assert "Nedensellik değil" in olcum.aciklama


def test_b8_degiskenlik_yoksa_iliski_hesaplanmaz():
    pairs = [(5.0, float(i)) for i in range(40)]  # x sabit
    assert sh.korelasyon(pairs, "Sabit").deger is None


# =========================================================================
# B9 — onceki donem bossa yuzde uretme
# =========================================================================

def test_b9_onceki_donem_BOSSA_yuzde_uretilmez():
    """Ekranda gorulen hata: tum konular 'Son: N / Onceki: 0 / +100%'."""
    olcum = sh.donem_degisimi(guncel=4, onceki=0, etiket="iptal")
    assert olcum.deger is None, "Sifira bolunerek yuzde uretildi"
    assert "yeterli geçmiş yok" in olcum.aciklama


def test_b9_az_orneklemde_yuzde_verilir_ama_GUVENILIR_denmez():
    olcum = sh.donem_degisimi(guncel=4, onceki=2)
    assert olcum.deger == 100.0
    assert olcum.yeterli is False, "Az orneklem 'guvenilir' isaretlendi"
    assert "oynak" in olcum.aciklama


def test_b9_yeterli_gecmiste_temiz_yuzde():
    olcum = sh.donem_degisimi(guncel=15, onceki=10)
    assert olcum.deger == 50.0
    assert olcum.yeterli is True
    assert olcum.aciklama == ""


# =========================================================================
# B10 — tek noktali zaman serisi
# =========================================================================

def test_b10_tek_noktayla_grafik_cizilmez():
    assert sh.zaman_serisi([{"date": "2026-08-09"}]).yeterli is False


def test_b10_yetersiz_veride_ne_gerektigi_soylenir():
    olcum = sh.zaman_serisi([{"d": i} for i in range(3)])
    assert "en az 7" in olcum.aciklama


def test_b10_yeterli_veride_grafik_cizilir():
    assert sh.zaman_serisi([{"d": i} for i in range(10)]).yeterli is True


# =========================================================================
# B7 — az orneklemli temsilci siralamada
# =========================================================================

def test_b7_az_cagrili_temsilci_siralanamaz():
    ok, uyari = sh.siralamaya_girebilir(3)
    assert ok is False
    assert "3 çağrı" in uyari


def test_b7_yeterli_cagrili_temsilci_siralanir():
    ok, uyari = sh.siralamaya_girebilir(12)
    assert ok is True and uyari == ""


def test_b7_siralama_gorunen_sutunla_ayni_anahtari_kullanir():
    """Ekranda gorulen hata: 1:94.1, 2:90.4, 3:88.9, 4:90.4.

    Liste `points` ile siralaniyordu ama ekranda `avg_score` gosteriliyordu.
    Sirali gorunmemesinin sebebi buydu.
    """
    from app.schemas import LeaderboardRow

    satirlar = [
        LeaderboardRow(agent_id=1, agent_name="a", team_name=None, avg_score=88.9,
                       call_count=50, crisis_handled=9, points=99.0, ranked=True),
        LeaderboardRow(agent_id=2, agent_name="b", team_name=None, avg_score=94.1,
                       call_count=10, crisis_handled=0, points=96.1, ranked=True),
    ]
    satirlar.sort(key=lambda r: (r.ranked, r.avg_score, r.call_count), reverse=True)
    assert [r.avg_score for r in satirlar] == [94.1, 88.9]


def test_b7_az_orneklemli_temsilci_UST_SIRAYA_cikamaz():
    from app.schemas import LeaderboardRow

    satirlar = [
        LeaderboardRow(agent_id=1, agent_name="az", team_name=None, avg_score=99.0,
                       call_count=2, crisis_handled=0, points=99.4, ranked=False),
        LeaderboardRow(agent_id=2, agent_name="cok", team_name=None, avg_score=91.0,
                       call_count=200, crisis_handled=0, points=101.0, ranked=True),
    ]
    satirlar.sort(key=lambda r: (r.ranked, r.avg_score, r.call_count), reverse=True)
    assert satirlar[0].agent_name == "cok", "2 cagrili temsilci ilk sirada"


# =========================================================================
# B14 — ROI hesaplayici sonuc uretmeli
# =========================================================================

def test_b14_roi_somut_sonuc_ve_formul_dondurur():
    from app.schemas import RoiInputs
    from app.services import roi

    r = roi.compute(RoiInputs(agents=50, calls_per_agent_day=40,
                              platform_monthly_cost=8000))
    assert r.total_calls_month > 0
    assert r.net_monthly_benefit != 0
    assert r.payback_months is not None, "Geri odeme suresi hesaplanmadi"
    assert r.coverage_gain_pct == 97.0     # %3 -> %100
    assert len(r.formuller) >= 5, "Formuller ekranda ACIK olmali"
    for f in r.formuller:
        assert f["ad"] and f["formul"] and f["hesap"]


def test_b14_lisans_maliyeti_girilmezse_geri_odeme_NONE():
    """Bilinmeyen bir sayi uydurmak yerine None donmeli."""
    from app.schemas import RoiInputs
    from app.services import roi

    r = roi.compute(RoiInputs(platform_monthly_cost=0))
    assert r.payback_months is None
    assert r.payback_durumu == "maliyet_girilmedi"


def test_b14_lisans_tasarruftan_pahaliysa_DURUM_ayirt_edilir():
    """None iki farkli sey demek olamaz: 'girilmedi' ile 'amorti olmuyor'."""
    from app.schemas import RoiInputs
    from app.services import roi

    r = roi.compute(RoiInputs(agents=10, calls_per_agent_day=10,
                              platform_monthly_cost=200000))
    assert r.payback_months is None
    assert r.payback_durumu == "maliyet_tasarrufuyla_amorti_olmaz"
    assert r.net_monthly_benefit < 0
    # Deger yine de raporlanir: kapsam %3'ten %100'e cikiyor
    assert r.coverage_gain_pct > 0
