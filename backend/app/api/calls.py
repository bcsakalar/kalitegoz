import csv
import io
import shutil
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import String, func, nullslast, select
from sqlalchemy.orm import Session, joinedload

from ..db import get_db
from ..deps import CurrentUser, get_current_user, require_staff
from ..models import Agent, Call, CallStatus, Role, Segment
from ..schemas import (
    BulkCallAction,
    BulkResult,
    BulkRescoreRequest,
    CallDetail,
    CallList,
    CallListItem,
    SimilarCall,
    TagsUpdate,
    TranscriptHit,
    TranscriptSearchResult,
)
from ..config import settings
from ..services import audit, masking
from ..services.ingest import IngestError, ingest_audio

router = APIRouter(prefix="/api/v1/calls", tags=["calls"])

_MEDIA_TYPES = {
    ".wav": "audio/wav",
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".ogg": "audio/ogg",
    ".flac": "audio/flac",
}

# En fazla yuklenebilir ses boyutu (200 MB) — upload dogrulama
MAX_UPLOAD_BYTES = 200 * 1024 * 1024


def _scoped(db: Session, user: CurrentUser):
    """Tenant + rol kapsamli temel sorgu.

    - Temsilci: yalnizca kendi cagrilari
    - Supervizor: yalnizca kendi takimindaki temsilcilerin cagrilari
    - Admin / kalite uzmani: tenant'in tum cagrilari
    Alt sorgu kullanilir (join yerine) — joinedload ile satir cogalmasini onler.
    """
    q = db.query(Call).filter(Call.tenant_id == user.tenant_id)
    if user.role == Role.agent:
        # agent_id yoksa hicbir cagri gormesin
        q = q.filter(Call.agent_id == (user.agent_id or -1))
    elif user.role == Role.supervisor and user.team_id:
        team_agents = select(Agent.id).where(
            Agent.tenant_id == user.tenant_id, Agent.team_id == user.team_id
        )
        q = q.filter(Call.agent_id.in_(team_agents))
    return q


def _apply_filters(
    q,
    status: CallStatus | None,
    agent_id: int | None,
    category: str | None,
    channel: str | None,
    campaign_id: int | None,
    min_score: float | None,
    max_score: float | None,
    only_crisis: bool | None,
    only_zeroed: bool | None,
    date_from: datetime | None,
    date_to: datetime | None,
    only_golden: bool | None = None,
    tag: str | None = None,
):
    if status is not None:
        q = q.filter(Call.status == status)
    if agent_id is not None:
        q = q.filter(Call.agent_id == agent_id)
    if category:
        q = q.filter(Call.category == category)
    if channel:
        q = q.filter(Call.channel == channel)
    if campaign_id is not None:
        q = q.filter(Call.campaign_id == campaign_id)
    if min_score is not None:
        q = q.filter(Call.total_score >= min_score)
    if max_score is not None:
        q = q.filter(Call.total_score <= max_score)
    if only_crisis:
        q = q.filter(Call.is_crisis.is_(True))
    if only_zeroed:
        q = q.filter(Call.zeroed.is_(True))
    if date_from is not None:
        q = q.filter(Call.created_at >= date_from)
    if date_to is not None:
        end = date_to + timedelta(days=1) if date_to.time() == datetime.min.time() else date_to
        q = q.filter(Call.created_at < end)
    if only_golden:
        q = q.filter(Call.is_golden.is_(True))
    if tag:
        # JSON listeyi metne cevirip etiketi ara (SQLite + Postgres uyumlu)
        q = q.filter(func.cast(Call.tags, String).like(f'%"{tag}"%'))
    return q


# Siralanabilir kolonlar. "duration" => uzun gorusmeleri one al (sesli + chat).
_SORT_COLUMNS = {
    "created_at": Call.created_at,
    "duration": Call.duration_sec,
    "score": Call.total_score,
    "csat": Call.predicted_csat,
}


