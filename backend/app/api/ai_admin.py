"""Coklu AI saglayici yonetimi (admin): saglayici/model/anahtar secimi, Ollama
model listeleme + indirme (pull), canli test. Kurum-bazli (Tenant.settings["ai"]).
"""

import json
import threading
from datetime import datetime, timedelta

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..deps import CurrentUser, require_admin
from ..models import AiUsage, Tenant
from ..schemas import AiUsageRow, AiUsageSummary
from ..services import ai_config, audit, model_catalog

router = APIRouter(prefix="/api/v1/admin/ai", tags=["ai-admin"])


@router.get("/usage", response_model=AiUsageSummary)
def ai_usage(days: int = 30, db: Session = Depends(get_db),
             user: CurrentUser = Depends(require_admin)):
    """Kurumun AI kullanimi: cagri sayisi, token, tahmini maliyet, gecikme —
    amaca (scoring/topics/...) ve saglayiciya gore kirilim. Ollama yerel = 0 maliyet."""
    since = datetime.utcnow() - timedelta(days=days)
    base = db.query(AiUsage).filter(AiUsage.tenant_id == user.tenant_id,
                                    AiUsage.created_at >= since)
    total_calls = base.count()

    def _rows(group_col):
        q = (base.with_entities(
                group_col, AiUsage.provider, func.count(AiUsage.id),
                func.coalesce(func.sum(AiUsage.prompt_tokens), 0),
                func.coalesce(func.sum(AiUsage.completion_tokens), 0),
                func.coalesce(func.sum(AiUsage.cost_usd), 0.0),
                func.coalesce(func.avg(AiUsage.latency_ms), 0))
             .group_by(group_col, AiUsage.provider).all())
        return [AiUsageRow(kind=str(r[0]), provider=r[1], calls=r[2], prompt_tokens=int(r[3]),
                           completion_tokens=int(r[4]), cost_usd=round(float(r[5]), 4),
                           avg_latency_ms=int(r[6] or 0)) for r in q]

    ok_count = base.filter(AiUsage.ok.is_(True)).count()
    total_tokens = int(db.query(
        func.coalesce(func.sum(AiUsage.prompt_tokens + AiUsage.completion_tokens), 0)
    ).filter(AiUsage.tenant_id == user.tenant_id, AiUsage.created_at >= since).scalar() or 0)
    total_cost = float(db.query(
        func.coalesce(func.sum(AiUsage.cost_usd), 0.0)
    ).filter(AiUsage.tenant_id == user.tenant_id, AiUsage.created_at >= since).scalar() or 0.0)

    return AiUsageSummary(
        period_days=days, total_calls=total_calls, total_tokens=total_tokens,
        total_cost_usd=round(total_cost, 4),
        ok_rate=round(ok_count / total_calls * 100, 1) if total_calls else 100.0,
        by_kind=_rows(AiUsage.kind), by_provider=_rows(AiUsage.provider))


# ---- Yardimcilar ----
def _ts(db: Session, tenant_id: int) -> dict | None:
    t = db.get(Tenant, tenant_id)
    return t.settings if t else None


def _ai(db: Session, tenant_id: int) -> dict:
    return (_ts(db, tenant_id) or {}).get("ai", {}) or {}


# ---- Semalar ----
class AIConfigUpdate(BaseModel):
    llm_provider: str | None = None
    vision_provider: str | None = None
    embed_provider: str | None = None
    llm_models: dict[str, str] | None = None      # {provider: model}
    vision_models: dict[str, str] | None = None
    embed_models: dict[str, str] | None = None
    keys: dict[str, str] | None = None            # {provider: apikey} (bos ise dokunulmaz)


class AITestRequest(BaseModel):
    provider: str | None = None   # bos ise kayitli LLM saglayicisi test edilir


class OllamaPullRequest(BaseModel):
    model: str


# ---- Config ----
def _yedege_dusme(db: Session, tenant_id: int, secili: str) -> dict:
    """Son 24 saatte secili saglayici yerine yerel modelle yapilan cagri sayisi.

    Ayri bir tabloya gerek yok: AiUsage her cagriyi GERCEKTEN kullanilan
    saglayici adiyla yaziyor. Secili saglayici bulutken kayitta 'ollama'
    goruyorsak, o cagri yedege dusmustur.
    """
    if secili == "ollama":
        return {"var": False, "adet": 0, "toplam": 0}  # yerelken dusulecek yer yok

    since = datetime.utcnow() - timedelta(hours=24)
    satirlar = (
        db.query(AiUsage.provider, func.count(AiUsage.id))
        .filter(AiUsage.tenant_id == tenant_id, AiUsage.created_at >= since,
                AiUsage.kind != "embed")  # gomme ayri saglayici secebilir
        .group_by(AiUsage.provider)
        .all()
    )
    sayim = {p: n for p, n in satirlar}
    dusen = sayim.get("ollama", 0)
    toplam = sum(sayim.values())
    return {"var": dusen > 0, "adet": dusen, "toplam": toplam, "secili": secili}


