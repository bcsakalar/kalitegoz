"""FAZ 3.4 — Kalibrasyon geri besleme döngüsü.

Her kaliteci düzeltmesi `calibration_examples` tablosuna yazılır. Bir kriterde
yeterli örnek birikince o kriterin **Katman B prompt'una few-shot örnek olarak
enjekte edilir**.

## Neden bu mekanizma?

FAZ 2 ölçümü kappa açığının tamamen dört öznel kriterde toplandığını ve
**hepsinin aynı yönde** olduğunu gösterdi (model uzmandan cömert):

    Aktif Dinleme        sapma +0.86   kappa 0.064
    Ihtiyac Analizi      sapma +0.73   kappa 0.081
    Cozum / Yonlendirme  sapma +0.73   kappa 0.184
    Bilgi Dogrulugu      sapma +0.21   kappa 0.237

Sabit bir kaydırma (calibration_scale) ölçeği hizalar ama modele **neyin neden
yanlış olduğunu** öğretmez. Few-shot örnek onu öğretir: "bu transkriptte bu
kriter 4 aldı, çünkü…".

## Ne YAPILMAZ

- Rubrik değiştirilmez. Kriter tanımı sabit kalır, yalnızca örnek eklenir.
- Geçmiş puanlar geriye dönük değiştirilmez.
- Her kalibrasyon etkisi sürümlenir (`prompt_version`) ve raporlanır.
"""

from __future__ import annotations

import hashlib
import logging

from sqlalchemy.orm import Session

from ..models import CalibrationExample, Criterion, Score

logger = logging.getLogger(__name__)

# Bir kriterde bu kadar örnek birikmeden prompt'a enjeksiyon YAPILMAZ.
# Tek bir düzeltmeden genelleme yapmak, kalibrasyonu gürültüye bağlar.
MIN_EXAMPLES = 3
# Prompt'a en fazla bu kadar örnek girer (token bütçesi + dikkat dağılması).
MAX_EXAMPLES = 4
# Transkript parçası bu uzunlukta kırpılır.
EXCERPT_CHARS = 600


def record_correction(
    db: Session,
    *,
    tenant_id: int,
    criterion_id: int,
    call_id: int | None,
    excerpt: str,
    ai_score: int | None,
    human_score: int,
    reason_code: str,
    note: str = "",
    user_id: int | None = None,
) -> CalibrationExample:
    """Bir düzeltmeyi kalibrasyon örneği olarak kaydet."""
    ex = CalibrationExample(
        tenant_id=tenant_id, criterion_id=criterion_id, call_id=call_id,
        excerpt=(excerpt or "")[:EXCERPT_CHARS], ai_score=ai_score,
        human_score=human_score, reason_code=reason_code, note=(note or "")[:500],
        created_by=user_id,
    )
    db.add(ex)
    return ex


def examples_for(db: Session, tenant_id: int, criterion_id: int) -> list[CalibrationExample]:
    """Bir kriterin prompt'una girecek örnekler.

    En yeni örnekler seçilir: rubrik yorumu zamanla oturur, eski düzeltmeler
    güncel anlayışı yansıtmayabilir.
    """
    rows = (
        db.query(CalibrationExample)
        .filter(
            CalibrationExample.tenant_id == tenant_id,
            CalibrationExample.criterion_id == criterion_id,
            CalibrationExample.is_active.is_(True),
        )
        .order_by(CalibrationExample.created_at.desc())
        .limit(MAX_EXAMPLES)
        .all()
    )
    return rows if len(rows) >= MIN_EXAMPLES else []


def build_block(db: Session, tenant_id: int, criteria: list[Criterion]) -> str:
    """Kriter grubu için few-shot bloğu üret. Örnek yoksa boş string döner."""
    parts: list[str] = []
    for c in criteria:
        rows = examples_for(db, tenant_id, c.id)
        if not rows:
            continue
        lines = [f"### '{c.name}' kriterinde kalite uzmaninin verdigi kararlar:"]
        for r in rows:
            ai = "yok" if r.ai_score is None else str(r.ai_score)
            lines.append(
                f'- Transkript: "{r.excerpt.strip()}"\n'
                f"  AI puani: {ai} -> UZMAN puani: {r.human_score}"
                + (f" ({r.note.strip()})" if r.note.strip() else "")
            )
        parts.append("\n".join(lines))

    if not parts:
        return ""
    return (
        "\n## KALITE UZMANININ ONCEKI KARARLARI (bunlara uy)\n"
        "Asagida, ayni rubrikte kalite uzmaninin GERCEK cagrilarda verdigi puanlar\n"
        "var. Benzer durumlarda UZMANIN olcegini kullan; kendi olcegini degil.\n\n"
        + "\n\n".join(parts)
        + "\n"
    )


def calibration_version(db: Session, tenant_id: int) -> str:
    """Aktif örnek kümesinin sürümü.

    Puanlama kaydına yazılır; "bu puan hangi kalibrasyonla üretildi?" sorusu
    sonradan cevaplanabilsin diye. Örnek kümesi değişince sürüm de değişir.
    """
    rows = (
        db.query(CalibrationExample.id)
        .filter(
            CalibrationExample.tenant_id == tenant_id,
            CalibrationExample.is_active.is_(True),
        )
        .order_by(CalibrationExample.id)
        .all()
    )
    if not rows:
        return "cal-0"
    digest = hashlib.sha1(",".join(str(r[0]) for r in rows).encode()).hexdigest()[:8]
    return f"cal-{len(rows)}-{digest}"


# ---------------------------------------------------------------------------
# Overturn (düzeltilen puan oranı) — rubrik muğlaklığının göstergesi
# ---------------------------------------------------------------------------

def overturn_stats(db: Session, tenant_id: int, criterion_id: int | None = None) -> dict:
    """Düzeltilen kriter / incelenen kriter.

    Yükseliyorsa sorun kalitecide değil RUBRİKTE'dir: kriter tanımı muğlak
    demektir. Bu yüzden eşiği aşan kriter için süpervizöre görev açılır.
    """
    q = (
        db.query(Score)
        .join(Score.call)
        .filter(Score.reviewed_at.isnot(None))
    )
    if criterion_id is not None:
        q = q.filter(Score.criterion_id == criterion_id)
    rows = q.all()
    incelenen = len(rows)
    duzeltilen = sum(1 for s in rows if s.override_score is not None)
    by_reason: dict[str, int] = {}
    for s in rows:
        if s.override_score is not None:
            code = s.override_reason_code or "diger"
            by_reason[code] = by_reason.get(code, 0) + 1
    return {
        "incelenen": incelenen,
        "duzeltilen": duzeltilen,
        "overturn_orani": round(duzeltilen / incelenen, 4) if incelenen else 0.0,
        "gerekce_dagilimi": by_reason,
    }
