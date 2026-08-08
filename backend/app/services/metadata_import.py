"""CSV metadata esleştirme — toplu ses aktariminda cagri bilgilerini eslestirme.

Senaryo: Santral/kayit sistemi geceleri binlerce wav'i klasore atar. Dosya adindan
yalnizca temsilci cikarilabiliyor; kampanya, musteri no gibi bilgiler santralin
CSV export'unda. Bu modul o CSV'yi cagrilarla eslestirir.

CSV bicimi (basliklar zorunlu, sira serbest):
    dosya;temsilci;kampanya;musteri_ref
    ayse.yilmaz_01.wav;ayse.yilmaz;Satış Hattı;MUS-1024

- Ayrac otomatik algilanir (`;` veya `,`) — TR Excel `;` kullanir.
- `dosya` disindaki sutunlar opsiyoneldir; bos birakilan alan DEGISTIRILMEZ.
- Eslesmeyen satirlar rapor edilir (sessizce yutulmaz).
- Idempotent: ayni CSV tekrar yuklenirse ayni sonucu verir.
"""

import csv
import io
import logging
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from ..models import Agent, Call, Campaign

logger = logging.getLogger(__name__)

REQUIRED_COLUMN = "dosya"
KNOWN_COLUMNS = {"dosya", "temsilci", "kampanya", "musteri_ref"}


class MetadataError(ValueError):
    pass


@dataclass
class ImportResult:
    matched: int = 0
    updated: int = 0
    not_found: list[str] = field(default_factory=list)
    unknown_campaign: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _sniff_reader(raw: bytes) -> csv.DictReader:
    text = raw.decode("utf-8-sig", errors="replace")  # BOM'lu Excel CSV'si
    sample = text[:2048]
    delim = ";" if sample.count(";") >= sample.count(",") else ","
    return csv.DictReader(io.StringIO(text), delimiter=delim)


def apply_metadata(db: Session, tenant_id: int, raw: bytes) -> ImportResult:
    """CSV'deki bilgileri mevcut cagrilara isle."""
    reader = _sniff_reader(raw)
    if not reader.fieldnames:
        raise MetadataError("CSV bos veya basliksiz")

    headers = {(h or "").strip().lower() for h in reader.fieldnames}
    if REQUIRED_COLUMN not in headers:
        raise MetadataError(
            f"'{REQUIRED_COLUMN}' sutunu zorunlu. Bulunan sutunlar: {sorted(headers)}"
        )

    campaigns = {
        c.name.strip().lower(): c
        for c in db.query(Campaign).filter(Campaign.tenant_id == tenant_id).all()
    }
    result = ImportResult()

    for i, row in enumerate(reader, start=2):  # 1 = baslik satiri
        clean = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
        filename = clean.get(REQUIRED_COLUMN, "")
        if not filename:
            continue

        call = (
            db.query(Call)
            .filter(Call.tenant_id == tenant_id, Call.filename == filename)
            .order_by(Call.created_at.desc())
            .first()
        )
        if call is None:
            result.not_found.append(filename)
            continue
        result.matched += 1
        changed = False

        agent_name = clean.get("temsilci")
        if agent_name:
            agent = (
                db.query(Agent)
                .filter(Agent.tenant_id == tenant_id, Agent.name == agent_name.lower())
                .first()
            )
            if agent is None:
                agent = Agent(tenant_id=tenant_id, name=agent_name.lower())
                db.add(agent)
                db.flush()
            if call.agent_id != agent.id:
                call.agent_id = agent.id
                changed = True

        camp_name = clean.get("kampanya")
        if camp_name:
            camp = campaigns.get(camp_name.lower())
            if camp is None:
                if camp_name not in result.unknown_campaign:
                    result.unknown_campaign.append(camp_name)
            elif call.campaign_id != camp.id:
                call.campaign_id = camp.id
                changed = True

        ref = clean.get("musteri_ref")
        if ref and call.customer_ref != ref:
            call.customer_ref = ref
            changed = True

        if changed:
            result.updated += 1

    db.commit()

    # Musteri referansi sonradan geldigi icin tekrar-arama tespiti yeniden hesaplanir
    # (ingest sirasinda ref yoktu, dolayisiyla FCR bilinmiyordu).
    from . import fcr

    for call in db.query(Call).filter(
        Call.tenant_id == tenant_id, Call.customer_ref.isnot(None)
    ).all():
        prev = fcr.detect_repeat(db, call)
        call.is_repeat = prev is not None
        call.repeat_of_id = prev.id if prev else None
    db.commit()

    logger.info(
        "CSV metadata: %d eslesti, %d guncellendi, %d bulunamadi",
        result.matched, result.updated, len(result.not_found),
    )
    return result
