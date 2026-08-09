"""Puanlama motoru degismezleri — B27, B28, B31 regresyon testleri.

Bu uc hata transkript seviyesinde ifade edilemez (altin set senaryosu olamaz):
motorun kendi ic davranisidir. Bu yuzden birim/entegrasyon testiyle korunurlar.

FAZ 1'de bu testler KIRMIZI olmali (hata henuz duzeltilmedi) ama takim yesil
kalmali. Cozum: xfail(strict=True). FAZ 2'de duzeltme yapilinca test "beklenmedik
sekilde gecti" diye takimi KIRAR ve isaretciyi kaldirmaya zorlar — kimse duzeltmeyi
sessizce atlayamaz.

Kaynak: docs/v2/00-MEVCUT-DURUM.md §9, docs/v2/01-KOK-NEDEN.md
"""

from __future__ import annotations

import pytest

from app.models import Criterion
from app.schemas import LLMDegerlendirme, LLMPuan
from app.services import scoring


def _crit(cid: int, name: str, weight: float = 1.0) -> Criterion:
    c = Criterion(
        name=name, group="Test", description=f"{name} kriteri",
        weight=weight, is_critical=False, critical_threshold=3,
        is_active=True, channel_scope="all",
    )
    c.id = cid
    return c


def _result(puanlar: list[LLMPuan]) -> LLMDegerlendirme:
    return LLMDegerlendirme(
        kategori="diger", ozet="test",
        musteri_duygu_baslangic="notr", musteri_duygu_bitis="notr",
        gelisim_onerisi="test", tahmini_csat=3.0, baskin_duygu="notr",
        duygu_yorungesi="sabit", sonraki_aksiyon="takip gerekmiyor",
        churn_riski="dusuk", musteri_efor=2.0, niyet_etiketleri=["test"],
        puanlar=puanlar, riskli_anlar=[],
    )


# ---------------------------------------------------------------------------
# B27 — Ayni kriter iki kez puanlanip agirligi iki kez sayilamaz
# ---------------------------------------------------------------------------

@pytest.mark.xfail(strict=True, reason="FAZ 2'de duzeltilecek — B27: _ensure_coverage tekrarlanan kriter_id'yi elemiyor")
def test_b27_tekrarlanan_kriter_elenir():
    """LLM ayni kriter_id'yi iki kez donerse yalnizca BIRI kalmali.

    Canli sistemde olculdu: cagri #24'te 11 puan satiri vardi, 'KVKK / Aydinlatma'
    iki kez. compute_total bu kriterin agirligini hem paya hem paydaya iki kez
    katiyordu.
    """
    criteria = [_crit(1, "Acilis"), _crit(2, "KVKK / Aydinlatma", weight=1.5)]
    result = _result([
        LLMPuan(kriter_id=1, puan=8, gerekce="ok", kanit="a"),
        LLMPuan(kriter_id=2, puan=9, gerekce="ok", kanit="b"),
        LLMPuan(kriter_id=2, puan=3, gerekce="tekrar", kanit="c"),  # <-- tekrar
    ])

    fixed = scoring._ensure_coverage(result, criteria, "transkript")

    ids = [p.kriter_id for p in fixed.puanlar]
    assert len(ids) == len(set(ids)), f"Tekrarlanan kriter elenmedi: {ids}"
    assert sorted(ids) == [1, 2]


@pytest.mark.xfail(strict=True, reason="FAZ 2'de duzeltilecek — B27: tekrarli kriter agirligi iki kez sayiliyor")
def test_b27_toplam_puan_agirligi_iki_kez_saymaz():
    """Tekrarli girdi geldiginde toplam, tekilleştirilmiş sonucla ayni olmali."""
    criteria = [_crit(1, "Acilis"), _crit(2, "KVKK / Aydinlatma", weight=1.5)]
    temiz = [LLMPuan(kriter_id=1, puan=8, gerekce="ok"), LLMPuan(kriter_id=2, puan=9, gerekce="ok")]
    tekrarli = temiz + [LLMPuan(kriter_id=2, puan=9, gerekce="tekrar")]

    beklenen = scoring.compute_total(temiz, criteria)
    gelen = scoring.compute_total(
        scoring._ensure_coverage(_result(tekrarli), criteria, "t").puanlar, criteria
    )
    assert gelen == beklenen, f"Agirlik iki kez sayildi: {gelen} != {beklenen}"


# ---------------------------------------------------------------------------
# B28 — Kanitsiz "notr 5" uydurulamaz
# ---------------------------------------------------------------------------

@pytest.mark.xfail(strict=True, reason="FAZ 2'de duzeltilecek — B28: eksik kriter icin kanitsiz 'notr 5' uyduruluyor")
def test_b28_degerlendirilemeyen_kriter_uydurma_puan_almaz(monkeypatch):
    """LLM bir kriteri atlarsa sistem 5 puan UYDURMAMALI.

    Dogru davranis: kriter 'yetersiz kanit' olarak isaretlenir ve insan kuyruguna
    duser. Uydurulan 5 puan ortalamaya gercek puan gibi giriyordu.
    """
    criteria = [_crit(1, "Acilis"), _crit(2, "Kapanis")]
    # Tamamlama cagrisi da basarisiz olsun -> sistem eksik kriterle bas basa kalir
    monkeypatch.setattr(
        scoring, "generate_json",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("LLM erisilemedi")),
    )
    result = _result([LLMPuan(kriter_id=1, puan=8, gerekce="ok", kanit="a")])

    fixed = scoring._ensure_coverage(result, criteria, "transkript")

    eksik = [p for p in fixed.puanlar if p.kriter_id == 2]
    assert eksik, "Eksik kriter hic raporlanmadi"
    p = eksik[0]
    assert getattr(p, "yetersiz_kanit", False) is True, (
        "Degerlendirilemeyen kriter 'yetersiz_kanit' olarak isaretlenmeli"
    )
    assert p.puan is None, f"Kanitsiz puan uyduruldu: {p.puan}"


@pytest.mark.xfail(strict=True, reason="FAZ 2'de duzeltilecek — B28: yetersiz_kanit kavrami henuz yok")
def test_b28_yetersiz_kanitli_kriter_ortalamaya_girmez():
    """Yetersiz kanitli kriter toplam puan aritmetigine KATILMAZ."""
    criteria = [_crit(1, "Acilis"), _crit(2, "Kapanis")]
    puanlar = [
        LLMPuan(kriter_id=1, puan=8, gerekce="ok"),
        LLMPuan(kriter_id=2, puan=None, gerekce="degerlendirilemedi", yetersiz_kanit=True),
    ]
    # Yalniz 1 numarali kriter sayilmali -> 8/10 -> 80.0
    assert scoring.compute_total(puanlar, criteria) == 80.0


# ---------------------------------------------------------------------------
# B31 — Yeniden puanlamada eski alarmlar gecersizlestirilmeli
# ---------------------------------------------------------------------------

@pytest.mark.xfail(strict=True, reason="FAZ 2'de duzeltilecek — B31: alarm gecersizlestirme servisi henuz yok")
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
    finally:
        db.close()
