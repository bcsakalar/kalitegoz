"""LLM istemcisi: Ollama (varsayilan/yerel) · Gemini · OpenAI · OpenRouter.

Aktif saglayici + model + anahtar, kurum ayarindan `ai_config` ile cozumlenir
(scoring worker'inda contextvar ile tasinir; yoksa .env global'e duser).
Tum cagrilarda cikti pydantic modele zorlanir; hata olursa 1 kez repair prompt.
KVKK: harici saglayiciya (gemini/openai/openrouter) giden metin DAIMA maskelenir.
"""

import json
import logging
import time
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from ..config import settings
from . import ai_config
from .ai_config import AIResolved
from .masking import mask_text

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    pass


def _chat_ollama(cfg: AIResolved, system: str, user: str) -> tuple[str, int, int]:
    resp = httpx.post(
        f"{cfg.base_url}/api/chat",
        json={
            "model": cfg.model,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.1, "num_ctx": settings.ollama_num_ctx},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        },
        timeout=settings.llm_timeout_sec,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["message"]["content"], int(data.get("prompt_eval_count") or 0), int(data.get("eval_count") or 0)


def _chat_gemini(cfg: AIResolved, system: str, user: str) -> tuple[str, int, int]:
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{cfg.model}:generateContent"
    )
    resp = httpx.post(
        url,
        params={"key": cfg.api_key},
        json={
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"},
        },
        timeout=settings.llm_timeout_sec,
    )
    resp.raise_for_status()
    data = resp.json()
    um = data.get("usageMetadata", {})
    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as exc:
        raise LLMError(f"Gemini beklenmedik yanit: {json.dumps(data)[:500]}") from exc
    return text, int(um.get("promptTokenCount") or 0), int(um.get("candidatesTokenCount") or 0)


def _chat_openai_compatible(cfg: AIResolved, system: str, user: str) -> tuple[str, int, int]:
    """OpenAI ve OpenRouter (ayni /chat/completions API'si, JSON modu)."""
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
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        },
        timeout=settings.llm_timeout_sec,
    )
    resp.raise_for_status()
    data = resp.json()
    usage = data.get("usage", {})
    return (data["choices"][0]["message"]["content"],
            int(usage.get("prompt_tokens") or 0), int(usage.get("completion_tokens") or 0))


def _record_usage(cfg: AIResolved, pt: int, ct: int, latency_ms: int, ok: bool) -> None:
    """LLM cagrisini AiUsage'a yaz (best-effort; kayit hatasi cagriyi bozmaz)."""
    meta = ai_config.usage_meta()
    if not meta or not meta.get("tenant_id"):
        return
    try:
        from ..db import SessionLocal
        from ..models import AiUsage
        db = SessionLocal()
        try:
            db.add(AiUsage(
                tenant_id=meta["tenant_id"], provider=cfg.provider, model=cfg.model,
                kind=meta.get("kind", "llm"), prompt_tokens=pt, completion_tokens=ct,
                latency_ms=latency_ms, ok=ok,
                cost_usd=ai_config.estimate_cost(cfg.provider, cfg.model, pt, ct),
            ))
            db.commit()
        finally:
            db.close()
    except Exception as exc:  # noqa: BLE001 — kayit asla ana akisi bozmaz
        logger.warning("AiUsage kaydi basarisiz: %s", exc)


def _chat(system: str, user: str, cfg: AIResolved | None = None) -> str:
    cfg = cfg or ai_config.active_llm()
    if cfg.provider != "ollama" and not cfg.api_key:
        raise LLMError(f"{cfg.provider} secili ama API anahtari girilmemis")
    # KVKK: harici saglayiciya giden metin DAIMA maskelenir; yerel (ollama) istege bagli
    if cfg.external or settings.mask_local_llm:
        system, user = mask_text(system), mask_text(user)
    t0 = time.monotonic()
    try:
        if cfg.provider == "gemini":
            text, pt, ct = _chat_gemini(cfg, system, user)
        elif cfg.provider in ("openai", "openrouter"):
            text, pt, ct = _chat_openai_compatible(cfg, system, user)
        else:
            text, pt, ct = _chat_ollama(cfg, system, user)
    except Exception:
        _record_usage(cfg, 0, 0, int((time.monotonic() - t0) * 1000), ok=False)
        raise
    _record_usage(cfg, pt, ct, int((time.monotonic() - t0) * 1000), ok=True)
    return text


