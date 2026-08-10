"""Gerçek müşteri anketi (CSAT) ve korelasyon — piyasa analizi §5.1.

## Bu testlerin savunduğu üç kural

1. **Ölçek sessizce dönüştürülmez.** 1-7'lik bir anketten gelen 7'yi 5'e
   kırpmak, verinin yanlış ölçekte olduğunu gizler. Hata fırlatılır.
2. **Küçük örneklemde korelasyon YAYIMLANMAZ.** 5 çağrıyla hesaplanan r=0.9
   gürültüdür; satış sunumuna girerse yalan olur.
3. **Onaylanmamış puan korelasyona girmez.** Kaliteci onaylamamış bir puanı
   iş sonucuyla ilişkilendirmek, henüz geçerli olmayan bir sayıyı kanıt
   saymaktır (aynı gerekçe B33'te de geçerliydi).
"""

import pytest

from app.models import Call, CallStatus, Channel, QAState
from app.services import csat
from tests.conftest import TestingSession, token_for


# ---------------------------------------------------------------- doğrulama

@pytest.mark.parametrize("puan", [1, 3, 5, 4.5])
def test_gecerli_puan_kabul_edilir(puan):
    p, k = csat.dogrula(puan, "anket")
    assert p == float(puan)
    assert k == "anket"


@pytest.mark.parametrize("puan", [0, 6, 7, 10, -1])
def test_olcek_disi_puan_SESSIZCE_KIRPILMAZ(puan):
    """1-5 dışı değer hata fırlatmalı — kırpmak ölçek hatasını gizler."""
    with pytest.raises(csat.CSATHatasi) as exc:
        csat.dogrula(puan, "anket")
    assert "1-5" in str(exc.value)


def test_bos_puan_reddedilir():
    with pytest.raises(csat.CSATHatasi):
        csat.dogrula(None, "anket")


def test_gecersiz_kaynak_reddedilir():
    with pytest.raises(csat.CSATHatasi):
        csat.dogrula(4, "nereden_geldigi_belirsiz")


def test_bos_kaynak_manuele_duser():
    _, k = csat.dogrula(4, "")
    assert k == "manuel"


# ---------------------------------------------------------------- korelasyon

def _cagri_uret(tenant_id, agent_id, ciftler, durum=QAState.final):
    """(kalite_puani, gercek_csat) ciftlerinden cagri uret."""
    db = TestingSession()
    try:
        for i, (puan, c_sat) in enumerate(ciftler):
            c = Call(tenant_id=tenant_id, filename=f"csat{i}.wav", audio_path="",
                     channel=Channel.voice, agent_id=agent_id,
                     status=CallStatus.done, total_score=puan,
                     qa_state=durum, actual_csat=c_sat, csat_source="anket")
            db.add(c)
        db.commit()
    finally:
        db.close()


def test_az_ornekle_korelasyon_SAYISI_GOSTERILMEZ(seeded):
    """5 çağrıyla mükemmel korelasyon bile yayımlanmamalı."""
    # Kusursuz dogrusal iliski kur — yine de yayimlanmamali
    _cagri_uret(seeded["tenant_a"], seeded["agent_a"],
                [(50, 1), (60, 2), (70, 3), (80, 4), (90, 5)])
    db = TestingSession()
    try:
        r = csat.korelasyon(db, seeded["tenant_a"])
    finally:
        db.close()

    assert r["korelasyon"] is None, "Az örneklemde korelasyon sayısı gösterildi"
    assert r["yeterli_veri"] is False
    assert "yeterli veri yok" in r["mesaj"].lower()


def test_yeterli_orneklemde_korelasyon_HESAPLANIR(seeded):
    ciftler = [(40 + i * 2, 1 + (i % 5)) for i in range(25)]
    _cagri_uret(seeded["tenant_a"], seeded["agent_a"], ciftler)
    db = TestingSession()
    try:
        r = csat.korelasyon(db, seeded["tenant_a"])
    finally:
        db.close()

    assert r["yeterli_veri"] is True
    assert r["n"] >= csat.MIN_ORNEKLEM
    assert r["korelasyon"] is not None
    assert -1.0 <= r["korelasyon"] <= 1.0


