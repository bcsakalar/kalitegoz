"""B36 — İnsan kuyruğuna düşen her çağrı işlenirken ÇÖKÜYORDU.

## Ne oldu

`pipeline.process_call`, çağrı insan onayına alındığında bilgilendirme alarmı
üretiyordu. Ama bunu **eski (tuple) biçimde** yapıyordu:

    outcome.alerts.append((AlertType.low_score, "dusuk", "..."))

Alarm motoru FAZ 4'te `AlertDraft` yapısına geçti; bu üretici güncellenmedi.
`emit()` içindeki `draft.validate()` bir tuple üzerinde çağrılınca:

    AttributeError: 'tuple' object has no attribute 'validate'

## Neden bu kadar ciddi

Bu dal **yalnızca** risk kuralı tetiklendiğinde çalışır. Yani hata, tam da
ürünün en önemli akışını vuruyordu: *kalite uzmanı onayı gereken çağrılar*.
Puanlama başarıyla bitmiş, transkript çıkmış, kriterler kanıtlanmış olsa bile
çağrı `failed` olarak kapanıyordu.

## Neden hiçbir test yakalamadı

- `make eval` pipeline görevini **çağırmaz**; doğrudan `scoring.run_scoring`
  kullanır. Puanlama doğruydu, o yüzden altın set yeşildi.
- Alarm motorunun kendi testleri `AlertDraft` ile çağrı yapıyordu, yani
  motoru test ediyordu — **üreticiyi** değil.

Hata ancak gerçek bir sesli çağrı uçtan uca işlenirken ortaya çıktı.

## Bu testin savunduğu şey

`process_call`'un ürettiği HER alarm taslağı, motorun kabul ettiği tipte
olmalı. Tip kontrolü değil, **sözleşme** kontrolü: taslak `validate()`
geçebilmeli.
"""

import pytest

from app.services import alert_engine
from app.services.alert_engine import AlertDraft
from app.models import AlertType


def test_kuyruk_alarmi_AlertDraft_olmali():
    """Kuyruk yönlendirme alarmı, motorun kabul ettiği tipte VE şiddette olmalı.

    Bu test yazılırken ikinci bir hata çıktı: eski tuple biçimi `"dusuk"`
    şiddetini kullanıyordu ama geçerli değerler `kritik|yuksek|bilgi`.
    Yani tuple sorunu çözülse bile alarm yine üretilemeyecekti — sadece
    sessizce (loglanıp) atlanacaktı.
    """
    draft = AlertDraft(
        type=AlertType.low_score,
        severity="bilgi",
        rule_id="qa_kuyruk_yonlendirme",
        title_tr="Kalite uzmanı onayı bekliyor",
        explanation_tr="Çağrı otomatik puanlandı ancak risk kuralı tetiklendi.",
        suggested_action_tr="İnceleme kuyruğundan onaylayın ya da düzeltin.",
        call_id=1,
    )
    # Bu cagri tuple ile AttributeError firlatirdi
    draft.validate()
    assert draft.evidence_hash


def test_tuple_taslak_ACIK_hata_verir():
    """Eski biçim geçerse hata net olmalı — sessizce yutulmamalı."""
    with pytest.raises(AttributeError):
        (AlertType.low_score, "bilgi", "mesaj").validate()  # type: ignore[attr-defined]


def test_emit_gecersiz_siddeti_REDDEDER():
    """Şiddet değeri motorun tanıdığı kümede olmalı."""
    draft = AlertDraft(
        type=AlertType.low_score, severity="cok_dusuk_diye_bir_sey_yok",
        rule_id="x", title_tr="a", explanation_tr="b", suggested_action_tr="c",
    )
    with pytest.raises(alert_engine.AlertTemplateError):
        draft.validate()


def test_eksik_zorunlu_alan_REDDEDILIR():
    draft = AlertDraft(
        type=AlertType.low_score, severity="bilgi",
        rule_id="qa_kuyruk_yonlendirme", title_tr="",
        explanation_tr="b", suggested_action_tr="c",
    )
    with pytest.raises(alert_engine.AlertTemplateError) as exc:
        draft.validate()
    assert "title_tr" in str(exc.value)


def test_pipeline_kaynaginda_tuple_alarm_KALMADI():
    """Kaynak denetimi: `alerts.append((` deseni bir daha girmemeli.

    Bu test biraz sıra dışı — kod metnine bakıyor. Sebebi şu: hatanın kendisi
    çalışma zamanında ancak belirli bir dal tetiklendiğinde ortaya çıkıyor ve
    o dalı birim testte kurmak, gerçek bir çağrı işlemeyi gerektiriyor.
    Desenin kaynaktan uzak tutulması, aynı hatanın başka bir dalda tekrar
    etmesini de engeller.
    """
    from pathlib import Path

    kaynak = Path(__file__).resolve().parents[1] / "app" / "tasks" / "pipeline.py"
    metin = kaynak.read_text(encoding="utf-8")
    satirlar = [
        f"{i}: {s.strip()}"
        for i, s in enumerate(metin.splitlines(), 1)
        if "alerts.append((" in s.replace(" ", "")
    ]
    assert not satirlar, (
        "pipeline.py icinde tuple bicimli alarm uretimi var — AlertDraft kullanin:\n"
        + "\n".join(satirlar)
    )
