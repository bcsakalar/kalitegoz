"""Bilgi bankasi (RAG): dokuman parcalama, embedding ve benzerlik aramasi.

Amac: temsilcinin verdigi bilginin sirket dokumanlariyla ORTUSUP ortusmedigini
kontrol etmek ("iade suresi 30 gun dedi, dokumanda 14 gun yaziyor" -> YANLIS BILGI).

Embedding: Ollama `nomic-embed-text` (yerel, ucretsiz) veya Gemini embeddings.
Arama: kosinus benzerligi. Chunk sayisi kurumsal SSS/prosedur dokumanlarinda
tipik olarak birkac bin mertebesindedir; Python tarafinda kosinus hesabi bu
olcekte yeterince hizlidir ve pgvector eklentisine bagimlilik yaratmaz.
(pgvector imaji compose'da hazir; cok buyuk korpuslarda vektor indeksine gecis
icin `KnowledgeChunk.embedding` kolonu Vector'e tasinabilir.)
"""

import logging
import math
import re

import httpx
from sqlalchemy.orm import Session

from ..config import settings
from ..models import KnowledgeChunk, KnowledgeDoc, Tenant
from . import ai_config

logger = logging.getLogger(__name__)

CHUNK_CHARS = 900
CHUNK_OVERLAP = 150
TOP_K = 4
MIN_SIMILARITY = 0.35


class KnowledgeError(RuntimeError):
    pass


# =====================================================================
# Metin cikarma & parcalama
# =====================================================================


def extract_text(filename: str, raw: bytes) -> str:
    """Desteklenen dosyadan duz metin cikar (.md/.txt/.pdf/.docx)."""
    name = filename.lower()
    if name.endswith((".md", ".txt")):
        return raw.decode("utf-8", errors="replace")
    if name.endswith(".pdf"):
        return _extract_pdf(raw)
    if name.endswith(".docx"):
        return _extract_docx(raw)
    raise KnowledgeError(f"Desteklenmeyen dosya turu: {filename} (.md .txt .pdf .docx)")


def _extract_pdf(raw: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        raise KnowledgeError("PDF okumak icin 'pypdf' gerekli")
    import io

    reader = PdfReader(io.BytesIO(raw))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def _extract_docx(raw: bytes) -> str:
    try:
        import docx  # python-docx
    except ImportError:
        raise KnowledgeError("DOCX okumak icin 'python-docx' gerekli")
    import io

    document = docx.Document(io.BytesIO(raw))
    return "\n".join(p.text for p in document.paragraphs)


def chunk_text(text: str) -> list[str]:
    """Metni ortusmeli parcalara bol (paragraf sinirlarina saygili)."""
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + CHUNK_CHARS)
        if end < len(text):
            # En yakin paragraf/cumle sinirinda kes
            for sep in ("\n\n", "\n", ". "):
                cut = text.rfind(sep, start + CHUNK_CHARS // 2, end)
                if cut != -1:
                    end = cut + len(sep)
                    break
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= len(text):
            break
        start = max(start + 1, end - CHUNK_OVERLAP)
    return chunks


# =====================================================================
# Embedding
# =====================================================================


def _ts(db: Session, tenant_id: int) -> dict | None:
    """Tenant ayarlari (AI saglayici config'i icin). Yoksa None -> .env fallback."""
    t = db.get(Tenant, tenant_id)
    return t.settings if t else None


def embed(texts: list[str], tenant_settings: dict | None = None,
          tenant_id: int | None = None, kind: str = "embed") -> list[list[float]]:
    """Metinleri vektore cevir. Saglayici kurum ayarindan: ollama | gemini | openai.

    NOT: Indeksleme ve sorgu AYNI saglayici/modelle yapilmali (boyut uyumu).
    Saglayici degisirse bilgi bankasi yeniden indekslenmelidir.

    tenant_id verilirse kullanim AiUsage'a kaydedilir (maliyet paneli — embedding).
    """
    if not texts:
        return []
    import time as _time

    cfg = ai_config.resolve(tenant_settings, "embed")
    if cfg.provider != "ollama" and not cfg.api_key:
        raise KnowledgeError(f"Embedding saglayicisi {cfg.provider} secili ama API anahtari yok")
    t0 = _time.monotonic()
    try:
        if cfg.provider == "gemini":
            out = [_embed_gemini(t, cfg) for t in texts]
        elif cfg.provider == "openai":
            out = _embed_openai(texts, cfg)
        else:
            out = [_embed_ollama(t, cfg) for t in texts]
    except Exception:
        _record_embed_usage(cfg, tenant_id, kind, len(texts),
                            int((_time.monotonic() - t0) * 1000), ok=False)
        raise
    _record_embed_usage(cfg, tenant_id, kind, len(texts),
                        int((_time.monotonic() - t0) * 1000), ok=True)
    return out


def _record_embed_usage(cfg, tenant_id, kind, count, latency_ms, ok) -> None:
    """Embedding cagrisini AiUsage'a yaz (best-effort; kayit hatasi akisi bozmaz)."""
    if not tenant_id:
        return
    try:
        from ..db import SessionLocal
        from ..models import AiUsage
        # Kaba token tahmini yoksa 0; maliyet bulut icin kaba cost tablosundan
        db = SessionLocal()
        try:
            db.add(AiUsage(
                tenant_id=tenant_id, provider=cfg.provider, model=cfg.model,
                kind=kind, prompt_tokens=0, completion_tokens=0,
                latency_ms=latency_ms, ok=ok, cost_usd=0.0))
            db.commit()
        finally:
            db.close()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Embed AiUsage kaydi basarisiz: %s", exc)


def _embed_ollama(text: str, cfg: ai_config.AIResolved) -> list[float]:
    try:
        resp = httpx.post(
            f"{cfg.base_url}/api/embeddings",
            json={"model": cfg.model, "prompt": text},
            timeout=settings.llm_timeout_sec,
        )
        resp.raise_for_status()
        return resp.json()["embedding"]
    except httpx.HTTPError as exc:
        raise KnowledgeError(
            f"Embedding alinamadi ({cfg.model}): {exc}. Model yuklu mu? `ollama pull {cfg.model}`"
        ) from exc


def _embed_gemini(text: str, cfg: ai_config.AIResolved) -> list[float]:
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{cfg.model}:embedContent"
    )
    resp = httpx.post(
        url, params={"key": cfg.api_key},
        json={"model": f"models/{cfg.model}", "content": {"parts": [{"text": text}]}},
        timeout=settings.llm_timeout_sec,
    )
    resp.raise_for_status()
    return resp.json()["embedding"]["values"]


