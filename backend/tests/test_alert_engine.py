"""FAZ 4.2 — alarm motoru: B4 (sablon) ve B12 (tekrarlar) regresyonu."""

from __future__ import annotations

import pytest

from app.models import Alert, AlertType
from app.services import alert_engine as ae

from .conftest import TestingSession


@pytest.fixture
def db(seeded):
    s = TestingSession()
    try:
        yield s
    finally:
        s.close()


# =========================================================================
# B4 — sablon zorunlu alanlari
# =========================================================================

def test_zorunlu_alan_eksikse_alarm_URETILEMEZ():
    """Serbest metinle alarm uretme yolu KAPALI olmali."""
    draft = ae.AlertDraft(
        type=AlertType.banned_word, severity="yuksek", rule_id="",
        title_tr="", explanation_tr="", suggested_action_tr="",
    )
    with pytest.raises(ae.AlertTemplateError) as exc:
        draft.validate()
    for alan in ("rule_id", "title_tr", "explanation_tr", "suggested_action_tr"):
        assert alan in str(exc.value)


def test_gecersiz_siddet_reddedilir():
    draft = ae.AlertDraft(
        type=AlertType.low_score, severity="orta", rule_id="x",
        title_tr="a", explanation_tr="b", suggested_action_tr="c",
    )
    with pytest.raises(ae.AlertTemplateError):
        draft.validate()


def test_yasakli_kelime_sablonu_terim_ve_alintiyi_AYRI_tutar():
    """B4'un kalbi: tespit edilen terim ile gosterilen alinti karismamali."""
    d = ae.banned_word_alert(
        1, terim="kesin çözülür", kategori="yasak_vaat", siddet="yuksek",
        kanit="Merak etmeyin, bu sorun kesin çözülür.", ts=42.0,
    )
    d.validate()
    assert "kesin çözülür" in d.explanation_tr     # tespit edilen terim
    assert d.evidence_quote.startswith("Merak")     # gosterilen alinti AYRI alan
    assert d.evidence_timestamp == 42.0
    assert d.suggested_action_tr


def test_her_sablon_gecerli():
    """Tum sablonlar zorunlu alanlari dolduruyor olmali."""
    for d in (
        ae.zeroing_alert(1, "KVKK", "anons yok", "kanit", 1.0),
        ae.banned_word_alert(1, "aptal", "hakaret", "yuksek", "alinti", 2.0),
        ae.compliance_alert(1, "kvkk_anons", "aciklama", "kanit", None),
        ae.crisis_alert(1, "avukatima verecegim", 5.0),
        ae.low_score_alert(1, 42.5),
        ae.review_needed_alert(1, "Aktif Dinleme", 2),
        ae.emotion_mismatch_alert(1),
    ):
        d.validate()  # firlatmamali
        assert d.title_tr and d.explanation_tr and d.suggested_action_tr


# =========================================================================
# B12 — tekrarlar
# =========================================================================

def test_ayni_ihlal_ikinci_kez_YENI_SATIR_ACMAZ(db, seeded):
    d = ae.banned_word_alert(1, "aptal", "hakaret", "yuksek", "Aptalca konusma", 3.0)

    a1, yeni1 = ae.emit(db, seeded["tenant_a"], None, d)
    db.flush()
    a2, yeni2 = ae.emit(db, seeded["tenant_a"], None, d)
    db.flush()

    assert yeni1 is True
    assert yeni2 is False, "Ayni ihlal ikinci alarm satiri acti (B12 geri geldi)"
    assert a1.id == a2.id
    assert a2.occurrence_count == 2
    assert db.query(Alert).filter(Alert.call_id == 1).count() == 1


def test_farkli_kanit_AYRI_alarm_uretir(db, seeded):
    d1 = ae.banned_word_alert(1, "aptal", "hakaret", "yuksek", "Birinci alinti", 3.0)
    d2 = ae.banned_word_alert(1, "aptal", "hakaret", "yuksek", "Ikinci farkli alinti", 9.0)
    ae.emit(db, seeded["tenant_a"], None, d1)
    ae.emit(db, seeded["tenant_a"], None, d2)
    db.flush()
    assert db.query(Alert).filter(Alert.call_id == 1).count() == 2


def test_kanitsiz_bulgu_da_cagri_basina_TEK_alarm(db, seeded):
    """'KVKK anonsu yok' gibi yokluk bulgusunda kanit yoktur; kural anahtardir."""
    d = ae.compliance_alert(1, "kvkk_anons", "Anons yapilmadi", "", None)
    ae.emit(db, seeded["tenant_a"], None, d)
    ae.emit(db, seeded["tenant_a"], None, d)
    db.flush()
    assert db.query(Alert).filter(Alert.call_id == 1).count() == 1


def test_gecersizlesen_alarm_dedup_engelini_kaldirir(db, seeded):
    """Yeniden puanlamada eski alarm gecersizlesir; yenisi uretilebilmeli."""
    d = ae.crisis_alert(1, "avukat", 1.0)
    a1, _ = ae.emit(db, seeded["tenant_a"], None, d)
    db.flush()
    a1.is_stale = True
    db.flush()

    a2, yeni = ae.emit(db, seeded["tenant_a"], None, d)
    db.flush()
    assert yeni is True
    assert a2.id != a1.id


# =========================================================================
# Rozet sayaci ve yasam dongusu
# =========================================================================

def test_rozet_yalniz_kritik_ve_yuksek_sayar(db, seeded):
    t = seeded["tenant_a"]
    ae.emit(db, t, None, ae.crisis_alert(1, "avukat", 1.0))            # kritik
    ae.emit(db, t, None, ae.low_score_alert(2, 40.0))                  # yuksek
    ae.emit(db, t, None, ae.emotion_mismatch_alert(3))                 # bilgi
    ae.emit(db, t, None, ae.review_needed_alert(4, "Aktif Dinleme", 1))  # bilgi
    db.commit()

    assert ae.badge_count(db, t) == 2, "Bilgi seviyesi alarmlar rozeti sisiriyor"


def test_okunan_alarm_rozetten_duser(db, seeded):
    t = seeded["tenant_a"]
    a, _ = ae.emit(db, t, None, ae.crisis_alert(1, "avukat", 1.0))
    db.commit()
    assert ae.badge_count(db, t) == 1

    ae.set_lifecycle(db, a, "okundu")
    db.commit()
    assert ae.badge_count(db, t) == 0


def test_gecersiz_isaretlenen_alarm_SILINMEZ(db, seeded):
    """'Bu alarm yanlis' bilgisi bir kalibrasyon sinyalidir, saklanir."""
    t = seeded["tenant_a"]
    a, _ = ae.emit(db, t, None, ae.crisis_alert(1, "avukat", 1.0))
    db.commit()

    ae.set_lifecycle(db, a, "gecersiz_isaretlendi", note="Musteri saka yapiyordu")
    db.commit()

    assert db.query(Alert).filter(Alert.id == a.id).count() == 1
    assert a.lifecycle == "gecersiz_isaretlendi"
    assert a.lifecycle_note
    assert ae.badge_count(db, t) == 0


def test_gecersiz_yasam_dongusu_reddedilir(db, seeded):
    a, _ = ae.emit(db, seeded["tenant_a"], None, ae.crisis_alert(1, "x", 1.0))
    with pytest.raises(ValueError):
        ae.set_lifecycle(db, a, "bilinmeyen_durum")
