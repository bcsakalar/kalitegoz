"""FastAPI bagimliliklari: kimlik dogrulama, tenant scoping, RBAC.

Her korumali endpoint `current_user` alir. Kullanici daima kendi tenant'ina
baglidir; servis katmani sorgularini tenant_id ile filtreler (tenant izolasyonu).
"""

from dataclasses import dataclass

import jwt
from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from .db import get_db
from .models import Role, User
from .security import decode_token


@dataclass
class CurrentUser:
    id: int
    tenant_id: int
    role: Role
    name: str
    email: str
    team_id: int | None
    agent_id: int | None


def _extract_token(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Kimlik dogrulama gerekli (Bearer token yok)")
    return authorization.split(" ", 1)[1].strip()


def get_current_user(
    request: Request,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> CurrentUser:
    token = _extract_token(authorization)
    try:
        payload = decode_token(token, "access")
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Oturum suresi doldu, tekrar giris yapin")
    except jwt.PyJWTError:
        raise HTTPException(401, "Gecersiz token")

    user = db.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(401, "Kullanici bulunamadi veya pasif")
    # Token icindeki tenant ile kullanicinin tenant'i tutmali (kacak onleme)
    if user.tenant_id != payload.get("tenant_id"):
        raise HTTPException(401, "Token tenant uyumsuz")

    cu = CurrentUser(
        id=user.id,
        tenant_id=user.tenant_id,
        role=user.role,
        name=user.name,
        email=user.email,
        team_id=user.team_id,
        agent_id=user.agent_id,
    )
    request.state.current_user = cu
    return cu


def require_roles(*roles: Role):
    """Belirli rolleri zorunlu kilan bagimlilik uretir."""

    allowed = set(roles)

    def _dep(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if user.role not in allowed:
            raise HTTPException(403, "Bu islem icin yetkiniz yok")
        return user

    return _dep


# Kisayollar
def require_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if user.role != Role.admin:
        raise HTTPException(403, "Yalnizca admin")
    return user


def require_staff(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """Admin / supervisor / quality — temsilci olmayan personel."""
    if user.role == Role.agent:
        raise HTTPException(403, "Bu islem icin personel yetkisi gerekli")
    return user
