"""Derin analitik API (Dalga 3a VoC + 3b dashboard).

Supervisor otomatik olarak kendi takimiyla sinirlanir; admin/quality tenant
genelini gorur. Boylece drill-down yetkiyle tutarli kalir.
"""

from collections import Counter
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from pydantic import BaseModel

from ..db import get_db
from ..deps import CurrentUser, require_staff
from ..models import Agent, Appeal, AppealStatus, Call, CallStatus, Role, Tenant
from ..schemas import (
    AppealAnalytics, ChurnCall, ChurnSummary,
    CorrelationInsight, EmergingTopic, ExecSummary,
)
from ..services import stats_honesty, ai_config, analytics
from ..services.llm import LLMError, generate_json

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


def _team_scope(user: CurrentUser) -> int | None:
    """Supervisor kendi takimiyla sinirli; digerleri tenant geneli (None)."""
    if user.role == Role.supervisor:
        return user.team_id
    return None


@router.get("/emerging", response_model=list[EmergingTopic])
def emerging(days: int = Query(7, ge=1, le=90),
             db: Session = Depends(get_db), user: CurrentUser = Depends(require_staff)):
    """Yukselen konular/sorunlar: son `days` gunu onceki ayni uzunluktaki donemle
    kiyaslar; kategori + niyet etiketlerinde ani artislari (proaktif erken uyari) doner."""
    now = datetime.utcnow()
    now_start = now - timedelta(days=days)
    prev_start = now - timedelta(days=2 * days)
    q = db.query(Call.category, Call.intent_tags, Call.created_at).filter(
        Call.tenant_id == user.tenant_id,
        Call.status == CallStatus.done,
        Call.created_at >= prev_start,
    )
    team_id = _team_scope(user)
    if team_id is not None:
        team_agents = select(Agent.id).where(
            Agent.tenant_id == user.tenant_id, Agent.team_id == team_id)
        q = q.filter(Call.agent_id.in_(team_agents))

    now_cat, prev_cat, now_int, prev_int = Counter(), Counter(), Counter(), Counter()
    for cat, tags, created in q.all():
        recent = created >= now_start
        if cat:
            (now_cat if recent else prev_cat)[cat] += 1
        for tg in (tags or []):
            (now_int if recent else prev_int)[tg] += 1

    out: list[EmergingTopic] = []

    def _collect(nowc: Counter, prevc: Counter, kind: str) -> None:
        for label, n in nowc.items():
            p = prevc.get(label, 0)
            if n > p and n >= 2:  # yukselen + asgari hacim (gurultu onleme)
                out.append(EmergingTopic(
                    label=label, kind=kind, now_count=n, prev_count=p,
                    change_pct=round((n - p) / max(p, 1) * 100.0, 0)))

    _collect(now_cat, prev_cat, "kategori")
    _collect(now_int, prev_int, "niyet")
    out.sort(key=lambda x: (x.change_pct, x.now_count), reverse=True)
    return out[:12]


# Korelasyon adaylari: (metrics JSON anahtari | Call kolonu, insan-okur etiket)
_CORR_FACTORS = [
    ("temsilci_konusma_orani", "Temsilci konuşma oranı (%)"),
    ("sessizlik_sn", "Toplam sessizlik (sn)"),
    ("temsilci_kesinti", "Temsilci kesintileri"),
    ("temsilci_kelime_dk", "Konuşma hızı (kelime/dk)"),
    ("temsilci_bagirma_sayisi", "Temsilci ses yükseltme"),
    ("duration_sec", "Görüşme süresi (sn)"),
]


def _pearson(pairs: list[tuple[float, float]]) -> float | None:
    n = len(pairs)
    if n < 8:
        return None
    mx = sum(x for x, _ in pairs) / n
    my = sum(y for _, y in pairs) / n
    cov = sum((x - mx) * (y - my) for x, y in pairs)
    vx = sum((x - mx) ** 2 for x, _ in pairs)
    vy = sum((y - my) ** 2 for _, y in pairs)
    if vx <= 0 or vy <= 0:
        return None
    return cov / (vx ** 0.5 * vy ** 0.5)


