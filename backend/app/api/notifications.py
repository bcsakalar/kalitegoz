"""Bildirim merkezi: kullaniciya ait tum aksiyon/uyarilari tek akista toplar.

Kaynaklar: okunmamis uyarilar (Alert), kullaniciya atanmis QA incelemeleri
(ReviewAssignment), temsilcinin acik koclugu (CoachingTask) ve kalite/admin icin
acik itirazlar (Appeal). Header'daki zil rozeti = unread_count.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import CurrentUser, get_current_user
from ..models import (
    Alert, Appeal, AppealStatus, CoachingTask, ReviewAssignment,
    ReviewStatus, Role, TaskStatus,
)
from ..schemas import NotificationFeed, NotificationItem

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


@router.get("", response_model=NotificationFeed)
def feed(limit: int = 40, db: Session = Depends(get_db),
         user: CurrentUser = Depends(get_current_user)):
    items: list[NotificationItem] = []
    is_staff = user.role != Role.agent

    if is_staff:
        aq = db.query(Alert).filter(Alert.tenant_id == user.tenant_id, Alert.is_read.is_(False),
        Alert.is_stale.is_(False))
        if user.role == Role.supervisor and user.team_id:
            aq = aq.filter((Alert.team_id == user.team_id) | (Alert.team_id.is_(None)))
        for a in aq.order_by(Alert.created_at.desc()).limit(limit).all():
            items.append(NotificationItem(
                kind="alert", ref_id=a.id, title="Uyari",
                message=a.message, link=f"/calls/{a.call_id}" if a.call_id else "/workflow",
                severity=a.severity or "orta", created_at=a.created_at))

        for r in (db.query(ReviewAssignment).filter(
                ReviewAssignment.tenant_id == user.tenant_id,
                ReviewAssignment.reviewer_id == user.id,
                ReviewAssignment.status == ReviewStatus.assigned)
                .order_by(ReviewAssignment.created_at.desc()).limit(limit).all()):
            items.append(NotificationItem(
                kind="review", ref_id=r.id, title="QA incelemesi atandi",
                message=f"#{r.call_id} numarali cagriyi incelemeniz bekleniyor.",
                link=f"/calls/{r.call_id}", severity="orta", created_at=r.created_at))

    if user.role in (Role.quality, Role.admin):
        for ap in (db.query(Appeal).filter(
                Appeal.tenant_id == user.tenant_id, Appeal.status == AppealStatus.open)
                .order_by(Appeal.created_at.desc()).limit(limit).all()):
            items.append(NotificationItem(
                kind="appeal", ref_id=ap.id, title="Itiraz bekliyor",
                message=f"#{ap.call_id} icin itiraz: {(ap.reason or '')[:80]}",
                link=f"/calls/{ap.call_id}", severity="orta", created_at=ap.created_at))

    if user.role == Role.agent and user.agent_id:
        for tsk in (db.query(CoachingTask).filter(
                CoachingTask.tenant_id == user.tenant_id,
                CoachingTask.assignee_agent_id == user.agent_id,
                CoachingTask.status == TaskStatus.open)
                .order_by(CoachingTask.created_at.desc()).limit(limit).all()):
            items.append(NotificationItem(
                kind="coaching", ref_id=tsk.id, title="Kocluk gorevi",
                message=(tsk.note or "Size bir kocluk gorevi atandi.")[:100],
                link=f"/calls/{tsk.call_id}", severity="orta", created_at=tsk.created_at))

    items.sort(key=lambda x: x.created_at, reverse=True)
    return NotificationFeed(unread_count=len(items), items=items[:limit])


@router.post("/read-all", status_code=204)
def read_all(db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    """Kullanicinin gordugu tum uyarilari okundu isaretler (yalnizca Alert kaynagi;
    inceleme/kocluk/itiraz aksiyon tamamlaninca kendiliginden dusuyor)."""
    q = db.query(Alert).filter(Alert.tenant_id == user.tenant_id, Alert.is_read.is_(False),
        Alert.is_stale.is_(False))
    if user.role == Role.supervisor and user.team_id:
        q = q.filter((Alert.team_id == user.team_id) | (Alert.team_id.is_(None)))
    for a in q.all():
        a.is_read = True
    db.commit()
