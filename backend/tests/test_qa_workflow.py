"""FAZ 3 — durum makinesi, kuyruk kurallari, geri besleme dongusu testleri."""

from __future__ import annotations

import random
from datetime import datetime, timedelta

import pytest

from app.models import (
    Agent,
    AuditLog,
    Call,
    CallStatus,
    Channel,
    Criterion,
    QAState,
    ReviewReason,
    Score,
    Tenant,
)
from app.services import qa_workflow, review_feedback

from .conftest import TestingSession


class Sabit(random.Random):
    """Deterministik rastgelelik: verilen degeri dondurur."""

    def __init__(self, value: float):
        super().__init__(0)
        self._value = value

    def random(self) -> float:  # noqa: D102
        return self._value


@pytest.fixture
def db(seeded):
    s = TestingSession()
    try:
        yield s
    finally:
        s.close()


def make_call(db, seeded, **kw) -> Call:
    call = Call(
        tenant_id=seeded["tenant_a"], agent_id=seeded["agent_a"],
        filename="t.wav", audio_path="", channel=Channel.voice,
        status=CallStatus.done, total_score=kw.pop("total_score", 85.0),
        **kw,
    )
    db.add(call)
    db.flush()
    return call


# =========================================================================
# 3.1 Durum makinesi
# =========================================================================

def test_gecerli_gecis_denetim_gunlugune_yazilir(db, seeded):
    call = make_call(db, seeded)
    qa_workflow.transition(db, call, QAState.human_queue, user_id=1, reason="test")
    db.commit()

    log = (
        db.query(AuditLog)
        .filter(AuditLog.entity_type == "call", AuditLog.entity_id == call.id)
        .one()
    )
    assert log.action == "qa_state_change"
    assert log.detail["from"] == "ai_puanlandi"
    assert log.detail["to"] == "insan_kuyrugunda"
    assert log.detail["reason"] == "test"


def test_gecersiz_gecis_reddedilir(db, seeded):
    """Durum makinesi 'yazili ama uygulanmayan' bir sema olmamali."""
    call = make_call(db, seeded, qa_state=QAState.ai_scored)
    with pytest.raises(qa_workflow.InvalidTransition):
        qa_workflow.transition(db, call, QAState.appeal_review)


def test_kesinlesme_zamani_ve_kullanicisi_kaydedilir(db, seeded):
    call = make_call(db, seeded)
    qa_workflow.finalize(db, call, user_id=42)
    db.commit()
    assert call.qa_state == QAState.final
    assert call.finalized_by == 42
    assert call.finalized_at is not None


def test_kesinlesmis_puan_itirazla_yeniden_acilir(db, seeded):
    call = make_call(db, seeded)
    qa_workflow.finalize(db, call, user_id=1)
    qa_workflow.open_appeal(db, call, user_id=2, reason="Kanit yanlis")
    db.commit()
    assert call.qa_state == QAState.appeal_review


def test_score_is_final_ozelligi(db, seeded):
    call = make_call(db, seeded, qa_state=QAState.human_queue)
    assert call.score_is_final is False
    call.qa_state = QAState.final
    assert call.score_is_final is True


# =========================================================================
# 3.2 Kuyruk kurallari — yedi kural
# =========================================================================

def test_kural1_sifirlanan_cagri_HER_ZAMAN_kuyruga(db, seeded):
    call = make_call(db, seeded, zeroed=True, total_score=0.0)
    d = qa_workflow.evaluate_queue_rules(db, call, rng=Sabit(0.99))
    assert d.should_queue
    assert ReviewReason.critical.value in d.reasons
    assert d.primary == ReviewReason.critical


def test_kural2_kriz_cagrisi_HER_ZAMAN_kuyruga(db, seeded):
    call = make_call(db, seeded, is_crisis=True)
    d = qa_workflow.evaluate_queue_rules(db, call, rng=Sabit(0.99))
    assert ReviewReason.crisis.value in d.reasons


