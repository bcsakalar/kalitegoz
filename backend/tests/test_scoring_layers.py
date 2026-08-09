"""KATMAN B + C testleri — kanit dogrulama, puan aritmetigi, sifirlama karari."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.schemas import LLMKanit, LLMKriterKarari
from app.services import scoring_layers as sl

TRANSCRIPT = (
    "[00:01 | 1sn] TEMSILCI: Netik İletişim'e hoş geldiniz, ben Mehmet. "
    "[00:05 | 5sn] TEMSILCI: Görüşmemiz kayıt altına alınmaktadır. "
    "[00:12 | 12sn] MUSTERI: Faturamda tanımadığım bir kalem var. "
    "[00:18 | 18sn] TEMSILCI: Hemen bakıyorum, 45 TL'lik bir abonelik başlatılmış."
)


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


def karar(cid, decision="met", puan=9, quote="", guven=0.9):
    return LLMKriterKarari(
        kriter_id=cid, karar=decision, puan=puan, guven=guven,
        gerekce="gerekce", kanitlar=[LLMKanit(quote=quote)] if quote else [],
    )


# =========================================================================
# Katman C — kanit dogrulama
# =========================================================================

def test_gercek_alinti_dogrulanir():
    d = sl.verify(karar(1, quote="ben Mehmet"), TRANSCRIPT)
    assert d.evidence_verified is True
    assert d.decision == "met"
    assert d.score == 9


def test_uydurma_alinti_yetersiz_kanita_dusurulur():
    """FAZ 1'de olculdu: kanitlarin %43.9'u transkriptte yoktu."""
    d = sl.verify(karar(1, decision="not_met", puan=2,
                        quote="Temsilci kurum adını hiç söylemedi"), TRANSCRIPT)
    assert d.decision == "insufficient_evidence"
    assert d.score is None, "Uydurma kanitla CEZA VERILDI"
    assert d.evidence_verified is False


def test_kanitsiz_ceza_verilemez():
    """B1'in kalbi: kanit listesi bossa dusuk puan gecerli olamaz."""
    d = sl.verify(karar(1, decision="not_met", puan=1, quote=""), TRANSCRIPT)
    assert d.decision == "insufficient_evidence"
    assert d.score is None


def test_yetersiz_kanit_karari_korunur():
    d = sl.verify(karar(1, decision="insufficient_evidence", puan=None), TRANSCRIPT)
    assert d.decision == "insufficient_evidence"
    assert d.score is None


def test_dusuk_guven_insan_kuyruguna():
    d = sl.verify(karar(1, quote="ben Mehmet", guven=0.5), TRANSCRIPT)
    assert d.needs_human is True


def test_yuksek_guvenli_dogrulanmis_karar_insan_istemez():
    d = sl.verify(karar(1, quote="ben Mehmet", guven=0.95), TRANSCRIPT)
    assert d.needs_human is False


# =========================================================================
# Puan aritmetigi
# =========================================================================

def _dec(cid, score, decision="met", weight_owner=None):
    return sl.CriterionDecision(
        criterion_id=cid, decision=decision, score=score, rationale="r",
        evidence_quote="q", evidence_ts=1.0, evidence_speaker="temsilci",
        confidence=0.9, evidence_verified=True, source_layer="B",
    )


def test_agirlikli_ortalama():
    criteria = [Crit(1, "A", weight=1.0), Crit(2, "B", weight=3.0)]
    # (8*1 + 10*3) / (4*10) * 100 = 38/40*100 = 95.0
    assert sl.compute_total([_dec(1, 8), _dec(2, 10)], criteria) == 95.0


def test_yetersiz_kanitli_kriter_ortalamaya_katilmaz():
    """B28: kanitsiz kriter ortalamayi asagi cekemez."""
    criteria = [Crit(1, "A"), Crit(2, "B")]
    only_a = sl.compute_total([_dec(1, 8)], criteria)
    with_unknown = sl.compute_total(
        [_dec(1, 8), _dec(2, None, "insufficient_evidence")], criteria
    )
    assert with_unknown == only_a == 80.0


def test_b27_tekrarlanan_kriter_bir_kez_sayilir():
    criteria = [Crit(1, "A"), Crit(2, "B", weight=1.5)]
    temiz = sl.compute_total([_dec(1, 8), _dec(2, 10)], criteria)
    tekrarli = sl.compute_total([_dec(1, 8), _dec(2, 10), _dec(2, 10)], criteria)
    assert tekrarli == temiz