def _embed_openai(texts: list[str], cfg: ai_config.AIResolved) -> list[list[float]]:
    resp = httpx.post(
        f"{cfg.base_url}/embeddings",
        headers={"Authorization": f"Bearer {cfg.api_key}"},
        json={"model": cfg.model, "input": texts},
        timeout=settings.llm_timeout_sec,
    )
    resp.raise_for_status()
    return [d["embedding"] for d in resp.json()["data"]]


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


# =====================================================================
# Indeksleme & arama
# =====================================================================


def index_document(db: Session, tenant_id: int, title: str, filename: str, raw: bytes) -> KnowledgeDoc:
    """Dokumani parcalayip embed ederek bilgi bankasina ekler."""
    text = extract_text(filename, raw)
    pieces = chunk_text(text)
    if not pieces:
        raise KnowledgeError("Dokumandan metin cikarilamadi (bos veya taranmis PDF olabilir)")

    vectors = embed(pieces, _ts(db, tenant_id))
    doc = KnowledgeDoc(tenant_id=tenant_id, title=title, source_filename=filename,
                       chunk_count=len(pieces))
    db.add(doc)
    db.flush()
    for i, (piece, vec) in enumerate(zip(pieces, vectors)):
        db.add(KnowledgeChunk(tenant_id=tenant_id, doc_id=doc.id, idx=i,
                              content=piece, embedding=vec))
    db.commit()
    db.refresh(doc)
    return doc


def search(db: Session, tenant_id: int, query: str, top_k: int = TOP_K) -> list[tuple[KnowledgeChunk, float]]:
    """Sorguya en yakin dokuman parcalarini dondur [(chunk, benzerlik)]."""
    chunks = db.query(KnowledgeChunk).filter(KnowledgeChunk.tenant_id == tenant_id).all()
    if not chunks:
        return []
    try:
        qvec = embed([query], _ts(db, tenant_id))[0]
    except KnowledgeError as exc:
        logger.warning("RAG arama atlandi: %s", exc)
        return []
    scored = [(c, cosine(qvec, c.embedding or [])) for c in chunks]
    scored = [(c, s) for c, s in scored if s >= MIN_SIMILARITY]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]


def build_context(db: Session, tenant_id: int, transcript: str, top_k: int = TOP_K) -> str:
    """Cagri transkriptine en ilgili bilgi bankasi pasajlarini prompt blogu yap.

    Bos string donerse bilgi bankasi yok/ilgisiz demektir; puanlama RAG'siz devam eder.
    """
    if not db.query(KnowledgeChunk.id).filter(KnowledgeChunk.tenant_id == tenant_id).first():
        return ""
    # Transkriptin tamami yerine temsilci repliklerinin ozu sorgu olarak kullanilir
    query = transcript[:3000]
    hits = search(db, tenant_id, query, top_k)
    if not hits:
        return ""
    lines = []
    for chunk, score in hits:
        doc_title = chunk.doc.title if chunk.doc else "Dokuman"
        lines.append(f"- [{doc_title} #{chunk.idx}] (benzerlik {score:.2f})\n  {chunk.content}")
    return (
        "\n## SIRKET BILGI BANKASI (dogruluk kontrolu icin)\n"
        "Temsilcinin verdigi bilgiyi asagidaki RESMI dokuman pasajlariyla karsilastir. "
        "Temsilci bunlara AYKIRI bir bilgi verdiyse (ornegin sure, ucret, sart farkli) "
        "bunu 'Bilgi Dogrulugu' kriterinde dusuk puanla ve riskli an olarak isaretle; "
        "gerekcede dokuman adini ve dogru bilgiyi belirt. Pasajlar konuyla ilgisizse "
        "bu bolumu yok say.\n"
        + "\n".join(lines) + "\n"
    )
