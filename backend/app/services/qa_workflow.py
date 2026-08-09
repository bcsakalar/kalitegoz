"""FAZ 3 — İki aşamalı kalite kontrol: durum makinesi + insan kuyruğu kuralları.

    AŞAMA 1 — YAPAY ZEKÂ PUANLAR   → %100 çağrı, kanıtlı, tekrarlanabilir
    AŞAMA 2 — KALİTECİ DOĞRULAR    → risk bazlı kuyruk, onayla / düzelt / itiraz

Bu modül ikisinin arasındaki kapıdır: hangi çağrının insana gideceğine karar
verir ve puanın ne zaman "kesinleştiğini" tanımlar.

**Kesinleşmemiş puan liderlik tablosuna ve karneye ham puan olarak girmez.**
Bu, ürünün dürüstlük iddiasının teknik karşılığıdır: onaylanmamış bir AI puanı
temsilcinin performans kaydına işlenmez.
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from ..models import Agent, AuditLog, Call, QAState, ReviewReason, Score

logger = logging.getLogger(__name__)

# --- Yapılandırılabilir varsayılanlar (tenant.settings["qa"] ile ezilir) ---
DEFAULTS = {
    "confidence_threshold": 0.70,   # 3. kural
    "low_score_percentile": 10,     # 4. kural — alt %10 dilim
    "random_sample_rate": 0.05,     # 6. kural — kör kontrol grubu
    "new_agent_days": 30,           # 7. kural
    "new_agent_sample_rate": 0.20,
}


def settings_for(tenant) -> dict:
    cfg = dict(DEFAULTS)
    if tenant is not None and isinstance(tenant.settings, dict):
        cfg.update(tenant.settings.get("qa") or {})
    return cfg


@dataclass
class QueueDecision:
    """Çağrı insan kuyruğuna girmeli mi, hangi kural(lar) yüzünden?"""

    should_queue: bool
    reasons: list[str] = field(default_factory=list)

    @property
    def primary(self) -> ReviewReason:
        """En yüksek öncelikli sebep — atama kaydında bu görünür."""
        order = [
            ReviewReason.critical, ReviewReason.crisis, ReviewReason.low_confidence,
            ReviewReason.emotion_mismatch, ReviewReason.low_score,
            ReviewReason.new_agent, ReviewReason.random,
        ]
        for r in order:
            if r.value in self.reasons:
                return r
        return ReviewReason.manual


def _low_score_cutoff(db: Session, tenant_id: int, percentile: int) -> float | None:
    """Kesinleşmiş çağrıların alt yüzdelik dilim sınırı.

    Yeterli geçmiş yoksa (n < 20) None döner — kural uygulanmaz. Az veriyle
    yüzdelik hesaplamak, ilk günlerde her çağrıyı kuyruğa atardı.
    """
    rows = (
        db.query(Call.total_score)
        .filter(
            Call.tenant_id == tenant_id,
            Call.total_score.isnot(None),
            Call.qa_state == QAState.final,
        )
        .all()
    )
    scores = sorted(r[0] for r in rows if r[0] is not None)
    if len(scores) < 20:
        return None
    idx = max(0, int(len(scores) * percentile / 100) - 1)
    return scores[idx]


def evaluate_queue_rules(
    db: Session,
    call: Call,
    *,
    tenant=None,
    rng: random.Random | None = None,
) -> QueueDecision:
    """FAZ 3.2'deki yedi kuralı uygula.

    Kurallar BİRİKİMLİDİR: birden fazlası tetiklenebilir, hepsi kaydedilir.
    Sebebi kaydetmek önemli — "neden inceliyorum?" sorusu kaliteci ekranının
    ilk satırıdır.
    """
    cfg = settings_for(tenant)
    rng = rng or random
    reasons: list[str] = []

    # 1. Sıfırlayıcı ihlal → HER ZAMAN insan onayı
    if call.zeroed:
        reasons.append(ReviewReason.critical.value)

    # 2. Kriz sinyali → HER ZAMAN
    if call.is_crisis:
        reasons.append(ReviewReason.crisis.value)

    # 3. Düşük güven veya yetersiz kanıt
    scores = db.query(Score).filter(Score.call_id == call.id).all()
    threshold = float(cfg["confidence_threshold"])
    if any(
        s.decision == "insufficient_evidence" or (s.confidence or 1.0) < threshold
        for s in scores
    ):
        reasons.append(ReviewReason.low_confidence.value)

    # 4. Toplam puan alt %10 diliminde
    if call.total_score is not None:
        cutoff = _low_score_cutoff(db, call.tenant_id, int(cfg["low_score_percentile"]))
        if cutoff is not None and call.total_score <= cutoff:
            reasons.append(ReviewReason.low_score.value)

    # 5. Duygu ↔ puan uyumsuzluğu (müşteri öfkeli ama puan yüksek)
    if call.emotion_mismatch:
        reasons.append(ReviewReason.emotion_mismatch.value)

    # 6 + 7. Örneklem — TEK çekiliş, iki oran.
    #
    # Yeni temsilci kuralı örneklem oranını YÜKSELTİR, asla düşürmez. (İlk
    # uygulamada yeni temsilci oranı kiracının yapılandırdığı oranın yerine
    # geçiyordu; kiracı %50 ayarlasa bile yeni temsilci %20'ye düşüyordu.)
    #
    # Tek çekiliş yapılır: aynı çağrı hem "rastgele" hem "yeni temsilci" diye
    # iki kez örneklenmez. Etiket, hangi kuralın oranı belirlediğini gösterir.
    random_rate = float(cfg["random_sample_rate"])
    agent = db.get(Agent, call.agent_id) if call.agent_id else None
    yeni_temsilci = False
    if agent is not None and agent.created_at:
        yeni_sinir = datetime.utcnow() - timedelta(days=int(cfg["new_agent_days"]))
        yeni_temsilci = agent.created_at >= yeni_sinir

    sample_rate = max(random_rate, float(cfg["new_agent_sample_rate"])) if yeni_temsilci \
        else random_rate

    # Zaten bir risk kuralı tetiklendiyse örnekleme gerek yok — çağrı kuyrukta.
    if not reasons and sample_rate > 0 and rng.random() < sample_rate:
        reasons.append(
            ReviewReason.new_agent.value if yeni_temsilci else ReviewReason.random.value
        )

    return QueueDecision(should_queue=bool(reasons), reasons=reasons)


# ---------------------------------------------------------------------------
# Durum makinesi
# ---------------------------------------------------------------------------

# Hangi geçiş hangi durumdan yapılabilir? İzin verilmeyen geçiş hatadır —
# durum makinesi "yazılı ama uygulanmayan" bir şema olmamalı.
ALLOWED: dict[QAState, set[QAState]] = {
    QAState.ai_scored: {QAState.human_queue, QAState.final},
    QAState.human_queue: {QAState.final, QAState.appeal_review},
    QAState.appeal_review: {QAState.final},
    QAState.final: {QAState.appeal_review},  # temsilci itirazı kesinleşmişi açabilir
}


class InvalidTransition(RuntimeError):
    pass


def transition(
    db: Session,
    call: Call,
    to_state: QAState,
    *,
    user_id: int | None = None,
    reason: str = "",
    detail: dict | None = None,
) -> Call:
    """Durumu değiştir ve denetim günlüğüne yaz.

    Her geçiş kaydedilir: kim, ne zaman, hangi gerekçe koduyla. Denetim izi
    olmayan bir durum makinesi kurumsal satışta savunulamaz.
    """
    frm = call.qa_state or QAState.ai_scored
    if to_state != frm and to_state not in ALLOWED.get(frm, set()):
        raise InvalidTransition(f"Gecersiz durum gecisi: {frm.value} -> {to_state.value}")

    call.qa_state = to_state
    if to_state == QAState.final:
        call.finalized_at = datetime.utcnow()
        call.finalized_by = user_id

    db.add(AuditLog(
        tenant_id=call.tenant_id, user_id=user_id,
        action="qa_state_change", entity_type="call", entity_id=call.id,
        detail={"from": frm.value, "to": to_state.value, "reason": reason, **(detail or {})},
    ))
    logger.info("Cagri %s: %s -> %s (%s)", call.id, frm.value, to_state.value, reason)
    return call


def route_after_scoring(
    db: Session, call: Call, *, tenant=None, rng: random.Random | None = None
) -> QueueDecision:
    """Puanlama bittikten sonra çağrıyı yönlendir.

    Risk kuralı tetiklenmediyse puan doğrudan **kesinleşir** — %100 kapsamın
    anlamı budur; her çağrıyı insana yollamak ürünün vaadini bozar.
    """
    decision = evaluate_queue_rules(db, call, tenant=tenant, rng=rng)
    call.queue_reasons = decision.reasons
    call.qa_state = QAState.ai_scored

    if decision.should_queue:
        transition(db, call, QAState.human_queue,
                   reason="risk_kurali", detail={"kurallar": decision.reasons})
    else:
        transition(db, call, QAState.final,
                   reason="risk_kurali_tetiklenmedi")
    return decision


def finalize(db: Session, call: Call, *, user_id: int, note: str = "") -> Call:
    """Kaliteci incelemeyi bitirdi → puan kesinleşti."""
    return transition(db, call, QAState.final, user_id=user_id,
                      reason="kaliteci_onayi", detail={"not": note} if note else None)


def open_appeal(db: Session, call: Call, *, user_id: int, reason: str) -> Call:
    """Temsilci itirazı — kesinleşmiş puanı bile yeniden açabilir."""
    return transition(db, call, QAState.appeal_review, user_id=user_id,
                      reason="temsilci_itirazi", detail={"gerekce": reason[:500]})