def test_hicbir_kriter_puanlanamadiysa_none():
    criteria = [Crit(1, "A")]
    assert sl.compute_total([_dec(1, None, "insufficient_evidence")], criteria) is None


# =========================================================================
# Sifirlama karari
# =========================================================================

def test_kritik_kriter_esik_altinda_sifirlar():
    criteria = [Crit(1, "KVKK", is_critical=True, critical_threshold=3)]
    z = sl.decide_zeroing([_dec(1, 0)], criteria)
    assert z.zeroed is True
    assert z.reason and "KVKK" in z.reason
    assert z.evidence, "Sifirlama kanitsiz birakildi"
    assert z.criterion_id == 1


def test_kritik_kriter_esik_ustunde_sifirlamaz():
    criteria = [Crit(1, "KVKK", is_critical=True, critical_threshold=3)]
    assert sl.decide_zeroing([_dec(1, 5)], criteria).zeroed is False


def test_yetersiz_kanit_ASLA_sifirlamaz():
    """Kanitsiz sifirlama urunun en pahali hatasidir."""
    criteria = [Crit(1, "KVKK", is_critical=True, critical_threshold=3)]
    z = sl.decide_zeroing([_dec(1, None, "insufficient_evidence")], criteria)
    assert z.zeroed is False


def test_kritik_olmayan_dusuk_kriter_sifirlamaz():
    criteria = [Crit(1, "Kapanis", is_critical=False)]
    assert sl.decide_zeroing([_dec(1, 0)], criteria).zeroed is False


# =========================================================================
# Kriter gruplama (bias azaltici)
# =========================================================================

def test_gruplar_azalan_agirlikta_ve_ucerli():
    criteria = [Crit(i, f"K{i}", weight=w) for i, w in enumerate([1.0, 2.0, 1.5, 1.0, 2.0], 1)]
    groups = sl.group_criteria(criteria)
    assert [len(g) for g in groups] == [3, 2]
    agirliklar = [c.weight for g in groups for c in g]
    assert agirliklar == sorted(agirliklar, reverse=True)


def test_kriterler_harf_kimlikle_sunulur():
    block, mapping = sl._criteria_block([Crit(7, "Acilis"), Crit(9, "Kapanis")])
    assert "[A] Acilis" in block
    assert "[B] Kapanis" in block
    assert mapping == {"A": 7, "B": 9}
    assert "7" not in block.split("\n")[0], "Sayisal id prompt'a sizdi"


def test_capalar_prompt_a_girer():
    block, _ = sl._criteria_block([Crit(1, "Acilis", anchor_10="Kurum + isim", anchor_0="Hicbiri")])
    assert "10 PUAN: Kurum + isim" in block
    assert "0 PUAN: Hicbiri" in block


def test_harf_cozulemezse_karar_atilir():
    group = [Crit(1, "A"), Crit(2, "B")]
    k = LLMKriterKarari(kriter_harf="Z", karar="met", puan=8)
    assert sl._resolve_letters([k], {"A": 1, "B": 2}, group) == []


def test_tek_kriterli_grupta_harf_hatasi_tolere_edilir():
    group = [Crit(5, "Tek")]
    k = LLMKriterKarari(kriter_harf="", karar="met", puan=8)
    out = sl._resolve_letters([k], {"A": 5}, group)
    assert len(out) == 1 and out[0].kriter_id == 5


# =========================================================================
# Katman A -> ortak karar tipi
# =========================================================================

def test_katman_a_bulgusu_karara_cevrilir():
    from app.services.deterministic import Finding

    f = Finding("acilis", "met", 10, "Kurum ve isim bildirildi.",
                evidence_quote="ben Mehmet", evidence_ts=1.2, evidence_speaker="temsilci")
    d = sl.from_finding(3, f)
    assert d.source_layer == "A"
    assert d.evidence_verified is True
    assert d.counts_toward_total is True


def test_katman_a_yetersiz_kanit_ortalamaya_katilmaz():
    from app.services.deterministic import Finding

    f = Finding("kvkk_anons", "insufficient_evidence", None, "Konusmaci ayrimi yok.",
                confidence=0.0)
    d = sl.from_finding(4, f)
    assert d.counts_toward_total is False
    assert d.needs_human is True
