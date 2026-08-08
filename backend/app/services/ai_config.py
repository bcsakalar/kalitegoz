"""Coklu AI saglayici yapilandirmasi (kurum-bazli, .env fallback).

Varsayilan DAIMA Ollama (yerel). Panelden Gemini / OpenAI / OpenRouter anahtari +
model secilebilir. Kurum ayari `Tenant.settings["ai"]` altinda tutulur:

    {
      "llm_provider":   "ollama"|"gemini"|"openai"|"openrouter",
      "vision_provider": "...",
      "embed_provider":  "...",
      "keys":   {"gemini": "...", "openai": "...", "openrouter": "..."},
      "llm_models":    {"ollama": "qwen2.5:7b-instruct", "gemini": "...", ...},
      "vision_models": {...},
      "embed_models":  {...}
    }

Scoring worker'inda aktif LLM config'i contextvar ile tasinir (imza kirilmaz).
"""

import contextlib
import contextvars
from dataclasses import dataclass

from ..config import settings

PROVIDERS = ["ollama", "gemini", "openai", "openrouter"]
# OpenRouter embedding sunmaz; embed icin yalnizca bunlar.
EMBED_PROVIDERS = ["ollama", "gemini", "openai"]
VISION_PROVIDERS = ["ollama", "gemini", "openai", "openrouter"]

OPENAI_BASE = "https://api.openai.com/v1"
OPENROUTER_BASE = "https://openrouter.ai/api/v1"

# Panel katalogu — onerilen modeller (kullanici yine de ozel model yazabilir)
CATALOG = {
    "ollama_recommended": [
        # --- Puanlama (LLM) ---
        {"name": "qwen2.5:7b-instruct", "size": "4.7 GB", "kind": "llm", "desc": "Dengeli varsayilan — Turkce guclu, hizli"},
        {"name": "qwen2.5:14b", "size": "9 GB", "kind": "llm", "desc": "En iyi kalite — 12GB VRAM'e sigar (onerilen)"},
        {"name": "gemma3:12b", "size": "8.1 GB", "kind": "llm", "desc": "Google Gemma 3 — 140+ dil, gorsel de yapar"},
        {"name": "qwen3:8b", "size": "5.2 GB", "kind": "llm", "desc": "Qwen3 — yeni nesil, hiz/kalite dengesi"},
        {"name": "qwen2.5:3b", "size": "2 GB", "kind": "llm", "desc": "Hizli / hafif — dusuk VRAM"},
        # --- Embedding (RAG / benzer cagri) ---
        {"name": "qwen3-embedding:4b", "size": "2.5 GB", "kind": "embed", "desc": "Qwen3 Embedding — cok dilli #1, Turkce en iyi"},
        {"name": "bge-m3", "size": "1.2 GB", "kind": "embed", "desc": "BGE-M3 — cok dilli, saglam (production)"},
        {"name": "nomic-embed-text", "size": "274 MB", "kind": "embed", "desc": "Nomic — hafif, hizli (Ingilizce agirlikli)"},
        # --- Gorsel denetim (Vision) ---
        {"name": "llama3.2-vision:11b", "size": "7.8 GB", "kind": "vision", "desc": "Llama 3.2 Vision — genel gorsel/dokuman en iyi"},
        {"name": "qwen3-vl:4b", "size": "3.3 GB", "kind": "vision", "desc": "Qwen3-VL — hafif, OCR/Turkce metin"},
    ],
    "gemini": ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash"],
    "openai": ["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini", "gpt-4.1"],
    "openrouter": [
        "openai/gpt-4o-mini", "anthropic/claude-sonnet-4",
        "google/gemini-2.5-flash", "meta-llama/llama-3.3-70b-instruct",
    ],
    "gemini_embed": ["gemini-embedding-001", "text-embedding-004"],
    "openai_embed": ["text-embedding-3-small", "text-embedding-3-large"],
    "gemini_vision": ["gemini-2.5-flash", "gemini-2.5-pro"],
    "openai_vision": ["gpt-4o-mini", "gpt-4o", "gpt-4.1"],
    "openrouter_vision": ["openai/gpt-4o-mini", "google/gemini-2.5-flash"],
}


@dataclass
class AIResolved:
    provider: str
    model: str
    api_key: str
    base_url: str   # openai-uyumlu taban veya ollama tabani ("" = gemini ozel)
    kind: str       # llm | vision | embed
    external: bool  # KVKK: harici saglayici -> metin maskelenir


def _ai(tenant_settings: dict | None) -> dict:
    if not tenant_settings:
        return {}
    a = tenant_settings.get("ai")
    return a if isinstance(a, dict) else {}


