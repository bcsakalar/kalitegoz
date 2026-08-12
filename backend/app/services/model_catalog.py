"""Canlı model kataloğu — sağlayıcının kendi API'sinden model listesi çeker.

## Neden sabit liste değil

`ai_config.CATALOG` elle yazılmış bir listeydi. İki sorunu vardı:

1. **Eskiyor.** Sağlayıcılar ayda birkaç model çıkarıyor; liste güncellenmezse
   kullanıcı yeni modeli seçemez. "gpt-4.1" listeye eklenene kadar yok sayılır.
2. **Eksik.** Elle yazılan 4-5 model, sağlayıcıdaki onlarcasının yanında
   keyfi bir seçki. Hangi modelin neden listede olduğu belli değil.

Bu modül listeyi **kaynağından** alır. Sabit liste yalnızca ağ/anahtar
yokken devreye giren yedek olarak kalır.

## Sağlayıcı uçları

| Sağlayıcı | Uç | Anahtar |
|---|---|---|
| Ollama | `{base}/api/tags` | gerekmez (yerel) |
| OpenRouter | `https://openrouter.ai/api/v1/models` | **gerekmez** (herkese açık) |
| OpenAI | `https://api.openai.com/v1/models` | gerekir |
| Gemini | `{base}/v1beta/models?key=…` | gerekir |

## Türe göre süzme

Bir modeli "puanlama"da göstermek ile "gömme"de göstermek farklı şeylerdir.
Süzme **sağlayıcının kendi meta verisiyle** yapılır, ad tahminiyle değil:

- **Gemini** — `supportedGenerationMethods`: `generateContent` → llm,
  `embedContent` → embed. Bu alan doğrudan sağlayıcıdan gelir.
- **OpenRouter** — `architecture.input_modalities` içinde `image` varsa
  vision. Gömme sunmadığı için embed listesi boştur.
- **OpenAI** — model kimliğinde `embedding` geçiyorsa embed. OpenAI liste
  ucunda yetenek meta verisi vermiyor; ad kalıbı tek kaynak.
- **Ollama** — `/api/tags` yanıtındaki `capabilities` alanı (`embedding`,
  `vision`, `completion`). Ad kalıbı yalnızca eski Ollama sürümlerinde
  yedek olarak kullanılır. Kurulu olmayan model listelenmez.

## Önbellek

Sağlayıcı listeleri saatte bir değişmez ama panel her açılışta çekerse
gereksiz gecikme olur. 15 dakikalık bellek içi önbellek yeterli; kullanıcı
"yenile" derse atlanır.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

import httpx

from . import ai_config

logger = logging.getLogger(__name__)

# Sağlayıcı listeleri hızlı değişmez; panelin her açılışında ağa çıkmak
# gereksiz gecikme demek.
ONBELLEK_SANIYE = 900

_onbellek: dict[str, tuple[float, list[dict]]] = {}

ISTEK_ZAMAN_ASIMI = 12.0


@dataclass
class KatalogSonuc:
    """Model listesi + nereden geldiği.

    `kaynak` alanı arayüzde gösterilir: kullanıcı canlı listeye mi yoksa
    yedek listeye mi baktığını bilmeli. "Liste eski olabilir" demek,
    sessizce eski liste göstermekten iyidir.
    """

    modeller: list[dict] = field(default_factory=list)
    kaynak: str = "canli"          # canli | onbellek | yedek
    hata: str = ""
    saglayici: str = ""
    tur: str = ""


def _onbellek_anahtari(saglayici: str, tur: str) -> str:
    return f"{saglayici}:{tur}"


def _onbellekten(anahtar: str) -> list[dict] | None:
    kayit = _onbellek.get(anahtar)
    if not kayit:
        return None
    zaman, veri = kayit
    if time.time() - zaman > ONBELLEK_SANIYE:
        return None
    return veri


# ---------------------------------------------------------------- Ollama

def _ollama_turu(m: dict) -> str:
    """Modelin turu — once OLLAMA'NIN KENDI meta verisi, sonra ad kalibi.

    Ollama `/api/tags` yanitinda `capabilities` alani donduruyor:
      ["embedding"]            -> gomme modeli
      ["completion", "vision"] -> gorsel destekli
      ["completion", "tools"]  -> duz LLM

    Ad kalibina guvenmek yanlis siniflandiriyordu: `bge-m3` bir gomme
    modelidir ama adinda "embed" gecmez, dolayisiyla LLM listesinde
    gorunuyordu. Saglayicinin beyani her zaman tahminden iyidir.
    """
    yetenekler = {str(x).lower() for x in (m.get("capabilities") or [])}
    if "embedding" in yetenekler:
        return "embed"
    if "vision" in yetenekler:
        return "vision"
    if yetenekler:
        return "llm"

    # capabilities yoksa (eski Ollama surumu) ad kalibina dus
    ad = (m.get("name") or "").lower()
    aile = " ".join(str(x) for x in ((m.get("details") or {}).get("families") or []))
    metin = f"{ad} {aile}".lower()
    if any(x in metin for x in ("embed", "bge", "gte", "e5-", "minilm", "arctic")):
        return "embed"
    if any(x in metin for x in ("-vl", "vision", "llava", "clip")):
        return "vision"
    return "llm"


def _ollama(base_url: str, tur: str) -> list[dict]:
    """Yerel KURULU modeller. Kurulu olmayan model listelenmez —
    seçilebilir gösterip sonra 'model yok' hatası vermek yanıltıcı olur."""
    resp = httpx.get(f"{base_url}/api/tags", timeout=ISTEK_ZAMAN_ASIMI)
    resp.raise_for_status()
    out = []
    for m in resp.json().get("models", []):
        ad = m.get("name", "")
        if not ad:
            continue
        model_turu = _ollama_turu(m)
        if tur != "hepsi" and model_turu != tur:
            continue
        boyut = m.get("size") or 0
        ayrinti = m.get("details") or {}
        ctx = ayrinti.get("context_length")
        out.append({
            "id": ad,
            "ad": ad,
            "tur": model_turu,
            # Metin DEGIL sayi donuyoruz: arayuz TR ve EN olarak biciimlendirir.
            # Sunucuda Turkce metin uretmek, EN arayuzde karma dil demekti.
            "boyut_gb": round(boyut / 1e9, 1) if boyut else None,
            "baglam": int(ctx) if ctx else None,
            "kurulu": True,
        })
    return sorted(out, key=lambda x: x["id"])


# ---------------------------------------------------------------- OpenRouter

def _openrouter(tur: str) -> list[dict]:
    """OpenRouter model listesi. Anahtar GEREKTIRMEZ — herkese açık uç.

    Bu, kullanıcının anahtar girmeden önce hangi modellerin bulunduğunu
    görebilmesi demektir.
    """
    resp = httpx.get(f"{ai_config.OPENROUTER_BASE}/models", timeout=ISTEK_ZAMAN_ASIMI)
    resp.raise_for_status()
    out = []
    for m in resp.json().get("data", []):
        kimlik = m.get("id")
        if not kimlik:
            continue
        mimari = m.get("architecture") or {}
        girdiler = mimari.get("input_modalities") or []
        gorsel = "image" in girdiler
        model_turu = "vision" if gorsel else "llm"
        if tur == "embed":
            continue  # OpenRouter gömme sunmuyor
        if tur != "hepsi" and model_turu != tur and not (tur == "llm" and gorsel):
            # Görsel modeller metin de üretir; llm listesinde de görünsünler
            continue
        ctx = m.get("context_length")
        fiyat = (m.get("pricing") or {}).get("prompt")
        try:
            fiyat_m = float(fiyat) * 1e6 if fiyat is not None else None
        except (TypeError, ValueError):
            fiyat_m = None
        out.append({
            "id": kimlik,
            "ad": m.get("name") or kimlik,
            "tur": model_turu,
            "baglam": int(ctx) if ctx else None,
            "fiyat_m": round(fiyat_m, 2) if fiyat_m else None,
            "ucretsiz": fiyat_m == 0,
            "kurulu": False,
        })
    return sorted(out, key=lambda x: x["id"])


# ---------------------------------------------------------------- OpenAI

def _openai(api_key: str, tur: str) -> list[dict]:
    if not api_key:
        raise ValueError("OpenAI API anahtarı gerekli")
    resp = httpx.get(
        f"{ai_config.OPENAI_BASE}/models",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=ISTEK_ZAMAN_ASIMI,
    )
    resp.raise_for_status()
    out = []
    for m in resp.json().get("data", []):
        kimlik = m.get("id", "")
        if not kimlik:
            continue
        dusuk = kimlik.lower()
        # OpenAI liste ucunda yetenek meta verisi YOK; ad kalıbı tek kaynak.
        if "embedding" in dusuk:
            model_turu = "embed"
        elif any(x in dusuk for x in ("whisper", "tts", "dall-e", "moderation", "sora")):
            continue  # bu ürünün kullanmadığı model aileleri
        else:
            model_turu = "llm"
        if tur != "hepsi" and model_turu != tur:
            # Vision istenmişse: OpenAI'de görsel yeteneği gpt-4o/4.1 ailesinde
            if not (tur == "vision" and model_turu == "llm"
                    and any(x in dusuk for x in ("gpt-4o", "gpt-4.1", "o3", "o4"))):
                continue
        out.append({"id": kimlik, "ad": kimlik, "tur": model_turu,
                    "kurulu": False})
    return sorted(out, key=lambda x: x["id"])


# ---------------------------------------------------------------- Gemini

def _gemini(api_key: str, tur: str) -> list[dict]:
    if not api_key:
        raise ValueError("Gemini API anahtarı gerekli")
    resp = httpx.get(
        "https://generativelanguage.googleapis.com/v1beta/models",
        params={"key": api_key, "pageSize": 200},
        timeout=ISTEK_ZAMAN_ASIMI,
    )
    resp.raise_for_status()
    out = []
    for m in resp.json().get("models", []):
        tam_ad = m.get("name", "")            # "models/gemini-2.5-flash"
        kimlik = tam_ad.split("/", 1)[-1]
        if not kimlik:
            continue
        # Yetenek SAGLAYICIDAN gelir — ad tahmini yapmıyoruz.
        yontemler = m.get("supportedGenerationMethods") or []
        if "embedContent" in yontemler:
            model_turu = "embed"
        elif "generateContent" in yontemler:
            model_turu = "llm"
        else:
            continue  # bu ürünün kullanamayacağı model (ör. yalnız tuneleme)
        if tur == "vision":
            # Gemini'de generateContent yapan modeller görsel de alır
            if model_turu != "llm":
                continue
        elif tur != "hepsi" and model_turu != tur:
            continue
        ctx = m.get("inputTokenLimit")
        out.append({
            "id": kimlik,
            "ad": m.get("displayName") or kimlik,
            "tur": model_turu,
            "baglam": int(ctx) if ctx else None,
            "kurulu": False,
        })
    return sorted(out, key=lambda x: x["id"])


# ---------------------------------------------------------------- yedek

def _yedek(saglayici: str, tur: str) -> list[dict]:
    """Ağ/anahtar yokken gösterilecek elle yazılmış liste.

    Bu liste ESKIYEBILIR ve arayüz bunu `kaynak="yedek"` ile söyler.
    """
    anahtar = {
        ("gemini", "llm"): "gemini",
        ("gemini", "embed"): "gemini_embed",
        ("gemini", "vision"): "gemini_vision",
        ("openai", "llm"): "openai",
        ("openai", "embed"): "openai_embed",
        ("openai", "vision"): "openai_vision",
        ("openrouter", "llm"): "openrouter",
        ("openrouter", "vision"): "openrouter_vision",
    }.get((saglayici, tur))
    if not anahtar:
        return []
    return [
        {"id": m, "ad": m, "tur": tur, "kurulu": False}
        for m in ai_config.CATALOG.get(anahtar, [])
    ]


# ---------------------------------------------------------------- genel

# Saglayicinin o yuzeyi HIC sunmadigi durumlar. Bos liste dondurup susmak
# yerine sebebini yaziyoruz — yoksa kullanici anahtarini yanlis sanir.
DESTEKLENMEYEN: dict[tuple[str, str], str] = {
    ("openrouter", "embed"):
        "OpenRouter gömme (embedding) modeli sunmuyor — yalnızca sohbet ve "
        "görsel modelleri var. Gömme için Ollama, OpenAI veya Gemini seçin.",
}


def listele(saglayici: str, tur: str = "llm", *, api_key: str = "",
            base_url: str = "", tazele: bool = False) -> KatalogSonuc:
    """Bir sağlayıcının modellerini getir.

    `tur`: llm | embed | vision | hepsi
    """
    if saglayici not in ai_config.PROVIDERS:
        return KatalogSonuc(kaynak="yedek", hata=f"Bilinmeyen sağlayıcı: {saglayici}",
                            saglayici=saglayici, tur=tur)

    if (saglayici, tur) in DESTEKLENMEYEN:
        # Bos liste + bos hata, kullaniciya "anahtarim mi yanlis?" dedirtir.
        # Sagalyici o yuzeyi HIC sunmuyorsa bunu acikca soyle.
        return KatalogSonuc(kaynak="canli", hata=DESTEKLENMEYEN[(saglayici, tur)],
                            saglayici=saglayici, tur=tur)

    anahtar = _onbellek_anahtari(saglayici, tur)
    if not tazele:
        onbellekli = _onbellekten(anahtar)
        if onbellekli is not None:
            return KatalogSonuc(modeller=onbellekli, kaynak="onbellek",
                                saglayici=saglayici, tur=tur)

    try:
        if saglayici == "ollama":
            modeller = _ollama(base_url or ai_config.ollama_fallback().base_url, tur)
        elif saglayici == "openrouter":
            modeller = _openrouter(tur)
        elif saglayici == "openai":
            modeller = _openai(api_key, tur)
        else:
            modeller = _gemini(api_key, tur)
        _onbellek[anahtar] = (time.time(), modeller)
        return KatalogSonuc(modeller=modeller, kaynak="canli",
                            saglayici=saglayici, tur=tur)
    except Exception as exc:  # noqa: BLE001 — liste alinamazsa panel calismaya devam etmeli
        logger.warning("Model listesi alinamadi (%s/%s): %s", saglayici, tur, exc)
        return KatalogSonuc(
            modeller=_yedek(saglayici, tur),
            kaynak="yedek",
            hata=_hata_mesaji(saglayici, exc),
            saglayici=saglayici, tur=tur,
        )


def hata_mesaji(saglayici: str, exc: Exception, *, baglam: str = "liste") -> str:
    """Kullaniciya NE YAPACAGINI soyleyen hata metni.

    Hem model listesi hem de panelin "baglantiyi test et" dugmesi bunu
    kullanir. Ham istisna metni ("Client error '401 Unauthorized' for url ...
    https://developer.mozilla.org/...") kullaniciya hicbir sey soylemiyordu.

    `baglam`: liste | test — sonunda verilen tavsiye buna gore degisir.
    """
    metin = str(exc)
    gecersiz = (f"{saglayici} API anahtarı geçersiz ya da yetkisiz. "
                "Anahtarı kontrol edip kaydedin.")
    if isinstance(exc, httpx.HTTPStatusError):
        kod = exc.response.status_code
        if kod in (401, 403):
            return gecersiz
        # Gemini gecersiz anahtara 401 DEGIL 400/API_KEY_INVALID donuyor;
        # olculdu. Sadece 401'e bakan kontrol onu "bilinmeyen hata" sayiyordu.
        if kod == 400:
            govde = ""
            try:
                govde = exc.response.text[:300]
            except Exception:  # noqa: BLE001 — govde okunamazsa kod yeter
                pass
            if "API_KEY_INVALID" in govde or "API key not valid" in govde:
                return gecersiz
            if "quota" in govde.lower():
                return f"{saglayici} kotası dolmuş görünüyor; hesabınızı kontrol edin."
            return f"{saglayici} isteği reddetti (400): {govde[:120] or metin[:120]}"
        if kod == 404:
            return (f"{saglayici} bu modeli bulamadı. Model adını kontrol edin "
                    "— listede olmayan bir ad yazılmış olabilir.")
        if kod == 429:
            return f"{saglayici} hız sınırı aşıldı; birkaç dakika sonra tekrar deneyin."
        return f"{saglayici} {kod} döndü: {metin[:120]}"
    if isinstance(exc, ValueError):
        return metin
    if baglam == "test":
        return f"{saglayici} sunucusuna ulaşılamadı ({metin[:100]})."
    return (f"{saglayici} model listesine ulaşılamadı ({metin[:80]}). "
            "Aşağıdaki liste yedek listedir ve eski olabilir.")


# Geriye donuk ad — modul icinde kullaniliyor.
_hata_mesaji = hata_mesaji
