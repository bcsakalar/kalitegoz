"""Puanlama motoru degismezleri — B27, B28, B31 regresyon testleri.

Bu uc hata transkript seviyesinde ifade edilemez (altin set senaryosu olamaz):
motorun kendi ic davranisidir. Bu yuzden birim/entegrasyon testiyle korunurlar.

FAZ 2'de UCU DE DUZELTILDI; testler artik yesil ve kalici koruma gorevi goruyor.
Kaynak: docs/internal/00-MEVCUT-DURUM.md §9, docs/internal/01-KOK-NEDEN.md
"""

from __future__ import annotations

from dataclasses import dataclass

from app.schemas import LLMKriterKarari
from app.services import scoring_layers as sl


@dataclass
class Crit:
    id: int
    name: str
    weight: float = 1.0
    is_critical: bool = False
    critical_threshold: int = 3
    description: str = "aciklama"
    anchor_10: str = ""
    anchor_0: str = ""


def _dec(cid: int, score: int | None, decision: str = "met") -> sl.CriterionDecision:
    return sl.CriterionDecision(
        criterion_id=cid, decision=decision, score=score, rationale="r",
        evidence_quote="q", evidence_ts=1.0, evidence_speaker="temsilci",
        confidence=0.9, evidence_verified=True, source_layer="B",
    )


# ---------------------------------------------------------------------------
# B27 — Ayni kriter iki kez puanlanip agirligi iki kez sayilamaz
# ---------------------------------------------------------------------------

def test_b27_tekrarlanan_kriter_elenir():
    """LLM ayni kriteri iki kez donerse yalnizca BIRI sayilmali.

    Canli sistemde olculdu: cagri #24'te 11 puan satiri vardi, 'KVKK / Aydinlatma'
    iki kez. Eski compute_total bu kriterin agirligini hem paya hem paydaya iki
    kez katiyordu.
    """
    criteria = [Crit(1, "Acilis"), Crit(2, "KVKK / Aydinlatma", weight=1.5)]
    temiz = sl.compute_total([_dec(1, 8), _dec(2, 9)], criteria)
    tekrarli = sl.compute_total([_dec(1, 8), _dec(2, 9), _dec(2, 3)], criteria)
    assert tekrarli == temiz, f"Agirlik iki kez sayildi: {tekrarli} != {temiz}"


def test_b27_evaluate_all_tekrarlanan_karari_elemeli(monkeypatch):
    """Katman B ayni kriter icin iki karar donerse ilki gecerli olmali."""
    criteria = [Crit(1, "Acilis")]
    monkeypatch.setattr(sl, "evaluate_group", lambda g, t, h, fs="", mo=None: [
        LLMKriterKarari(kriter_id=1, karar="met", puan=9),
        LLMKriterKarari(kriter_id=1, karar="not_met", puan=2),
    ])
    out = sl.evaluate_all(criteria, "transkript", "")
    assert len(out) == 1
    assert out[0].puan == 9


# ---------------------------------------------------------------------------
# B28 — Kanitsiz "notr 5" uydurulamaz
# ---------------------------------------------------------------------------

def test_b28_degerlendirilemeyen_kriter_uydurma_puan_almaz(monkeypatch):
    """LLM bir kriteri atlarsa sistem 5 puan UYDURMAMALI.

    Dogru davranis: kriter 'insufficient_evidence' isaretlenir ve insan
    kuyruguna duser. Uydurulan 5 puan ortalamaya gercek puan gibi giriyordu.
    """
    criteria = [Crit(1, "Acilis"), Crit(2, "Kapanis")]
    monkeypatch.setattr(sl, "evaluate_group", lambda g, t, h, fs="", mo=None: [
        LLMKriterKarari(kriter_id=1, karar="met", puan=8)
    ] if any(c.id == 1 for c in g) else [])

    out = sl.evaluate_all(criteria, "transkript", "")
    eksik = [k for k in out if k.kriter_id == 2]
    assert eksik, "Eksik kriter hic raporlanmadi"
    assert eksik[0].karar == "insufficient_evidence"
    assert eksik[0].puan is None, f"Kanitsiz puan uyduruldu: {eksik[0].puan}"


def test_b28_yetersiz_kanitli_kriter_ortalamaya_girmez():
    """Yetersiz kanitli kriter toplam puan aritmetigine KATILMAZ."""
    criteria = [Crit(1, "Acilis"), Crit(2, "Kapanis")]
    puanlar = [_dec(1, 8), _dec(2, None, "insufficient_evidence")]
    # Yalniz 1 numarali kriter sayilir -> 8/10 -> 80.0
    assert sl.compute_total(puanlar, criteria) == 80.0


def test_b28_kanitsiz_kriter_sifirlama_tetikleyemez():
    """Kanitsiz sifirlama urunun en pahali hatasidir."""
    criteria = [Crit(1, "KVKK", is_critical=True, critical_threshold=3)]
    z = sl.decide_zeroing([_dec(1, None, "insufficient_evidence")], criteria)
    assert z.zeroed is False


# ---------------------------------------------------------------------------
# B31 — Yeniden puanlamada eski alarmlar gecersizlestirilmeli
# ---------------------------------------------------------------------------

def test_b31_yeniden_puanlama_eski_alarmlari_gecersizler(seeded):
    """Bir cagri yeniden puanlandiginda onceki alarmlari ekranda ASILI KALMAMALI.

    Olculdu: scores ve violations siliniyor ama alerts birikiyordu; eski/gecersiz
    KVKK alarmi cagri duzgun yeniden puanlansa bile gorunuyordu (B2'nin en olasi
    aciklamasi).
    """
    from app.models import Alert, AlertType
    from app.services import alerts as alerts_svc

    from .conftest import TestingSession

    db = TestingSession()
    try:
        db.add(Alert(
            tenant_id=seeded["tenant_a"], call_id=seeded["call_a"],
            type=AlertType.banned_word, severity="yuksek",
            message="Uyum ihlali (KVKK) — eski kosumdan kalma",
        ))
        db.commit()

        alerts_svc.invalidate_for_call(db, seeded["call_a"])
        db.commit()

        kalan = (
            db.query(Alert)
            .filter(Alert.call_id == seeded["call_a"], Alert.is_stale.is_(False))
            .count()
        )
        assert kalan == 0, f"{kalan} eski alarm gecersizlestirilmedi"

        # Alarm SILINMEZ — denetim izi olarak kalir
        toplam = db.query(Alert).filter(Alert.call_id == seeded["call_a"]).count()
        assert toplam == 1, "Alarm silinmis; denetim izi kayboldu"
    finally:
        db.close()


def test_b31_gecersizlesen_alarm_kullaniciya_gosterilmez(seeded):
    from app.models import Alert, AlertType
    from app.services import alerts as alerts_svc

    from .conftest import TestingSession

    db = TestingSession()
    try:
        db.add(Alert(tenant_id=seeded["tenant_a"], call_id=seeded["call_a"],
                     type=AlertType.zeroing, severity="yuksek", message="eski"))
        db.add(Alert(tenant_id=seeded["tenant_a"], call_id=seeded["call_other_team"],
                     type=AlertType.crisis, severity="yuksek", message="guncel"))
        db.commit()

        alerts_svc.invalidate_for_call(db, seeded["call_a"])
        db.commit()

        aktif = alerts_svc.active_query(db, seeded["tenant_a"]).all()
        assert [a.message for a in aktif] == ["guncel"]
    finally:
        db.close()