def _apply_sort(q, sort: str, order: str):
    """Siralamayi uygula. Islenmemis cagrilarin NULL degeri HER ZAMAN sona duser
    (uzun gorusmeye gore siralarken pending cagrilar listeyi bozmasin). id.desc()
    esitlikte deterministik sayfalama saglar."""
    col = _SORT_COLUMNS.get(sort, Call.created_at)
    direction = col.asc() if order == "asc" else col.desc()
    return q.order_by(nullslast(direction), Call.id.desc())


@router.post("/upload", response_model=CallListItem, status_code=201)
async def upload_call(
    request: Request,
    file: UploadFile = File(...),
    agent_name: str | None = Form(default=None),
    campaign_id: int | None = Form(default=None),
    # Musteri referansi (CRM ID / musteri no / telefon HASH'i). Verilirse ayni
    # musterinin tekrar aramasi tespit edilir -> GERCEK FCR. KVKK: ham telefon
    # numarasi gondermeyin, hash'leyin.
    customer_ref: str | None = Form(default=None),
    user: CurrentUser = Depends(require_staff),
    db: Session = Depends(get_db),
):
    if not file.filename:
        raise HTTPException(400, "Dosya adi bos")
    size = 0
    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                tmp.close()
                Path(tmp.name).unlink(missing_ok=True)
                raise HTTPException(413, "Dosya cok buyuk (limit 200 MB)")
            tmp.write(chunk)
        tmp_path = Path(tmp.name)
    try:
        call = ingest_audio(
            db, user.tenant_id, tmp_path, file.filename,
            agent_name=agent_name, campaign_id=campaign_id,
            customer_ref=customer_ref, move=True,
        )
    except IngestError as exc:
        tmp_path.unlink(missing_ok=True)
        raise HTTPException(400, str(exc))
    audit.log(db, action="upload_call", tenant_id=user.tenant_id, user_id=user.id,
              entity_type="call", entity_id=call.id,
              ip=request.client.host if request.client else "")
    return call