def _global_default_model(kind: str, provider: str) -> str:
    if provider == "ollama":
        return {"llm": settings.ollama_model, "vision": settings.ollama_vision_model,
                "embed": settings.embed_model}[kind]
    if provider == "gemini":
        return {"llm": settings.gemini_model, "vision": settings.gemini_vision_model,
                "embed": settings.gemini_embed_model}[kind]
    # openai / openrouter icin .env yok -> katalog varsayilani
    defaults = {
        ("llm", "openai"): "gpt-4o-mini", ("llm", "openrouter"): "openai/gpt-4o-mini",
        ("vision", "openai"): "gpt-4o-mini", ("vision", "openrouter"): "openai/gpt-4o-mini",
        ("embed", "openai"): "text-embedding-3-small",
    }
    return defaults.get((kind, provider), "")


def _global_key(provider: str) -> str:
    return {"gemini": settings.gemini_api_key}.get(provider, "")


def resolve(tenant_settings: dict | None, kind: str) -> AIResolved:
    """Bir tenant + amac (llm/vision/embed) icin efektif saglayici+model+anahtar."""
    ai = _ai(tenant_settings)
    allowed = {"llm": PROVIDERS, "vision": VISION_PROVIDERS, "embed": EMBED_PROVIDERS}[kind]
    pkey = {"llm": "llm_provider", "vision": "vision_provider", "embed": "embed_provider"}[kind]

    provider = ai.get(pkey)
    if provider not in allowed:
        # .env global saglayici (ollama/gemini) veya ollama
        provider = settings.llm_provider if settings.llm_provider in allowed else "ollama"

    model = (ai.get(f"{kind}_models", {}) or {}).get(provider) or _global_default_model(kind, provider)
    api_key = (ai.get("keys", {}) or {}).get(provider) or _global_key(provider)
    base_url = {"ollama": settings.ollama_base_url, "openai": OPENAI_BASE,
                "openrouter": OPENROUTER_BASE, "gemini": ""}[provider]
    return AIResolved(provider, model, api_key, base_url, kind, provider != "ollama")


# --- Aktif LLM config (scoring worker'inda set edilir) ---
_active: contextvars.ContextVar = contextvars.ContextVar("ai_llm_cfg", default=None)
# Kullanim kaydi icin bloktaki tenant_id + amac (kind); yoksa kayit atlanir.
_usage: contextvars.ContextVar = contextvars.ContextVar("ai_usage_meta", default=None)

# Yaklasik bulut fiyatlari (USD / 1K token) — panelde tahmini maliyet icin.
# Ollama yerel: 0. Degerler kaba; kesin faturayi saglayici belirler.
COST_PER_1K = {
    "gemini-2.0-flash": (0.0001, 0.0004), "gemini-1.5-flash": (0.000075, 0.0003),
    "gemini-1.5-pro": (0.00125, 0.005), "gpt-4o-mini": (0.00015, 0.0006),
    "gpt-4o": (0.0025, 0.01), "gpt-4.1-mini": (0.0004, 0.0016),
}


def estimate_cost(provider: str, model: str, prompt_tokens: int, completion_tokens: int) -> float:
    if provider == "ollama":
        return 0.0
    pin, pout = COST_PER_1K.get(model.split("/")[-1], (0.0005, 0.0015))
    return round(prompt_tokens / 1000 * pin + completion_tokens / 1000 * pout, 6)


def set_active(cfg: AIResolved):
    return _active.set(cfg)


def reset_active(token) -> None:
    _active.reset(token)


def usage_meta() -> dict | None:
    """Aktif kullanim baglami: {tenant_id, kind} veya None (kayit atla)."""
    return _usage.get()


def active_llm() -> AIResolved:
    """Aktif LLM config'i dondur; yoksa global (.env) cozumlemesine dus."""
    cfg = _active.get()
    return cfg if cfg is not None else resolve(None, "llm")


def ollama_fallback() -> AIResolved:
    """Birincil (bulut) saglayici coktugunde donulecek yerel Ollama config'i."""
    return AIResolved("ollama", settings.ollama_model, "", settings.ollama_base_url, "llm", False)


@contextlib.contextmanager
def use_llm(tenant_settings: dict | None, tenant_id: int | None = None, kind: str = "scoring"):
    """Bir blok boyunca aktif LLM config'ini kurumun ayarina sabitler.

    Tum LLM cagiran servisler (scoring, topics, scorecard) bu blok icinde
    calisirsa kurumun saglayici secimi (Ollama/Gemini/OpenAI/OpenRouter) gecerli olur.
    tenant_id verilirse LLM cagrilari AiUsage tablosuna kaydedilir (maliyet paneli).
    """
    tok = set_active(resolve(tenant_settings, "llm"))
    utok = _usage.set({"tenant_id": tenant_id, "kind": kind}) if tenant_id else None
    try:
        yield
    finally:
        reset_active(tok)
        if utok is not None:
            _usage.reset(utok)


def masked_key(key: str) -> str:
    """Anahtari panelde maskeli goster (son 4 hane)."""
    if not key:
        return ""
    return ("•" * 6) + key[-4:] if len(key) > 4 else "••••"
