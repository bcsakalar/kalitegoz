"""B44 — sesli işçi çalışmıyorken "İşlemeyi başlat" sessizce hiçbir şey yapmıyordu.

## Ne bulundu

Sesli çağrılar `voice` kuyruğuna gider (`celery_app.task_routes`) ve o
kuyruğu **yalnızca host'ta çalışan native worker** tüketir
(`scripts/run-host-worker.ps1`) — Whisper konteynerin bellek tavanına
sığmadığı için (exit 137).

Host worker çalışmıyorken "İşlemeyi başlat"a basmak:

1. 20 çağrıyı `voice` kuyruğuna atar,
2. Celery **başarıyla** döner (kuyruğa yazmak başarılıdır),
3. panel "20 kuyruğa alındı" der,
4. ve çağrılar **sonsuza kadar** `pending` kalır.

Hiçbir yerde hata görünmez. Kullanıcı sistemin bozuk olduğunu ancak
saatler sonra fark eder — ya da hiç etmez.

Bu, projedeki "sessiz başarısızlık" listesinin en pahalı örneği: ürünün
ANA AKIŞI, hata vermeden çalışmıyor.

## Bu testlerin savunduğu şey

1. `/admin/processing` hangi kuyrukların dinlendiğini **bildiriyor**.
2. Sesli işçi yoksa `voice_worker_active=False` ve **ne yapılacağını**
   söyleyen bir ipucu dönüyor.
3. Broker yanıt vermezse panel çökmüyor, "bilinmiyor" diyor.
4. Arayüz uyarıyı gerçekten basıyor (kaynak düzeyinde kilit).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.api import admin as admin_api

from .conftest import token_for


def _hdr(seeded):
    return token_for(seeded["admin_a"], seeded["tenant_a"], "admin")


def _inspect_dondur(kuyruklar):
    """`celery_app.control.inspect(...).active_queues()` sonucunu taklit et."""
    sahte = MagicMock()
    sahte.control.inspect.return_value.active_queues.return_value = kuyruklar
    return patch.dict("sys.modules", {}) if False else patch(
        "app.tasks.celery_app.celery_app", sahte)


# ------------------------------------------------------------------ tespit

def test_sesli_isci_VARSA_aktif_bildirilir():
    with _inspect_dondur({"voice-host@PC": [{"name": "voice"}]}):
        canli, ipucu = admin_api._sesli_worker_canli()
    assert canli is True
    assert ipucu == "", "Isci calisirken uyari gosterilmemeli"


def test_sesli_isci_YOKSA_ne_yapilacagi_soylenir():
    """Sadece "calismiyor" demek yetmez; kullanici komutu bilmeli."""
    with _inspect_dondur({"fast@konteyner": [{"name": "fast"}]}):
        canli, ipucu = admin_api._sesli_worker_canli()
    assert canli is False
    assert "run-host-worker" in ipucu, f"Cozum adimi yazilmamis: {ipucu}"


def test_HIC_isci_yoksa_ayri_mesaj():
    """Broker bos donerse sorun yalnizca sesli isci degil, tum arka plan."""
    with _inspect_dondur({}):
        canli, ipucu = admin_api._sesli_worker_canli()
    assert canli is False
    assert ipucu and "run-host-worker" in ipucu


def test_broker_COKERSE_panel_calismaya_devam_eder():
    """Isci durumu sorgulanamiyorsa yonetim ekrani acilmali — sadece bilmiyor."""
    sahte = MagicMock()
    sahte.control.inspect.side_effect = OSError("broker yok")
    with patch("app.tasks.celery_app.celery_app", sahte):
        canli, ipucu = admin_api._sesli_worker_canli()
    assert canli is False
    assert ipucu, "Sebep yazilmamis"


# ------------------------------------------------------------------ uç

def test_processing_ucu_ISCI_DURUMUNU_donduruyor(seeded, client):
    """Alan kaldirilirsa arayuz uyariyi hic gosteremez."""
    r = client.get("/api/v1/admin/processing", headers=_hdr(seeded))
    assert r.status_code == 200
    veri = r.json()
    for alan in ("voice_worker_active", "voice_worker_hint", "pending_calls", "paused"):
        assert alan in veri, f"/admin/processing yanitinda '{alan}' yok"
    assert isinstance(veri["voice_worker_active"], bool)


# ------------------------------------------------------------------ kaynak denetimi

def test_arayuz_UYARIYI_basiyor():
    """Sunucu dogru bilgiyi donse de arayuz gostermezse kullanici goremez.

    Bu depoda "kural yazili, uygulanmiyor" kalibi defalarca yasandi; uyarinin
    render edildigi kaynak duzeyinde kilitleniyor.
    """
    from pathlib import Path

    p = Path(__file__).resolve().parents[2] / "frontend" / "app" / "admin" / "page.tsx"
    if not p.exists():
        return
    metin = p.read_text(encoding="utf-8")
    assert "voice_worker_active === false" in metin, (
        "Yonetim ekrani sesli isci uyarisini gostermiyor")
    assert "voice_worker_hint" in metin, "Ipucu metni basilmiyor"


def test_sesli_cagri_VOICE_kuyruguna_gidiyor():
    """Yonlendirme degisirse bu kontrolun anlami kalmaz."""
    from app.tasks.celery_app import celery_app

    yollar = celery_app.conf.task_routes or {}
    assert yollar.get("kalitegoz.process_call", {}).get("queue") == "voice", (
        "process_call artik 'voice' kuyruguna gitmiyor — uyari yanlis yere bakiyor")
