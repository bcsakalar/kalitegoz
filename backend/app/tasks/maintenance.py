"""Bakim gorevleri: KVKK saklama suresi (retention) ve toplu yeniden puanlama."""

import logging
from datetime import datetime, timedelta
from pathlib import Path

from ..db import SessionLocal
from ..models import Call, CallStatus, Tenant
from ..services import audit, events
from .celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="kalitegoz.apply_retention")
def apply_retention() -> dict:
    """Tenant bazli saklama suresi dolan cagrilari siler (ses dosyasi + kayit).

    Her gece calisir (celery beat). Silme islemi audit log'a yazilir —
    KVKK'da "ne zaman, ne kadar veri silindi" sorusunun cevabi burada.
    """
    db = SessionLocal()
    summary: dict[str, int] = {}
    try:
        for tenant in db.query(Tenant).filter(Tenant.is_active.is_(True)).all():
            days = tenant.retention_days or 0
            if days <= 0:
                continue  # 0/negatif => sinirsiz saklama
            cutoff = datetime.utcnow() - timedelta(days=days)
            stale = db.query(Call).filter(
                Call.tenant_id == tenant.id, Call.created_at < cutoff
            ).all()
            if not stale:
                continue

            deleted = 0
            for call in stale:
                if call.audio_path:
                    Path(call.audio_path).unlink(missing_ok=True)
                transcript = Path("/data/storage/transcripts") / f"{call.id}.json"
                transcript.unlink(missing_ok=True)
                db.delete(call)  # segment/score/violation cascade ile gider
                deleted += 1
            db.commit()

            audit.log(
                db, action="retention_delete", tenant_id=tenant.id,
                entity_type="call", detail={
                    "deleted": deleted, "retention_days": days,
                    "cutoff": cutoff.isoformat(timespec="seconds"),
                },
            )
            summary[tenant.slug] = deleted
            logger.info("Retention: tenant=%s %d cagri silindi (>%d gun)",
                        tenant.slug, deleted, days)
        return summary
    except Exception:
        logger.exception("Retention gorevi basarisiz")
        db.rollback()
        return summary
    finally:
        db.close()


@celery_app.task(name="kalitegoz.detect_anomalies")
def detect_anomalies() -> dict:
    """Temsilci performansinda ANI DUSUS tespiti (trend alarmi).

    Kalite ekibi tek tek grafik incelemez; dususu sistem yakalamali.
    Yontem: son 7 gun ortalamasi, onceki 21 gun ortalamasindan belirgin
    (>= DROP_THRESHOLD puan) dusukse supervizore alarm dusulur.
    Ayni temsilci icin 7 gunde bir kez alarm (spam onleme).
    """
    from datetime import datetime, timedelta

    from sqlalchemy import func

    from ..models import Agent, Alert, AlertType, Call, CallStatus, Tenant

    DROP_THRESHOLD = 8.0   # puan (0-100 olceginde)
    MIN_CALLS = 5          # her iki donemde de asgari cagri

    db = SessionLocal()
    created: dict[str, int] = {}
    try:
        now = datetime.utcnow()
        recent_start = now - timedelta(days=7)
        prior_start = now - timedelta(days=28)

        for tenant in db.query(Tenant).filter(Tenant.is_active.is_(True)).all():
            count = 0
            fresh: list[tuple[Alert, str]] = []  # commit sonrasi canli yayin icin
            for agent in db.query(Agent).filter(Agent.tenant_id == tenant.id).all():
                def avg_between(start, end):
                    return db.query(func.avg(Call.total_score), func.count(Call.id)).filter(
                        Call.agent_id == agent.id,
                        Call.status == CallStatus.done,
                        Call.total_score.isnot(None),
                        Call.created_at >= start,
                        Call.created_at < end,
                    ).one()

                recent_avg, recent_n = avg_between(recent_start, now)
                prior_avg, prior_n = avg_between(prior_start, recent_start)
                if recent_n < MIN_CALLS or prior_n < MIN_CALLS:
                    continue
                if recent_avg is None or prior_avg is None:
                    continue
                drop = float(prior_avg) - float(recent_avg)
                if drop < DROP_THRESHOLD:
                    continue

                # Spam onleme: son 7 gunde ayni temsilci icin alarm var mi?
                exists = db.query(Alert.id).filter(
                    Alert.tenant_id == tenant.id,
                    Alert.type == AlertType.score_drop,
                    Alert.created_at >= recent_start,
                    Alert.message.like(f"%{agent.name}%"),
                ).first()
                if exists:
                    continue

                row = Alert(
                    tenant_id=tenant.id, team_id=agent.team_id,
                    type=AlertType.score_drop, severity="orta",
                    message=(
                        f"{agent.name}: son 7 gun ortalamasi {float(recent_avg):.1f} "
                        f"(onceki 3 hafta {float(prior_avg):.1f}) — {drop:.1f} puan dusus. "
                        f"Kocluk gerekebilir."
                    ),
                )
                db.add(row)
                fresh.append((row, agent.name))
                count += 1
            if count:
                db.commit()
                created[tenant.slug] = count
                logger.info("Anomali: tenant=%s %d dusus alarmi", tenant.slug, count)
                # Commit sonrasi canli yayin (id ancak burada olusur)
                for row, agent_name in fresh:
                    events.publish_alert({
                        "id": row.id,
                        "tenant_id": row.tenant_id,
                        "team_id": row.team_id,
                        "call_id": None,
                        "type": row.type.value,
                        "severity": row.severity,
                        "message": row.message,
                        "is_read": False,
                        "created_at": row.created_at.isoformat() if row.created_at else None,
                        "agent": agent_name,
                    })
        return created
    except Exception:
        logger.exception("Anomali tespiti basarisiz")
        db.rollback()
        return created
    finally:
        db.close()


