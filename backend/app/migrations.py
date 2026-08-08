"""Idempotent hafif sema migrasyonlari (boot'ta calisir).

`Base.metadata.create_all` yalnizca EKSIK TABLOLARI olusturur; mevcut bir tabloya
YENI KOLON ekleyemez. Bu modul, uygulama gelistikce eklenen kolonlari/indeksleri
`ADD COLUMN IF NOT EXISTS` ile guvenle uygular — boylece hem temiz kurulum hem de
mevcut veritabani, elle `psql` calistirmadan kendini onarir (self-healing schema).

Alembic'e gecilene kadar kopru cozum; her ifade tekrar-calistirilabilir olmalidir.
"""

import logging

from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

# (aciklama, SQL) — hepsi IF NOT EXISTS ile idempotent. Postgres hedefli.
_STATEMENTS: list[tuple[str, str]] = [
    ("calls.is_golden",
     "ALTER TABLE calls ADD COLUMN IF NOT EXISTS is_golden BOOLEAN NOT NULL DEFAULT FALSE"),
    ("calls.tags",
     "ALTER TABLE calls ADD COLUMN IF NOT EXISTS tags JSON NOT NULL DEFAULT '[]'::json"),
    ("calls.embedding",
     "ALTER TABLE calls ADD COLUMN IF NOT EXISTS embedding JSON"),
    ("calls.error",
     "ALTER TABLE calls ADD COLUMN IF NOT EXISTS error TEXT"),
    ("calls.coaching",
     "ALTER TABLE calls ADD COLUMN IF NOT EXISTS coaching TEXT"),
    ("calibration_sessions.scheduled_at",
     "ALTER TABLE calibration_sessions ADD COLUMN IF NOT EXISTS scheduled_at TIMESTAMP"),
    ("ix_calls_is_golden",
     "CREATE INDEX IF NOT EXISTS ix_calls_is_golden ON calls (is_golden)"),
    ("ix_calibration_sessions_scheduled_at",
     "CREATE INDEX IF NOT EXISTS ix_calibration_sessions_scheduled_at "
     "ON calibration_sessions (scheduled_at)"),
]


def run_light_migrations(engine: Engine) -> None:
    """Idempotent kolon/indeks migrasyonlarini uygula. Postgres disi (SQLite test)
    ortamda sessizce atlanir — orada create_all zaten guncel semayi kurar."""
    if engine.dialect.name != "postgresql":
        return
    applied = 0
    with engine.begin() as conn:
        for label, sql in _STATEMENTS:
            try:
                conn.execute(text(sql))
                applied += 1
            except Exception as exc:  # noqa: BLE001 — biri patlarsa digerleri denensin
                logger.warning("Migrasyon atlandi (%s): %s", label, exc)
    logger.info("Hafif sema migrasyonlari tamam (%d ifade).", applied)