@router.get("/correlations", response_model=list[CorrelationInsight])
def correlations(days: int = Query(90, ge=7, le=365),
                 db: Session = Depends(get_db), user: CurrentUser = Depends(require_staff)):
    """Hangi görüşme davranışı kalite puanıyla ilişkili? Geçmiş çağrılardan Pearson
    korelasyonu hesaplar (ör. 'temsilci çok konuşunca puan düşüyor'). Nedensellik değil
    ilişki; yöneticiye nereye odaklanacağını gösterir."""
    since = datetime.utcnow() - timedelta(days=days)
    q = db.query(Call.metrics, Call.duration_sec, Call.total_score).filter(
        Call.tenant_id == user.tenant_id, Call.status == CallStatus.done,
        Call.total_score.isnot(None), Call.created_at >= since)
    team_id = _team_scope(user)
    if team_id is not None:
        q = q.filter(Call.agent_id.in_(
            select(Agent.id).where(Agent.tenant_id == user.tenant_id, Agent.team_id == team_id)))
    rows = q.all()

    out: list[CorrelationInsight] = []
    for key, label in _CORR_FACTORS:
        pairs: list[tuple[float, float]] = []
        for metrics, dur, score in rows:
            if key == "duration_sec":
                x = dur
            else:
                x = (metrics or {}).get(key)
            if x is None or score is None:
                continue
            try:
                pairs.append((float(x), float(score)))
            except (TypeError, ValueError):
                continue
        # B8: n < 30 ise KATSAYI GOSTERILMEZ. Onceden n=24 ile "+0.68 guclu
        # iliski" deniyordu; bu, istatistiksel olarak savunulamaz ve bir cagri
        # merkezi muduru bunu gorup urune guvenmeyi birakir.
        olcum = stats_honesty.korelasyon(pairs, label)
        if not olcum.yeterli:
            # Egilim gozlemi gosterilir ama katsayi ve "guclu iliski" iddiasi YOK
            if len(pairs) >= 5:
                out.append(CorrelationInsight(
                    factor=key, label=label, corr=None, n=olcum.n,
                    direction="unknown", strength="belirsiz",
                    insight=olcum.aciklama, significant=False))
            continue

        r = olcum.deger
        if abs(r) < 0.15:   # zayif/gurultu iliskileri gizle
            continue
        a = abs(r)
        strength = "guclu" if a >= 0.5 else ("orta" if a >= 0.3 else "zayif")
        direction = "positive" if r > 0 else "negative"
        out.append(CorrelationInsight(
            factor=key, label=label, corr=round(r, 2), n=olcum.n,
            direction=direction, strength=strength,
            insight=olcum.aciklama, significant=True))
    out.sort(key=lambda c: (c.significant, abs(c.corr or 0)), reverse=True)
    return out


class _ExecLLM(BaseModel):
    headline: str
    wins: list[str]
    risks: list[str]
    actions: list[str]


