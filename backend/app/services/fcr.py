"""FCR (First Call Resolution — ilk temasta cozum) tespiti.

Iki mod:

1. GERCEK FCR (customer_ref verilmisse): Ayni musteri, belirlenen pencere icinde
   (FCR_WINDOW_DAYS, tipik 7 gun) TEKRAR aradiysa ilk temas cozum saglamamistir.
   Sektor standardi olcum budur; "cagri iyi gecti" hissine degil, musterinin
   geri donup donmedigine bakar.

2. TAHMINI FCR (customer_ref yoksa): kriz olmayan + puani esigin ustundeki
   cagrilar cozulmus varsayilir. Yaklasiktir; entegrasyon yapilana kadar gecerli.

customer_ref kaynagi: CRM ID, musteri numarasi veya telefon numarasinin hash'i
olabilir. Ham telefon numarasi KVKK acisindan saklanmamalidir — cagiran sistem
hash'leyip gondermelidir.
"""

import logging
from datetime import timedelta

from sqlalchemy.orm import Session

from ..models import Call, CallStatus

logger = logging.getLogger(__name__)

# Bu pencere icinde ayni musteri tekrar aradiysa ilk cagri "cozulmemis" sayilir
FCR_WINDOW_DAYS = 7


def detect_repeat(db: Session, call: Call) -> Call | None:
    """Bu cagri, ayni musterinin yakin zamandaki bir cagrisinin tekrari mi?

    Doner: tekrarlandigi onceki cagri (varsa), yoksa None.
    Yan etki YOK — cagirani karar verir.
    """
    if not call.customer_ref:
        return None
    since = call.created_at - timedelta(days=FCR_WINDOW_DAYS)
    return (
        db.query(Call)
        .filter(
            Call.tenant_id == call.tenant_id,
            Call.customer_ref == call.customer_ref,
            Call.id != call.id,
            Call.created_at < call.created_at,
            Call.created_at >= since,
        )
        .order_by(Call.created_at.desc())
        .first()
    )


def apply_repeat_flags(db: Session, call: Call) -> None:
    """Cagriyi tekrar olarak isaretle ve ONCEKI cagriyi 'cozum saglamadi' yap."""
    previous = detect_repeat(db, call)
    if previous is None:
        return
    call.is_repeat = True
    call.repeat_of_id = previous.id
    logger.info(
        "Tekrar arama: cagri %s, %s numarali cagrinin tekrari (musteri=%s)",
        call.id, previous.id, call.customer_ref,
    )


def compute_fcr(db: Session, tenant_id: int, team_id: int | None = None) -> tuple[float | None, bool]:
    """Ekip/sirket FCR'ini hesapla.

    Doner: (yuzde, gercek_mi). gercek_mi=False ise tahmini moddadir.
    """
    from ..models import Agent

    base = db.query(Call).filter(
        Call.tenant_id == tenant_id, Call.status == CallStatus.done
    )
    if team_id:
        base = base.join(Agent, Call.agent_id == Agent.id).filter(Agent.team_id == team_id)

    # customer_ref'i olan cagri varsa GERCEK FCR hesaplanabilir
    identified = base.filter(Call.customer_ref.isnot(None))
    total_identified = identified.count()
    if total_identified >= 10:  # anlamli olcum icin asgari hacim
        # Tekrarlanan (yani cozulememiş) cagri sayisi
        repeated = identified.filter(Call.is_repeat.is_(True)).count()
        resolved = total_identified - repeated
        return round(resolved / total_identified * 100, 1), True

    total = base.count()
    if not total:
        return None, False
    good = base.filter(Call.is_crisis.is_(False), Call.total_score >= 70).count()
    return round(good / total * 100, 1), False