def test_kural3_dusuk_guven_kuyruga(db, seeded):
    call = make_call(db, seeded)
    db.add(Score(call_id=call.id, criterion_name="K", score=8,
                 decision="met", confidence=0.4))
    db.flush()
    d = qa_workflow.evaluate_queue_rules(db, call, rng=Sabit(0.99))
    assert ReviewReason.low_confidence.value in d.reasons


def test_kural3_yetersiz_kanit_kuyruga(db, seeded):
    call = make_call(db, seeded)
    db.add(Score(call_id=call.id, criterion_name="K", score=None,
                 decision="insufficient_evidence", confidence=1.0))
    db.flush()
    d = qa_workflow.evaluate_queue_rules(db, call, rng=Sabit(0.99))
    assert ReviewReason.low_confidence.value in d.reasons


def test_kural4_az_veriyle_yuzdelik_uygulanmaz(db, seeded):
    """n<20 iken yuzdelik hesaplamak ilk gunlerde her cagriyi kuyruga atardi."""
    call = make_call(db, seeded, total_score=10.0)
    d = qa_workflow.evaluate_queue_rules(db, call, rng=Sabit(0.99))
    assert ReviewReason.low_score.value not in d.reasons


def test_kural4_yeterli_veriyle_alt_dilim_kuyruga(db, seeded):
    for i in range(25):
        c = make_call(db, seeded, total_score=50.0 + i, qa_state=QAState.final)
        c.finalized_at = datetime.utcnow()
    db.flush()
    dusuk = make_call(db, seeded, total_score=50.0)
    d = qa_workflow.evaluate_queue_rules(db, dusuk, rng=Sabit(0.99))
    assert ReviewReason.low_score.value in d.reasons


def test_kural5_duygu_puan_uyumsuzlugu(db, seeded):
    call = make_call(db, seeded, emotion_mismatch=True)
    d = qa_workflow.evaluate_queue_rules(db, call, rng=Sabit(0.99))
    assert ReviewReason.emotion_mismatch.value in d.reasons


def test_kural6_rastgele_ornek(db, seeded):
    """Eski temsilcide ornekleme etiketi 'random' olmali."""
    eski = db.get(Agent, seeded["agent_a"])
    eski.created_at = datetime.utcnow() - timedelta(days=400)
    db.flush()
    call = make_call(db, seeded)
    d = qa_workflow.evaluate_queue_rules(db, call, rng=Sabit(0.01))
    assert ReviewReason.random.value in d.reasons


def test_kural6_ornekleme_disinda_kalan_cagri_kuyruga_girmez(db, seeded):
    call = make_call(db, seeded)
    d = qa_workflow.evaluate_queue_rules(db, call, rng=Sabit(0.99))
    assert d.should_queue is False


def test_kural7_yeni_temsilci_daha_yuksek_oranda_ornekleniyor(db, seeded):
    """Yeni temsilci %20, digerleri %5. 0.10 rastgele deger: yalniz yeni temsilci."""
    yeni = Agent(tenant_id=seeded["tenant_a"], name="yeni.temsilci",
                 created_at=datetime.utcnow() - timedelta(days=3))
    db.add(yeni)
    db.flush()
    call = make_call(db, seeded)
    call.agent_id = yeni.id
    db.flush()

    d = qa_workflow.evaluate_queue_rules(db, call, rng=Sabit(0.10))
    assert ReviewReason.new_agent.value in d.reasons


def test_kural7_eski_temsilci_ayni_oranda_ornekleme_disinda(db, seeded):
    eski = db.get(Agent, seeded["agent_a"])
    eski.created_at = datetime.utcnow() - timedelta(days=400)
    db.flush()
    call = make_call(db, seeded)
    d = qa_workflow.evaluate_queue_rules(db, call, rng=Sabit(0.10))
    assert d.should_queue is False