def _config_out(db: Session, tenant_id: int) -> dict:
    ai = _ai(db, tenant_id)
    keys = ai.get("keys", {}) or {}
    ts = _ts(db, tenant_id)
    llm = ai_config.resolve(ts, "llm")
    vision = ai_config.resolve(ts, "vision")
    embed = ai_config.resolve(ts, "embed")

    return {
        "llm_provider": llm.provider,
        "vision_provider": vision.provider,
        "embed_provider": embed.provider,
        "llm_models": ai.get("llm_models", {}) or {},
        "vision_models": ai.get("vision_models", {}) or {},
        "embed_models": ai.get("embed_models", {}) or {},

        # ETKIN model — su an GERCEKTEN kullanilan.
        #
        # `*_models` yalnizca kiracinin panelden yaptigi SECIMI tasir; bos
        # olabilir ve o zaman sistem .env varsayilanina duser. Panel yalnizca
        # secimi gosterdigi icin, hicbir secim yapilmamis bir kurulumda model
        # alani BOS gorunuyordu ve kullanici "hicbir sey ayarli degil"
        # saniyordu — oysa sistem calisiyordu.
        #
        # Bu alanlar "su an ne kullaniliyor" sorusunun cevabidir.
        "effective": {
            "llm": {"provider": llm.provider, "model": llm.model,
                    "external": llm.external},
            "vision": {"provider": vision.provider, "model": vision.model,
                       "external": vision.external},
            "embed": {"provider": embed.provider, "model": embed.model,
                      "external": embed.external},
        },
        # Herhangi bir yuzey bulut saglayiciya gidiyorsa veri kurum disina
        # cikiyor demektir; guvenlik sayfasi ve panel bunu belirtmeli.
        "veri_disari_cikiyor": any(c.external for c in (llm, vision, embed)),

        # SESSIZ DUSME PANOSU
        #
        # Bulut saglayici hata verirse sistem yerel Ollama'ya duser (bkz.
        # llm.generate_json). Bu, bulut kesintisinde puanlamanin durmamasi
        # icindir — ama cagri SECILENDEN BASKA bir modelle puanlanir.
        # Izi yalnizca konteyner logunda kalirsa kullanici Gemini ile
        # puanlandigini sanip yerel modelin puanina bakar.
        #
        # Burada son 24 saatin sayimi veriliyor; panel uyari gosterir.
        "yedege_dusme": _yedege_dusme(db, tenant_id, llm.provider),
        "yedek_acik": settings.llm_fallback_ollama,

        "keys_set": {p: bool(keys.get(p)) for p in ("gemini", "openai", "openrouter")},
        "providers": ai_config.PROVIDERS,
        "embed_providers": ai_config.EMBED_PROVIDERS,
        "vision_providers": ai_config.VISION_PROVIDERS,
    }


@router.get("/config")
def get_ai_config(db: Session = Depends(get_db), user: CurrentUser = Depends(require_admin)):
    return _config_out(db, user.tenant_id)


@router.get("/catalog")
def get_catalog(user: CurrentUser = Depends(require_admin)):
    """Onerilen modeller (Ollama indirilebilir + bulut model listeleri).

    NOT: Bu SABIT listedir ve eskiyebilir. Canli liste icin /ai/models
    kullanin — o, saglayicinin kendi API'sinden ceker.
    """
    return ai_config.CATALOG


@router.get("/models")
def list_models(
    provider: str,
    kind: str = "llm",
    refresh: bool = False,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_admin),
):
    """Bir saglayicinin CANLI model listesi.

    Anahtar kiracinin ayarindan alinir; kullanicinin anahtari tekrar
    girmesine gerek yoktur. OpenRouter anahtar gerektirmez — kullanici
    anahtar girmeden once de listeyi gorebilir.

    Liste alinamazsa yedek (sabit) liste doner ve `kaynak: "yedek"` ile
    bunu SOYLER. Sessizce eski liste gostermek, kullaniciyi olmayan bir
    modeli sectigini sanmaya birakir.
    """
    if kind not in ("llm", "embed", "vision", "hepsi"):
        raise HTTPException(400, f"Gecersiz tur: {kind}")

    tenant = db.get(Tenant, user.tenant_id)
    ai = (tenant.settings or {}).get("ai", {}) if tenant else {}
    anahtar = (ai.get("keys", {}) or {}).get(provider, "") or ai_config._global_key(provider)

    sonuc = model_catalog.listele(
        provider, kind,
        api_key=anahtar,
        base_url=settings.ollama_base_url,
        tazele=refresh,
    )
    return {
        "saglayici": sonuc.saglayici,
        "tur": sonuc.tur,
        "kaynak": sonuc.kaynak,
        "hata": sonuc.hata,
        "modeller": sonuc.modeller,
    }


