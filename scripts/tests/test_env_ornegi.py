"""`.env` ile `.env.example` aynı anahtar kümesini taşıyor mu?

## Neden host tarafında

Bu denetim `backend/tests` altında olamaz: `make test` konteynerde koşar ve
konteynere yalnızca `backend/` bağlanır — `.env.example` orada yoktur. Test
oraya konsaydı **her koşuda sessizce atlanır**, yani hiçbir şeyi korumazdı.
Atlanan test, olmayan testtir.

## Neyi korur

1. `.env.example`'da olan her anahtar `.env`'de de var (kullanıcı depoyu
   klonlayıp `generate-secrets.sh` çalıştırdığında eksik alan kalmasın).
2. `.env.example` hiçbir gerçek sır içermiyor.
3. Yeni eklenen davranış anahtarları belgeleniyor — kullanıcı varlığından
   haberdar olmadığı bir anahtarı kapatamaz.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parents[2]
ORNEK = KOK / ".env.example"
GERCEK = KOK / ".env"


def _anahtarlar(yol: Path) -> dict[str, str]:
    if not yol.exists():
        return {}
    cikti: dict[str, str] = {}
    for satir in yol.read_text(encoding="utf-8").splitlines():
        satir = satir.strip()
        if not satir or satir.startswith("#") or "=" not in satir:
            continue
        ad, _, deger = satir.partition("=")
        cikti[ad.strip()] = deger.strip()
    return cikti


def test_ornek_dosya_VAR():
    assert ORNEK.exists(), ".env.example yok — klonlayan ne yazacagini bilemez"


def test_ORNEKTEKI_her_anahtar_gercekte_de_var():
    """Eksik anahtar sessiz varsayilana duser; kullanici sebebini goremez."""
    if not GERCEK.exists():
        pytest.skip(".env yok (temiz klon) — karsilastirilacak bir sey yok")
    eksik = sorted(set(_anahtarlar(ORNEK)) - set(_anahtarlar(GERCEK)))
    assert not eksik, f".env'de eksik anahtarlar: {eksik}"


def test_YEDEGE_DUSME_anahtari_belgeli():
    """B38: `llm_fallback_ollama` once hicbir yerde tanimli degildi.

    Kod `getattr(..., True)` diyordu; kullanici .env'e yazsa bile etkisiz
    kaliyordu ve panelde de gorunmuyordu. Anahtarin belgeli kalmasi,
    davranisin kapatilabilir OLDUGUNUN tek isareti.
    """
    metin = ORNEK.read_text(encoding="utf-8")
    assert "LLM_FALLBACK_OLLAMA" in metin, "LLM_FALLBACK_OLLAMA .env.example'da yok"
    # Yalnizca adi degil, NE YAPTIGI da yazmali
    satirlar = metin.splitlines()
    i = next(k for k, s in enumerate(satirlar) if s.startswith("LLM_FALLBACK_OLLAMA"))
    yorum = [s for s in satirlar[max(0, i - 8):i] if s.startswith("#")]
    assert yorum, "LLM_FALLBACK_OLLAMA'nin ustunde aciklama yorumu yok"


def test_ornekte_GERCEK_SIR_yok():
    """Ornek dosya depoya girer; icinde calisan bir sir olmamali."""
    metin = ORNEK.read_text(encoding="utf-8")
    supheli: list[str] = []
    for satir in metin.splitlines():
        if satir.startswith("#") or "=" not in satir:
            continue
        ad, _, deger = satir.partition("=")
        deger = deger.strip()
        if not deger:
            continue
        # Gercek anahtar kaliplari
        if re.match(r"^sk-[A-Za-z0-9_-]{20,}$", deger):
            supheli.append(ad)
        elif re.match(r"^AIza[A-Za-z0-9_-]{30,}$", deger):
            supheli.append(ad)
        # Uzun rastgele degerler: sir uretecinin ciktisina benziyor
        elif len(deger) >= 40 and re.fullmatch(r"[A-Za-z0-9+/=_-]+", deger):
            supheli.append(ad)
    assert not supheli, f".env.example'da gercek sir olabilir: {supheli}"
