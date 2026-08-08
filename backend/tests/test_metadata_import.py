"""CSV metadata esleştirme: ayrac algilama, eslesme, tekrar-arama yeniden hesabi."""

import pytest

from app.models import Agent, Call, CallStatus, Campaign, Channel
from app.services import metadata_import
from tests.conftest import TestingSession


def _mk_call(db, tenant_id, filename, agent_id=None):
    c = Call(tenant_id=tenant_id, filename=filename, audio_path="", channel=Channel.voice,
             agent_id=agent_id, status=CallStatus.done, total_score=80.0)
    db.add(c)
    db.flush()
    return c


def test_requires_dosya_column(seeded):
    db = TestingSession()
    try:
        with pytest.raises(metadata_import.MetadataError, match="dosya"):
            metadata_import.apply_metadata(db, seeded["tenant_a"], b"temsilci;kampanya\na;b\n")
    finally:
        db.close()


def test_matches_and_sets_customer_ref(seeded):
    db = TestingSession()
    try:
        _mk_call(db, seeded["tenant_a"], "cagri_01.wav")
        db.commit()
        csv = "dosya;musteri_ref\ncagri_01.wav;MUS-500\n".encode("utf-8")
        r = metadata_import.apply_metadata(db, seeded["tenant_a"], csv)
        assert r.matched == 1 and r.updated == 1
        call = db.query(Call).filter(Call.filename == "cagri_01.wav").first()
        assert call.customer_ref == "MUS-500"
    finally:
        db.close()


def test_comma_delimiter_also_works(seeded):
    """TR Excel ';' kullanir ama ',' de kabul edilmeli (otomatik algilama)."""
    db = TestingSession()
    try:
        _mk_call(db, seeded["tenant_a"], "c2.wav")
        db.commit()
        csv = "dosya,musteri_ref\nc2.wav,MUS-9\n".encode("utf-8")
        r = metadata_import.apply_metadata(db, seeded["tenant_a"], csv)
        assert r.matched == 1
        assert db.query(Call).filter(Call.filename == "c2.wav").first().customer_ref == "MUS-9"
    finally:
        db.close()


def test_bom_encoded_csv(seeded):
    """Excel'in kaydettigi BOM'lu UTF-8 okunabilmeli."""
    db = TestingSession()
    try:
        _mk_call(db, seeded["tenant_a"], "c3.wav")
        db.commit()
        csv = "﻿dosya;musteri_ref\nc3.wav;MUS-3\n".encode("utf-8")
        r = metadata_import.apply_metadata(db, seeded["tenant_a"], csv)
        assert r.matched == 1
    finally:
        db.close()


def test_reports_missing_files(seeded):
    db = TestingSession()
    try:
        csv = "dosya;musteri_ref\nyok_boyle.wav;X\n".encode("utf-8")
        r = metadata_import.apply_metadata(db, seeded["tenant_a"], csv)
        assert r.matched == 0
        assert "yok_boyle.wav" in r.not_found
    finally:
        db.close()


def test_creates_agent_if_missing(seeded):
    db = TestingSession()
    try:
        _mk_call(db, seeded["tenant_a"], "c4.wav")
        db.commit()
        csv = "dosya;temsilci\nc4.wav;yeni.temsilci\n".encode("utf-8")
        metadata_import.apply_metadata(db, seeded["tenant_a"], csv)
        agent = db.query(Agent).filter(
            Agent.tenant_id == seeded["tenant_a"], Agent.name == "yeni.temsilci").first()
        assert agent is not None
        assert db.query(Call).filter(Call.filename == "c4.wav").first().agent_id == agent.id
    finally:
        db.close()


def test_unknown_campaign_reported_not_created(seeded):
    """Bilinmeyen kampanya sessizce OLUSTURULMAZ — rapor edilir (yazim hatasi olabilir)."""
    db = TestingSession()
    try:
        _mk_call(db, seeded["tenant_a"], "c5.wav")
        db.commit()
        csv = "dosya;kampanya\nc5.wav;Olmayan Hat\n".encode("utf-8")
        r = metadata_import.apply_metadata(db, seeded["tenant_a"], csv)
        assert "Olmayan Hat" in r.unknown_campaign
        assert db.query(Campaign).filter(Campaign.name == "Olmayan Hat").first() is None
    finally:
        db.close()


def test_matches_existing_campaign(seeded):
    db = TestingSession()
    try:
        camp = Campaign(tenant_id=seeded["tenant_a"], name="Destek Hattı")
        db.add(camp)
        _mk_call(db, seeded["tenant_a"], "c6.wav")
        db.commit()
        csv = "dosya;kampanya\nc6.wav;destek hattı\n".encode("utf-8")  # kucuk harf
        r = metadata_import.apply_metadata(db, seeded["tenant_a"], csv)
        assert r.updated == 1
        assert db.query(Call).filter(Call.filename == "c6.wav").first().campaign_id == camp.id
    finally:
        db.close()


def test_empty_field_does_not_overwrite(seeded):
    """Bos birakilan sutun mevcut degeri SILMEMELI."""
    db = TestingSession()
    try:
        c = _mk_call(db, seeded["tenant_a"], "c7.wav")
        c.customer_ref = "ESKI-REF"
        db.commit()
        csv = "dosya;musteri_ref;temsilci\nc7.wav;;ayse\n".encode("utf-8")
        metadata_import.apply_metadata(db, seeded["tenant_a"], csv)
        assert db.query(Call).filter(Call.filename == "c7.wav").first().customer_ref == "ESKI-REF"
    finally:
        db.close()


def test_is_tenant_scoped(seeded):
    """Baska tenant'in ayni isimli dosyasi guncellenmemeli."""
    db = TestingSession()
    try:
        _mk_call(db, seeded["tenant_b"], "ortak.wav")
        db.commit()
        csv = "dosya;musteri_ref\nortak.wav;HACK\n".encode("utf-8")
        r = metadata_import.apply_metadata(db, seeded["tenant_a"], csv)
        assert r.matched == 0
        assert db.query(Call).filter(Call.filename == "ortak.wav").first().customer_ref is None
    finally:
        db.close()


def test_recomputes_repeat_after_ref_import(seeded):
    """Musteri referansi CSV ile sonradan gelince tekrar-arama tespiti calismali."""
    from datetime import datetime, timedelta

    db = TestingSession()
    try:
        c1 = _mk_call(db, seeded["tenant_a"], "ilk.wav", seeded["agent_a"])
        c1.created_at = datetime.utcnow() - timedelta(days=3)
        c2 = _mk_call(db, seeded["tenant_a"], "ikinci.wav", seeded["agent_a"])
        db.commit()
        csv = "dosya;musteri_ref\nilk.wav;MUS-77\nikinci.wav;MUS-77\n".encode("utf-8")
        metadata_import.apply_metadata(db, seeded["tenant_a"], csv)

        second = db.query(Call).filter(Call.filename == "ikinci.wav").first()
        assert second.is_repeat is True, "3 gun sonraki ayni musteri = tekrar arama"
        assert second.repeat_of_id == c1.id
    finally:
        db.close()
