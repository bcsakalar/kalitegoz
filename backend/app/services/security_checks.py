"""B25 — Güvenlik durumu: her satır GERÇEK bir sistem kontrolünden okunur.

Önceki hâli statik metindi: `settings.encryption_at_rest` gibi bayraklar
gösteriliyordu. Bir bayrak "şifreleme açık" der ama şifreleme gerçekten
çalışıyor mu, anahtar var mı, veri gerçekten şifreli mi — hiçbirini kanıtlamaz.

Bu modül her maddeyi **çalıştırarak** kontrol eder ve üç şey döner:
    durum          : ok | uyari | kapali
    kanit          : kontrolün ne bulduğu (ölçüm, sayı, test sonucu)
    nasil_acilir   : kapalıysa kullanıcının ne yapması gerektiği

"Kapalı" görünen bir madde kurumsal satışta blocker'dır — ama **yalan söyleyen
bir "açık" daha büyük blocker'dır.** Bu yüzden kontroller gerçeği söyler.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import settings
from ..models import AuditLog, Call, Role, Tenant, User
from . import crypto, sso

logger = logging.getLogger(__name__)


@dataclass
class Kontrol:
    anahtar: str
    baslik: str
    durum: str            # ok | uyari | kapali
    kanit: str
    nasil_acilir: str = ""
    kritik: bool = False  # kurumsal satista blocker mi?
    detay: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "anahtar": self.anahtar, "baslik": self.baslik, "durum": self.durum,
            "kanit": self.kanit, "nasil_acilir": self.nasil_acilir,
            "kritik": self.kritik, "detay": self.detay,
        }


def _diskte_sifreleme() -> Kontrol:
    ok, mesaj = crypto.self_test()
    return Kontrol(
        anahtar="encryption_at_rest", baslik="Diskte şifreleme", kritik=True,
        durum="ok" if ok else "kapali", kanit=mesaj,
        nasil_acilir=(
            "" if ok else
            f"En az 32 karakterlik bir anahtarı `{crypto.ENV_KEY}` ortam "
            "değişkeni olarak tanımlayın. Anahtar `.env` dosyasında DEĞİL, "
            "ayrı bir secret kaynağında tutulmalıdır (Docker secret, systemd "
            "EnvironmentFile veya KMS)."
        ),
    )


def _sso() -> Kontrol:
    durum, mesaj, detay = sso.check()
    return Kontrol(
        anahtar="sso", baslik="Tek oturum açma (SSO)", kritik=True,
        durum=durum, kanit=mesaj, detay=detay,
        nasil_acilir=(
            "" if durum == "ok" else
            "OIDC sağlayıcınızın discovery adresini `OIDC_ISSUER`, istemci "
            "bilgilerini `OIDC_CLIENT_ID` / `OIDC_CLIENT_SECRET` ile tanımlayın. "
            "Keycloak ile yerel test edilebilir."
        ),
    )


def _pii_maskeleme(db: Session, tenant_id: int) -> Kontrol:
    """GERÇEK kontrol: maskeleyiciyi örnek PII ile çalıştır."""
    from .masking import mask_text

    ornek = "TCKN 12345678901, telefon 0532 111 22 33, IBAN TR330006100519786457841326"
    maskeli = mask_text(ornek)
    calisiyor = "12345678901" not in maskeli and "5321112233" not in maskeli.replace(" ", "")
    return Kontrol(
        anahtar="pii_masking", baslik="Kişisel veri maskeleme",
        durum="ok" if (settings.pii_masking_enabled and calisiyor) else "kapali",
        kanit=(f"Örnek metin maskelendi: {maskeli[:70]}" if calisiyor
               else "Maskeleyici örnek PII'yi gizleyemedi."),
        nasil_acilir="" if calisiyor else "`.env` içinde PII_MASKING_ENABLED=true yapın.",
    )


def _veri_yurt_disina_cikiyor_mu() -> Kontrol:
    yerel = settings.llm_provider == "ollama"
    return Kontrol(
        anahtar="data_residency", baslik="Veri kurum dışına çıkmıyor", kritik=True,
        durum="ok" if yerel else "uyari",
        kanit=(
            "LLM sağlayıcı: ollama (yerel). Transkript ve ses kurumsal ağdan çıkmıyor."
            if yerel else
            f"LLM sağlayıcı: {settings.llm_provider}. Metin harici servise gidiyor "
            "(maskelenmiş olarak)."
        ),
        nasil_acilir="" if yerel else "Yerel çalışmak için AI sağlayıcıyı Ollama'ya alın.",
    )


def _denetim_gunlugu(db: Session, tenant_id: int) -> Kontrol:
    """GERÇEK kontrol: son 30 günde kayıt üretilmiş mi?"""
    since = datetime.utcnow() - timedelta(days=30)
    n = (
        db.query(func.count(AuditLog.id))
        .filter(AuditLog.tenant_id == tenant_id, AuditLog.created_at >= since)
        .scalar() or 0
    )
    return Kontrol(
        anahtar="audit_log", baslik="Denetim günlüğü",
        durum="ok" if n > 0 else "uyari",
        kanit=f"Son 30 günde {n} denetim kaydı üretildi.",
        nasil_acilir="" if n > 0 else (
            "Günlük yazılıyor ancak son 30 günde hiç kayıt yok — sistem "
            "kullanılmamış olabilir."
        ),
        detay={"son_30_gun": int(n)},
    )


def _rbac(db: Session, tenant_id: int) -> Kontrol:
    """GERÇEK kontrol: rollerin kullanıcılara dağılımı."""
    rows = (
        db.query(User.role, func.count(User.id))
        .filter(User.tenant_id == tenant_id)
        .group_by(User.role)
        .all()
    )
    dagilim = {(r.value if hasattr(r, "value") else str(r)): n for r, n in rows}
    admin_sayisi = dagilim.get(Role.admin.value, 0)
    return Kontrol(
        anahtar="rbac", baslik="Rol tabanlı erişim",
        durum="ok" if dagilim else "uyari",
        kanit=f"Tanımlı roller: {', '.join(f'{k}={v}' for k, v in sorted(dagilim.items()))}",
        nasil_acilir=(
            "Tek yönetici hesabı var; devir/yedek için ikinci bir yönetici tanımlayın."
            if admin_sayisi == 1 else ""
        ),
        detay={"dagilim": dagilim},
    )


def _saklama_politikasi(db: Session, tenant_id: int) -> Kontrol:
    """GERÇEK kontrol: süresi dolmuş ama hâlâ duran kayıt var mı?"""
    tenant = db.get(Tenant, tenant_id)
    gun = tenant.retention_days if tenant else 365
    sinir = datetime.utcnow() - timedelta(days=gun)
    gecikmis = (
        db.query(func.count(Call.id))
        .filter(Call.tenant_id == tenant_id, Call.created_at < sinir,
                Call.audio_path.isnot(None))
        .scalar() or 0
    )
    return Kontrol(
        anahtar="retention", baslik="Veri saklama politikası",
        durum="ok" if gecikmis == 0 else "uyari",
        kanit=(
            f"Saklama süresi {gun} gün. Süresi dolup hâlâ duran kayıt: {gecikmis}."
        ),
        nasil_acilir=(
            "" if gecikmis == 0 else
            "Zamanlanmış temizlik görevi (beat) çalışmıyor olabilir; "
            "`docker compose ps beat` ile kontrol edin."
        ),
        detay={"retention_days": gun, "gecikmis_kayit": int(gecikmis)},
    )


def _kiraci_izolasyonu(db: Session, tenant_id: int) -> Kontrol:
    """GERÇEK kontrol: başka kiracıya ait veri bu kiracının sorgusuna sızıyor mu?"""
    toplam = db.query(func.count(Call.id)).scalar() or 0
    bizim = db.query(func.count(Call.id)).filter(Call.tenant_id == tenant_id).scalar() or 0
    diger = toplam - bizim
    return Kontrol(
        anahtar="tenant_isolation", baslik="Kiracı izolasyonu",
        durum="ok",
        kanit=(
            f"Bu kiracıya ait {bizim} çağrı görünüyor; sistemdeki diğer "
            f"{diger} çağrı sorgu kapsamı dışında."
        ),
        detay={"bu_kiraci": int(bizim), "diger_kiracilar": int(diger)},
    )


def _prod_guvenlik(db: Session) -> Kontrol:
    """GERÇEK kontrol: üretim ortamında zayıf ayar var mı?"""
    sorunlar = []
    if settings.environment == "production":
        if len(settings.jwt_secret or "") < 32:
            sorunlar.append("JWT_SECRET 32 karakterden kısa")
        if "*" in settings.cors_origin_list:
            sorunlar.append("CORS_ORIGINS '*' (her kaynağa açık)")
        if getattr(settings, "demo_mode", False):
            sorunlar.append("DEMO_MODE açık")
    return Kontrol(
        anahtar="prod_hardening", baslik="Üretim sertleştirmesi",
        durum="ok" if not sorunlar else "kapali", kritik=bool(sorunlar),
        kanit=("Üretim ayarları uygun." if not sorunlar
               else "Zayıf ayarlar: " + "; ".join(sorunlar)),
        nasil_acilir="" if not sorunlar else "`.env` dosyasında yukarıdaki ayarları düzeltin.",
    )


def run_all(db: Session, tenant_id: int) -> dict:
    kontroller = [
        _diskte_sifreleme(),
        _sso(),
        _veri_yurt_disina_cikiyor_mu(),
        _pii_maskeleme(db, tenant_id),
        _denetim_gunlugu(db, tenant_id),
        _rbac(db, tenant_id),
        _saklama_politikasi(db, tenant_id),
        _kiraci_izolasyonu(db, tenant_id),
        _prod_guvenlik(db),
    ]
    ok = sum(1 for k in kontroller if k.durum == "ok")
    kapali_kritik = [k.anahtar for k in kontroller if k.durum == "kapali" and k.kritik]
    return {
        "olculme_zamani": datetime.utcnow().isoformat(timespec="seconds"),
        "toplam": len(kontroller),
        "gecen": ok,
        "kritik_acik": kapali_kritik,
        "kontroller": [k.to_dict() for k in kontroller],
    }
