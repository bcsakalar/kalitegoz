"""Gamification: puan, seri (streak), challenge ilerlemesi.

Mevcut rozet/lig sistemine derinlik ekler. Hepsi cagri verisinden TURETILIR
(ayri sayac tutulmaz), boylece her zaman guncel ve manipulasyona kapali.

- points     : temsilcinin donem puani (kalite + hacim + kriz yonetimi)
- streak     : ust uste esik ustu 'iyi' cagri sayisi (motivasyon)
- challenges : aktif hedeflerin ilerlemesi
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from ..models import Call, CallStatus, Challenge

GOOD_SCORE = 80.0  # 'iyi cagri' esigi (streak icin)


def points(avg_score: float | None, call_count: int, crisis_handled: int) -> int:
    """Basit, seffaf puan formulu.

    Kalite agirlikli (ortalama puan x hacim carpani) + kriz yonetimi bonusu.
    Supervisor lig siralamasiyla ayni ruh; burada temsilciye gosterilecek
    tek sayi.
    """
    if not call_count or avg_score is None:
        return 0
    # Hacim carpani: cok cagri = daha guvenilir ortalama (log benzeri, sinirli)
    volume = min(1.5, 1.0 + call_count / 100)
    base = avg_score * volume
    return int(round(base + crisis_handled * 5))


def current_streak(db: Session, agent_id: int, threshold: float = GOOD_SCORE) -> int:
    """En son cagridan geriye dogru KESINTISIZ esik-ustu cagri sayisi.

    Ilk esik-alti cagrida seri kirilir. Motivasyon gostergesi: '7 cagridir 80+'.
    """
    calls = (
        db.query(Call.total_score)
        .filter(
            Call.agent_id == agent_id,
            Call.status == CallStatus.done,
            Call.total_score.isnot(None),
        )
        .order_by(Call.created_at.desc())
        .limit(200)
        .all()
    )
    streak = 0
    for (score,) in calls:
        if score is not None and score >= threshold:
            streak += 1
        else:
            break
    return streak


def _challenge_progress(db: Session, ch: Challenge, agent_id: int) -> int:
    """Bir challenge'in bir temsilci icin ilerlemesi (metric'e gore)."""
    q = db.query(Call).filter(
        Call.agent_id == agent_id,
        Call.status == CallStatus.done,
        Call.created_at >= ch.starts_at,
    )
    if ch.ends_at:
        q = q.filter(Call.created_at <= ch.ends_at)

    if ch.metric == "call_count":
        return q.count()
    if ch.metric == "score_above":
        return q.filter(Call.total_score >= ch.threshold).count()
    if ch.metric == "zero_violations":
        return q.filter(Call.zeroed.is_(False), Call.total_score >= ch.threshold).count()
    if ch.metric == "avg_score":
        scores = [s for (s,) in q.with_entities(Call.total_score).all() if s is not None]
        return int(round(sum(scores) / len(scores))) if scores else 0
    return 0


def active_challenges(db: Session, tenant_id: int, agent_id: int,
                      team_id: int | None = None) -> list[dict]:
    """Temsilci icin gecerli aktif challenge'lar + ilerleme."""
    now = datetime.utcnow()
    q = db.query(Challenge).filter(
        Challenge.tenant_id == tenant_id,
        Challenge.is_active.is_(True),
    )
    out = []
    for ch in q.all():
        if ch.ends_at and ch.ends_at < now:
            continue
        if ch.team_id is not None and ch.team_id != team_id:
            continue
        progress = _challenge_progress(db, ch, agent_id)
        out.append({
            "id": ch.id,
            "title": ch.title,
            "description": ch.description,
            "metric": ch.metric,
            "target": ch.target,
            "progress": progress,
            "completed": progress >= ch.target,
            "reward_points": ch.reward_points,
            "ends_at": ch.ends_at.isoformat() if ch.ends_at else None,
        })
    return out


def agent_gamification(db: Session, tenant_id: int, agent_id: int,
                       team_id: int | None = None, days: int = 30) -> dict:
    """Temsilci icin toplu gamification ozeti (self-servis panelinde gosterilir)."""
    from sqlalchemy import func

    since = datetime.utcnow() - timedelta(days=days)
    base = db.query(Call).filter(
        Call.agent_id == agent_id, Call.status == CallStatus.done,
        Call.created_at >= since,
    )
    avg, n = base.with_entities(func.avg(Call.total_score), func.count(Call.id)).one()
    crisis = base.filter(Call.is_crisis.is_(True)).count()
    return {
        "points": points(float(avg) if avg else None, int(n), int(crisis or 0)),
        "streak": current_streak(db, agent_id),
        "challenges": active_challenges(db, tenant_id, agent_id, team_id),
    }
