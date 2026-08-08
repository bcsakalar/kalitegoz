from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import Integer, cast, func
from sqlalchemy.orm import Session, joinedload

from ..db import get_db
from ..deps import CurrentUser, get_current_user
from ..models import (
    Agent,
    AgentBadge,
    Badge,
    Call,
    CallStatus,
    Role,
    Score,
    Team,
    Tenant,
)
from ..schemas import (
    AgentScorecard,
    AgentSummary,
    BadgeOut,
    CoachingPlanOut,
    CriterionAvg,
    TrendPoint,
    WeakCriterion,
)
from ..services import ai_config
from ..services.llm import LLMError, generate_json


class _CoachingLLM(BaseModel):
    focus: list[str]
    plan: str

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])


def _team_name_map(db: Session, tenant_id: int) -> dict[int, str]:
    return {t.id: t.name for t in db.query(Team).filter(Team.tenant_id == tenant_id).all()}


@router.get("/{agent_id}/coaching-plan", response_model=CoachingPlanOut)
def coaching_plan(agent_id: int, days: int = 30, db: Session = Depends(get_db),
                  user: CurrentUser = Depends(get_current_user)):
    """Temsilcinin tekrarlayan zayif kriterlerinden AI kisisel gelisim plani uretir.
    Kurumun secili AI saglayicisini kullanir. Koçlugu olceklenebilir yapar."""
    agent = db.query(Agent).filter(Agent.id == agent_id, Agent.tenant_id == user.tenant_id).first()
    if agent is None:
        raise HTTPException(404, "Temsilci bulunamadi")
    if user.role == Role.agent and user.agent_id != agent_id:
        raise HTTPException(403, "Bu islem icin yetkiniz yok")
    if user.role == Role.supervisor and user.team_id and agent.team_id != user.team_id:
        raise HTTPException(403, "Bu temsilci sizin takiminizda degil")

    since = datetime.utcnow() - timedelta(days=days)
    rows = (
        db.query(Score.criterion_name, func.avg(Score.score), func.count(Score.id))
        .join(Call, Score.call_id == Call.id)
        .filter(Call.agent_id == agent_id, Call.tenant_id == user.tenant_id,
                Call.status == CallStatus.done, Call.created_at >= since)
        .group_by(Score.criterion_name).order_by(func.avg(Score.score)).all()
    )
    call_count = db.query(func.count(Call.id)).filter(
        Call.agent_id == agent_id, Call.tenant_id == user.tenant_id,
        Call.status == CallStatus.done, Call.created_at >= since).scalar() or 0
    if not rows or call_count < 3:
        raise HTTPException(400, "Yeterli veri yok — kocluk plani icin en az 3 puanli cagri gerekli")

    weak = [WeakCriterion(name=r[0], avg=round(float(r[1] or 0), 1)) for r in rows[:5]]
    weak_txt = "\n".join(f"- {w.name}: ortalama {w.avg}/10" for w in weak)
    system = ("Sen kidemli bir cagri merkezi kalite koçusun. Bir temsilcinin en zayif "
              "kriterlerine bakip KISA, somut, uygulanabilir ve motive edici bir kisisel "
              "gelisim plani uretirsin. Turkce, yalnizca gecerli JSON dondur.")
    user_p = (f"Temsilci: {agent.name}. Son {days} gunde {call_count} degerlendirilmis cagri.\n"
              f"En zayif kriterler:\n{weak_txt}\n\n"
              'Su JSON semasiyla yanit ver: {"focus": ["odak alani", ...(2-3 madde)], '
              '"plan": "3-4 cumlelik somut haftalik gelisim plani"}')
    tenant = db.get(Tenant, user.tenant_id)
    try:
        with ai_config.use_llm(tenant.settings if tenant else None, user.tenant_id, "coaching"):
            result = generate_json(_CoachingLLM, system, user_p)
    except LLMError as exc:
        raise HTTPException(502, f"Kocluk plani uretilemedi (LLM): {exc}")

    return CoachingPlanOut(agent_id=agent.id, agent_name=agent.name, call_count=call_count,
                           weak_criteria=weak, focus=result.focus[:4], plan=result.plan)


