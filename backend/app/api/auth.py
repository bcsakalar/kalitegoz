"""Kimlik dogrulama: parola girisi, demo (rol secimli) giris, token yenileme, SSO (OIDC)."""

import secrets
from datetime import timedelta, datetime, timezone
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..deps import CurrentUser, get_current_user
from ..models import AuthToken, Role, Tenant, User
from ..schemas import (
    AcceptInviteRequest, AuthConfigOut, BrandingOut, ChangePasswordRequest,
    DemoLoginRequest, ForgotPasswordRequest, InviteInfoOut, LoginRequest, MeOut,
    RefreshRequest, RegisterOrgRequest, ResetPasswordRequest, ResetResultOut, TokenPair,
)
from ..security import create_access_token, create_refresh_token, decode_token, hash_password, verify_password
from ..services import audit, onboarding

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _tokens(user: User) -> TokenPair:
    return TokenPair(
        access_token=create_access_token(user.id, user.tenant_id, user.role.value),
        refresh_token=create_refresh_token(user.id, user.tenant_id),
    )


def _tenant(db: Session, slug: str) -> Tenant:
    tenant = db.query(Tenant).filter(Tenant.slug == slug, Tenant.is_active.is_(True)).first()
    if tenant is None:
        raise HTTPException(404, f"Tenant bulunamadi: {slug}")
    return tenant


@router.post("/login", response_model=TokenPair)
def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)):
    tenant = _tenant(db, body.tenant_slug)
    user = (
        db.query(User)
        .filter(User.tenant_id == tenant.id, User.email == body.email.lower().strip())
        .first()
    )
    if user is None or not user.is_active or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "E-posta veya parola hatali")
    if not user.password_set:
        raise HTTPException(403, "Davet henüz kabul edilmedi — davet bağlantısından parolanızı belirleyin")
    audit.log(db, action="login", tenant_id=tenant.id, user_id=user.id,
              ip=request.client.host if request.client else "")
    return _tokens(user)


@router.post("/demo-login", response_model=TokenPair)
def demo_login(body: DemoLoginRequest, db: Session = Depends(get_db)):
    """Demo modu: landing'den rol secip tek tikla giris (parolasiz).

    Her rol icin o roldeki ilk aktif kullaniciyla oturum acilir. Yalnizca
    DEMO_MODE=true iken calisir.
    """
    if not settings.demo_mode:
        raise HTTPException(403, "Demo giris kapali")
    try:
        role = Role(body.role)
    except ValueError:
        raise HTTPException(400, f"Gecersiz rol: {body.role}")
    tenant = _tenant(db, body.tenant_slug)
    user = (
        db.query(User)
        .filter(User.tenant_id == tenant.id, User.role == role, User.is_active.is_(True))
        .order_by(User.id)
        .first()
    )
    if user is None:
        raise HTTPException(404, f"{body.role} rolunde demo kullanici yok")
    return _tokens(user)


@router.post("/refresh", response_model=TokenPair)
def refresh(body: RefreshRequest, db: Session = Depends(get_db)):
    try:
        payload = decode_token(body.refresh_token, "refresh")
    except jwt.PyJWTError:
        raise HTTPException(401, "Gecersiz veya suresi dolmus refresh token")
    user = db.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(401, "Kullanici bulunamadi")
    return _tokens(user)