def test_kurallar_birikimli(db, seeded):
    call = make_call(db, seeded, zeroed=True, is_crisis=True, emotion_mismatch=True)
    d = qa_workflow.evaluate_queue_rules(db, call, rng=Sabit(0.99))
    assert len(d.reasons) == 3
    assert d.primary == ReviewReason.critical  # en yuksek oncelik


def test_yonlendirme_risk_yoksa_dogrudan_kesinlesir(db, seeded):
    """%100 kapsam: her cagriyi insana yollamak urunun vaadini bozar."""
    call = make_call(db, seeded)
    d = qa_workflow.route_after_scoring(db, call, rng=Sabit(0.99))
    db.commit()
    assert d.should_queue is False
    assert call.qa_state == QAState.final


def test_yonlendirme_risk_varsa_kuyruga(db, seeded):
    call = make_call(db, seeded, zeroed=True)
    d = qa_workflow.route_after_scoring(db, call, rng=Sabit(0.99))
    db.commit()
    assert d.should_queue is True
    assert call.qa_state == QAState.human_queue
    assert call.queue_reasons == [ReviewReason.critical.value]


def test_tenant_ayari_esikleri_ezer(db, seeded):
    eski = db.get(Agent, seeded["agent_a"])
    eski.created_at = datetime.utcnow() - timedelta(days=400)
    tenant = db.get(Tenant, seeded["tenant_a"])
    tenant.settings = {"qa": {"random_sample_rate": 0.5}}
    db.flush()
    call = make_call(db, seeded)
    d = qa_workflow.evaluate_queue_rules(db, call, tenant=tenant, rng=Sabit(0.3))
    assert ReviewReason.random.value in d.reasons


def test_yeni_temsilci_orani_kiraci_oranini_DUSURMEZ(db, seeded):
    """Kiraci %50 ayarladiysa yeni temsilci %20'ye dusurulemez.

    Ilk uygulamada yeni temsilci orani kiraci oraninin YERINE geciyordu;
    kiraci ornekleme oranini yukseltse bile yeni temsilciler daha AZ
    orneklenir hale geliyordu.
    """
    yeni = Agent(tenant_id=seeded["tenant_a"], name="yeni2",
                 created_at=datetime.utcnow() - timedelta(days=2))
    db.add(yeni)
    tenant = db.get(Tenant, seeded["tenant_a"])
    tenant.settings = {"qa": {"random_sample_rate": 0.5, "new_agent_sample_rate": 0.2}}
    db.flush()
    call = make_call(db, seeded)
    call.agent_id = yeni.id
    db.flush()

    d = qa_workflow.evaluate_queue_rules(db, call, tenant=tenant, rng=Sabit(0.3))
    assert d.should_queue, "Kiraci orani (%50) yeni temsilci orani (%20) ile ezilmis"


# =========================================================================
# 3.4 Geri besleme dongusu
# =========================================================================

def _crit(db, seeded, name="Aktif Dinleme") -> Criterion:
    c = Criterion(tenant_id=seeded["tenant_a"], name=name,
                  description="d", group="Iletisim")
    db.add(c)
    db.flush()
    return c


def test_tek_duzeltmeden_genelleme_yapilmaz(db, seeded):
    """MIN_EXAMPLES esigi altinda prompt'a enjeksiyon YOK."""
    c = _crit(db, seeded)
    review_feedback.record_correction(
        db, tenant_id=seeded["tenant_a"], criterion_id=c.id, call_id=None,
        excerpt="ornek", ai_score=9, human_score=4, reason_code="baglam_kacirildi")
    db.flush()
    assert review_feedback.examples_for(db, seeded["tenant_a"], c.id) == []
    assert review_feedback.build_block(db, seeded["tenant_a"], [c]) == ""


