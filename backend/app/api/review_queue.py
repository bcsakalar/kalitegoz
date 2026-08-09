"""FAZ 3.3/3.5 — Kaliteci inceleme kuyruğu, onay/düzeltme ve itiraz akışı.

Ekranın hedefi: **bir çağrı incelemesi 8-10 dakikadan 2 dakikaya insin.**
Bu, ürünün ROI vaadidir. Backend tarafında bunun karşılığı üç şeydir:

1. **Tek istekte tam bağlam** — `GET /review-queue/next` çağrıyı, transkripti,
   kriter kartlarını, kanıtları ve kuyruğa düşme sebebini birlikte döner.
   Kaliteci sekme değiştirmez, ikinci istek beklemez.
2. **Tek istekte tam karar** — `POST /review-queue/{id}/submit` bütün kriterlerin
   onay/düzeltmesini tek seferde alır. Kriter başına ayrı istek, 10 kriterlik
   bir çağrıda 10 tur demek olurdu.
3. **Otomatik sıradaki** — `submit` yanıtı bir sonraki çağrıyı da döner.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import CurrentUser, require_staff
from ..models import (
    AuditLog,
    Call,
    OverrideReasonCode,
    QAState,
    Score,
    Segment,
)
from ..services import qa_workflow, review_feedback

router = APIRouter(prefix="/api/v1", tags=["inceleme"])


# ---------------------------------------------------------------------------
# Şemalar
# ---------------------------------------------------------------------------

class KriterKarti(BaseModel):
    score_id: int
    criterion_id: int | None
    ad: str
    grup: str
    agirlik: float
    ai_puani: int | None
    karar: str
    guven: float
    gerekce: str
    kanit: str
    kanit_saniye: float | None
    kanit_dogrulandi: bool
    katman: str
    duzeltilmis_puan: int | None
    incelendi: bool


class InceleneCagri(BaseModel):
    call_id: int
    ref: str
    dosya: str
    temsilci: str | None
    toplam_puan: float | None
    sifirlandi: bool
    sifirlama_gerekcesi: str | None
    sifirlama_kaniti: str | None
    qa_durumu: str
    kuyruk_sebepleri: list[str]
    sure_sn: float | None
    ozet: str | None
    kriterler: list[KriterKarti]
    transkript: list[dict]
    kalan_kuyruk: int


class KriterKarari(BaseModel):
    score_id: int
    # None = onayla (AI puanı doğru). Sayı = düzelt.
    yeni_puan: int | None = Field(default=None, ge=0, le=10)
    gerekce_kodu: OverrideReasonCode | None = None
    not_: str = Field(default="", alias="not")

    model_config = {"populate_by_name": True}


class IncelemeGonder(BaseModel):
    kararlar: list[KriterKarari]
    kapanis_notu: str = ""



# ---------------------------------------------------------------------------
# Kuyruk
# ---------------------------------------------------------------------------

def _queue_query(db: Session, tenant_id: int):
    return (
        db.query(Call)
        .filter(Call.tenant_id == tenant_id, Call.qa_state == QAState.human_queue)
        .order_by(
            # Kritik olanlar önce: sıfırlanmış ve kriz çağrıları beklemez.
            Call.zeroed.desc(), Call.is_crisis.desc(), Call.created_at.asc()
        )
    )


def _build_payload(db: Session, call: Call, kalan: int) -> InceleneCagri:
    scores = (
        db.query(Score)
        .filter(Score.call_id == call.id)
        .order_by(Score.weight.desc(), Score.id)
        .all()
    )
    segments = (
        db.query(Segment).filter(Segment.call_id == call.id).order_by(Segment.idx).all()
    )
    return InceleneCagri(
        call_id=call.id,
        ref=f"#{call.id:04d}",
        dosya=call.filename,
        temsilci=call.agent.name if call.agent else None,
        toplam_puan=call.total_score,
        sifirlandi=bool(call.zeroed),
        sifirlama_gerekcesi=call.zeroing_reason,
        sifirlama_kaniti=call.zeroing_evidence,
        qa_durumu=(call.qa_state or QAState.ai_scored).value,
        kuyruk_sebepleri=list(call.queue_reasons or []),
        sure_sn=call.duration_sec,
        ozet=call.summary,
        kriterler=[
            KriterKarti(
                score_id=s.id, criterion_id=s.criterion_id, ad=s.criterion_name,
                grup=s.criterion_group, agirlik=s.weight, ai_puani=s.score,
                karar=s.decision, guven=s.confidence, gerekce=s.rationale,
                kanit=s.evidence, kanit_saniye=s.evidence_ts,
                kanit_dogrulandi=bool(s.evidence_verified), katman=s.source_layer,
                duzeltilmis_puan=s.override_score, incelendi=s.reviewed_at is not None,
            )
            for s in scores
        ],
        transkript=[
            {"idx": g.idx, "konusmaci": g.speaker, "saniye": g.start_sec, "metin": g.text}
            for g in segments
        ],
        kalan_kuyruk=kalan,
    )


@router.get("/review-queue/next", response_model=InceleneCagri | None)
def next_in_queue(db: Session = Depends(get_db),
                  user: CurrentUser = Depends(require_staff)):
    """Kuyruktaki bir sonraki çağrıyı TAM bağlamıyla getir."""
    q = _queue_query(db, user.tenant_id)
    call = q.first()
    if call is None:
        return None
    return _build_payload(db, call, kalan=q.count())


@router.get("/review-queue/stats")
def queue_stats(db: Session = Depends(get_db),
                user: CurrentUser = Depends(require_staff)):
    """Kuyruk durumu + bugünkü inceleme hızı (ROI ölçümü)."""
    bugun = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    bekleyen = _queue_query(db, user.tenant_id).count()
    bugun_biten = (
        db.query(func.count(Call.id))
        .filter(
            Call.tenant_id == user.tenant_id,
            Call.qa_state == QAState.final,
            Call.finalized_at >= bugun,
        )
        .scalar()
    ) or 0

    # Ortalama inceleme süresi: kuyruğa düşme -> kesinleşme
    sureler = (
        db.query(Call.created_at, Call.finalized_at)
        .filter(
            Call.tenant_id == user.tenant_id,
            Call.qa_state == QAState.final,
            Call.finalized_at.isnot(None),
            Call.finalized_at >= bugun,
        )
        .all()
    )
    return {
        "bekleyen": bekleyen,
        "bugun_tamamlanan": bugun_biten,
        "sebep_dagilimi": _reason_breakdown(db, user.tenant_id),
        "olculen_inceleme_sayisi": len(sureler),
    }


def _reason_breakdown(db: Session, tenant_id: int) -> dict[str, int]:
    out: dict[str, int] = {}
    for (reasons,) in db.query(Call.queue_reasons).filter(
        Call.tenant_id == tenant_id, Call.qa_state == QAState.human_queue
    ):
        for r in reasons or []:
            out[r] = out.get(r, 0) + 1
    return out


# ---------------------------------------------------------------------------
# İnceleme gönderimi
# ---------------------------------------------------------------------------

@router.post("/review-queue/{call_id}/submit", response_model=InceleneCagri | None)
def submit_review(call_id: int, body: IncelemeGonder,
                  db: Session = Depends(get_db),
                  user: CurrentUser = Depends(require_staff)):
    """Tüm kriter kararlarını tek seferde al, çağrıyı kesinleştir, sıradakini dön.

    Düzeltilen her kriter `calibration_examples`'a yazılır ve o kriterin
    prompt'una few-shot örnek olarak döner (FAZ 3.4 geri besleme döngüsü).
    """
    call = db.get(Call, call_id)
    if call is None or call.tenant_id != user.tenant_id:
        raise HTTPException(404, "Cagri bulunamadi")

    scores = {s.id: s for s in db.query(Score).filter(Score.call_id == call.id)}
    segments = db.query(Segment).filter(Segment.call_id == call.id).order_by(Segment.idx).all()
    excerpt = " ".join(g.text for g in segments)[: review_feedback.EXCERPT_CHARS]

    duzeltilen = 0
    for karar in body.kararlar:
        s = scores.get(karar.score_id)
        if s is None:
            raise HTTPException(400, f"Bu cagriya ait olmayan puan: {karar.score_id}")

        s.reviewed_at = datetime.utcnow()
        s.reviewed_by = user.user_id

        if karar.yeni_puan is None:
            continue  # onaylandi — AI puani dogru

        if karar.gerekce_kodu is None:
            raise HTTPException(400, "Duzeltme icin gerekce kodu zorunludur")

        s.override_score = karar.yeni_puan
        s.override_reason_code = karar.gerekce_kodu.value
        s.override_reason = karar.not_
        s.overridden_by = user.user_id
        s.overridden_at = datetime.utcnow()
        duzeltilen += 1

        if s.criterion_id is not None:
            review_feedback.record_correction(
                db, tenant_id=call.tenant_id, criterion_id=s.criterion_id,
                call_id=call.id, excerpt=excerpt, ai_score=s.score,
                human_score=karar.yeni_puan, reason_code=karar.gerekce_kodu.value,
                note=karar.not_, user_id=user.user_id,
            )

    qa_workflow.finalize(db, call, user_id=user.user_id, note=body.kapanis_notu)
    db.add(AuditLog(
        tenant_id=call.tenant_id, user_id=user.user_id, action="review_submit",
        entity_type="call", entity_id=call.id,
        detail={"incelenen": len(body.kararlar), "duzeltilen": duzeltilen},
    ))
    db.commit()

    q = _queue_query(db, user.tenant_id)
    nxt = q.first()
    return _build_payload(db, nxt, kalan=q.count()) if nxt else None


@router.get("/review-queue/reason-codes")
def reason_codes():
    """Düzeltme gerekçe kodları — serbest metin yerine sabit liste."""
    etiket = {
        "kanit_yanlis": "Gösterilen kanıt hatalı",
        "baglam_kacirildi": "Çağrının bağlamı kaçırıldı",
        "kriter_yanlis_yorumlandi": "Kriter yanlış yorumlandı",
        "stt_hatasi": "Transkript hatası",
        "rubrik_mugak": "Kriter tanımı net değil",
        "diger": "Diğer",
    }
    return [{"kod": c.value, "etiket": etiket[c.value]} for c in OverrideReasonCode]


# ---------------------------------------------------------------------------
# İtiraz akışı — uçlar `api/workflow.py`'de; burada YALNIZCA kalibrasyon
# görünürlüğü var. İtiraz endpoint'lerini burada tekrar tanımlamak, aynı yola
# iki farklı handler koymak (ve FAZ 1'de "çift implementasyon" diye işaretlediğim
# hatayı tekrar üretmek) olurdu. workflow.py durum makinesine bağlandı.
# ---------------------------------------------------------------------------

@router.get("/calibration/overturn")
def overturn(criterion_id: int | None = None, db: Session = Depends(get_db),
             user: CurrentUser = Depends(require_staff)):
    """Düzeltilen puan oranı — yükseliyorsa rubrik muğlak demektir."""
    return review_feedback.overturn_stats(db, user.tenant_id, criterion_id)


@router.get("/calibration/examples")
def calibration_examples(db: Session = Depends(get_db),
                         user: CurrentUser = Depends(require_staff)):
    """Prompt'a beslenen kalibrasyon örnekleri — şeffaflık için görünür."""
    from ..models import CalibrationExample, Criterion

    rows = (
        db.query(CalibrationExample, Criterion.name)
        .join(Criterion, Criterion.id == CalibrationExample.criterion_id)
        .filter(CalibrationExample.tenant_id == user.tenant_id,
                CalibrationExample.is_active.is_(True))
        .order_by(CalibrationExample.created_at.desc())
        .limit(200)
        .all()
    )
    return {
        "surum": review_feedback.calibration_version(db, user.tenant_id),
        "ornekler": [
            {"id": e.id, "kriter": ad, "ai_puani": e.ai_score,
             "uzman_puani": e.human_score, "gerekce_kodu": e.reason_code,
             "not": e.note}
            for e, ad in rows
        ],
    }