@router.get("/me", response_model=MeOut)
def me(user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    tenant = db.get(Tenant, user.tenant_id)
    return MeOut(
        id=user.id, email=user.email, name=user.name, role=user.role.value,
        tenant_id=user.tenant_id, tenant_name=tenant.name if tenant else "",
        team_id=user.team_id, agent_id=user.agent_id,
    )


# =====================================================================
# Beyaz etiket (public) — giris ekrani markayi auth OLMADAN cekebilsin
# =====================================================================
@router.get("/config", response_model=AuthConfigOut)
def public_auth_config(db: Session = Depends(get_db)):
    """Giris/kurulum ekrani icin auth'suz yapilandirma.

    needs_setup=True ise (henuz gercek kurum yok) frontend 'Kurumunuzu olusturun'
    ekranini gosterir. org_slug girisin varsayilan hedefidir (on-prem tek kurum).
    """
    pt = onboarding.primary_tenant(db)
    return AuthConfigOut(
        sso_enabled=settings.sso_enabled,
        demo_mode=settings.demo_mode,
        needs_setup=not onboarding.has_real_org(db),
        org_slug=pt.slug if pt else None,
        org_name=pt.name if pt else None,
    )


@router.get("/branding", response_model=BrandingOut)
def public_branding(tenant: str = "demo", db: Session = Depends(get_db)):
    t = db.query(Tenant).filter(Tenant.slug == tenant).first()
    if t is None:
        return BrandingOut(brand_name=settings.brand_name, brand_color=settings.brand_color)
    return BrandingOut(
        brand_name=t.brand_name or settings.brand_name,
        brand_color=t.brand_color or settings.brand_color,
        logo_data_url=t.logo_data_url,
    )


# =====================================================================
# Kurumsal onboarding: kurum olusturma + davet/parola akislari
# =====================================================================
@router.post("/register-org", response_model=TokenPair, status_code=201)
def register_org(body: RegisterOrgRequest, request: Request, db: Session = Depends(get_db)):
    """Ilk kurulum: sirket kendi kurumunu + ilk admin'ini olusturur.

    Guvenlik: yalnizca HENUZ gercek (demo disi) kurum yokken calisir. Kurum
    kurulduktan sonra bu uc kapanir; yeni kullanicilar admin DAVETI ile eklenir.
    """
    if onboarding.has_real_org(db):
        raise HTTPException(403, "Kurum zaten kurulu. Yeni kullanicilar davet ile eklenir.")
    try:
        tenant, admin = onboarding.create_organization(
            db, body.org_name, body.admin_name, body.admin_email, body.password)
    except onboarding.OnboardingError as exc:
        raise HTTPException(400, str(exc))
    audit.log(db, action="register_org", tenant_id=tenant.id, user_id=admin.id,
              ip=request.client.host if request.client else "", detail={"org": tenant.name})
    return _tokens(admin)


@router.get("/invite/{token}", response_model=InviteInfoOut)
def invite_info(token: str, db: Session = Depends(get_db)):
    """Davet linki bilgisi — parola belirleme ekrani icin (auth'suz)."""
    from datetime import datetime as _dt
    row = db.query(AuthToken).filter(
        AuthToken.token == token, AuthToken.purpose == "invite").first()
    if row is None or row.used_at is not None or row.expires_at < _dt.utcnow():
        return InviteInfoOut(valid=False)
    user = db.get(User, row.user_id)
    tenant = db.get(Tenant, row.tenant_id)
    if user is None:
        return InviteInfoOut(valid=False)
    return InviteInfoOut(valid=True, email=user.email, name=user.name,
                         org_name=tenant.name if tenant else "")


@router.post("/accept-invite", response_model=TokenPair)
def accept_invite(body: AcceptInviteRequest, db: Session = Depends(get_db)):
    """Davetli kullanici parolasini belirler, hesabini aktive eder ve oturum acar."""
    try:
        user, _row = onboarding.consume_token(db, body.token, "invite")
    except onboarding.OnboardingError as exc:
        raise HTTPException(400, str(exc))
    user.password_hash = hash_password(body.password)
    user.password_set = True
    user.is_active = True
    db.commit()
    audit.log(db, action="accept_invite", tenant_id=user.tenant_id, user_id=user.id)
    return _tokens(user)


@router.post("/forgot-password", response_model=ResetResultOut)
def forgot_password(body: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """Self-servis parola sifirlama. Guvenlik: e-posta kayitli olsun olmasin AYNI
    mesaj doner (varlik sizmasin) ve link yanitta DONMEZ; SMTP ile gonderilir."""
    email = body.email.lower().strip()
    q = db.query(User).filter(User.email == email, User.is_active.is_(True))
    if body.org_slug:
        t = db.query(Tenant).filter(Tenant.slug == body.org_slug).first()
        if t is not None:
            q = q.filter(User.tenant_id == t.id)
    user = q.first()
    if user and user.password_set:
        token = onboarding.issue_token(db, user, "reset", hours=2)
        url = onboarding.link_for(token, "reset")
        onboarding.send_auth_email(
            user.email, "KaliteGoz parola sifirlama",
            f"Parolanizi sifirlamak icin baglantiya tiklayin:\n{url}\n\nBaglanti 2 saat gecerlidir.")
    return ResetResultOut(message="Eğer bu e-posta kayıtlıysa, sıfırlama bağlantısı gönderildi.")


@router.post("/reset-password", response_model=TokenPair)
def reset_password(body: ResetPasswordRequest, db: Session = Depends(get_db)):
    """Sifirlama token'i ile yeni parola belirle ve oturum ac."""
    try:
        user, _row = onboarding.consume_token(db, body.token, "reset")
    except onboarding.OnboardingError as exc:
        raise HTTPException(400, str(exc))
    user.password_hash = hash_password(body.password)
    user.password_set = True
    db.commit()
    audit.log(db, action="reset_password", tenant_id=user.tenant_id, user_id=user.id)
    return _tokens(user)


@router.post("/change-password")
def change_password(body: ChangePasswordRequest,
                    user: CurrentUser = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    """Oturum acmis kullanicinin parola degistirmesi."""
    u = db.get(User, user.id)
    if u is None or not verify_password(body.old_password, u.password_hash):
        raise HTTPException(400, "Mevcut parola hatalı")
    u.password_hash = hash_password(body.new_password)
    u.password_set = True
    db.commit()
    audit.log(db, action="change_password", tenant_id=u.tenant_id, user_id=u.id)
    return {"ok": True}


# =====================================================================
# SSO / OIDC (kurumsal tek oturum acma) — Okta / Entra / Keycloak / Google
# =====================================================================
_OIDC_CACHE: dict = {}


def _oidc_config() -> dict:
    """OIDC discovery dokumanini cek (process ici cache'lenir)."""
    if not settings.sso_enabled or not settings.oidc_issuer:
        raise HTTPException(404, "SSO yapilandirilmamis")
    if "config" not in _OIDC_CACHE:
        url = settings.oidc_issuer.rstrip("/") + "/.well-known/openid-configuration"
        try:
            resp = httpx.get(url, timeout=10)
            resp.raise_for_status()
            _OIDC_CACHE["config"] = resp.json()
        except httpx.HTTPError as exc:
            raise HTTPException(502, f"OIDC saglayiciya ulasilamadi: {exc}")
    return _OIDC_CACHE["config"]


def _sso_state_token() -> str:
    """CSRF korumasi: kisa omurlu imzali state (cookie'siz)."""
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"nonce": secrets.token_urlsafe(16), "type": "sso_state",
         "iat": now, "exp": now + timedelta(minutes=10)},
        settings.jwt_secret, algorithm=settings.jwt_algorithm,
    )


@router.get("/sso/login")
def sso_login():
    """Kullaniciyi OIDC saglayicinin giris sayfasina yonlendirir."""
    cfg = _oidc_config()
    state = _sso_state_token()
    params = {
        "response_type": "code",
        "client_id": settings.oidc_client_id,
        "redirect_uri": settings.oidc_redirect_uri,
        "scope": "openid email profile",
        "state": state,
    }
    return RedirectResponse(f"{cfg['authorization_endpoint']}?{urlencode(params)}")


@router.get("/sso/callback")
def sso_callback(code: str = "", state: str = "", db: Session = Depends(get_db)):
    """OIDC geri cagrisi: code'u token'a cevir, kullaniciyi bul/olustur, oturum ac."""
    cfg = _oidc_config()
    try:
        decode_token(state, "sso_state")
    except jwt.PyJWTError:
        raise HTTPException(400, "Gecersiz veya suresi dolmus SSO state")
    if not code:
        raise HTTPException(400, "Yetki kodu (code) eksik")

    # 1) code -> token
    try:
        tok = httpx.post(cfg["token_endpoint"], data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": settings.oidc_redirect_uri,
            "client_id": settings.oidc_client_id,
            "client_secret": settings.oidc_client_secret,
        }, timeout=10)
        tok.raise_for_status()
        access = tok.json().get("access_token")
        # 2) userinfo -> email/ad
        ui = httpx.get(cfg["userinfo_endpoint"],
                       headers={"Authorization": f"Bearer {access}"}, timeout=10)
        ui.raise_for_status()
        claims = ui.json()
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"OIDC token/userinfo hatasi: {exc}")

    email = (claims.get("email") or "").lower().strip()
    name = claims.get("name") or claims.get("preferred_username") or email
    if not email:
        raise HTTPException(400, "OIDC saglayici e-posta dondurmedi (email scope gerekli)")

    tenant = db.query(Tenant).filter(Tenant.slug == settings.oidc_default_tenant).first()
    if tenant is None:
        raise HTTPException(500, "Varsayilan SSO tenant bulunamadi")
    user = db.query(User).filter(User.tenant_id == tenant.id, User.email == email).first()
    if user is None:
        # Yeni kullanici en dusuk yetkiyle (guvenli varsayilan) acilir
        try:
            role = Role(settings.oidc_default_role)
        except ValueError:
            role = Role.agent
        user = User(
            tenant_id=tenant.id, email=email, name=name,
            password_hash=hash_password(secrets.token_urlsafe(24)),
            role=role, is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    elif not user.is_active:
        raise HTTPException(403, "Kullanici pasif")

    audit.log(db, action="sso_login", tenant_id=tenant.id, user_id=user.id,
              detail={"email": email})
    pair = _tokens(user)
    # Token'lari frontend'e fragment ile tasi (URL query'de kalmaz, loglanmaz)
    url = (f"{settings.frontend_url}/sso#access_token={pair.access_token}"
           f"&refresh_token={pair.refresh_token}")
    return RedirectResponse(url)
