"""Alarm yasam dongusu.

B31: Bir cagri yeniden puanlandiginda `scores` ve `violations` siliniyordu ama
`alerts` birikiyordu. Eski/hatali bir alarm (orn. eksik transkriptle uretilmis
KVKK ihlali) cagri duzgun yeniden puanlansa bile ekranda ASILI KALIYORDU —
B2'nin en olasi aciklamasi budur.

Alarmlar SILINMEZ, `is_stale` ile gecersizlestirilir: denetim izi ve kalibrasyon
sinyali olarak degerlidir ("bu alarm sonradan gecersiz cikti" bilgisi rubrigin
mugak oldugunu gosterebilir), ama kullaniciya gosterilmez.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from ..models import Alert

logger = logging.getLogger(__name__)


def invalidate_for_call(db: Session, call_id: int) -> int:
    """Cagriya ait tum aktif alarmlari gecersizlestir. Doner: etkilenen satir."""
    n = (
        db.query(Alert)
        .filter(Alert.call_id == call_id, Alert.is_stale.is_(False))
        .update({Alert.is_stale: True}, synchronize_session=False)
    )
    if n:
        logger.info("Cagri %s icin %d alarm gecersizlestirildi (yeniden puanlama).", call_id, n)
    return n


def active_query(db: Session, tenant_id: int):
    """Kullaniciya gosterilecek alarmlar — gecersizlesenler DAHIL DEGIL."""
    return (
        db.query(Alert)
        .filter(Alert.tenant_id == tenant_id, Alert.is_stale.is_(False))
    )
