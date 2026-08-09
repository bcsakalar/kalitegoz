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
    # --- FAZ 2: uc katmanli puanlama ---
    ("calls.zeroing_reason",
     "ALTER TABLE calls ADD COLUMN IF NOT EXISTS zeroing_reason TEXT"),
    ("calls.zeroing_evidence",
     "ALTER TABLE calls ADD COLUMN IF NOT EXISTS zeroing_evidence TEXT"),
    ("calls.zeroing_evidence_ts",
     "ALTER TABLE calls ADD COLUMN IF NOT EXISTS zeroing_evidence_ts DOUBLE PRECISION"),
    ("calls.zeroing_criterion_id",
     "ALTER TABLE calls ADD COLUMN IF NOT EXISTS zeroing_criterion_id INTEGER"),
    ("criteria.evaluation_mode",
     "ALTER TABLE criteria ADD COLUMN IF NOT EXISTS evaluation_mode VARCHAR(16) "
     "NOT NULL DEFAULT 'llm_evidence'"),
    ("criteria.check_key",
     "ALTER TABLE criteria ADD COLUMN IF NOT EXISTS check_key VARCHAR(32)"),
    ("criteria.anchor_10",
     "ALTER TABLE criteria ADD COLUMN IF NOT EXISTS anchor_10 TEXT NOT NULL DEFAULT ''"),
    ("criteria.anchor_0",
     "ALTER TABLE criteria ADD COLUMN IF NOT EXISTS anchor_0 TEXT NOT NULL DEFAULT ''"),
    ("scores.decision",
     "ALTER TABLE scores ADD COLUMN IF NOT EXISTS decision VARCHAR(24) NOT NULL DEFAULT 'met'"),
    ("scores.confidence",
     "ALTER TABLE scores ADD COLUMN IF NOT EXISTS confidence DOUBLE PRECISION NOT NULL DEFAULT 1.0"),
    ("scores.evidence_verified",
     "ALTER TABLE scores ADD COLUMN IF NOT EXISTS evidence_verified BOOLEAN NOT NULL DEFAULT FALSE"),
    ("scores.source_layer",
     "ALTER TABLE scores ADD COLUMN IF NOT EXISTS source_layer VARCHAR(1) NOT NULL DEFAULT 'B'"),
    ("scores.rubric_version_id",
     "ALTER TABLE scores ADD COLUMN IF NOT EXISTS rubric_version_id INTEGER"),
    # score artik NULL olabilir: 'insufficient_evidence' -> kanitsiz ceza yok (B28)
    ("scores.score nullable",
     "ALTER TABLE scores ALTER COLUMN score DROP NOT NULL"),
    # B27: ayni cagrida ayni kriter iki kez puanlanamaz (agirlik iki kez sayiliyordu).
    # Once MEVCUT tekrarlar temizlenir (en dusuk id kalir), sonra kisit konur —
    # aksi halde tekil indeks mevcut veri yuzunden hic olusturulamaz.
    ("scores tekrar temizligi (B27)",
     "DELETE FROM scores s USING scores d "
     "WHERE s.call_id = d.call_id AND s.criterion_id = d.criterion_id "
     "  AND s.criterion_id IS NOT NULL AND s.id > d.id"),
    ("uq_scores_call_criterion",
     "CREATE UNIQUE INDEX IF NOT EXISTS uq_scores_call_criterion "
     "ON scores (call_id, criterion_id) WHERE criterion_id IS NOT NULL"),
    # Mevcut kiracilarin rubrigini uc katmanli motora bagla (ad bazli, idempotent).
    # Yeni kurulumda seed zaten dogru yaziyor; bu, calisan sistemler icin.
    ("criteria -> Katman A baglantisi",
     "UPDATE criteria SET evaluation_mode='deterministic', check_key=CASE "
     "  WHEN lower(name) LIKE 'acilis%' OR lower(name) LIKE 'açılış%' THEN 'acilis' "
     "  WHEN lower(name) LIKE 'kvkk%' THEN 'kvkk_anons' "
     "  WHEN lower(name) LIKE 'kimlik%' THEN 'kimlik_dogrulama' "
     "  WHEN lower(name) LIKE 'kapanis%' OR lower(name) LIKE 'kapanış%' THEN 'kapanis' "
     "  WHEN lower(name) LIKE 'yasakli kelime%' OR lower(name) LIKE 'yasaklı kelime%' "
     "       THEN 'yasakli_kelime' END "
     "WHERE check_key IS NULL AND ("
     "  lower(name) LIKE 'acilis%' OR lower(name) LIKE 'açılış%' OR lower(name) LIKE 'kvkk%' "
     "  OR lower(name) LIKE 'kimlik%' OR lower(name) LIKE 'kapanis%' OR lower(name) LIKE 'kapanış%' "
     "  OR lower(name) LIKE 'yasakli kelime%' OR lower(name) LIKE 'yasaklı kelime%')"),
    # 4C cercevesi: onceden 7 grup vardi ve 4'u tek kriterlikti (gruplama fiilen yoktu)
    ("criteria -> 4C gruplama",
     "UPDATE criteria SET \"group\" = CASE "
     "  WHEN lower(name) LIKE 'kvkk%' OR lower(name) LIKE 'kimlik%' "
     "       OR lower(name) LIKE 'script%' THEN 'Uyum' "
     "  WHEN lower(name) LIKE 'acilis%' OR lower(name) LIKE 'açılış%' "
     "       OR lower(name) LIKE 'kapanis%' OR lower(name) LIKE 'kapanış%' "
     "       OR lower(name) LIKE 'yasakli kelime%' OR lower(name) LIKE 'yasaklı kelime%' "
     "       OR lower(name) LIKE 'aktif dinleme%' THEN 'Iletisim' "
     "  WHEN lower(name) LIKE 'bilgi%' OR lower(name) LIKE 'ihtiyac%' "
     "       OR lower(name) LIKE 'ihtiyaç%' THEN 'Yetkinlik' "
     "  WHEN lower(name) LIKE 'cozum%' OR lower(name) LIKE 'çözüm%' THEN 'Musteri Odagi' "
     "  ELSE \"group\" END "
     "WHERE \"group\" NOT IN ('Uyum','Iletisim','Yetkinlik','Musteri Odagi')"),
    ("alerts.is_stale",
     "ALTER TABLE alerts ADD COLUMN IF NOT EXISTS is_stale BOOLEAN NOT NULL DEFAULT FALSE"),
    ("ix_alerts_is_stale",
     "CREATE INDEX IF NOT EXISTS ix_alerts_is_stale ON alerts (is_stale)"),
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
    applied = skipped = 0
    # HER IFADE KENDI TRANSACTION'INDA. Tek transaction kullanilirsa Postgres'te
    # bir ifadenin patlamasi transaction'i "aborted" yapar ve SONRAKI TUM ifadeler
    # "current transaction is aborted" ile atlanir — yani tek bir hata butun
    # migrasyon zincirini sessizce dusurur. (Bu, FAZ 2'de bizzat yasandi:
    # uq_scores_call_criterion patlayinca ondan sonraki 5 migrasyon uygulanmadi.)
    for label, sql in _STATEMENTS:
        try:
            with engine.begin() as conn:
                conn.execute(text(sql))
            applied += 1
        except Exception as exc:  # noqa: BLE001 — biri patlarsa digerleri denensin
            skipped += 1
            logger.warning("Migrasyon atlandi (%s): %s", label, exc)
    logger.info("Hafif sema migrasyonlari tamam (%d uygulandi, %d atlandi).", applied, skipped)
