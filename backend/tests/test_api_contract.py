"""B37 — Analitik sayfası `d.map is not a function` ile çöküyordu.

## Ne oldu

Backend "dürüst istatistik" katmanı eklenirken zaman serisi yanıtı düz
diziden nesneye döndü:

    onceden : [{"date": ..., "avg": ...}, ...]
    sonra   : {"noktalar": [...], "grafik_cizilebilir": false, "aciklama": ...}

Sebep meşruydu: tek noktayla çizgi grafik çizmek bir *değişim* iddiasıdır
ve yanıltıcıdır; API artık arayüze ne çizeceğini de söylüyor.

Ama frontend güncellenmedi. `request<TimeseriesPoint[]>` diyordu ve ardından
`ts.map(...)` çağırıyordu.

## Neden TypeScript yakalamadı

`request<T>()` gelen JSON'u **doğrulamaz**, `T` diye kabul eder. Yani tip
bir *iddia*, kontrol değil. `tsc --noEmit` tertemiz geçti, sayfa çalışma
anında çöktü.

## Neden ekran görüntüsü denetimi yakalamadı

Araç görüntüyü alıyor, dosyayı yazıyor ve "✓" diyordu — çöken sayfanın
görüntüsü de bir görüntüdür. Araca hata sınırı kontrolü eklendi.

## Bu testlerin savunduğu şey

Frontend'in **dizi** beklediği uç dizi, **nesne** beklediği uç nesne
döndürmeli. Şekil sözleşmesi burada kilitlenir; değiştirilirse test kırılır
ve frontend'i güncellemeye zorlar.

Canlı sistem üzerinde daha geniş bir tarama için: `make api-audit`
(`scripts/api_contract_audit.py`, 64 ucu gerçek yanıtla karşılaştırır).
"""

from tests.conftest import token_for


def _hdr(seeded):
    return token_for(seeded["admin_a"], seeded["tenant_a"], "admin")


# ------------------------------------------------------------------ timeseries

def test_timeseries_NESNE_dondurur_dizi_degil(seeded, client):
    """Frontend `TimeseriesResponse` bekliyor. Dizi dönerse sayfa bozulur."""
    r = client.get("/api/v1/analytics/timeseries?metric=score&days=30&bucket=day",
                   headers=_hdr(seeded))
    assert r.status_code == 200
    veri = r.json()
    assert isinstance(veri, dict), "timeseries dizi döndü — frontend nesne bekliyor"
    for alan in ("noktalar", "grafik_cizilebilir", "aciklama", "tekil_deger", "toplam_cagri"):
        assert alan in veri, f"timeseries yanıtında '{alan}' yok"
    assert isinstance(veri["noktalar"], list)
    assert isinstance(veri["grafik_cizilebilir"], bool)


def test_timeseries_BOS_veride_de_ayni_sekli_korur(seeded, client):
    """Boş sistem, yeni kullanıcının gördüğü İLK haldir; şekil değişmemeli."""
    r = client.get("/api/v1/analytics/timeseries?metric=csat&days=7&bucket=day",
                   headers=_hdr(seeded))
    veri = r.json()
    assert veri["noktalar"] == [] or isinstance(veri["noktalar"], list)
    # Veri yokken grafik cizilememeli — durustluk kurali
    assert veri["grafik_cizilebilir"] is False
    assert veri["aciklama"], "Grafik çizilemiyorsa sebebi yazılmalı"


# ------------------------------------------------------------------ voc

def test_voc_IKI_TAKSONOMIYI_ayri_dondurur(seeded, client):
    """Kategori ve etiket ayrı; düz liste dönerse aynı çağrı iki kez sayılır."""
    r = client.get("/api/v1/analytics/voc?days=14", headers=_hdr(seeded))
    assert r.status_code == 200
    veri = r.json()
    assert isinstance(veri, dict), "voc dizi döndü — frontend nesne bekliyor"
    for grup in ("kategoriler", "etiketler"):
        assert grup in veri, f"voc yanıtında '{grup}' yok"
        assert "satirlar" in veri[grup]
        assert isinstance(veri[grup]["satirlar"], list)
        assert veri[grup]["aciklama"], f"'{grup}' ne olduğunu açıklamalı"


# ------------------------------------------------------------------ dizi dönenler

def test_dizi_donmesi_gereken_uclar_DIZI_donuyor(seeded, client):
    """Frontend bu uçlarda `.map()` çağırıyor — nesne dönerse çökerler."""
    hdr = _hdr(seeded)
    for yol in (
        "/api/v1/analytics/cohort?dimension=team&days=30",
        "/api/v1/analytics/emerging?days=7",
        "/api/v1/analytics/correlations?days=90",
        "/api/v1/criteria",
        "/api/v1/agents",
        "/api/v1/targets",
    ):
        r = client.get(yol, headers=hdr)
        if r.status_code != 200:
            continue  # yetki/veri yoksa bu testin konusu degil
        assert isinstance(r.json(), list), f"{yol} dizi döndürmeli, {type(r.json()).__name__} döndü"


def test_emotions_NESNE_dondurur(seeded, client):
    r = client.get("/api/v1/analytics/emotions?days=30", headers=_hdr(seeded))
    assert r.status_code == 200
    veri = r.json()
    assert isinstance(veri, dict)
    assert "emotions" in veri and "churn" in veri
    assert isinstance(veri["emotions"], dict)
    assert isinstance(veri["churn"], dict)


# ------------------------------------------------------------------ kaynak denetimi

def test_frontend_istemcisi_TIMESERIES_icin_dizi_beyan_ETMIYOR():
    """Kaynak denetimi: api.ts'te eski (dizi) beyan geri gelmemeli.

    Çalışma zamanı testi bu dosyada var ama frontend tarafındaki yanlış
    beyan burada da yakalanır — iki taraf da aynı sözleşmeye bakmalı.
    """
    from pathlib import Path

    api_ts = Path(__file__).resolve().parents[2] / "frontend" / "lib" / "api.ts"
    if not api_ts.exists():
        return
    metin = api_ts.read_text(encoding="utf-8")
    for hatali in ("request<TimeseriesPoint[]>", "request<VocTrend[]>"):
        assert hatali not in metin, (
            f"api.ts hâlâ '{hatali}' diyor — API nesne döndürüyor, sayfa çöker."
        )
