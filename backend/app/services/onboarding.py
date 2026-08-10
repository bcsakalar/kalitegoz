"""Kurumsal onboarding: yeni organizasyon (tenant) olusturma + davet/parola token'lari.

On-prem, sirket basina model: ilk admin kendi kurumunu olusturur; sonra kullanicilari
davet eder. Yeni kuruma makul bir baslangic rubrigi + yasakli kelime + rozet seti
verilir (kalite puanlamasi kutudan cikar cikmaz calissin). E-posta (SMTP) varsa davet/
sifirlama linki gonderilir; yoksa link admin panelinde gosterilir (on-prem'de yaygin).
"""

import re
import secrets
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText

from sqlalchemy.orm import Session

from ..config import settings
from ..models import AuthToken, Badge, BannedWord, Criterion, Role, Tenant, User
from ..security import hash_password
from ..seed import DEFAULT_BADGES, DEFAULT_BANNED_WORDS, DEFAULT_CRITERIA

DEMO_SLUG = "demo"

# IC KIRACILAR — kullaniciya ASLA kurum olarak sunulmaz.
#
# `make eval` izole bir `__golden__` kiracisi, performans olcumu de `__perf__`
# kiracisi kurar. Bunlar olcum araclarinin calisma alanidir, birer musteri
# degil. Ayirt edilmedikleri icin giris ekrani kurumu "__golden__" diye
# gosteriyor ve tarayici `tenant_slug=golden` gonderiyordu — kullanicilar
# `demo` kiracisinda oldugu icin HER GIRIS 401 aliyordu. (B35, bizzat yasandi:
# make eval kosulan bir makinede arayuze hic girilemiyordu.)
#
# Isimlendirme kurali: cift alt cizgiyle baslayan kiraci adi = ic kiraci.
IC_KIRACI_ADLARI = {"__golden__", "__perf__"}
IC_KIRACI_SLUGLARI = {"golden", "perf"}


def _gercek_kurum_sorgusu(db: Session):
    """Demo ve IC kiracilar disindaki aktif kurumlar."""
    return (
        db.query(Tenant)
        .filter(
            Tenant.slug != DEMO_SLUG,
            Tenant.slug.notin_(IC_KIRACI_SLUGLARI),
            Tenant.name.notin_(IC_KIRACI_ADLARI),
            # autoescape ZORUNLU: SQL LIKE'da "_" tek karakter jokeridir.
            # autoescape olmadan "__%" deseni ADI 2+ karakter olan HER kurumu
            # eler ve primary_tenant None doner (testler yakaladi).
            ~Tenant.name.startswith("__", autoescape=True),
            Tenant.is_active.is_(True),
        )
    )


class OnboardingError(ValueError):
    pass


def slugify(name: str) -> str:
    s = (name or "").lower().strip()
    for a, b in {"ç": "c", "ğ": "g", "ı": "i", "ö": "o", "ş": "s", "ü": "u", "i̇": "i"}.items():
        s = s.replace(a, b)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "kurum"


def unique_slug(db: Session, name: str) -> str:
    base = slugify(name)
    slug, i = base, 2
    while db.query(Tenant).filter(Tenant.slug == slug).first() is not None:
        slug, i = f"{base}-{i}", i + 1
    return slug


def has_real_org(db: Session) -> bool:
    """Demo disi (gercek) aktif bir kurum var mi? Kurulum ekranini bunun tersinde gosteririz."""
    return _gercek_kurum_sorgusu(db).first() is not None


def primary_tenant(db: Session) -> Tenant | None:
    """Girisin varsayilan hedefi: varsa ilk gercek kurum, yoksa demo (on-prem tek kurum)."""
    real = _gercek_kurum_sorgusu(db).order_by(Tenant.id).first()
    return real or db.query(Tenant).filter(Tenant.slug == DEMO_SLUG).first()


def create_organization(
    db: Session, org_name: str, admin_name: str, admin_email: str, password: str
) -> tuple[Tenant, User]:
    """Yeni kurum + ilk admin + makul baslangic rubrigi. On-prem ilk kurulum."""
    org_name = (org_name or "").strip()
    admin_email = (admin_email or "").lower().strip()
    admin_name = (admin_name or "").strip()
    if not org_name or not admin_email or not admin_name:
        raise OnboardingError("Kurum adi, yonetici adi ve e-posta zorunlu")
    if "@" not in admin_email:
        raise OnboardingError("Gecerli bir e-posta girin")
    if len(password) < 8:
        raise OnboardingError("Parola en az 8 karakter olmali")

    tenant = Tenant(
        name=org_name, slug=unique_slug(db, org_name),
        retention_days=365, processing_paused=False, is_active=True,
    )
    db.add(tenant)
    db.flush()

    admin = User(
        tenant_id=tenant.id, email=admin_email, name=admin_name,
        password_hash=hash_password(password), role=Role.admin,
        is_active=True, password_set=True,
    )
    db.add(admin)

    # Baslangic rubrigi + yasakli kelime + rozet (kalite puanlamasi hazir gelsin)
    for item in DEFAULT_CRITERIA:
        db.add(Criterion(tenant_id=tenant.id, **item))
    for bw in DEFAULT_BANNED_WORDS:
        db.add(BannedWord(tenant_id=tenant.id, **bw))
    for b in DEFAULT_BADGES:
        db.add(Badge(tenant_id=tenant.id, **b))

    db.commit()
    db.refresh(tenant)
    db.refresh(admin)
    return tenant, admin


def issue_token(db: Session, user: User, purpose: str, hours: int = 72) -> str:
    """Davet ('invite') veya parola sifirlama ('reset') icin tek kullanimlik token."""
    token = secrets.token_urlsafe(32)
    db.add(AuthToken(
        tenant_id=user.tenant_id, user_id=user.id, token=token, purpose=purpose,
        expires_at=datetime.utcnow() + timedelta(hours=hours),
    ))
    db.commit()
    return token


def consume_token(db: Session, token: str, purpose: str) -> tuple[User, AuthToken]:
    """Token'i dogrula ve kullanildi olarak isaretle (cagiran parolayi ayarlayip commit eder)."""
    row = (
        db.query(AuthToken)
        .filter(AuthToken.token == token, AuthToken.purpose == purpose)
        .first()
    )
    if row is None or row.used_at is not None or row.expires_at < datetime.utcnow():
        raise OnboardingError("Bağlantı geçersiz veya süresi dolmuş")
    user = db.get(User, row.user_id)
    if user is None or not user.is_active:
        raise OnboardingError("Kullanıcı bulunamadı veya pasif")
    row.used_at = datetime.utcnow()
    return user, row


def link_for(token: str, purpose: str) -> str:
    path = "accept-invite" if purpose == "invite" else "reset-password"
    return f"{settings.frontend_url.rstrip('/')}/{path}?token={token}"


def send_auth_email(to_email: str, subject: str, body: str) -> bool:
    """SMTP yapilandirilmissa e-posta gonderir; degilse False (link panelde gosterilir)."""
    if not settings.smtp_host:
        return False
    try:
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = settings.smtp_from
        msg["To"] = to_email
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as s:
            if settings.smtp_use_tls:
                s.starttls()
            if settings.smtp_user:
                s.login(settings.smtp_user, settings.smtp_password)
            s.sendmail(settings.smtp_from, [to_email], msg.as_string())
        return True
    except Exception:
        return False
