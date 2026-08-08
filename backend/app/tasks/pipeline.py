"""Celery pipeline: STT -> diarization -> akustik metrik -> uyum + LLM puanlama.

Hata yonetimi: STT/LLM hatasinda cagri "failed" durumuna duser; Celery otomatik
retry (ustel geri cekilme) uygular, deneme hakki bitince kalici failed kalir ve
admin panelden yeniden kuyruga alinabilir.
"""

import json
import logging
from datetime import datetime

from ..config import settings
from ..db import SessionLocal
from ..models import Alert, Call, CallStatus, Segment
from ..services import (
    acoustics,
    audio,
    diarization,
    events,
    metrics,
    notifications,
    scoring,
    webhooks,
)
from ..services.scoring import ScoringOutcome
from .celery_app import celery_app

logger = logging.getLogger(__name__)

MAX_RETRIES = 2


def _save_transcript_file(call: Call, segments: list[dict]) -> None:
    """Transkripti dosya sistemine de yaz (DB disinda kalici kopya)."""
    settings.transcript_dir.mkdir(parents=True, exist_ok=True)
    path = settings.transcript_dir / f"{call.id}.json"
    path.write_text(
        json.dumps(
            {"call_id": call.id, "filename": call.filename, "segments": segments},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _apply_outcome(db, call: Call, outcome: ScoringOutcome) -> None:
    """Puanlama sonucundan alarm kayitlari olustur ve webhook/canli yayin tetikle."""
    team_id = call.agent.team_id if call.agent else None
    rows = [
        Alert(
            tenant_id=call.tenant_id,
            call_id=call.id,
            team_id=team_id,
            type=alert_type,
            severity=severity,
            message=message,
        )
        for alert_type, severity, message in outcome.alerts
    ]
    for row in rows:
        db.add(row)
    db.commit()

    # Canli yayin (best-effort). Commit'ten SONRA yapilir: aksi halde WebSocket
    # istemcisi, rollback ile geri alinabilecek bir alarmi gorurdu. `id` de
    # ancak commit sonrasi olusur ve istemcinin REST ile ayni sekli gormesi
    # icin gereklidir (okundu isaretlemek id ister).
    for row in rows:
        events.publish_alert({
            "id": row.id,
            "tenant_id": row.tenant_id,
            "team_id": row.team_id,
            "call_id": row.call_id,
            "type": row.type.value,
            "severity": row.severity,
            "message": row.message,
            "is_read": False,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "agent": call.agent.name if call.agent else None,
        })

    # Webhook + Slack/Teams (best-effort; pipeline'i dusurmez)
    for alert_type, severity, message in outcome.alerts:
        payload = {
            "call_id": call.id,
            "tenant_id": call.tenant_id,
            "agent": call.agent.name if call.agent else None,
            "severity": severity,
            "message": message,
            "total_score": outcome.total_score,
        }
        webhooks.emit(alert_type.value, payload)
        notifications.notify(alert_type.value, payload)


@celery_app.task(name="kalitegoz.process_call", bind=True, max_retries=MAX_RETRIES)
def process_call(self, call_id: int) -> None:
    """Tam pipeline: transkripsiyon + akustik metrik + uyum + puanlama."""
    db = SessionLocal()
    call = db.get(Call, call_id)
    if call is None:
        logger.error("Cagri bulunamadi: %s", call_id)
        db.close()
        return
    try:
        call.status = CallStatus.transcribing
        call.error = None
        db.commit()

        # Docker DISI (native) worker'da DB'deki container yolu (/data/...) host
        # yoluna cevrilir; Docker icinde no-op (host_data_dir bos).
        apath = settings.resolve_path(call.audio_path)

        info = audio.probe(apath)
        call.duration_sec = round(info.duration_sec, 2)
        db.commit()

        segments = diarization.diarize_and_transcribe(apath)
        db.query(Segment).filter(Segment.call_id == call.id).delete()
        for i, seg in enumerate(segments):
            db.add(
                Segment(
                    call_id=call.id,
                    idx=i,
                    speaker=seg["speaker"],
                    start_sec=seg["start"],
                    end_sec=seg["end"],
                    text=seg["text"],
                )
            )
        db.commit()
        _save_transcript_file(call, segments)

        # Konusma metrikleri (zamanlama) + akustik metrikler (ses tonu/bagirma).
        # Ikisi de deterministik; LLM'e nesnel dayanak olarak verilir.
        call.metrics = {
            **metrics.compute_metrics(segments, call.duration_sec or 0.0),
            **acoustics.analyze(apath, segments),
        }
        call.status = CallStatus.scoring
        db.commit()

        outcome = scoring.run_scoring(db, call)
        call.status = CallStatus.done
        call.processed_at = datetime.utcnow()
        db.commit()
        _apply_outcome(db, call, outcome)
        logger.info(
            "Cagri %s tamamlandi: %.1f puan (zeroed=%s crisis=%s)",
            call.id, call.total_score or 0, outcome.zeroed, outcome.is_crisis,
        )
    except Exception as exc:
        logger.exception("Cagri %s islenemedi", call_id)
        db.rollback()
        call.retry_count = (call.retry_count or 0) + 1
        call.status = CallStatus.failed
        call.error = f"{type(exc).__name__}: {exc}"[:2000]
        db.commit()
        # Ustel geri cekilme ile retry (STT/LLM gecici hatalari icin)
        if self.request.retries < MAX_RETRIES:
            db.close()
            raise self.retry(exc=exc, countdown=30 * (self.request.retries + 1))
    finally:
        db.close()


@celery_app.task(name="kalitegoz.process_chat", bind=True, max_retries=MAX_RETRIES)
def process_chat(self, call_id: int) -> None:
    """Chat gorusmesi pipeline'i: STT yok; metrik + uyum + LLM puanlama."""
    db = SessionLocal()
    call = db.get(Call, call_id)
    if call is None:
        db.close()
        return
    try:
        call.status = CallStatus.scoring
        call.error = None
        segments = (
            db.query(Segment).filter(Segment.call_id == call.id).order_by(Segment.idx).all()
        )
        msg_dicts = [
            {"speaker": s.speaker, "ts_sec": s.start_sec, "text": s.text} for s in segments
        ]
        call.metrics = metrics.compute_chat_metrics(msg_dicts)
        db.commit()

        outcome = scoring.run_scoring(db, call)
        call.status = CallStatus.done
        call.processed_at = datetime.utcnow()
        db.commit()
        _apply_outcome(db, call, outcome)
        logger.info("Chat %s tamamlandi: %.1f puan", call.id, call.total_score or 0)
    except Exception as exc:
        logger.exception("Chat %s islenemedi", call_id)
        db.rollback()
        call.retry_count = (call.retry_count or 0) + 1
        call.status = CallStatus.failed
        call.error = f"{type(exc).__name__}: {exc}"[:2000]
        db.commit()
        # LLM gecici olarak erisilemiyorsa (restart/asiri yuk) kalici hata sayma
        if self.request.retries < MAX_RETRIES:
            db.close()
            raise self.retry(exc=exc, countdown=30 * (self.request.retries + 1))
    finally:
        db.close()


@celery_app.task(name="kalitegoz.rescore_call", bind=True, max_retries=MAX_RETRIES)
def rescore_call(self, call_id: int) -> None:
    """Sadece LLM puanlamayi yeniden calistir (mevcut transkript uzerinden).

    Rubrik degistiginde STT'yi tekrar calistirmadan yeniden puanlamak icin.
    """
    db = SessionLocal()
    call = db.get(Call, call_id)
    if call is None:
        db.close()
        return
    try:
        call.status = CallStatus.scoring
        call.error = None
        db.commit()

        outcome = scoring.run_scoring(db, call)
        call.status = CallStatus.done
        call.processed_at = datetime.utcnow()
        db.commit()
        _apply_outcome(db, call, outcome)
    except Exception as exc:
        logger.exception("Cagri %s yeniden puanlanamadi", call_id)
        db.rollback()
        call.retry_count = (call.retry_count or 0) + 1
        call.status = CallStatus.failed
        call.error = f"{type(exc).__name__}: {exc}"[:2000]
        db.commit()
        if self.request.retries < MAX_RETRIES:
            db.close()
            raise self.retry(exc=exc, countdown=30 * (self.request.retries + 1))
    finally:
        db.close()