@router.get("", response_model=list[AgentSummary])
def list_agents(db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    done = (Call.agent_id == Agent.id) & (Call.status == CallStatus.done)
    q = (
        db.query(
            Agent.id,
            Agent.name,
            func.count(Call.id).label("call_count"),
            func.avg(Call.total_score).label("avg_score"),
            func.max(Call.created_at).label("last_call_at"),
        )
        .outerjoin(Call, done)
        .filter(Agent.tenant_id == user.tenant_id)
    )
    # Temsilci yalnizca kendini gorur; supervisor yalnizca kendi takimini
    if user.role == Role.agent:
        q = q.filter(Agent.id == (user.agent_id or -1))
    elif user.role == Role.supervisor and user.team_id:
        q = q.filter(Agent.team_id == user.team_id)
    rows = q.group_by(Agent.id, Agent.name).order_by(func.avg(Call.total_score).desc().nulls_last()).all()
    return [
        AgentSummary(
            id=r.id, name=r.name, call_count=r.call_count,
            avg_score=round(r.avg_score, 1) if r.avg_score is not None else None,
            last_call_at=r.last_call_at,
        )
        for r in rows
    ]


@router.get("/{agent_id}", response_model=AgentScorecard)
def get_agent(agent_id: int, db: Session = Depends(get_db),
              user: CurrentUser = Depends(get_current_user)):
    agent = (
        db.query(Agent)
        .filter(Agent.id == agent_id, Agent.tenant_id == user.tenant_id)
        .first()
    )
    if agent is None:
        raise HTTPException(404, "Temsilci bulunamadi")
    # Temsilci sadece kendi karnesini gorebilir
    if user.role == Role.agent and user.agent_id != agent_id:
        raise HTTPException(403, "Yalnizca kendi karnenizi gorebilirsiniz")

    done = (Call.agent_id == agent_id) & (Call.status == CallStatus.done)
    stats = db.query(
        func.count(Call.id), func.avg(Call.total_score), func.avg(Call.predicted_csat),
        func.sum(cast(Call.zeroed, Integer)),
        func.sum(cast(Call.is_crisis, Integer)),
    ).filter(done).one()

    day = func.date(Call.created_at)
    trend_rows = (
        db.query(day.label("d"), func.avg(Call.total_score), func.count(Call.id))
        .filter(done, Call.total_score.isnot(None))
        .group_by(day).order_by(day).all()
    )
    crit_rows = (
        db.query(Score.criterion_name, func.avg(Score.score), func.count(Score.id))
        .join(Call, Score.call_id == Call.id)
        .filter(done)
        .group_by(Score.criterion_name).order_by(func.avg(Score.score)).all()
    )
    recent = (
        db.query(Call)
        .options(joinedload(Call.agent), joinedload(Call.campaign))
        .filter(Call.agent_id == agent_id)
        .order_by(Call.created_at.desc()).limit(10).all()
    )
    badges = (
        db.query(Badge.code, Badge.name, Badge.icon, Badge.description, AgentBadge.period)
        .join(AgentBadge, AgentBadge.badge_id == Badge.id)
        .filter(AgentBadge.agent_id == agent_id)
        .order_by(AgentBadge.awarded_at.desc()).all()
    )
    team_names = _team_name_map(db, user.tenant_id)

    # Basit haftalik kocluk ozeti: en zayif kriter uzerinden
    weakest = crit_rows[0] if crit_rows else None
    if weakest and weakest[1] is not None and weakest[1] < 7:
        coaching = (
            f"Bu donem en zayif alanin '{weakest[0]}' (ortalama {weakest[1]:.1f}/10). "
            f"Onumuzdeki hafta bu kritere odaklan; benzer cagrilarda yuksek puan alan "
            f"ornekleri incele."
        )
    else:
        coaching = "Bu donem tum kriterlerde dengeli ve guclu bir performans sergiledin. Boyle devam!"

    return AgentScorecard(
        id=agent.id, name=agent.name, team_name=team_names.get(agent.team_id),
        call_count=stats[0] or 0,
        avg_score=round(stats[1], 1) if stats[1] is not None else None,
        avg_csat=round(stats[2], 1) if stats[2] is not None else None,
        zeroed_count=int(stats[3] or 0), crisis_count=int(stats[4] or 0),
        trend=[TrendPoint(date=str(d), avg_score=round(a, 1), call_count=c) for d, a, c in trend_rows],
        criteria=[CriterionAvg(criterion_name=n, avg_score=round(a, 2), count=c) for n, a, c in crit_rows],
        badges=[BadgeOut(code=b[0], name=b[1], icon=b[2], description=b[3], period=b[4] or "") for b in badges],
        recent_calls=recent,
        weekly_coaching=coaching,
    )
