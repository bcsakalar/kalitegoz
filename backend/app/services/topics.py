"""Konu kesfi ve kok-neden analizi (speech analytics'in "neden ariyorlar?" sorusu).

Sabit kategori listesi (fatura/iptal/ariza...) "ne tur" cagri oldugunu soyler ama
"BU HAFTA NEDEN ariyorlar?" sorusuna cevap vermez. Ornek: "fatura" kategorisindeki
cagrilarin yarisi aslinda "yeni tarife gecisinde cift ucretlendirme" yuzunden
geliyorsa, bunu kategori listesi GOSTERMEZ — kumeleme gosterir.

Yontem:
1. Her cagrinin ozeti (LLM'in yazdigi) embed edilir — RAG icin kurdugumuz
   altyapinin aynisi (nomic-embed-text).
2. Kosinus benzerligine dayali esik-tabanli kumeleme (agglomerative benzeri,
   tek gecis). Kume sayisini onceden bilmedigimiz icin k-means uygun degil;
   esik tabanli yaklasim yeni temalarin kendiliginden ortaya cikmasini saglar.
3. Her kume icin LLM'e tek bir cagri: temayi adlandir + kok neden + aksiyon onerisi.

Neden scikit-learn/HDBSCAN degil: tek bag daha (~100 MB) ve bu olcekte
(yuzlerce-binlerce cagri) numpy ile kosinus matrisi yeterince hizli.
"""

import logging

from sqlalchemy.orm import Session

from ..models import Call, CallStatus, Tenant
from ..schemas import LLMKonuAnalizi
from . import ai_config, knowledge
from .llm import generate_json

logger = logging.getLogger(__name__)

# Bu benzerligin ustundeki cagrilar ayni temaya konur (0-1). Yuksek => daha cok,
# daha dar kume; dusuk => az ama genis kume.
SIMILARITY_THRESHOLD = 0.72
MIN_CLUSTER_SIZE = 2      # tek cagrilik "tema" gurultudur
MAX_CLUSTERS = 12         # dashboard'da anlamli kalmasi icin
MAX_CALLS = 400           # performans siniri (en yeni N cagri)

TOPIC_SYSTEM = (
    "Sen bir cagri merkezi operasyon analistisin. Sana AYNI TEMADA oldugu tespit "
    "edilmis cagri ozetleri verilir. Bu cagrilarin ORTAK sebebini bulur, temaya "
    "kisa bir ad verir ve kok nedeni tek cumleyle aciklarsin. Yanitin HER ZAMAN "
    "sadece gecerli JSON olur."
)


def _topic_prompt(summaries: list[str]) -> str:
    listed = "\n".join(f"- {s}" for s in summaries[:15])
    return f"""## AYNI TEMADAKI CAGRI OZETLERI ({len(summaries)} cagri)
{listed}

## GOREV
1. Bu cagrilarin ortak temasina KISA bir ad ver (en fazla 5 kelime, Turkce).
2. Kok nedeni tek cumleyle acikla (musteriler NEDEN ariyor?).
3. Operasyona somut bir aksiyon oner (bu cagrilar nasil AZALTILIR?).

SADECE su semada JSON dondur:
{{"baslik": "...", "kok_neden": "...", "aksiyon": "..."}}"""


def _cluster(vectors: list[list[float]], threshold: float) -> list[list[int]]:
    """Esik tabanli tek gecisli kumeleme. Doner: her kume icin indis listesi.

    Her cagri, merkezine yeterince benzedigi ILK kumeye katilir; hicbirine
    benzemiyorsa yeni kume acar. Kume merkezi calisan ortalamadir.
    """
    clusters: list[list[int]] = []
    centroids: list[list[float]] = []
    for i, vec in enumerate(vectors):
        best, best_sim = -1, 0.0
        for c, centroid in enumerate(centroids):
            sim = knowledge.cosine(vec, centroid)
            if sim > best_sim:
                best, best_sim = c, sim
        if best >= 0 and best_sim >= threshold:
            clusters[best].append(i)
            # Merkezi guncelle (calisan ortalama)
            n = len(clusters[best])
            centroids[best] = [
                (old * (n - 1) + new) / n for old, new in zip(centroids[best], vec)
            ]
        else:
            clusters.append([i])
            centroids.append(list(vec))
    return clusters


def discover(db: Session, tenant_id: int, days: int = 30) -> list[dict]:
    """Tema kesfi — kurumun AI saglayici config'ini (LLM + embedding) aktif ederek."""
    tenant = db.get(Tenant, tenant_id)
    ts = tenant.settings if tenant else None
    with ai_config.use_llm(ts, tenant_id, "topics"):
        return _discover_inner(db, tenant_id, days, ts)


def _discover_inner(db: Session, tenant_id: int, days: int, ts: dict | None) -> list[dict]:
    """Son `days` gundeki cagrilarda tema kesfi. Doner: kume listesi (buyukten kucuge).

    Her kume: {baslik, kok_neden, aksiyon, cagri_sayisi, ortalama_puan,
               kategoriler, ornek_cagrilar}
    """
    from datetime import datetime, timedelta

    since = datetime.utcnow() - timedelta(days=days)
    calls = (
        db.query(Call)
        .filter(
            Call.tenant_id == tenant_id,
            Call.status == CallStatus.done,
            Call.summary.isnot(None),
            Call.summary != "",
            Call.created_at >= since,
        )
        .order_by(Call.created_at.desc())
        .limit(MAX_CALLS)
        .all()
    )
    if len(calls) < MIN_CLUSTER_SIZE:
        return []

    summaries = [c.summary or "" for c in calls]
    try:
        vectors = knowledge.embed(summaries, ts)
    except knowledge.KnowledgeError as exc:
        logger.warning("Konu kesfi atlandi (embedding yok): %s", exc)
        return []

    raw = _cluster(vectors, SIMILARITY_THRESHOLD)
    raw = [c for c in raw if len(c) >= MIN_CLUSTER_SIZE]
    raw.sort(key=len, reverse=True)
    raw = raw[:MAX_CLUSTERS]

    out: list[dict] = []
    for indices in raw:
        members = [calls[i] for i in indices]
        scores = [m.total_score for m in members if m.total_score is not None]
        cats: dict[str, int] = {}
        for m in members:
            if m.category:
                cats[m.category] = cats.get(m.category, 0) + 1

        # Temayi LLM'e adlandirt; basarisiz olursa en sik kategoriye duser
        try:
            analiz = generate_json(
                LLMKonuAnalizi, TOPIC_SYSTEM,
                _topic_prompt([m.summary or "" for m in members]),
            )
            baslik, kok, aksiyon = analiz.baslik, analiz.kok_neden, analiz.aksiyon
        except Exception as exc:
            logger.warning("Tema adlandirilamadi: %s", exc)
            top_cat = max(cats, key=cats.get) if cats else "diger"
            baslik, kok, aksiyon = f"{top_cat} kaynakli cagrilar", "", ""

        out.append({
            "baslik": baslik,
            "kok_neden": kok,
            "aksiyon": aksiyon,
            "cagri_sayisi": len(members),
            "ortalama_puan": round(sum(scores) / len(scores), 1) if scores else None,
            "kategoriler": cats,
            "ornek_cagrilar": [
                {"id": m.id, "filename": m.filename, "ozet": (m.summary or "")[:160]}
                for m in members[:3]
            ],
        })
    return out