@router.get("/exec-summary", response_model=ExecSummary)
def exec_summary(days: int = Query(30, ge=7, le=180),
                 db: Session = Depends(get_db), user: CurrentUser = Depends(require_staff)):
    """Dönemin yönetici özeti: temel metrikleri toplayıp kurumun LLM'iyle kısa,
    aksiyon odaklı bir yönetici brifingi üretir (başlık + kazanımlar + riskler + aksiyonlar)."""
    from sqlalchemy import Integer, cast, func

    from ..models import Score

    since = datetime.utcnow() - timedelta(days=days)
    base = db.query(Call).filter(Call.tenant_id == user.tenant_id,
                                 Call.status == CallStatus.done, Call.created_at >= since)
    team_id = _team_scope(user)
    if team_id is not None:
        base = base.filter(Call.agent_id.in_(
            select(Agent.id).where(Agent.tenant_id == user.tenant_id, Agent.team_id == team_id)))

    stats = base.with_entities(
        func.count(Call.id), func.avg(Call.total_score), func.avg(Call.predicted_csat),
        func.sum(cast(Call.zeroed, Integer)), func.sum(cast(Call.is_crisis, Integer)),
    ).one()
    n = stats[0] or 0
    avg_score = round(stats[1], 1) if stats[1] is not None else None
    if n < 3:
        return ExecSummary(period_days=days, call_count=n, avg_score=avg_score,
                           headline="Bu dönemde özet için yeterli veri yok.",
                           wins=[], risks=[], actions=[], generated_at=datetime.utcnow())

    cat_rows = (base.with_entities(Call.category, func.count(Call.id))
                .group_by(Call.category).order_by(func.count(Call.id).desc()).limit(5).all())
    weak = (db.query(Score.criterion_name, func.avg(Score.score))
            .join(Call, Score.call_id == Call.id)
            .filter(Call.tenant_id == user.tenant_id, Call.status == CallStatus.done,
                    Call.created_at >= since)
            .group_by(Score.criterion_name).order_by(func.avg(Score.score)).limit(4).all())

    cat_str = ", ".join(f"{c or 'diger'} x{k}" for c, k in cat_rows)
    weak_str = ", ".join(f"{n2}({round(float(a or 0), 1)})" for n2, a in weak)
    csat_str = round(stats[2], 1) if stats[2] else "-"
    facts = (
        f"Dönem: son {days} gün\nDeğerlendirilen çağrı: {n}\n"
        f"Ortalama kalite: {avg_score}/100\n"
        f"Ortalama CSAT: {csat_str}/5\n"
        f"Sıfırlanan (kritik ihlal): {int(stats[3] or 0)}\nKriz çağrısı: {int(stats[4] or 0)}\n"
        f"En sık kategoriler: {cat_str}\n"
        f"En zayıf kriterler: {weak_str}"
    )
    system = ("Sen bir çağrı merkezi kalite direktörünün analistisin. Verilen dönem "
              "metriklerinden ÜST YÖNETİME kısa bir brifing yazarsın. Türkçe, net, "
              "abartısız. Yalnızca geçerli JSON döndür.")
    user_p = (facts + "\n\nŞu JSON şemasıyla yanıt ver: "
              '{"headline": "tek cümle genel durum", '
              '"wins": ["1-3 kazanım"], "risks": ["1-3 risk"], '
              '"actions": ["1-3 somut aksiyon önerisi"]}')
    tenant = db.get(Tenant, user.tenant_id)
    try:
        with ai_config.use_llm(tenant.settings if tenant else None, user.tenant_id, "summary"):
            r = generate_json(_ExecLLM, system, user_p)
    except LLMError as exc:
        raise HTTPException(502, f"Yönetici özeti üretilemedi (LLM): {exc}")
    return ExecSummary(period_days=days, call_count=n, avg_score=avg_score,
                       headline=r.headline, wins=r.wins[:3], risks=r.risks[:3],
                       actions=r.actions[:3], generated_at=datetime.utcnow())