def test_yeterli_ornek_birikince_few_shot_uretilir(db, seeded):
    c = _crit(db, seeded)
    for i in range(review_feedback.MIN_EXAMPLES):
        review_feedback.record_correction(
            db, tenant_id=seeded["tenant_a"], criterion_id=c.id, call_id=None,
            excerpt=f"transkript {i}", ai_score=9, human_score=4,
            reason_code="kriter_yanlis_yorumlandi", note="temsilci kesmedi")
    db.flush()

    block = review_feedback.build_block(db, seeded["tenant_a"], [c])
    assert "Aktif Dinleme" in block
    assert "AI puani: 9 -> UZMAN puani: 4" in block
    assert "temsilci kesmedi" in block


def test_pasif_ornek_prompt_a_girmez(db, seeded):
    c = _crit(db, seeded)
    for i in range(review_feedback.MIN_EXAMPLES):
        ex = review_feedback.record_correction(
            db, tenant_id=seeded["tenant_a"], criterion_id=c.id, call_id=None,
            excerpt="x", ai_score=9, human_score=4, reason_code="diger")
        ex.is_active = False
    db.flush()
    assert review_feedback.build_block(db, seeded["tenant_a"], [c]) == ""


def test_kalibrasyon_surumu_ornek_degisince_degisir(db, seeded):
    c = _crit(db, seeded)
    v0 = review_feedback.calibration_version(db, seeded["tenant_a"])
    review_feedback.record_correction(
        db, tenant_id=seeded["tenant_a"], criterion_id=c.id, call_id=None,
        excerpt="x", ai_score=9, human_score=4, reason_code="diger")
    db.flush()
    assert review_feedback.calibration_version(db, seeded["tenant_a"]) != v0


def test_overturn_orani_hesaplanir(db, seeded):
    call = make_call(db, seeded)
    c = _crit(db, seeded)
    db.add(Score(call_id=call.id, criterion_id=c.id, criterion_name=c.name,
                 score=8, reviewed_at=datetime.utcnow()))
    db.add(Score(call_id=call.id, criterion_id=c.id, criterion_name=c.name,
                 score=9, reviewed_at=datetime.utcnow(), override_score=5,
                 override_reason_code="kanit_yanlis"))
    db.flush()

    st = review_feedback.overturn_stats(db, seeded["tenant_a"])
    assert st["incelenen"] == 2
    assert st["duzeltilen"] == 1
    assert st["overturn_orani"] == 0.5
    assert st["gerekce_dagilimi"] == {"kanit_yanlis": 1}


# =========================================================================
# Enum kalicilik — DB'ye ADI degil DEGERI yazilmali
# =========================================================================

def test_qa_state_veritabanina_DEGER_olarak_yazilir(db, seeded):
    """SQLAlchemy varsayilani enum ADINI yazar ('final'); migration ve API ise
    DEGERI kullaniyor ('kesinlesti'). Ikisi ayrisirsa okuma LookupError verir.

    Bu, canli sistemde bizzat yasandi: `make eval` kosumu
    "'kesinlesti' is not among the defined enum values" ile dustu.
    """
    from sqlalchemy import text

    call = make_call(db, seeded)
    qa_workflow.finalize(db, call, user_id=1)
    db.commit()

    ham = db.execute(
        text("SELECT qa_state FROM calls WHERE id = :i"), {"i": call.id}
    ).scalar()
    assert ham == "kesinlesti", f"DB'ye enum ADI yazilmis: {ham!r}"


def test_migrationdaki_deger_okunabilir(db, seeded):
    """Migration'in yazdigi ham deger ORM tarafindan okunabilmeli."""
    from sqlalchemy import text

    call = make_call(db, seeded)
    db.commit()
    db.execute(text("UPDATE calls SET qa_state='insan_kuyrugunda' WHERE id=:i"),
               {"i": call.id})
    db.commit()
    db.expire_all()

    tekrar = db.get(Call, call.id)
    assert tekrar.qa_state == QAState.human_queue