@router.get("", response_model=CallList)
def list_calls(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    status: CallStatus | None = None,
    agent_id: int | None = None,
    category: str | None = None,
    channel: str | None = None,
    campaign_id: int | None = None,
    min_score: float | None = Query(default=None, ge=0, le=100),
    max_score: float | None = Query(default=None, ge=0, le=100),
    only_crisis: bool | None = None,
    only_zeroed: bool | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    only_golden: bool | None = None,
    tag: str | None = None,
    # Siralama: created_at (tarih) | duration (sure) | score (puan) | csat.
    # duration+desc => en uzun gorusmeler en ustte (uzun sesli/chat incelemesi).
    sort: str = Query(default="created_at", pattern="^(created_at|duration|score|csat)$"),
    order: str = Query(default="desc", pattern="^(asc|desc)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    q = _scoped(db, user).options(joinedload(Call.agent), joinedload(Call.campaign))
    q = _apply_filters(q, status, agent_id, category, channel, campaign_id,
                       min_score, max_score, only_crisis, only_zeroed, date_from, date_to,
                       only_golden, tag)
    total = q.with_entities(func.count(Call.id)).scalar() or 0
    items = (
        _apply_sort(q, sort, order)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return CallList(items=items, total=total, page=page, page_size=page_size)


@router.post("/{call_id}/golden", response_model=CallListItem)
def toggle_golden(call_id: int, db: Session = Depends(get_db),
                  user: CurrentUser = Depends(require_staff)):
    """Cagriyi 'ornek/altin cagri' olarak isaretle/kaldir (egitim kutuphanesi)."""
    call = _scoped(db, user).options(joinedload(Call.agent)).filter(Call.id == call_id).first()
    if call is None:
        raise HTTPException(404, "Cagri bulunamadi")
    call.is_golden = not call.is_golden
    db.commit()
    db.refresh(call)
    audit.log(db, action="toggle_golden", tenant_id=user.tenant_id, user_id=user.id,
              entity_type="call", entity_id=call.id, detail={"is_golden": call.is_golden})
    return call


@router.put("/{call_id}/tags", response_model=CallListItem)
def set_tags(call_id: int, body: TagsUpdate, db: Session = Depends(get_db),
             user: CurrentUser = Depends(require_staff)):
    """Cagriya manuel etiket ata (benzersiz, kirpilmis, en fazla 20)."""
    call = _scoped(db, user).options(joinedload(Call.agent)).filter(Call.id == call_id).first()
    if call is None:
        raise HTTPException(404, "Cagri bulunamadi")
    seen: set[str] = set()
    clean: list[str] = []
    for tval in body.tags:
        t2 = (tval or "").strip()[:40]
        if t2 and t2.lower() not in seen:
            seen.add(t2.lower())
            clean.append(t2)
    call.tags = clean[:20]
    db.commit()
    db.refresh(call)
    audit.log(db, action="set_tags", tenant_id=user.tenant_id, user_id=user.id,
              entity_type="call", entity_id=call.id, detail={"tags": clean[:20]})
    return call


@router.post("/bulk", response_model=BulkResult)
def bulk_action(body: BulkCallAction, db: Session = Depends(get_db),
                user: CurrentUser = Depends(require_staff)):
    """Secili cagrilarda toplu islem: ornek isaretle/kaldir, etiket ekle/cikar, sil.
    Liste ekranindan cok sayida cagriyi tek hamlede yonet."""
    if not body.ids:
        return BulkResult(affected=0, action=body.action)
    calls = _scoped(db, user).filter(Call.id.in_(body.ids[:500])).all()
    tag = (body.tag or "").strip()[:40]
    affected = 0
    for c in calls:
        if body.action == "golden_on":
            c.is_golden = True
        elif body.action == "golden_off":
            c.is_golden = False
        elif body.action == "tag_add" and tag:
            cur = list(c.tags or [])
            if tag.lower() not in {x.lower() for x in cur}:
                c.tags = (cur + [tag])[:20]
        elif body.action == "tag_remove" and tag:
            c.tags = [x for x in (c.tags or []) if x.lower() != tag.lower()]
        elif body.action == "delete":
            Path(c.audio_path).unlink(missing_ok=True)
            db.delete(c)
        else:
            continue
        affected += 1
    db.commit()
    audit.log(db, action="bulk_call_action", tenant_id=user.tenant_id, user_id=user.id,
              entity_type="call", detail={"action": body.action, "count": affected, "tag": tag})
    return BulkResult(affected=affected, action=body.action)


def _call_embed_text(c: Call) -> str:
    """Embedding icin cagri metni: ozet + kategori + niyet etiketleri."""
    parts = [c.summary or "", c.category or "", " ".join(c.intent_tags or [])]
    return " ".join(p for p in parts if p).strip()


def _cosine(a: list, b: list) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    import math
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


@router.get("/{call_id}/similar", response_model=list[SimilarCall])
def similar_calls(call_id: int, limit: int = Query(8, ge=1, le=20),
                  db: Session = Depends(get_db), user: CurrentUser = Depends(require_staff)):
    """Bu cagriya benzer gecmis cagrilar. Embedding varsa SEMANTIK benzerlik (kosinus);
    yoksa ortak niyet etiketi + kategori + puan yakinligi (heuristik). Kalibrasyon ve egitim icin."""
    base = _scoped(db, user).options(joinedload(Call.agent)).filter(Call.id == call_id).first()
    if base is None:
        raise HTTPException(404, "Cagri bulunamadi")
    base_tags = {t.lower() for t in (base.intent_tags or [])}

    # Temel cagrinin embedding'i yoksa aninda uret (best-effort)
    base_emb = base.embedding
    if not base_emb and _call_embed_text(base):
        try:
            from ..models import Tenant
            from ..services import knowledge
            tenant = db.get(Tenant, user.tenant_id)
            base_emb = knowledge.embed(
                [_call_embed_text(base)], tenant.settings if tenant else None,
                tenant_id=user.tenant_id, kind="embed")[0]
            base.embedding = base_emb
            db.commit()
        except Exception:  # noqa: BLE001 — embedding yoksa heuristige duseriz
            base_emb = None

    cand = (_scoped(db, user).options(joinedload(Call.agent))
            .filter(Call.id != call_id, Call.status == CallStatus.done).limit(1000).all())

    def _shared(c: Call) -> list[str]:
        ct = {t.lower() for t in (c.intent_tags or [])}
        return [t for t in (base.intent_tags or []) if t.lower() in ct]

    scored: list[tuple[float, list[str], Call]] = []
    emb_hits = sum(1 for c in cand if c.embedding)
    use_embed = base_emb and emb_hits >= 3
    if use_embed:
        for c in cand:
            if not c.embedding:
                continue
            sim = round(_cosine(base_emb, c.embedding), 3)
            if sim <= 0.30:   # semantik gurultu esigi
                continue
            scored.append((sim, _shared(c), c))
    else:
        # Heuristik: ortak etiket (Jaccard) + kategori + puan yakinligi
        for c in cand:
            ctags = {t.lower() for t in (c.intent_tags or [])}
            shared = base_tags & ctags
            jac = len(shared) / len(base_tags | ctags) if (base_tags | ctags) else 0.0
            cat = 0.25 if (base.category and c.category == base.category) else 0.0
            prox = 0.0
            if base.total_score is not None and c.total_score is not None:
                prox = max(0.0, 0.2 * (1 - abs(base.total_score - c.total_score) / 100))
            sim = round(min(1.0, jac * 0.7 + cat + prox), 3)
            if sim <= 0.05:
                continue
            scored.append((sim, _shared(c), c))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [SimilarCall(id=c.id, filename=c.filename, agent_name=c.agent.name if c.agent else None,
                        category=c.category, total_score=c.total_score, similarity=sim,
                        shared_tags=tags) for sim, tags, c in scored[:limit]]


@router.post("/embed-backfill")
def embed_backfill(limit: int = Query(400, ge=1, le=2000),
                   db: Session = Depends(get_db), user: CurrentUser = Depends(require_staff)):
    """Embedding'i olmayan tamamlanmis cagrilara toplu embedding uretir (semantik
    benzer-cagri aramasini aktive eder). Kurumun embed saglayicisini kullanir."""
    from ..models import Tenant
    from ..services import knowledge
    rows = (_scoped(db, user).filter(Call.status == CallStatus.done, Call.embedding.is_(None))
            .order_by(Call.created_at.desc()).limit(limit).all())
    targets = [(c, _call_embed_text(c)) for c in rows]
    targets = [(c, txt) for c, txt in targets if txt]
    if not targets:
        return {"embedded": 0, "message": "Embedding uretilecek cagri yok."}
    tenant = db.get(Tenant, user.tenant_id)
    try:
        vecs = knowledge.embed([txt for _, txt in targets], tenant.settings if tenant else None,
                               tenant_id=user.tenant_id, kind="embed")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"Embedding uretilemedi: {exc}")
    for (c, _), v in zip(targets, vecs):
        c.embedding = v
    db.commit()
    return {"embedded": len(targets)}


@router.get("/export.csv")
def export_csv(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_staff),
    status: CallStatus | None = None,
    agent_id: int | None = None,
    category: str | None = None,
    channel: str | None = None,
    campaign_id: int | None = None,
    min_score: float | None = Query(default=None, ge=0, le=100),
    max_score: float | None = Query(default=None, ge=0, le=100),
    only_crisis: bool | None = None,
    only_zeroed: bool | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
):
    q = _scoped(db, user).options(joinedload(Call.agent))
    q = _apply_filters(q, status, agent_id, category, channel, campaign_id,
                       min_score, max_score, only_crisis, only_zeroed, date_from, date_to)
    rows = q.order_by(Call.created_at.desc()).limit(10000).all()

    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")
    writer.writerow([
        "id", "dosya", "kanal", "temsilci", "kategori", "sure_sn", "puan",
        "sifirlandi", "kriz", "csat", "durum", "duygu_baslangic", "duygu_bitis",
        "olusturulma", "ozet",
    ])
    for c in rows:
        writer.writerow([
            c.id, c.filename, c.channel.value if hasattr(c.channel, "value") else c.channel,
            c.agent.name if c.agent else "", c.category or "",
            c.duration_sec if c.duration_sec is not None else "",
            c.total_score if c.total_score is not None else "",
            "evet" if c.zeroed else "hayir", "evet" if c.is_crisis else "hayir",
            c.predicted_csat if c.predicted_csat is not None else "",
            c.status.value, c.sentiment_start or "", c.sentiment_end or "",
            c.created_at.isoformat(sep=" ", timespec="seconds"),
            (c.summary or "").replace("\n", " "),
        ])
    return Response(
        content="﻿" + buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="kalitegoz_cagrilar.csv"'},
    )


@router.get("/search", response_model=TranscriptSearchResult)
def search_transcripts(
    q: str = Query(min_length=2, description="Aranacak ifade (konusma metninde gecen)"),
    speaker: str | None = Query(default=None, pattern="^(musteri|temsilci)$"),
    channel: str | None = None,
    agent_id: int | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Tum transkriptlerde ifade arama — "su cumle gecen cagrilari getir".

    Kalite ekibinin en sik ihtiyaci: "avukat diyen tum cagrilar", "kesin cozulur
    diyen temsilciler", "iptal ediyorum gecen gorusmeler". Sonuclar cagri +
    konusmaci + saniye ile doner; UI'da tiklaninca sesin o anina atlanir.

    Kapsam: kullanicinin gorebildigi cagrilarla sinirlidir (tenant + rol).
    """
    # Gorulebilir cagri id'leri (tenant + rol kapsami)
    visible = _scoped(db, user).with_entities(Call.id)
    if channel:
        visible = visible.filter(Call.channel == channel)
    if agent_id is not None:
        visible = visible.filter(Call.agent_id == agent_id)
    visible_ids = visible.subquery()

    pattern = f"%{q.strip()}%"
    base = (
        db.query(Segment)
        .join(Call, Segment.call_id == Call.id)
        .filter(Segment.call_id.in_(select(visible_ids.c.id)))
        .filter(Segment.text.ilike(pattern))
    )
    if speaker:
        base = base.filter(Segment.speaker == speaker)

    total_hits = base.with_entities(func.count(Segment.id)).scalar() or 0
    total_calls = base.with_entities(func.count(func.distinct(Segment.call_id))).scalar() or 0

    # Cagri basina eslesme sayisi (UI'da "3 eslesme" gostermek icin)
    counts = dict(
        base.with_entities(Segment.call_id, func.count(Segment.id))
        .group_by(Segment.call_id).all()
    )

    rows = (
        base.options(joinedload(Segment.call).joinedload(Call.agent))
        .order_by(Call.created_at.desc(), Segment.idx)
        .limit(limit).all()
    )
    items = [
        TranscriptHit(
            call_id=s.call_id, filename=s.call.filename,
            channel=s.call.channel.value if hasattr(s.call.channel, "value") else str(s.call.channel),
            agent_name=s.call.agent.name if s.call.agent else None,
            category=s.call.category, total_score=s.call.total_score,
            created_at=s.call.created_at, speaker=s.speaker,
            ts_sec=s.start_sec, text=s.text,
            match_count=counts.get(s.call_id, 1),
        )
        for s in rows
    ]
    return TranscriptSearchResult(
        query=q, total_hits=total_hits, total_calls=total_calls, items=items
    )


def _get_call(db: Session, user: CurrentUser, call_id: int) -> Call:
    call = (
        _scoped(db, user)
        .options(
            joinedload(Call.agent), joinedload(Call.campaign),
            joinedload(Call.segments), joinedload(Call.scores), joinedload(Call.violations),
        )
        .filter(Call.id == call_id)
        .first()
    )
    if call is None:
        raise HTTPException(404, "Cagri bulunamadi")
    return call


@router.get("/{call_id}", response_model=CallDetail)
def get_call(call_id: int, request: Request, reveal: bool = False,
             db: Session = Depends(get_db),
             user: CurrentUser = Depends(get_current_user)):
    """Cagri detayi. KVKK: transkript/ozet varsayilan MASKELI doner.

    Yalnizca admin/kalite `?reveal=true` ile ham veriyi gorebilir; bu erisim
    denetim gunlugune `reveal_pii` olarak yazilir (kim, ne zaman, hangi cagri).
    """
    call = _get_call(db, user, call_id)  # once varlik/kapsam dogrulamasi (404)
    can_reveal = user.role in (Role.admin, Role.quality)
    revealing = reveal and can_reveal and settings.pii_masking_enabled
    do_mask = settings.pii_masking_enabled and not revealing

    audit.log(db, action="reveal_pii" if revealing else "view_call",
              tenant_id=user.tenant_id, user_id=user.id,
              entity_type="call", entity_id=call.id,
              ip=request.client.host if request.client else "")

    # audit commit'i objeleri expire etti; tek sorguda eager-load ile tazele,
    # sonra bellekte maskele ve expunge et (maskeli metin ASLA DB'ye yazilmaz).
    call = _get_call(db, user, call_id)
    if do_mask:
        for seg in call.segments:
            seg.text = masking.mask_text(seg.text)
        if call.summary:
            call.summary = masking.mask_text(call.summary)
        if call.next_action:
            call.next_action = masking.mask_text(call.next_action)
    call.pii_masked = do_mask
    db.expunge_all()
    return call


@router.get("/{call_id}/audio")
def get_audio(call_id: int, request: Request, db: Session = Depends(get_db),
              user: CurrentUser = Depends(get_current_user)):
    call = _scoped(db, user).filter(Call.id == call_id).first()
    if call is None:
        raise HTTPException(404, "Cagri bulunamadi")
    # audio_path bos olabilir (chat kanali veya sentetik demo kaydi).
    # Path("") -> "." yani MEVCUT BIR KLASOR; dogrudan exists() kontrolu
    # yaniltir ve FileResponse klasore carpip 500 verir.
    if not call.audio_path.strip():
        raise HTTPException(404, "Bu kayit icin ses dosyasi yok")
    path = Path(call.audio_path)
    if not path.is_file():
        raise HTTPException(404, "Ses dosyasi bulunamadi")
    media = _MEDIA_TYPES.get(path.suffix.lower(), "application/octet-stream")
    audit.log(db, action="download_audio", tenant_id=user.tenant_id, user_id=user.id,
              entity_type="call", entity_id=call.id,
              ip=request.client.host if request.client else "")
    return FileResponse(path, media_type=media, filename=call.filename)


@router.post("/{call_id}/rescore", response_model=CallListItem)
def rescore(call_id: int, full: bool = False, db: Session = Depends(get_db),
            user: CurrentUser = Depends(require_staff)):
    call = _scoped(db, user).filter(Call.id == call_id).first()
    if call is None:
        raise HTTPException(404, "Cagri bulunamadi")
    if call.status in (CallStatus.transcribing, CallStatus.scoring):
        raise HTTPException(409, "Cagri su anda isleniyor")

    from ..tasks.pipeline import process_call, rescore_call

    call.status = CallStatus.pending
    db.commit()
    if full:
        process_call.delay(call.id)
    else:
        rescore_call.delay(call.id)
    db.refresh(call)
    return call


@router.post("/rescore-bulk")
def rescore_bulk_endpoint(body: BulkRescoreRequest, request: Request,
                          db: Session = Depends(get_db),
                          user: CurrentUser = Depends(require_staff)):
    """Rubrik degistikten sonra toplu yeniden puanlama (STT'siz, hizli kuyrukta).

    call_ids bos ise tenant'in TUM tamamlanmis cagrilari yeniden puanlanir.
    """
    from ..tasks.maintenance import rescore_bulk

    rescore_bulk.delay(user.tenant_id, body.call_ids)
    audit.log(db, action="rescore_bulk", tenant_id=user.tenant_id, user_id=user.id,
              detail={"call_ids": body.call_ids or "all"},
              ip=request.client.host if request.client else "")
    return {"queued": True, "message": "Yeniden puanlama kuyruga alindi"}


@router.delete("/{call_id}", status_code=204)
def delete_call(call_id: int, db: Session = Depends(get_db),
                user: CurrentUser = Depends(require_staff)):
    call = _scoped(db, user).filter(Call.id == call_id).first()
    if call is None:
        raise HTTPException(404, "Cagri bulunamadi")
    Path(call.audio_path).unlink(missing_ok=True)
    db.delete(call)
    db.commit()