@router.get("/churn", response_model=ChurnSummary)
def churn(days: int = Query(30, ge=1, le=365),
          db: Session = Depends(get_db), user: CurrentUser = Depends(require_staff)):
    """Churn/retention panosu: kayıp riski dağılımı + takip listesi. Yüksek riskli
    müşterileri (düşük puan + olumsuz seyir) proaktif geri arama için öne çıkarır."""
    since = datetime.utcnow() - timedelta(days=days)
    q = db.query(Call).filter(Call.tenant_id == user.tenant_id, Call.status == CallStatus.done,
                              Call.churn_risk.isnot(None), Call.created_at >= since)
    team_id = _team_scope(user)
    if team_id is not None:
        q = q.filter(Call.agent_id.in_(
            select(Agent.id).where(Agent.tenant_id == user.tenant_id, Agent.team_id == team_id)))

    counts = {"yuksek": 0, "orta": 0, "dusuk": 0}
    for (risk,) in q.with_entities(Call.churn_risk).all():
        if risk in counts:
            counts[risk] += 1
    total = sum(counts.values())
    high_calls = (q.filter(Call.churn_risk == "yuksek")
                  .order_by(Call.total_score.asc().nulls_first(), Call.created_at.desc())
                  .limit(20).all())
    agent_names = {a.id: a.name for a in db.query(Agent).filter(Agent.tenant_id == user.tenant_id)}
    retention = [ChurnCall(
        id=c.id, filename=c.filename, agent_name=agent_names.get(c.agent_id),
        category=c.category, churn_risk=c.churn_risk, total_score=c.total_score,
        predicted_csat=c.predicted_csat, created_at=c.created_at) for c in high_calls]
    return ChurnSummary(
        period_days=days, high=counts["yuksek"], medium=counts["orta"], low=counts["dusuk"],
        total_scored=total, high_rate=round(counts["yuksek"] / total * 100, 1) if total else 0.0,
        retention_list=retention)


@router.get("/appeals", response_model=AppealAnalytics)
def appeals(days: int = Query(90, ge=1, le=365),
            db: Session = Depends(get_db), user: CurrentUser = Depends(require_staff)):
    """İtiraz analitiği: temsilcilerin AI puanına itirazları ne kadar, ne oranda kabul
    ediliyor (overturn) ve ortalama çözüm süresi. Yüksek overturn = AI kalibrasyon sinyali."""
    since = datetime.utcnow() - timedelta(days=days)
    rows = db.query(Appeal).filter(Appeal.tenant_id == user.tenant_id,
                                   Appeal.created_at >= since).all()
    total = len(rows)
    op = sum(1 for a in rows if a.status == AppealStatus.open)
    acc = sum(1 for a in rows if a.status == AppealStatus.accepted)
    rej = sum(1 for a in rows if a.status == AppealStatus.rejected)
    resolved = [a for a in rows if a.resolved_at is not None]
    avg_days = (round(sum((a.resolved_at - a.created_at).total_seconds() for a in resolved)
                      / len(resolved) / 86400, 1) if resolved else None)
    return AppealAnalytics(
        period_days=days, total=total, open=op, accepted=acc, rejected=rej,
        overturn_rate=round(acc / (acc + rej) * 100, 1) if (acc + rej) else 0.0,
        avg_resolution_days=avg_days)


@router.get("/timeseries")
def timeseries(
    metric: str = Query("score", pattern="^(score|csat|effort)$"),
    days: int = Query(30, ge=1, le=365),
    bucket: str = Query("day", pattern="^(day|week)$"),
    db: Session = Depends(get_db), user: CurrentUser = Depends(require_staff),
):
    return analytics.metric_timeseries(
        db, user.tenant_id, metric, days, bucket, _team_scope(user))


@router.get("/voc")
def voc(days: int = Query(14, ge=1, le=180), db: Session = Depends(get_db),
        user: CurrentUser = Depends(require_staff)):
    """Musterinin Sesi — kategori/niyet siklik trendi (artan/azalan)."""
    return analytics.category_trends(db, user.tenant_id, days, _team_scope(user))


@router.get("/emotions")
def emotions(days: int = Query(30, ge=1, le=365), db: Session = Depends(get_db),
             user: CurrentUser = Depends(require_staff)):
    return {
        "emotions": analytics.emotion_distribution(db, user.tenant_id, days, _team_scope(user)),
        "churn": analytics.churn_summary(db, user.tenant_id, days, _team_scope(user)),
    }


@router.get("/cohort")
def cohort(dimension: str = Query("team", pattern="^(team|campaign)$"),
           days: int = Query(30, ge=1, le=365), db: Session = Depends(get_db),
           user: CurrentUser = Depends(require_staff)):
    return analytics.cohort_compare(db, user.tenant_id, dimension, days)
