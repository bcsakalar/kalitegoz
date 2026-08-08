from celery import Celery
from celery.schedules import crontab

from ..config import settings

celery_app = Celery(
    "kalitegoz",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.pipeline", "app.tasks.maintenance"],
)

celery_app.conf.update(
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,  # STT uzun surer; worker basina tek is
    broker_connection_retry_on_startup=True,
    result_expires=3600,
    timezone="Europe/Istanbul",
    # Kuyruk ayrimi: agir STT isleri "voice"; hizli isler (chat, yeniden puanlama,
    # bakim) "fast" kuyrugunda. Boylece bir chat, siradaki uzun STT'yi beklemez.
    task_default_queue="fast",
    task_routes={
        "kalitegoz.process_call": {"queue": "voice"},
        "kalitegoz.process_chat": {"queue": "fast"},
        "kalitegoz.rescore_call": {"queue": "fast"},
        "kalitegoz.rescore_bulk": {"queue": "fast"},
        "kalitegoz.apply_retention": {"queue": "fast"},
        "kalitegoz.detect_anomalies": {"queue": "fast"},
        "kalitegoz.award_badges": {"queue": "fast"},
    },
    beat_schedule={
        # KVKK: her gece 03:15'te saklama suresi dolan kayitlari sil
        "retention-nightly": {
            "task": "kalitegoz.apply_retention",
            "schedule": crontab(hour=3, minute=15),
        },
        # Trend alarmi: her sabah 07:00'de performans dususlerini tara
        # (supervizor gune alarm listesiyle baslasin)
        "anomaly-daily": {
            "task": "kalitegoz.detect_anomalies",
            "schedule": crontab(hour=7, minute=0),
        },
        # Gamification: her pazartesi 08:00'de haftalik rozetleri dagit
        "badges-weekly": {
            "task": "kalitegoz.award_badges",
            "schedule": crontab(day_of_week=1, hour=8, minute=0),
        },
        # E-posta raporu: her pazartesi 08:30'da haftalik ekip raporunu yolla
        # (SMTP yapilandirilmamissa uretilir ama gonderilmez)
        "weekly-report": {
            "task": "kalitegoz.send_weekly_reports",
            "schedule": crontab(day_of_week=1, hour=8, minute=30),
        },
    },
)
