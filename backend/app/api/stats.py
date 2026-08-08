from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import CurrentUser, get_current_user
from ..models import Agent, Call, CallStatus, Role
from ..schemas import Overview, TrendPoint

router = APIRouter(prefix="/api/v1/stats", tags=["stats"])


def _scope(q, user: CurrentUser):
    q = q.filter(Call.tenant_id == user.tenant_id)
    if user.role == Role.agent:
        q = q.filter(Call.agent_id == (user.agent_id or -1))
    elif user.role == Role.supervisor and user.team_id:
        q = q.join(Agent, Call.agent_id == Agent.id).filter(Agent.team_id == user.team_id)
    return q


@router.get("/overview", response_model=Overview)
def overview(db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    total = _scope(db.query(func.count(Call.id)), user).scalar() or 0

    status_rows = dict(
        _scope(db.query(Call.status, func.count(Call.id)), user).group_by(Call.status).all()
    )
    done = status_rows.get(CallStatus.done, 0)
    failed = status_rows.get(CallStatus.failed, 0)
    processing = total - done - failed

    done_q = lambda base: _scope(base, user).filter(Call.status == CallStatus.done)  # noqa: E731

    avg_score = done_q(db.query(func.avg(Call.total_score))).scalar()
    avg_csat = done_q(db.query(func.avg(Call.predicted_csat))).scalar()
    low = done_q(db.query(func.count(Call.id))).filter(Call.total_score < 60).scalar() or 0
    zeroed = done_q(db.query(func.count(Call.id))).filter(Call.zeroed.is_(True)).scalar() or 0
    crisis = done_q(db.query(func.count(Call.id))).filter(Call.is_crisis.is_(True)).scalar() or 0

    cat_rows = (
        done_q(db.query(Call.category, func.count(Call.id)))
        .filter(Call.category.isnot(None))
        .group_by(Call.category).all()
    )

    since = datetime.utcnow() - timedelta(days=14)
    day = func.date(Call.created_at)
    trend_rows = (
        done_q(db.query(day.label("d"), func.avg(Call.total_score), func.count(Call.id)))
        .filter(Call.total_score.isnot(None), Call.created_at >= since)
        .group_by(day).order_by(day).all()
    )

    return Overview(
        total_calls=total, done_calls=done, processing_calls=processing, failed_calls=failed,
        avg_score=round(avg_score, 1) if avg_score is not None else None,
        low_score_calls=low, zeroed_calls=zeroed, crisis_calls=crisis,
        avg_csat=round(avg_csat, 1) if avg_csat is not None else None,
        category_dist={c: n for c, n in cat_rows},
        trend=[TrendPoint(date=str(d), avg_score=round(a, 1), call_count=c) for d, a, c in trend_rows],
    )