def test_onaylanmamis_cagri_korelasyona_GIRMEZ(seeded):
    """Kaliteci onaylamamış puan iş sonucuyla ilişkilendirilmemeli."""
    _cagri_uret(seeded["tenant_a"], seeded["agent_a"],
                [(50 + i, 1 + (i % 5)) for i in range(30)],
                durum=QAState.human_queue)
    db = TestingSession()
    try:
        r = csat.korelasyon(db, seeded["tenant_a"])
    finally:
        db.close()

    assert r["n"] == 0, "İnceleme kuyruğundaki çağrı korelasyona girdi"
    assert r["korelasyon"] is None


def test_sabit_veride_korelasyon_SIFIR_DEGIL_TANIMSIZ(seeded):
    """Tüm CSAT'lar aynıysa 'ilişki yok' değil, 'ölçülemez' denmeli."""
    _cagri_uret(seeded["tenant_a"], seeded["agent_a"],
                [(50 + i, 4) for i in range(25)])
    db = TestingSession()
    try:
        r = csat.korelasyon(db, seeded["tenant_a"])
    finally:
        db.close()

    assert r["korelasyon"] is None
    assert "ölçülemez" in r["mesaj"].lower()


def test_zayif_korelasyon_RUBRIGI_isaret_eder(seeded):
    """r<0.2 çıkınca uyarı modeli değil rubriği sorgulamalı."""
    # Kalite puani artarken CSAT rastgele — iliski yok
    ciftler = [(40 + i * 2, [1, 5, 2, 4, 3][i % 5]) for i in range(25)]
    _cagri_uret(seeded["tenant_a"], seeded["agent_a"], ciftler)
    db = TestingSession()
    try:
        r = csat.korelasyon(db, seeded["tenant_a"])
    finally:
        db.close()

    if r["korelasyon"] is not None and abs(r["korelasyon"]) < 0.2:
        assert "rubriğin" in r.get("uyari", "").lower()


# ---------------------------------------------------------------- API

def test_api_gecersiz_puani_400_ile_REDDEDER(seeded, client):
    hdr = token_for(seeded["admin_a"], seeded["tenant_a"], "admin")
    r = client.post(f"/api/v1/csat/{seeded['call_a']}",
                    json={"puan": 7, "kaynak": "anket"}, headers=hdr)
    assert r.status_code == 400
    # Proje hatalari zarf icinde donduruyor: {"error": {"message_tr": ...}}
    assert "1-5" in r.json()["error"]["message_tr"]


def test_api_gecerli_puani_yazar(seeded, client):
    hdr = token_for(seeded["admin_a"], seeded["tenant_a"], "admin")
    r = client.post(f"/api/v1/csat/{seeded['call_a']}",
                    json={"puan": 4, "kaynak": "anket", "yorum": "hızlı çözüm"},
                    headers=hdr)
    assert r.status_code == 200
    assert r.json()["actual_csat"] == 4.0


def test_api_baska_kiracinin_cagrisina_yazamaz(seeded, client):
    """Tenant izolasyonu CSAT ucunda da geçerli olmalı."""
    hdr = token_for(seeded["admin_b"], seeded["tenant_b"], "admin")
    r = client.post(f"/api/v1/csat/{seeded['call_a']}",
                    json={"puan": 4}, headers=hdr)
    assert r.status_code == 404


def test_toplu_giriste_hatali_satir_digerlerini_DUSURMEZ(seeded, client):
    hdr = token_for(seeded["admin_a"], seeded["tenant_a"], "admin")
    r = client.post("/api/v1/csat/bulk", headers=hdr, json={"kayitlar": [
        {"call_id": seeded["call_a"], "puan": 5, "kaynak": "anket"},
        {"call_id": seeded["call_a"], "puan": 99},          # olcek disi
        {"call_id": 999999, "puan": 3},                      # yok
        {"call_id": seeded["call_other_team"], "puan": 3, "kaynak": "anket"},
    ]})
    assert r.status_code == 200
    veri = r.json()
    assert veri["yazilan"] == 2, "Geçerli satırlar yazılmadı"
    assert veri["hatali"] == 2
    assert len(veri["hatalar"]) == 2
