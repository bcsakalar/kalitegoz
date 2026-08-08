"""Append-only denetim gunlugu yardimcisi."""

from sqlalchemy.orm import Session

from ..models import AuditLog


def log(
    db: Session,
    *,
    action: str,
    tenant_id: int | None = None,
    user_id: int | None = None,
    entity_type: str = "",
    entity_id: int | None = None,
    detail: dict | None = None,
    ip: str = "",
    commit: bool = True,
) -> None:
    """Denetim kaydi ekler. Tablo append-only'dir (guncelleme/silme yapilmaz)."""
    db.add(
        AuditLog(
            tenant_id=tenant_id,
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            detail=detail,
            ip=ip,
        )
    )
    if commit:
        db.commit()
