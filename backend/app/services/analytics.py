"""Derin analitik: zaman serisi, VoC konu trendi, duygu dagilimi, kohort.

Mevcut kokpit anlik bir goruntu verir; bu modul ZAMAN boyutunu ekler:
- metric_timeseries : gunluk/haftalik ortalama puan/CSAT/hacim
- category_trends   : VoC — konu/kategori sikligi son pencerede arttri mi azaldi mi
- emotion_distribution : 8 duygunun dagilimi
- cohort_compare    : takim/kampanya kiyaslamasi (drill-down icin)

Hepsi tenant-izole; supervisor ise team_id ile daraltilir (cagiran verir).
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import Agent, Call, CallStatus, Campaign, Team

METRICS = {"score": Call.total_score, "csat": Call.predicted_csat, "effort": Call.customer_effort}


def _base_query(db: Session, tenant_id: int, team_id: int | None = None, since=None):
    q = db.query(Call).filter(
        Call.tenant_id == tenant_id,
        Call.status == CallStatus.done,
    )
    if since is not None:
        q = q.filter(Call.created_at >= since)
    if team_id is not None:
        team_agents = db.query(Agent.id).filter(
            Agent.tenant_id == tenant_id, Agent.team_id == team_id
        )
        q = q.filter(Call.agent_id.in_(team_agents))
    return q


def metric_timeseries(
    db: Session, tenant_id: int, metric: str = "score", days: int = 30,
    bucket: str = "day", team_id: int | None = None,
) -> list[dict]:
    """Gunluk/haftalik ortalama metrik + cagri hacmi.

    bucket: 'day' | 'week'. Bos gunler atlanir (grafik tarafi bosluklari yonetir).
    """
    col = METRICS.get(metric, Call.total_score)
    since = datetime.utcnow() - timedelta(days=days)
    rows = _base_query(db, tenant_id, team_id, since).with_entities(
        Call.created_at, col
    ).all()

    buckets: dict[str, list[float]] = defaultdict(list)
    counts: dict[str, int] = defaultdict(int)
    for created, value in rows:
        if created is None:
            continue
        if bucket == "week":
            monday = created - timedelta(days=created.weekday())
            key = monday.strftime("%Y-%m-%d")
        else:
            key = created.strftime("%Y-%m-%d")
        counts[key] += 1
        if value is not None:
            buckets[key].append(float(value))

    out = []
    for key in sorted(counts):
        vals = buckets.get(key, [])
        out.append({
            "date": key,
            "avg": round(sum(vals) / len(vals), 1) if vals else None,
            "count": counts[key],
        })
    return out


def category_trends(db: Session, tenant_id: int, days: int = 14,
                    team_id: int | None = None) -> list[dict]:
    """VoC: son `days` penceredeki kategori sikligini onceki esit pencereyle kiyasla.

    'iptal talepleri son 2 haftada %40 artti' tarzi trendi ortaya cikarir.
    Ayrica niyet etiketleri de ayni mantikla trendlenir.
    """
    now = datetime.utcnow()
    recent_start = now - timedelta(days=days)
    prior_start = now - timedelta(days=2 * days)

    def _counts(start, end):
        cat = Counter()
        intent = Counter()
        rows = _base_query(db, tenant_id, team_id).filter(
            Call.created_at >= start, Call.created_at < end
        ).with_entities(Call.category, Call.intent_tags).all()
        for category, tags in rows:
            if category:
                cat[category] += 1
            for tag in (tags or []):
                intent[tag] += 1
        return cat, intent

    recent_cat, recent_int = _counts(recent_start, now)
    prior_cat, prior_int = _counts(prior_start, recent_start)

    def _trend(recent: Counter, prior: Counter, kind: str) -> list[dict]:
        keys = set(recent) | set(prior)
        out = []
        for k in keys:
            r, p = recent.get(k, 0), prior.get(k, 0)
            if p == 0:
                change = 100.0 if r > 0 else 0.0
            else:
                change = round(100 * (r - p) / p, 1)
            out.append({"kind": kind, "label": k, "recent": r, "prior": p, "change_pct": change})
        return sorted(out, key=lambda x: x["recent"], reverse=True)

    return _trend(recent_cat, prior_cat, "category") + _trend(recent_int, prior_int, "intent")


def emotion_distribution(db: Session, tenant_id: int, days: int = 30,
                         team_id: int | None = None) -> dict[str, int]:
    since = datetime.utcnow() - timedelta(days=days)
    rows = _base_query(db, tenant_id, team_id, since).with_entities(
        Call.emotion, func.count(Call.id)
    ).group_by(Call.emotion).all()
    return {(e or "notr"): n for e, n in rows}


def churn_summary(db: Session, tenant_id: int, days: int = 30,
                  team_id: int | None = None) -> dict[str, int]:
    since = datetime.utcnow() - timedelta(days=days)
    rows = _base_query(db, tenant_id, team_id, since).with_entities(
        Call.churn_risk, func.count(Call.id)
    ).group_by(Call.churn_risk).all()
    out = {"dusuk": 0, "orta": 0, "yuksek": 0}
    for risk, n in rows:
        if risk in out:
            out[risk] = n
    return out


def cohort_compare(db: Session, tenant_id: int, dimension: str = "team",
                   days: int = 30) -> list[dict]:
    """Takim veya kampanya bazli kiyaslama (drill-down icin).

    Her kohort icin: cagri sayisi, ortalama puan, ortalama CSAT, kriz sayisi.
    """
    since = datetime.utcnow() - timedelta(days=days)
    base = _base_query(db, tenant_id, None, since)

    # Cagri satirlarini bir kez cekip Python tarafinda topla — is_crisis toplami
    # icin veritabani-bagimsiz kalir (SQLite/Postgres ayni davranir).
    if dimension == "campaign":
        names = {c.id: c.name for c in db.query(Campaign).filter(Campaign.tenant_id == tenant_id).all()}
        key_of = lambda row: names.get(row[0], "Kampanyasiz")
        rows = base.with_entities(
            Call.campaign_id, Call.total_score, Call.predicted_csat, Call.is_crisis
        ).all()
    else:  # team
        agent_team = {a.id: a.team_id for a in db.query(Agent).filter(Agent.tenant_id == tenant_id).all()}
        team_names = {t.id: t.name for t in db.query(Team).filter(Team.tenant_id == tenant_id).all()}
        key_of = lambda row: team_names.get(agent_team.get(row[0]), "Takimsiz")
        rows = base.with_entities(
            Call.agent_id, Call.total_score, Call.predicted_csat, Call.is_crisis
        ).all()

    agg: dict = defaultdict(lambda: {"count": 0, "score_sum": 0.0, "score_n": 0,
                                     "csat_sum": 0.0, "csat_n": 0, "crisis": 0})
    for row in rows:
        _, score, csat, crisis = row
        a = agg[key_of(row)]
        a["count"] += 1
        if score is not None:
            a["score_sum"] += float(score); a["score_n"] += 1
        if csat is not None:
            a["csat_sum"] += float(csat); a["csat_n"] += 1
        if crisis:
            a["crisis"] += 1

    out = [{
        "label": label,
        "count": a["count"],
        "avg_score": round(a["score_sum"] / a["score_n"], 1) if a["score_n"] else None,
        "avg_csat": round(a["csat_sum"] / a["csat_n"], 2) if a["csat_n"] else None,
        "crisis": a["crisis"],
    } for label, a in agg.items()]
    return sorted(out, key=lambda x: (x["avg_score"] or 0), reverse=True)
