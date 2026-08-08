"""Bilgi bankasi yonetimi: dokuman yukleme (PDF/DOCX/MD/TXT), listeleme, arama.

Yuklenen dokumanlar parcalanip embed edilir; puanlama sirasinda temsilcinin
verdigi bilgi bu dokumanlarla karsilastirilir (yanlis bilgi tespiti).
"""

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import CurrentUser, require_admin, require_staff
from ..models import KnowledgeChunk, KnowledgeDoc
from ..schemas import KnowledgeDocOut, KnowledgeSearchHit
from ..services import audit, knowledge

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])

MAX_DOC_BYTES = 20 * 1024 * 1024  # 20 MB


@router.get("/docs", response_model=list[KnowledgeDocOut])
def list_docs(db: Session = Depends(get_db), user: CurrentUser = Depends(require_staff)):
    return (
        db.query(KnowledgeDoc)
        .filter(KnowledgeDoc.tenant_id == user.tenant_id)
        .order_by(KnowledgeDoc.created_at.desc())
        .all()
    )


@router.post("/docs", response_model=KnowledgeDocOut, status_code=201)
async def upload_doc(
    request: Request,
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_admin),
):
    if not file.filename:
        raise HTTPException(400, "Dosya adi bos")
    raw = await file.read()
    if len(raw) > MAX_DOC_BYTES:
        raise HTTPException(413, "Dokuman cok buyuk (limit 20 MB)")
    try:
        doc = knowledge.index_document(
            db, user.tenant_id, title or file.filename, file.filename, raw
        )
    except knowledge.KnowledgeError as exc:
        raise HTTPException(400, str(exc))
    audit.log(db, action="knowledge_upload", tenant_id=user.tenant_id, user_id=user.id,
              entity_type="knowledge_doc", entity_id=doc.id,
              detail={"chunks": doc.chunk_count, "file": file.filename},
              ip=request.client.host if request.client else "")
    return doc


@router.delete("/docs/{doc_id}", status_code=204)
def delete_doc(doc_id: int, db: Session = Depends(get_db),
               user: CurrentUser = Depends(require_admin)):
    doc = db.query(KnowledgeDoc).filter(
        KnowledgeDoc.id == doc_id, KnowledgeDoc.tenant_id == user.tenant_id).first()
    if doc is None:
        raise HTTPException(404, "Dokuman bulunamadi")
    db.delete(doc)
    db.commit()


@router.get("/search", response_model=list[KnowledgeSearchHit])
def search_docs(q: str, top_k: int = 4, db: Session = Depends(get_db),
                user: CurrentUser = Depends(require_staff)):
    """Bilgi bankasinda anlamsal arama — RAG'in ne bulacagini onizlemek icin."""
    if len(q.strip()) < 2:
        raise HTTPException(400, "Arama metni cok kisa")
    hits = knowledge.search(db, user.tenant_id, q, min(top_k, 10))
    return [
        KnowledgeSearchHit(
            doc_id=c.doc_id, doc_title=c.doc.title if c.doc else "",
            idx=c.idx, content=c.content, similarity=round(s, 3),
        )
        for c, s in hits
    ]


@router.post("/seed-demo", response_model=KnowledgeDocOut, status_code=201)
def seed_demo_knowledge(db: Session = Depends(get_db),
                        user: CurrentUser = Depends(require_admin)):
    """Demo: resmi 'Iade/Cayma/Kargo Prosedürü' dokumanini indeksler.

    Embedding icin Ollama'nin ayakta ve embed modelinin yuklu olmasi gerekir;
    bu yuzden uygulama acilisinda degil, `make demo` sirasinda tetiklenir.
    """
    from ..config import settings as cfg
    from ..seed import DEMO_KNOWLEDGE_DOC

    if not cfg.demo_mode:
        raise HTTPException(403, "Demo modu kapali")
    existing = db.query(KnowledgeDoc).filter(
        KnowledgeDoc.tenant_id == user.tenant_id,
        KnowledgeDoc.source_filename == DEMO_KNOWLEDGE_DOC["filename"],
    ).first()
    if existing:
        return existing
    try:
        doc = knowledge.index_document(
            db, user.tenant_id, DEMO_KNOWLEDGE_DOC["title"],
            DEMO_KNOWLEDGE_DOC["filename"],
            DEMO_KNOWLEDGE_DOC["content"].encode("utf-8"),
        )
    except knowledge.KnowledgeError as exc:
        raise HTTPException(503, f"Bilgi bankasi indekslenemedi: {exc}")
    return doc


@router.get("/stats")
def stats(db: Session = Depends(get_db), user: CurrentUser = Depends(require_staff)):
    docs = db.query(KnowledgeDoc).filter(KnowledgeDoc.tenant_id == user.tenant_id).count()
    chunks = db.query(KnowledgeChunk).filter(KnowledgeChunk.tenant_id == user.tenant_id).count()
    return {"documents": docs, "chunks": chunks, "rag_active": chunks > 0}
