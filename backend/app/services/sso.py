"""Tek oturum açma (SSO) — OIDC.

Kurumsal satışta SSO bir "nice to have" değil, çoğu ihalede **zorunlu maddedir**.
Güvenlik sayfasında "kapalı" görünmesi doğrudan blocker'dır (B25).

## Yapılandırma

    OIDC_ISSUER=https://keycloak.sirket.local/realms/kalitegoz
    OIDC_CLIENT_ID=kalitegoz
    OIDC_CLIENT_SECRET=...
    OIDC_REDIRECT_URI=https://kalitegoz.sirket.local/api/v1/auth/sso/callback

Keycloak ile yerel test edilebilir.

## Kontrol GERÇEKTİR

`check()` bir bayrak okumaz: sağlayıcının **discovery adresine gider**,
`authorization_endpoint` ve `token_endpoint` alanlarının varlığını doğrular.
Ayar var ama sağlayıcı erişilemiyorsa durum `uyari` olur — "açık" demek
yanıltıcı olurdu.
"""

from __future__ import annotations

import logging
import os
import time

import httpx

logger = logging.getLogger(__name__)

DISCOVERY_SUFFIX = "/.well-known/openid-configuration"
_CACHE_TTL = 300  # sn — guvenlik sayfasi her acilista saglayiciya gitmesin
_cache: dict = {"t": 0.0, "sonuc": None}


# Yonetim ekranindan girilen ayarlar burada tutulur (S12). Ortam degiskeni
# YEDEK olarak kalir: konteyner tabanli kurulumlar env ile de yapilandirabilir.
# Oncelik: veritabani ayari > ortam degiskeni.
_db_config: dict = {}


def set_db_config(cfg: dict | None) -> None:
    """Kiraci ayarindan gelen OIDC yapilandirmasini yukle (yonetim ekrani)."""
    global _db_config
    _db_config = {k: str(v or "").strip() for k, v in (cfg or {}).items()}
    _cache.update(t=0.0, sonuc=None)  # yeniden kontrol edilsin


def config() -> dict:
    """Etkin OIDC yapilandirmasi. Veritabani ayari ortam degiskenini EZER."""
    def _al(anahtar: str, env: str) -> str:
        return _db_config.get(anahtar) or os.environ.get(env, "").strip()

    return {
        "issuer": _al("issuer", "OIDC_ISSUER"),
        "client_id": _al("client_id", "OIDC_CLIENT_ID"),
        "client_secret": _al("client_secret", "OIDC_CLIENT_SECRET"),
        "redirect_uri": _al("redirect_uri", "OIDC_REDIRECT_URI"),
    }


def kaynak() -> str:
    """Ayar nereden geliyor? Guvenlik sayfasi bunu gosterir."""
    if _db_config.get("issuer"):
        return "yonetim_ekrani"
    if os.environ.get("OIDC_ISSUER"):
        return "ortam_degiskeni"
    return "yok"


def is_configured() -> bool:
    c = config()
    return bool(c["issuer"] and c["client_id"] and c["client_secret"])


def discovery(issuer: str, timeout: float = 4.0) -> dict | None:
    url = issuer.rstrip("/") + DISCOVERY_SUFFIX
    try:
        resp = httpx.get(url, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("OIDC discovery basarisiz (%s): %s", url, exc)
        return None


def check(force: bool = False) -> tuple[str, str, dict]:
    """GERÇEK kontrol → (durum, mesaj, detay).

    durum: ok | uyari | kapali
    """
    now = time.time()
    if not force and _cache["sonuc"] and now - _cache["t"] < _CACHE_TTL:
        return _cache["sonuc"]

    c = config()
    if not is_configured():
        eksik = [k for k in ("issuer", "client_id", "client_secret") if not c[k]]
        sonuc = (
            "kapali",
            f"OIDC yapılandırılmamış (eksik: {', '.join(eksik)}). "
            "Kullanıcılar yalnızca e-posta/parola ile giriyor.",
            {"configured": False},
        )
        _cache.update(t=now, sonuc=sonuc)
        return sonuc

    doc = discovery(c["issuer"])
    if doc is None:
        sonuc = (
            "uyari",
            f"OIDC yapılandırılmış ({c['issuer']}) ancak sağlayıcıya ulaşılamıyor. "
            "SSO şu an çalışmıyor.",
            {"configured": True, "reachable": False, "issuer": c["issuer"]},
        )
        _cache.update(t=now, sonuc=sonuc)
        return sonuc

    eksik_uc = [
        k for k in ("authorization_endpoint", "token_endpoint", "jwks_uri")
        if not doc.get(k)
    ]
    if eksik_uc:
        sonuc = (
            "uyari",
            f"Sağlayıcı yanıt verdi ancak eksik uç nokta: {', '.join(eksik_uc)}.",
            {"configured": True, "reachable": True, "missing": eksik_uc},
        )
    else:
        sonuc = (
            "ok",
            f"OIDC sağlayıcı doğrulandı: {c['issuer']} "
            f"({doc.get('issuer', '')}). Yetkilendirme ve token uçları erişilebilir.",
            {
                "configured": True, "reachable": True,
                "issuer": doc.get("issuer"),
                "authorization_endpoint": doc.get("authorization_endpoint"),
            },
        )
    _cache.update(t=now, sonuc=sonuc)
    return sonuc


def authorize_url(state: str, nonce: str) -> str | None:
    """Kullanıcıyı sağlayıcıya yönlendirecek adres."""
    c = config()
    if not is_configured():
        return None
    doc = discovery(c["issuer"])
    if not doc or not doc.get("authorization_endpoint"):
        return None
    from urllib.parse import urlencode

    params = {
        "response_type": "code",
        "client_id": c["client_id"],
        "redirect_uri": c["redirect_uri"],
        "scope": "openid email profile",
        "state": state,
        "nonce": nonce,
    }
    return f"{doc['authorization_endpoint']}?{urlencode(params)}"


def exchange_code(code: str) -> dict | None:
    """Yetkilendirme kodunu token ile değiştir."""
    c = config()
    doc = discovery(c["issuer"]) if is_configured() else None
    if not doc or not doc.get("token_endpoint"):
        return None
    try:
        resp = httpx.post(
            doc["token_endpoint"],
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": c["redirect_uri"],
                "client_id": c["client_id"],
                "client_secret": c["client_secret"],
            },
            timeout=8.0,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("OIDC token degisimi basarisiz: %s", exc)
        return None