@router.put("/config")
def put_ai_config(body: AIConfigUpdate, db: Session = Depends(get_db),
                  user: CurrentUser = Depends(require_admin)):
    tenant = db.get(Tenant, user.tenant_id)
    ai = dict((tenant.settings or {}).get("ai", {}) or {})

    def _prov(val, allowed):
        if val is not None and val not in allowed:
            raise HTTPException(400, f"Gecersiz saglayici: {val}")
        return val

    if _prov(body.llm_provider, ai_config.PROVIDERS):
        ai["llm_provider"] = body.llm_provider
    if _prov(body.vision_provider, ai_config.VISION_PROVIDERS):
        ai["vision_provider"] = body.vision_provider
    if _prov(body.embed_provider, ai_config.EMBED_PROVIDERS):
        ai["embed_provider"] = body.embed_provider
    for field in ("llm_models", "vision_models", "embed_models"):
        val = getattr(body, field)
        if val is not None:
            ai[field] = {**(ai.get(field, {}) or {}), **val}
    if body.keys:
        cur = dict(ai.get("keys", {}) or {})
        for p, k in body.keys.items():
            if k and k.strip() and not k.startswith("•"):  # bos veya maskeli ise dokunma
                cur[p] = k.strip()
        ai["keys"] = cur

    s = dict(tenant.settings or {})
    s["ai"] = ai
    tenant.settings = s
    db.commit()
    audit.log(db, action="update_ai_config", tenant_id=tenant.id, user_id=user.id,
              detail={"llm": ai.get("llm_provider")})
    return _config_out(db, user.tenant_id)


@router.post("/test")
def test_ai(body: AITestRequest, db: Session = Depends(get_db),
            user: CurrentUser = Depends(require_admin)):
    """Secili (veya belirtilen) LLM saglayicisini kucuk bir istekle canli test et."""
    ts = _ts(db, user.tenant_id)
    if body.provider:
        ai = dict((ts or {}).get("ai", {}) or {})
        ai["llm_provider"] = body.provider
        ts = {**(ts or {}), "ai": ai}
    cfg = ai_config.resolve(ts, "llm")
    from ..services.llm import test_config, LLMError
    try:
        out = test_config(cfg)
        return {"ok": True, "provider": cfg.provider, "model": cfg.model, "output": out[:300]}
    except (LLMError, httpx.HTTPError, Exception) as exc:  # noqa: BLE001
        # Ham istisna metni ("Client error '401 Unauthorized' for url ...
        # https://developer.mozilla.org/...") kullaniciya ne yapacagini
        # soylemiyordu. Model listesiyle ayni cevirici kullaniliyor.
        return {
            "ok": False, "provider": cfg.provider, "model": cfg.model,
            "error": model_catalog.hata_mesaji(cfg.provider, exc, baglam="test"),
            "ham": str(exc)[:300],  # ayrintiyi isteyen yonetici icin
        }


# ---- Ollama model yonetimi ----
def _human(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.0f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


@router.get("/ollama/models")
def ollama_models(user: CurrentUser = Depends(require_admin)):
    """Host Ollama'da yuklu modeller."""
    try:
        r = httpx.get(f"{settings.ollama_base_url}/api/tags", timeout=10)
        r.raise_for_status()
        return {"models": [{"name": m["name"], "size": _human(m.get("size", 0))}
                           for m in r.json().get("models", [])]}
    except httpx.HTTPError as exc:
        return {"models": [], "error": f"Ollama'ya ulasilamadi: {exc}"}


# Model indirme durumu (bellek-ici, en iyi caba; tek api replica'da calisir)
_pull_status: dict[str, dict] = {}


def _do_pull(base_url: str, model: str) -> None:
    _pull_status[model] = {"status": "baslatiliyor", "percent": 0.0, "done": False, "error": None}
    try:
        with httpx.stream("POST", f"{base_url}/api/pull",
                          json={"name": model, "stream": True}, timeout=None) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if not line:
                    continue
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if d.get("error"):
                    _pull_status[model] = {"status": "hata", "percent": 0, "done": True, "error": d["error"][:300]}
                    return
                st = d.get("status", "")
                total, completed = d.get("total"), d.get("completed")
                pct = (completed / total * 100) if (total and completed) else _pull_status[model].get("percent", 0)
                _pull_status[model] = {"status": st, "percent": round(pct, 1),
                                       "done": st == "success", "error": None}
        _pull_status[model] = {"status": "tamamlandi", "percent": 100.0, "done": True, "error": None}
    except Exception as exc:  # noqa: BLE001
        _pull_status[model] = {"status": "hata", "percent": 0, "done": True, "error": str(exc)[:300]}


@router.post("/ollama/pull")
def ollama_pull(body: OllamaPullRequest, user: CurrentUser = Depends(require_admin)):
    model = body.model.strip()
    if not model:
        raise HTTPException(400, "Model adi bos")
    cur = _pull_status.get(model)
    if cur and not cur.get("done"):
        return {"started": True, "already": True}
    threading.Thread(target=_do_pull, args=(settings.ollama_base_url, model), daemon=True).start()
    return {"started": True}


@router.get("/ollama/pull-status")
def pull_status(user: CurrentUser = Depends(require_admin)):
    """Devam eden/biten indirmelerin durumu (bellek-ici, en iyi caba)."""
    return _pull_status