@celery_app.task(name="kalitegoz.award_badges")
def award_badges() -> dict:
    """Rozet otomatik dagitimi (gamification kural motoru).

    Kurallar (haftalik degerlendirilir, ayni rozet ayni donemde tekrar verilmez):
    - zero_violation : donemde hic sifirlayici ihlal yok + en az 5 cagri
    - crisis_master  : en az 2 kriz cagrisi ve kriz cagrilarinda ortalama >= 75
    - empathy_champ  : musteri duygusunu en cok iyilestiren (olumsuz -> olumlu)
    - fastest_solution: en yuksek FCR (tekrar aranmayan cagri orani)
    """
    from datetime import datetime, timedelta

    from sqlalchemy import func

    from ..models import Agent, AgentBadge, Badge, Call, CallStatus, Tenant

    db = SessionLocal()
    awarded: dict[str, int] = {}
    try:
        now = datetime.utcnow()
        since = now - timedelta(days=7)
        period = f"{now.isocalendar().year}-W{now.isocalendar().week:02d}"

        for tenant in db.query(Tenant).filter(Tenant.is_active.is_(True)).all():
            badges = {b.code: b for b in db.query(Badge).filter(Badge.tenant_id == tenant.id)}
            if not badges:
                continue
            count = 0

            def give(agent_id: int, code: str) -> None:
                nonlocal count
                badge = badges.get(code)
                if badge is None:
                    return
                exists = db.query(AgentBadge.id).filter(
                    AgentBadge.agent_id == agent_id,
                    AgentBadge.badge_id == badge.id,
                    AgentBadge.period == period,
                ).first()
                if exists:
                    return
                db.add(AgentBadge(tenant_id=tenant.id, agent_id=agent_id,
                                  badge_id=badge.id, period=period))
                count += 1

            agents = db.query(Agent).filter(Agent.tenant_id == tenant.id).all()
            empathy_best: tuple[int, int] | None = None  # (agent_id, iyilesme_sayisi)

            for agent in agents:
                base = db.query(Call).filter(
                    Call.agent_id == agent.id, Call.status == CallStatus.done,
                    Call.created_at >= since,
                )
                total = base.count()
                if total < 5:
                    continue

                # Sifir ihlal
                if base.filter(Call.zeroed.is_(True)).count() == 0:
                    give(agent.id, "zero_violation")

                # Kriz ustasi
                crisis = base.filter(Call.is_crisis.is_(True))
                crisis_n = crisis.count()
                if crisis_n >= 2:
                    crisis_avg = crisis.with_entities(func.avg(Call.total_score)).scalar()
                    if crisis_avg and float(crisis_avg) >= 75:
                        give(agent.id, "crisis_master")

                # Empati: duyguyu olumsuzdan olumluya cevirme sayisi
                improved = base.filter(
                    Call.sentiment_start == "olumsuz", Call.sentiment_end == "olumlu"
                ).count()
                if improved and (empathy_best is None or improved > empathy_best[1]):
                    empathy_best = (agent.id, improved)

                # En hizli cozum: tekrar aranmayan cagri orani (musteri referansi varsa)
                identified = base.filter(Call.customer_ref.isnot(None))
                ident_n = identified.count()
                if ident_n >= 5:
                    repeats = identified.filter(Call.is_repeat.is_(True)).count()
                    if repeats == 0:
                        give(agent.id, "fastest_solution")

            if empathy_best:
                give(empathy_best[0], "empathy_champ")

            if count:
                db.commit()
                awarded[tenant.slug] = count
                logger.info("Rozet: tenant=%s %d rozet verildi (%s)", tenant.slug, count, period)
        return awarded
    except Exception:
        logger.exception("Rozet dagitimi basarisiz")
        db.rollback()
        return awarded
    finally:
        db.close()


@celery_app.task(name="kalitegoz.rescore_bulk")
def rescore_bulk(tenant_id: int, call_ids: list[int] | None = None) -> int:
    """Rubrik degistiginde toplu yeniden puanlama (STT'siz, mevcut transkriptle).

    call_ids verilmezse tenant'in tamamlanmis TUM cagrilari yeniden puanlanir.
    Her cagri ayri gorev olarak kuyruga atilir; boylece tek tek izlenebilir.
    """
    from .pipeline import rescore_call

    db = SessionLocal()
    try:
        q = db.query(Call.id).filter(
            Call.tenant_id == tenant_id, Call.status == CallStatus.done
        )
        if call_ids:
            q = q.filter(Call.id.in_(call_ids))
        ids = [row[0] for row in q.all()]
        for cid in ids:
            rescore_call.delay(cid)
        logger.info("Toplu yeniden puanlama: %d cagri kuyruga alindi", len(ids))
        return len(ids)
    finally:
        db.close()


@celery_app.task(name="kalitegoz.send_weekly_reports")
def send_weekly_reports() -> dict:
    """Haftalik ekip raporunu tum aktif tenant'lara e-postayla gonderir (Dalga 7).

    SMTP yapilandirilmamissa rapor uretilir ama gonderilmez (hata degil).
    """
    from ..services import email_reports

    db = SessionLocal()
    try:
        result = email_reports.send_all_tenants(db)
        sent = sum(1 for r in result.values() if r.get("sent"))
        logger.info("Haftalik rapor: %d tenant islendi, %d gonderildi", len(result), sent)
        return {"tenants": len(result), "sent": sent}
    except Exception:
        logger.exception("Haftalik rapor gorevi basarisiz")
        return {"error": True}
    finally:
        db.close()
