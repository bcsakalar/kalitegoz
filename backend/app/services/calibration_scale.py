"""Post-hoc skala kalibrasyonu — LLM puanını uzman ölçeğine hizalar.

## Neden gerekli

FAZ 2 ölçümü, LLM ile puanlanan kriterlerde **sistematik ve tek yönlü** bir
sapma gösterdi (altın set, n=45-49 kriter başına):

    Aktif Dinleme        ortalama sapma  +1.73
    Cozum / Yonlendirme  ortalama sapma  +1.24
    Ihtiyac Analizi      ortalama sapma  +1.16

Bu rastgele gürültü değil, **ölçek hizasızlığı**: model uzmandan sistematik
olarak cömert puanlıyor. Literatürde LLM-as-a-judge'ın üç tekrarlayan hata
modundan biri ("insan ölçeğiyle hizasızlık", arXiv 2601.08654). Çözümü de
oradan: sonradan kalibrasyon.

## Ne yapar, ne YAPMAZ

YAPAR: kriter bazında öğrenilmiş bir kaydırma uygular, sürümü kaydeder.
YAPMAZ: geçmiş puanları geriye dönük değiştirmez, düzeltmeleri gizlice
ağırlıklara işlemez. Her kalibrasyon etkisi sürümlenir ve raporlanır
(prompt "asla yapma" ilkesi: kalibrasyon şeffaf olmalı).

Deterministik kriterler (Katman A) **kalibre EDİLMEZ** — onların sapması
zaten sıfır ve kalibrasyon yalnızca gürültü ekler.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Kalibrasyon sürümü. Her puanlama kaydı bunu taşır; kalibrasyon değişince
# artar ve öncesi/sonrası karşılaştırılabilir olur.
CALIBRATION_VERSION = "cal-2026-08-09"

# Kaydırma, altın set ölçümünden öğrenildi: ortalama sapmanın tersi.
# Yalnızca |sapma| >= 1.0 olan kriterlere uygulanır — daha küçük sapmayı
# düzeltmek örneklem gürültüsünü kovalamak olur (n=45-49).
_MIN_BIAS = 1.0

_DEFAULT_OFFSETS: dict[str, float] = {
    "Aktif Dinleme": -1.7,
    "Cozum / Yonlendirme": -1.2,
    "Ihtiyac Analizi": -1.2,
}

_OVERRIDE_PATH = Path("/data/calibration/offsets.json")


def _load_offsets() -> dict[str, float]:
    """Kalibrasyonu dosyadan oku (varsa); yoksa gömülü değerler.

    `make eval` ölçümünden yeni kaydırmalar üretilip buraya yazılabilir —
    böylece kalibrasyon kod değişikliği gerektirmez, ama yine de sürümlenir.
    """
    try:
        if _OVERRIDE_PATH.exists():
            data = json.loads(_OVERRIDE_PATH.read_text(encoding="utf-8"))
            offsets = data.get("offsets", {})
            if isinstance(offsets, dict):
                return {str(k): float(v) for k, v in offsets.items()}
    except Exception as exc:  # noqa: BLE001 — kalibrasyon dosyasi puanlamayi dusurmez
        logger.warning("Kalibrasyon dosyasi okunamadi: %s", exc)
    return dict(_DEFAULT_OFFSETS)


def offset_for(criterion_name: str) -> float:
    off = _load_offsets().get(criterion_name, 0.0)
    return off if abs(off) >= _MIN_BIAS else 0.0


# Ölçülmüş kriter güvenilirliği (altın set kappa'sı, sınav altkümesi).
# Bu tablo bir performans notu değil, bir ÜRÜN DAVRANIŞI girdisidir: sistemin
# güvenilir olmadığını BİLDİĞİ kriterde puanı düşük güvenle işaretler ve
# çağrıyı insan kuyruğuna gönderir (qa_workflow kural 3).
#
# "Yapay zekâ %100 doğru" iddiası kurmak yerine sistemin sınırını bilmesi ve
# yönetmesi, ürünün satış argümanıdır.
MEASURED_KAPPA: dict[str, float] = {
    "KVKK / Aydinlatma": 1.00,
    "Yasakli Kelime / Uslup": 1.00,
    "Acilis": 1.00,
    "Kapanis": 0.90,
    "Kimlik Dogrulama": 0.49,
    "Bilgi Dogrulugu": 0.21,
    "Script Uyumu": 0.19,
    "Cozum / Yonlendirme": 0.13,
    "Aktif Dinleme": 0.04,
    "Ihtiyac Analizi": 0.03,
}
# Bu kappa'nın altındaki kriterler GÜVENİLİR SAYILMAZ; güven skoru tavanlanır ve
# çağrı insan onayına düşer. 0.40, "orta düzeyde uyum" sınırı olarak kabul edilir.
RELIABLE_KAPPA = 0.40
# Güvenilmez kriterin güven skoru bu değeri aşamaz. qa_workflow eşiği 0.70
# olduğu için bu, insan incelemesini GARANTİ eder.
UNRELIABLE_CONFIDENCE_CAP = 0.60


def confidence_cap(criterion_name: str, source_layer: str) -> float | None:
    """Bu kriterde AI'nin puanı ne kadar güvenilir? None = sınır yok."""
    if source_layer == "A":
        return None  # deterministik karar, ölçülen kappa'sı zaten 0.90+
    kappa = MEASURED_KAPPA.get(criterion_name)
    if kappa is None or kappa >= RELIABLE_KAPPA:
        return None
    return UNRELIABLE_CONFIDENCE_CAP


def apply(criterion_name: str, score: int | None, *, source_layer: str) -> int | None:
    """Puanı uzman ölçeğine hizala. 0-10 dışına taşmaz.

    Katman A (deterministik) puanları DEĞİŞTİRİLMEZ: sapmaları zaten sıfır.
    """
    if score is None or source_layer == "A":
        return score
    off = offset_for(criterion_name)
    if not off:
        return score
    return max(0, min(10, round(score + off)))