def _extract_json(raw: str) -> str:
    """Kod bloklari / basindaki-sonundaki gurultuyu temizleyip JSON govdesini cikar."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1] if raw.count("```") >= 2 else raw.lstrip("`")
        if raw.startswith("json"):
            raw = raw[4:]
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("Yanit icinde JSON nesnesi bulunamadi")
    return raw[start : end + 1]


def _generate_with(model_cls: type[T], system: str, user: str, cfg: AIResolved) -> T:
    """Verilen config ile JSON uret; gecersizse repair prompt ile retry."""
    last_error: Exception | None = None
    prompt = user
    for attempt in range(settings.llm_max_retries + 1):
        try:
            raw = _chat(system, prompt, cfg)
        except httpx.HTTPError as exc:
            raise LLMError(f"LLM erisim hatasi ({cfg.provider}/{cfg.model}): {exc}") from exc
        try:
            return model_cls.model_validate_json(_extract_json(raw))
        except (ValidationError, ValueError, json.JSONDecodeError) as exc:
            last_error = exc
            logger.warning("LLM JSON dogrulama hatasi (deneme %d): %s", attempt + 1, exc)
            schema = json.dumps(model_cls.model_json_schema(), ensure_ascii=False)
            prompt = (
                "Onceki yanitin gecersizdi ve su hatayi verdi:\n"
                f"{exc}\n\n"
                "Onceki (hatali) yanitin:\n"
                f"{raw[:4000]}\n\n"
                "Ayni degerlendirmeyi asagidaki JSON semasina TAM uyumlu sekilde, "
                "aciklama eklemeden, SADECE gecerli JSON olarak yeniden yaz:\n"
                f"{schema}\n\n"
                "Orijinal gorev:\n"
                f"{user}"
            )
    raise LLMError(f"LLM ciktisi {settings.llm_max_retries + 1} denemede dogrulanamadi: {last_error}")


def generate_json_with(model_cls: type[T], system: str, user: str, cfg: AIResolved) -> T:
    """Belirli bir model config'i ile JSON uret (S2c — kriter bazli yonlendirme).

    Hata durumunda varsayilan modele DUSER: bir kurulumun buyuk modeli
    indirmemis olmasi puanlamayi durdurmamali.
    """
    try:
        return _generate_with(model_cls, system, user, cfg)
    except LLMError:
        logger.warning(
            "Yonlendirilen model (%s) basarisiz; varsayilan modele dusuluyor.", cfg.model)
        return generate_json(model_cls, system, user)


def generate_json(model_cls: type[T], system: str, user: str) -> T:
    """LLM'den JSON iste. Birincil (bulut) saglayici erisim/anahtar hatasi verirse
    ve fallback aciksa yerel Ollama'ya duser — puanlama tek saglayiciya bagli kalmaz."""
    cfg = ai_config.active_llm()
    try:
        return _generate_with(model_cls, system, user, cfg)
    except LLMError:
        fallback_on = getattr(settings, "llm_fallback_ollama", True)
        if cfg.provider != "ollama" and fallback_on:
            logger.warning("Birincil saglayici (%s/%s) basarisiz; yerel Ollama'ya dusuluyor.",
                           cfg.provider, cfg.model)
            return _generate_with(model_cls, system, user, ai_config.ollama_fallback())
        raise


def test_config(cfg: AIResolved) -> str:
    """Panelden 'Test et': verilen config ile kucuk bir istek yap, ham yaniti dondur."""
    return _chat(
        "Sen bir test asistanisin. SADECE gecerli JSON dondur.",
        'Su JSON\'u aynen dondur: {"ok": true, "mesaj": "baglanti calisiyor"}',
        cfg,
    )
