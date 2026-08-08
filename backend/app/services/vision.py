"""Vision: chat'e eklenen ekran goruntusu / belge denetimi.

Coklu saglayici: Ollama (llava/qwen-vl) · Gemini · OpenAI · OpenRouter — kurum
ayarindan (ai_config) cozumlenir. Goruntuyu gorme-yetenegli LLM'e gonderip
yapilandirilmis analiz cikarir: ne iceriyor, KVKK riski, hassas veri.
"""

from __future__ import annotations

import base64
import logging

import httpx

from ..config import settings
from . import ai_config
from .ai_config import AIResolved
from .schemas_vision import VisionResult

logger = logging.getLogger(__name__)


class VisionError(RuntimeError):
    pass


_SYSTEM = (
    "Sen bir cagri merkezi kalite denetim asistanisin. Sana bir musteri "
    "ek/gorseli (ekran goruntusu, fatura, belge) verilecek. Turkce, KISA ve "
    "yalnizca gecerli JSON ile yanit ver."
)

_PROMPT = """Bu gorseli incele ve SADECE su JSON semasiyla yanit ver:
{
  "aciklama": "gorselde ne var, 1-2 cumle",
  "belge_turu": "fatura|ekran_goruntusu|kimlik|sozlesme|diger",
  "kvkk_riski": "dusuk|orta|yuksek",
  "hassas_veri": ["kart_no"|"tckn"|"telefon"|"adres"|"iban" ...],
  "ozet_not": "temsilci/kalite icin kisa not"
}
Gorselde aciktan kart numarasi, TCKN, IBAN gibi kisisel/mali veri varsa
kvkk_riski YUKSEK olmali ve hassas_veri listesine eklenmeli."""


def _analyze_ollama(cfg: AIResolved, image_b64: str) -> str:
    resp = httpx.post(
        f"{cfg.base_url}/api/generate",
        json={
            "model": cfg.model,
            "prompt": f"{_SYSTEM}\n\n{_PROMPT}",
            "images": [image_b64],
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.1},
        },
        timeout=settings.llm_timeout_sec,
    )
    if resp.status_code == 404:
        raise VisionError(
            f"Vision modeli bulunamadi ({cfg.model}). Once cekin: ollama pull {cfg.model}")
    resp.raise_for_status()
    return resp.json().get("response", "")


def _analyze_gemini(cfg: AIResolved, image_b64: str, mime: str) -> str:
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{cfg.model}:generateContent?key={cfg.api_key}"
    )
    resp = httpx.post(
        url,
        json={
            "contents": [{
                "parts": [
                    {"text": f"{_SYSTEM}\n\n{_PROMPT}"},
                    {"inline_data": {"mime_type": mime, "data": image_b64}},
                ]
            }],
            "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"},
        },
        timeout=settings.llm_timeout_sec,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]


def _analyze_openai_compatible(cfg: AIResolved, image_b64: str, mime: str) -> str:
    headers = {"Authorization": f"Bearer {cfg.api_key}"}
    if "openrouter" in cfg.base_url:
        headers["HTTP-Referer"] = "https://kalitegoz.local"
        headers["X-Title"] = "KaliteGoz"
    resp = httpx.post(
        f"{cfg.base_url}/chat/completions",
        headers=headers,
        json={
            "model": cfg.model,
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": [
                    {"type": "text", "text": _PROMPT},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{image_b64}"}},
                ]},
            ],
        },
        timeout=settings.llm_timeout_sec,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def analyze_image(image_bytes: bytes, mime: str = "image/png",
                  tenant_settings: dict | None = None) -> VisionResult:
    """Goruntuyu denetle; yapilandirilmis VisionResult dondur. Saglayici kurum
    ayarindan (ai_config vision) cozumlenir; anahtar yoksa hata verir."""
    if not settings.vision_enabled:
        raise VisionError("Vision kapali (VISION_ENABLED=false)")
    import json

    cfg = ai_config.resolve(tenant_settings, "vision")
    if cfg.provider != "ollama" and not cfg.api_key:
        raise VisionError(f"Vision saglayicisi {cfg.provider} secili ama API anahtari yok")

    image_b64 = base64.b64encode(image_bytes).decode("ascii")
    if cfg.provider == "gemini":
        raw = _analyze_gemini(cfg, image_b64, mime)
    elif cfg.provider in ("openai", "openrouter"):
        raw = _analyze_openai_compatible(cfg, image_b64, mime)
    else:
        raw = _analyze_ollama(cfg, image_b64)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise VisionError(f"Vision JSON parse edilemedi: {raw[:200]}") from exc
    return VisionResult(**data)
