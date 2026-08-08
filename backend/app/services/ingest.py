"""Ses/chat dosyasi alimi — upload endpoint'i ve watch-folder ayni yolu kullanir.

Her cagri bir tenant'a ve istege bagli bir kampanyaya (kuyruk) baglidir.
Temsilci dosya adindan otomatik cikarilabilir; tenant bazinda tekildir.
"""

import re
import shutil
from pathlib import Path
from uuid import uuid4

from sqlalchemy.orm import Session

from ..config import settings
from ..models import Agent, Call, CallStatus, Channel, Tenant
from .audio import AUDIO_EXTS


class IngestError(ValueError):
    pass


def is_paused(db: Session, tenant_id: int) -> bool:
    """Tenant'ta isleme duraklatildi mi? Duraklatildiysa cagri kuyruga ATILMAZ."""
    tenant = db.get(Tenant, tenant_id)
    return bool(tenant and tenant.processing_paused)


def parse_agent_from_filename(filename: str) -> str | None:
    """'ayse.yilmaz_fatura_01.wav' -> 'ayse.yilmaz' (ilk '_' oncesi)."""
    stem = Path(filename).stem
    if "_" not in stem:
        return None
    candidate = stem.split("_", 1)[0].strip()
    if re.fullmatch(r"[A-Za-z0-9ÇĞİÖŞÜçğıöşü.\-]{2,64}", candidate):
        return candidate.lower()
    return None


def get_or_create_agent(
    db: Session, tenant_id: int, name: str, team_id: int | None = None
) -> Agent:
    name = name.strip().lower()
    agent = (
        db.query(Agent)
        .filter(Agent.tenant_id == tenant_id, Agent.name == name)
        .first()
    )
    if agent is None:
        agent = Agent(tenant_id=tenant_id, name=name, team_id=team_id)
        db.add(agent)
        db.flush()
    return agent


def ingest_audio(
    db: Session,
    tenant_id: int,
    src_path: Path,
    original_name: str,
    agent_name: str | None = None,
    campaign_id: int | None = None,
    customer_ref: str | None = None,
    move: bool = False,
) -> Call:
    """Dosyayi depoya al, Call kaydi olustur ve pipeline'i kuyruga at."""
    ext = Path(original_name).suffix.lower()
    if ext not in AUDIO_EXTS:
        raise IngestError(f"Desteklenmeyen dosya turu: {ext} (izinli: {sorted(AUDIO_EXTS)})")

    settings.audio_dir.mkdir(parents=True, exist_ok=True)
    dest = settings.audio_dir / f"{uuid4().hex}{ext}"
    if move:
        shutil.move(str(src_path), dest)
    else:
        shutil.copy2(str(src_path), dest)

    agent = None
    resolved = agent_name or parse_agent_from_filename(original_name)
    if resolved:
        agent = get_or_create_agent(db, tenant_id, resolved)

    call = Call(
        tenant_id=tenant_id,
        filename=original_name,
        audio_path=str(dest),
        channel=Channel.voice,
        agent_id=agent.id if agent else None,
        campaign_id=campaign_id,
        customer_ref=(customer_ref or "").strip() or None,
        status=CallStatus.pending,
    )
    db.add(call)
    db.commit()
    db.refresh(call)

    # Ayni musteri yakin zamanda tekrar aradiysa isaretle (gercek FCR icin)
    from . import fcr

    fcr.apply_repeat_flags(db, call)
    db.commit()

    # Isleme duraklatildiysa cagri "pending" kalir; Yonetim > Isleme'den baslatilir
    if not is_paused(db, tenant_id):
        # Import burada: celery -> ingest dongusel bagimliligini kirmak icin
        from ..tasks.pipeline import process_call

        process_call.delay(call.id)
    return call


def ingest_chat(
    db: Session,
    tenant_id: int,
    filename: str,
    messages: list[dict],
    agent_name: str | None = None,
    campaign_id: int | None = None,
) -> Call:
    """Chat gorusmesini al: Call(channel=chat) + Segment'ler olustur, puanlamaya at."""
    agent = None
    resolved = agent_name or parse_agent_from_filename(filename)
    if resolved:
        agent = get_or_create_agent(db, tenant_id, resolved)

    call = Call(
        tenant_id=tenant_id,
        filename=filename,
        audio_path="",  # chat'te ses yok
        channel=Channel.chat,
        agent_id=agent.id if agent else None,
        campaign_id=campaign_id,
        status=CallStatus.pending,
    )
    db.add(call)
    db.flush()

    ordered = sorted(messages, key=lambda m: m.get("ts_sec", 0.0))
    from ..models import Segment

    for i, msg in enumerate(ordered):
        db.add(
            Segment(
                call_id=call.id,
                idx=i,
                speaker=msg.get("speaker", "bilinmeyen"),
                start_sec=float(msg.get("ts_sec", 0.0)),
                end_sec=float(msg.get("ts_sec", 0.0)),
                text=msg.get("text", ""),
            )
        )
    call.duration_sec = ordered[-1].get("ts_sec", 0.0) if ordered else 0.0
    db.commit()
    db.refresh(call)

    if not is_paused(db, tenant_id):
        from ..tasks.pipeline import process_chat

        process_chat.delay(call.id)
    return call
