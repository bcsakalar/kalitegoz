"""Supervisor kokpiti (ekip KPI duvari) + liderlik tablosu (gamification)."""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import Integer, cast, func
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import CurrentUser, get_current_user, require_staff
from ..models import Agent, Alert, Call, CallStatus, Role, Team, Violation
from ..schemas import LeaderboardRow, SupervisorCockpit

router = APIRouter(prefix="/api/v1", tags=["supervisor"])


def _points(avg_score: float, call_count: int, crisis: int) -> float:
    """Lig puani: kalite agirlikli + hacim bonusu + kriz yonetimi bonusu."""
    return round((avg_score or 0) + min(call_count, 50) * 0.2 + crisis * 3, 1)


def _leaderboard_rows(db: Session, tenant_id: int, team_id: int | None, since: datetime | None):
    done = (Call.agent_id == Agent.id) & (Call.status == CallStatus.done)
    if since is not None:
        done = done & (Call.created_at >= since)
    q = (
        db.query(
            Agent.id, Agent.name, Agent.team_id,
            func.avg(Call.total_score), func.count(Call.id),
            func.sum(cast(Call.is_crisis, Integer)),
        )
        .outerjoin(Call, done)
        .filter(Agent.tenant_id == tenant_id)
    )
    if team_id:
        q = q.filter(Agent.team_id == team_id)
    rows = q.group_by(Agent.id, Agent.name, Agent.team_id).all()
    team_names = {t.id: t.name for t in db.query(Team).filter(Team.tenant_id == tenant_id).all()}
    result = []
    for aid, name, tid, avg, cnt, crisis in rows:
        avg = round(avg or 0, 1)
        crisis = int(crisis or 0)
        result.append(LeaderboardRow(
            agent_id=aid, agent_name=name, team_name=team_names.get(tid),
            avg_score=avg, call_count=cnt or 0, crisis_handled=crisis,
            points=_points(avg, cnt or 0, crisis),
        ))
    result.sort(key=lambda r: r.points, reverse=True)
    return result


@router.get("/supervisor/topics")
def discover_topics(days: int = 30, refresh: bool = False,
                    db: Session = Depends(get_db),
                    user: CurrentUser = Depends(require_staff)):
    """Konu kesfi: "musteriler BU DONEM neden ariyor?" (kok-neden kumeleme).

    Embedding + LLM cagrisi gerektirir; sonuc Redis'te 6 saat cache'lenir.
    refresh=true ile yeniden hesaplatilir.
    """
    import json

    import redis as redis_lib

    from ..config import settings
    from ..services import topics

    cache_key = f"kalitegoz:topics:{user.tenant_id}:{days}"
    try:
        r = redis_lib.from_url(settings.redis_url)
        if not refresh:
            cached = r.get(cache_key)
            if cached:
                return {"cached": True, "topics": json.loads(cached)}
    except Exception:
        r = None  # Redis yoksa cache'siz devam

    result = topics.discover(db, user.tenant_id, days)
    if r is not None:
        try:
            r.setex(cache_key, 6 * 3600, json.dumps(result, ensure_ascii=False))
        except Exception:
            pass
    return {"cached": False, "topics": result}


@router.get("/leaderboard", response_model=list[LeaderboardRow])
def leaderboard(
    period: str = Query(default="all", pattern="^(week|month|all)$"),
    team_id: int | None = None,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    since = None
    if period == "week":
        since = datetime.utcnow() - timedelta(days=7)
    elif period == "month":
        since = datetime.utcnow() - timedelta(days=30)
    # Supervisor varsayilan olarak kendi takimi
    if user.role == Role.supervisor and team_id is None:
        team_id = user.team_id
    return _leaderboard_rows(db, user.tenant_id, team_id, since)


@router.get("/supervisor/cockpit", response_model=SupervisorCockpit)
def cockpit(team_id: int | None = None, db: Session = Depends(get_db),
            user: CurrentUser = Depends(require_staff)):
    if user.role == Role.supervisor:
        team_id = user.team_id  # supervisor daima kendi takimi

    done = db.query(Call).filter(Call.tenant_id == user.tenant_id, Call.status == CallStatus.done)
    if team_id:
        done = done.join(Agent, Call.agent_id == Agent.id).filter(Agent.team_id == team_id)

    base = done.with_entities(
        func.avg(Call.total_score), func.avg(Call.predicted_csat),
        func.sum(cast(Call.is_crisis, Integer)), func.sum(cast(Call.zeroed, Integer)),
        func.avg(Call.duration_sec), func.count(Call.id),
    ).one()
    avg_score, avg_csat, crisis, zeroed, avg_dur, total = base

    # FCR: musteri referansi varsa GERCEK (tekrar arama bazli), yoksa tahmini
    from ..services import fcr as fcr_service

    fcr, fcr_is_real = fcr_service.compute_fcr(db, user.tenant_id, team_id)

    # Ihlal dagilimi
    vq = db.query(Violation.category, func.count(Violation.id)).filter(
        Violation.tenant_id == user.tenant_id)
    if team_id:
        vq = vq.join(Call, Violation.call_id == Call.id).join(
            Agent, Call.agent_id == Agent.id).filter(Agent.team_id == team_id)
    violation_dist = {cat or "diger": n for cat, n in vq.group_by(Violation.category).all()}

    aq = db.query(func.count(Alert.id)).filter(
        Alert.tenant_id == user.tenant_id, Alert.is_read.is_(False))
    if team_id:
        aq = aq.filter((Alert.team_id == team_id) | (Alert.team_id.is_(None)))
    unread = aq.scalar() or 0

    repeat_calls = done.filter(Call.is_repeat.is_(True)).count()

    return SupervisorCockpit(
        team_id=team_id,
        avg_score=round(avg_score, 1) if avg_score is not None else None,
        avg_csat=round(avg_csat, 1) if avg_csat is not None else None,
        crisis_calls=int(crisis or 0), zeroed_calls=int(zeroed or 0),
        avg_handle_sec=round(avg_dur, 1) if avg_dur is not None else None,
        fcr_estimate=fcr, fcr_is_real=fcr_is_real, repeat_calls=repeat_calls,
        unread_alerts=unread,
        violation_dist=violation_dist,
        agents=_leaderboard_rows(db, user.tenant_id, team_id, None),
    )
