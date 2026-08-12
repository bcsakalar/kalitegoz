"""Gerçek müşteri anketi (CSAT) ve kalite puanıyla korelasyonu.

## Neden bu modül var

Ürün "bu çağrı kaliteli" diyor. Peki bu tanım doğru mu?

Şimdiye kadarki bütün doğrulama **içeriden**ydi: altın set puanlarını sistemi
geliştiren taraf yazdı (`docs/KALITE-METODOLOJISI.md` §4.0), `predicted_csat`'ı
da aynı model üretti. İkisi de rubriğin kendisini sorgulayamaz.

Müşterinin anket puanı **dışarıdan** gelir. Kalite puanı yüksek olan çağrılarda
müşteri memnun değilse, sorun modelde değil **rubrikte**dir: yanlış şeyleri
ölçüyoruzdur. Bu modül o soruyu sorulabilir hale getirir.

## İki ayrı soru, iki ayrı metrik

1. **Rubrik geçerliliği** — kalite puanı ile gerçek CSAT arasındaki
   korelasyon (Pearson r). "Ölçtüğümüz şey müşterinin hissettiğiyle ilgili mi?"
2. **Tahmin doğruluğu** — `predicted_csat` ile `actual_csat` arasındaki
   ortalama hata (MAE). "Model müşterinin puanını tahmin edebiliyor mu?"

Bunlar farklı sorulardır ve karıştırılmamalıdır: rubrik geçerli olup tahmin
kötü olabilir, ya da tersi.

## Dürüstlük kuralı

Örneklem küçükken korelasyon **yayımlanmaz**. 5 çağrıyla hesaplanan r=0.9,
gürültüdür ve satış sunumuna girerse yalan olur. Eşik altında sayı yerine
"yeterli veri yok" döner.

Eşiğin gerekçesi: Pearson r için n<20'de güven aralığı o kadar geniştir ki
r=0.2 ile r=0.7 ayırt edilemez. 20, bu projede kullanılan diğer dürüstlük
kapılarıyla (bkz. `stats_honesty.py`) tutarlı bir alt sınır.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime

from sqlalchemy import and_
from sqlalchemy.orm import Session

from ..models import Call, QAState

logger = logging.getLogger(__name__)

# Altinda korelasyon SAYISI gosterilmez.
MIN_ORNEKLEM = 20

# Kabul edilen kaynaklar — denetimde "bu puan nereden geldi" cevaplanabilsin.
KAYNAKLAR = {"anket", "manuel", "ice_aktarma"}


class CSATHatasi(ValueError):
    """Gecersiz CSAT girisi."""


def dogrula(puan: float, kaynak: str) -> tuple[float, str]:
    """Girdiyi kabul etmeden once dogrula.

    Sessizce kirpmak yerine HATA firlatilir: 7 puanlik bir anketten gelen 7'yi
    5'e kirpmak, olcegin yanlis oldugunu gizler ve veri sessizce bozulur.
    """
    if puan is None:
        raise CSATHatasi("CSAT puani bos olamaz")
    try:
        p = float(puan)
    except (TypeError, ValueError):
        raise CSATHatasi(f"CSAT puani sayi olmali, gelen: {puan!r}") from None
    if not (1.0 <= p <= 5.0):
        raise CSATHatasi(
            f"CSAT puani 1-5 arasinda olmali, gelen: {p}. "
            "Farkli bir olcek kullaniyorsaniz (1-7, 1-10, NPS) once 1-5'e "
            "donusturun — sistemin sessizce donusturmesi olcegi gizler."
        )
    k = (kaynak or "").strip() or "manuel"
    if k not in KAYNAKLAR:
        raise CSATHatasi(f"Gecersiz kaynak: {k!r}. Gecerli: {sorted(KAYNAKLAR)}")
    return p, k


def kaydet(db: Session, call: Call, puan: float, *, kaynak: str = "manuel",
           yorum: str = "") -> Call:
    """Bir cagriya gercek CSAT puanini isle."""
    p, k = dogrula(puan, kaynak)
    call.actual_csat = p
    call.csat_source = k
    call.csat_comment = (yorum or "").strip() or None
    call.csat_at = datetime.utcnow()
    return call


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    """Pearson korelasyon katsayisi. Varyans sifirsa None (tanimsiz)."""
    n = len(xs)
    if n < 2:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx <= 0 or syy <= 0:
        # Tek yonlu sabit veri: korelasyon TANIMSIZ, 0 degil.
        # 0 dondurmek "iliski yok" der; dogrusu "olculemez".
        return None
    return sxy / math.sqrt(sxx * syy)


def _yorumla(r: float) -> str:
    a = abs(r)
    if a >= 0.7:
        güç = "güçlü"
    elif a >= 0.4:
        güç = "orta"
    elif a >= 0.2:
        güç = "zayıf"
    else:
        güç = "yok denecek kadar zayıf"
    yön = "pozitif" if r >= 0 else "NEGATİF"
    return f"{güç} {yön}"


def korelasyon(db: Session, tenant_id: int, *, gunler: int | None = None) -> dict:
    """Kalite puani <-> gercek CSAT iliskisi.

    YALNIZCA kesinlesmis (`final`) cagrilar sayilir: kaliteci onaylamamis bir
    puanla korelasyon hesaplamak, henuz gecerli olmayan bir sayiyi is sonucuyla
    iliskilendirmek olurdu (bkz. B33).
    """
    q = db.query(Call).filter(
        Call.tenant_id == tenant_id,
        Call.actual_csat.isnot(None),
        Call.total_score.isnot(None),
        Call.qa_state == QAState.final,
    )
    if gunler:
        from datetime import timedelta
        q = q.filter(Call.created_at >= datetime.utcnow() - timedelta(days=gunler))
    cagrilar = q.all()

    n = len(cagrilar)
    sonuc: dict = {
        "n": n,
        "yeterli_veri": n >= MIN_ORNEKLEM,
        "asgari_ornekleme": MIN_ORNEKLEM,
        "korelasyon": None,
        "yorum": "",
        "tahmin_mae": None,
        "tahmin_n": 0,
        "mesaj": "",
    }

    if n < MIN_ORNEKLEM:
        sonuc["mesaj"] = (
            f"Korelasyon için yeterli veri yok ({n}/{MIN_ORNEKLEM} çağrı). "
            "Küçük örneklemde korelasyon yayımlamak yanıltıcı olur; "
            "sayı bilinçli olarak gösterilmiyor."
        )
        return sonuc

    r = _pearson([float(c.total_score) for c in cagrilar],
                 [float(c.actual_csat) for c in cagrilar])
    if r is None:
        sonuc["mesaj"] = (
            "Korelasyon hesaplanamadı: puanların ya da CSAT değerlerinin "
            "tamamı aynı. İlişki yok değil — **ölçülemez**."
        )
        return sonuc

    sonuc["korelasyon"] = round(r, 4)
    sonuc["yorum"] = _yorumla(r)
    sonuc["mesaj"] = (
        f"{n} kesinleşmiş çağrıda kalite puanı ile müşteri anketi arasında "
        f"{_yorumla(r)} ilişki (r={r:.2f})."
    )

    # Tahmin dogrulugu AYRI bir soru: model musterinin puanini bilebiliyor mu?
    tahminli = [c for c in cagrilar if c.predicted_csat is not None]
    if tahminli:
        sonuc["tahmin_n"] = len(tahminli)
        sonuc["tahmin_mae"] = round(
            sum(abs(float(c.predicted_csat) - float(c.actual_csat)) for c in tahminli)
            / len(tahminli), 3)

    if r < 0.2:
        sonuc["uyari"] = (
            "Kalite puanı ile müşteri memnuniyeti arasında anlamlı bir ilişki "
            "ÖLÇÜLEMEDİ. Bu, modelin değil **rubriğin** sorgulanması gereken "
            "bir bulgudur: ölçülen kriterler müşterinin önemsediği şeylerle "
            "örtüşmüyor olabilir."
        )
    return sonuc


def dagilim(db: Session, tenant_id: int) -> list[dict]:
    """Kalite bandi basina ortalama gercek CSAT — korelasyonun okunabilir hali.

    Tek bir r sayisi ikna etmez; "90+ alan cagrilarda musteri 4.6, 60 altinda
    2.8 veriyor" cumlesi eder.
    """
    bantlar = [(90, 101, "90-100"), (75, 90, "75-89"), (60, 75, "60-74"), (0, 60, "0-59")]
    cagrilar = db.query(Call).filter(
        Call.tenant_id == tenant_id,
        Call.actual_csat.isnot(None),
        Call.total_score.isnot(None),
        Call.qa_state == QAState.final,
    ).all()

    out = []
    for lo, hi, ad in bantlar:
        grup = [c for c in cagrilar if lo <= float(c.total_score) < hi]
        out.append({
            "bant": ad,
            "n": len(grup),
            "ortalama_csat": (
                round(sum(float(c.actual_csat) for c in grup) / len(grup), 2)
                if grup else None),
        })
    return out
