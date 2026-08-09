"""FAZ 4.2 — Alarm motoru: şablon, tekilleştirme, şiddet, yaşam döngüsü.

## Kapatılan hatalar

**B4 — bozuk şablon.** Alarm metni tek bir serbest string olarak kuruluyordu
(`f"Yasakli kelime ({kategori}): '{terim}' — {kanit[:80]}"`). Tespit edilen
ifade ile gösterilen alıntı birbirini tutmadığında kullanıcı
*"'kesin çözülür' — Kesinlikle daha avantajlı"* gibi anlamsız bir cümle
görüyordu. Artık her alarm **zorunlu alanlarla** üretilir; alanlar eksikse
alarm oluşturulamaz.

**B12 — tekrarlar.** Aynı ihlal aynı çağrıda birden çok alarm üretiyordu
(#18 için 4 alarm, #13/#12/#11 için aynı KVKK alarmı ikişer kez; rozet "22"
ama çoğu kopya). Artık `(call_id, rule_id, evidence_hash)` üçlüsü tekildir;
tekrar gelen ihlal `occurrence_count` artırır.

## Şiddet ve rozet
`kritik` (sıfırlayıcı, kriz) · `yuksek` · `bilgi`.
**Rozet sayacı yalnızca `kritik` + `yuksek` sayar** — "bilgi" seviyesindeki
alarmlar rozeti şişirip kullanıcıyı alarm körlüğüne itiyordu.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from ..models import Alert, AlertType

logger = logging.getLogger(__name__)

SEVERITIES = ("kritik", "yuksek", "bilgi")
# Rozet (okunmamış sayacı) yalnızca bunları sayar.
BADGE_SEVERITIES = ("kritik", "yuksek")

LIFECYCLE = ("yeni", "okundu", "aksiyon_alindi", "gecersiz_isaretlendi")


class AlertTemplateError(ValueError):
    """Zorunlu alanı eksik alarm — şablon motoru bunu üretemez."""


@dataclass
class AlertDraft:
    """Bir alarmın üretilmeden önceki tam hâli.

    Zorunlu alanlar burada toplanır ve `validate()` geçmeden DB'ye yazılmaz.
    Serbest metinle alarm üretme yolu KAPALIDIR.
    """

    type: AlertType
    severity: str
    rule_id: str
    title_tr: str
    explanation_tr: str
    suggested_action_tr: str
    call_id: int | None = None
    evidence_quote: str = ""
    evidence_timestamp: float | None = None
    extra: dict = field(default_factory=dict)

    def validate(self) -> None:
        eksik = [
            ad for ad, deger in (
                ("rule_id", self.rule_id),
                ("title_tr", self.title_tr),
                ("explanation_tr", self.explanation_tr),
                ("suggested_action_tr", self.suggested_action_tr),
            ) if not (deger or "").strip()
        ]
        if eksik:
            raise AlertTemplateError(
                f"Alarm zorunlu alanlari eksik: {', '.join(eksik)} (rule_id={self.rule_id!r})"
            )
        if self.severity not in SEVERITIES:
            raise AlertTemplateError(
                f"Gecersiz siddet: {self.severity!r} (gecerli: {SEVERITIES})"
            )

    @property
    def evidence_hash(self) -> str:
        """Tekillik anahtarının kanıt bileşeni.

        Kanıt yoksa kuralın kendisi anahtardır — böylece "KVKK anonsu yok"
        gibi kanıtsız (yokluk) bulguları da çağrı başına tek alarm üretir.
        """
        temel = (self.evidence_quote or "").strip().lower() or f"__rule__{self.rule_id}"
        return hashlib.sha1(temel.encode("utf-8")).hexdigest()[:40]

    @property
    def message(self) -> str:
        """Geriye dönük uyumluluk: eski `message` alanı başlık + açıklama."""
        return f"{self.title_tr} — {self.explanation_tr}"


def emit(db: Session, tenant_id: int, team_id: int | None,
         draft: AlertDraft) -> tuple[Alert, bool]:
    """Alarmı üret ya da mevcut olanın sayacını artır.

    Doner: (alarm, yeni_mi). `yeni_mi=False` ise bu bir TEKRARDIR ve yeni satır
    açılmamıştır — B12'nin çözümü budur.
    """
    draft.validate()

    mevcut = None
    if draft.call_id is not None:
        mevcut = (
            db.query(Alert)
            .filter(
                Alert.call_id == draft.call_id,
                Alert.rule_id == draft.rule_id,
                Alert.evidence_hash == draft.evidence_hash,
                Alert.is_stale.is_(False),
            )
            .first()
        )

    if mevcut is not None:
        mevcut.occurrence_count = (mevcut.occurrence_count or 1) + 1
        logger.debug("Alarm tekrari (call=%s rule=%s) -> sayac %d",
                     draft.call_id, draft.rule_id, mevcut.occurrence_count)
        return mevcut, False

    alert = Alert(
        tenant_id=tenant_id, call_id=draft.call_id, team_id=team_id,
        type=draft.type, severity=draft.severity, message=draft.message,
        title_tr=draft.title_tr, explanation_tr=draft.explanation_tr,
        evidence_quote=draft.evidence_quote,
        evidence_timestamp=draft.evidence_timestamp,
        suggested_action_tr=draft.suggested_action_tr,
        rule_id=draft.rule_id, evidence_hash=draft.evidence_hash,
        occurrence_count=1, lifecycle="yeni",
    )
    db.add(alert)
    # Flush ZORUNLU: `emit` bir dongude arka arkaya cagriliyor ve tekillik
    # sorgusu henuz flush edilmemis satiri GOREMEZ. Flush olmadan ayni toplu
    # islemdeki iki ozdes alarm ikisi de yazilirdi — B12'nin ta kendisi.
    db.flush()
    return alert, True


def set_lifecycle(db: Session, alert: Alert, durum: str, note: str = "") -> Alert:
    """Alarm yaşam döngüsünü ilerlet.

    `gecersiz_isaretlendi` de bir KALİBRASYON SİNYALİDİR: kullanıcı "bu alarm
    yanlış" diyorsa kural fazla hassas demektir. Bu yüzden alarm silinmez,
    işaretlenir ve raporlanır.
    """
    if durum not in LIFECYCLE:
        raise ValueError(f"Gecersiz alarm durumu: {durum!r}")
    alert.lifecycle = durum
    alert.lifecycle_note = note
    if durum in ("okundu", "aksiyon_alindi", "gecersiz_isaretlendi"):
        alert.is_read = True
    return alert


def badge_count(db: Session, tenant_id: int, team_id: int | None = None) -> int:
    """Rozet sayacı — YALNIZCA kritik + yüksek, okunmamış ve geçerli alarmlar.

    Önceden tüm alarmlar sayılıyordu; "bilgi" seviyesindekiler ve kopyalar
    rozeti şişirip kullanıcıyı alarm körlüğüne itiyordu.
    """
    q = db.query(Alert).filter(
        Alert.tenant_id == tenant_id,
        Alert.is_read.is_(False),
        Alert.is_stale.is_(False),
        Alert.severity.in_(BADGE_SEVERITIES),
    )
    if team_id is not None:
        q = q.filter((Alert.team_id == team_id) | (Alert.team_id.is_(None)))
    return q.count()


# ---------------------------------------------------------------------------
# Şablonlar — her alarm türü için zorunlu alanları dolduran tek yer
# ---------------------------------------------------------------------------

def zeroing_alert(call_id: int, kriter: str, gerekce: str,
                  kanit: str, ts: float | None) -> AlertDraft:
    return AlertDraft(
        type=AlertType.zeroing, severity="kritik", rule_id=f"zeroing:{kriter}",
        call_id=call_id,
        title_tr=f"Sıfırlayıcı ihlal — {kriter}",
        explanation_tr=gerekce,
        evidence_quote=kanit, evidence_timestamp=ts,
        suggested_action_tr=(
            "Çağrıyı dinleyip sıfırlamayı onaylayın veya düzeltin. Onaylarsanız "
            "temsilciye aynı gün geri bildirim verin."
        ),
    )


def banned_word_alert(call_id: int, terim: str, kategori: str, siddet: str,
                      kanit: str, ts: float | None) -> AlertDraft:
    return AlertDraft(
        type=AlertType.banned_word,
        severity="kritik" if siddet == "yuksek" else "yuksek",
        rule_id=f"banned:{kategori}:{terim}", call_id=call_id,
        title_tr=f"Yasaklı ifade — {kategori}",
        explanation_tr=f"Temsilci \"{terim}\" ifadesini kullandı.",
        evidence_quote=kanit, evidence_timestamp=ts,
        suggested_action_tr=(
            "Alıntıyı dinleyip bağlamı doğrulayın. İhlal gerçekse temsilciye "
            "koçluk görevi açın."
        ),
    )


def compliance_alert(call_id: int, kural: str, aciklama: str,
                     kanit: str, ts: float | None) -> AlertDraft:
    return AlertDraft(
        type=AlertType.banned_word, severity="kritik",
        rule_id=f"compliance:{kural}", call_id=call_id,
        title_tr="Uyum ihlali",
        explanation_tr=aciklama,
        evidence_quote=kanit, evidence_timestamp=ts,
        suggested_action_tr=(
            "Zorunlu anonsun yapılıp yapılmadığını kayıttan doğrulayın; "
            "yapılmadıysa temsilciye uyum eğitimi planlayın."
        ),
    )


def crisis_alert(call_id: int, kanit: str, ts: float | None) -> AlertDraft:
    return AlertDraft(
        type=AlertType.crisis, severity="kritik", rule_id="crisis:eskalasyon",
        call_id=call_id,
        title_tr="Kriz sinyali — müşteri eskalasyon belirtisi",
        explanation_tr="Müşteri hukuki süreç, şikâyet veya iptal tehdidinde bulundu.",
        evidence_quote=kanit, evidence_timestamp=ts,
        suggested_action_tr=(
            "Bugün içinde müşteriyi geri arayın ve konuyu yönetici takibine alın."
        ),
    )


def low_score_alert(call_id: int, puan: float) -> AlertDraft:
    return AlertDraft(
        type=AlertType.low_score, severity="yuksek", rule_id="low_score",
        call_id=call_id,
        title_tr=f"Düşük kalite puanı — {puan:.1f}",
        explanation_tr="Çağrı, kalite eşiğinin altında puanlandı.",
        suggested_action_tr="Çağrıyı inceleyip gelişim alanını temsilciyle paylaşın.",
    )


def review_needed_alert(call_id: int, kriterler: str, adet: int) -> AlertDraft:
    return AlertDraft(
        type=AlertType.low_score, severity="bilgi", rule_id="review_needed",
        call_id=call_id,
        title_tr="Kalite uzmanı onayı bekliyor",
        explanation_tr=f"{adet} kriter yeterli kanıtla puanlanamadı ({kriterler}).",
        suggested_action_tr="İnceleme kuyruğundan çağrıyı açıp kriterleri onaylayın.",
    )


def emotion_mismatch_alert(call_id: int) -> AlertDraft:
    return AlertDraft(
        type=AlertType.low_score, severity="bilgi", rule_id="emotion_mismatch",
        call_id=call_id,
        title_tr="Duygu–puan uyumsuzluğu",
        explanation_tr=(
            "Müşterinin duygu durumu ile tahmini memnuniyet çelişiyor; "
            "puanlamada bir hata olabilir."
        ),
        suggested_action_tr="Çağrıyı dinleyip puanı doğrulayın.",
    )
