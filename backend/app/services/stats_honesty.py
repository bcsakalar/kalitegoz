"""İstatistiksel dürüstlük kuralları — B8, B9, B10'un ortak kökü.

Üç hatanın da tek bir sebebi vardı: **sistem, veri yetersizken de bir sayı
üretmek zorunda hissediyordu.**

    B8  n=24 ile "+0.68 güçlü ilişki" denildi
    B9  önceki dönem 0 iken "▲+100%" denildi
    B10 tek veri noktasıyla zaman serisi grafiği çizildi

Bir çağrı merkezi müdürü bu üç şeyi de görür ve ürüne güvenmeyi bırakır.
Doğru davranış, sayı üretmemek ve **neyin eksik olduğunu söylemektir.**

Bu modül, "yeterli veri var mı?" sorusunu tek yerde cevaplar; her analitik uç
buradan geçer. Eşikler burada, çağrı yerlerinde değil — aksi halde her ekran
kendi eşiğini uydururdu.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

# Pearson korelasyonu için asgari örneklem. n<30'da korelasyon katsayısı
# gösterilmez; güven aralığı çok geniştir ve yanıltıcıdır.
MIN_N_CORRELATION = 30
# Dönem karşılaştırması için önceki dönemde asgari gözlem.
MIN_N_PERIOD_COMPARE = 5
# Zaman serisi çizmek için asgari nokta.
MIN_POINTS_TIMESERIES = 7
# Bir temsilcinin sıralamaya girebilmesi için asgari çağrı.
MIN_CALLS_RANKING = 5

Yeterlilik = Literal["yeterli", "yetersiz"]


@dataclass
class Olcum:
    """Bir metrik ve onun **güvenilir olup olmadığı**.

    `deger` None ise arayüz sayı göstermez; `aciklama`yı gösterir.
    Bu tip, "veri yok" durumunu sıfırdan ayırmayı zorunlu kılar.
    """

    deger: float | None
    yeterli: bool
    n: int
    aciklama: str

    def to_dict(self) -> dict:
        return {
            "deger": self.deger,
            "yeterli_veri": self.yeterli,
            "n": self.n,
            "aciklama": self.aciklama,
        }


def pearson(pairs: list[tuple[float, float]]) -> float | None:
    if len(pairs) < 2:
        return None
    n = len(pairs)
    mx = sum(p[0] for p in pairs) / n
    my = sum(p[1] for p in pairs) / n
    cov = sum((x - mx) * (y - my) for x, y in pairs)
    vx = sum((x - mx) ** 2 for x, _ in pairs)
    vy = sum((y - my) ** 2 for _, y in pairs)
    if vx == 0 or vy == 0:
        return None
    return cov / (vx ** 0.5 * vy ** 0.5)


def korelasyon(pairs: list[tuple[float, float]], etiket: str) -> Olcum:
    """B8: n < 30 ise korelasyon KATSAYISI gösterilmez.

    Onun yerine "eğilim gözlemi — henüz istatistiksel olarak anlamlı değil"
    denir. Katsayı gizlenir; gözlem gizlenmez.
    """
    n = len(pairs)
    if n < MIN_N_CORRELATION:
        return Olcum(
            deger=None, yeterli=False, n=n,
            aciklama=(
                f"{etiket} için eğilim gözlemi var ancak henüz istatistiksel olarak "
                f"anlamlı değil (n={n}). Katsayı için en az {MIN_N_CORRELATION} "
                "puanlanmış çağrı gerekir."
            ),
        )
    r = pearson(pairs)
    if r is None:
        return Olcum(None, False, n, f"{etiket} için değişkenlik yok, ilişki hesaplanamaz.")

    # Fisher z ile %95 güven aralığı — katsayıyı yalnız aralığıyla göster.
    import math

    z = 0.5 * math.log((1 + r) / (1 - r)) if abs(r) < 1 else 0.0
    se = 1 / math.sqrt(n - 3) if n > 3 else 0.0
    lo, hi = (math.tanh(z - 1.96 * se), math.tanh(z + 1.96 * se)) if se else (r, r)

    guc = "güçlü" if abs(r) >= 0.5 else ("orta" if abs(r) >= 0.3 else "zayıf")
    yon = "yükseliyor" if r > 0 else "düşüyor"
    return Olcum(
        deger=round(r, 2), yeterli=True, n=n,
        aciklama=(
            f"{etiket} arttıkça puan {yon} ({guc} ilişki, r={r:.2f}, "
            f"%95 GA [{lo:.2f}, {hi:.2f}], n={n}). Nedensellik değil ilişkidir."
        ),
    )


def donem_degisimi(guncel: int, onceki: int, etiket: str = "") -> Olcum:
    """B9: önceki dönem boşsa YÜZDE ÜRETME.

    "Son: 4 / Önceki: 0 / ▲+100%" cümlesi matematiksel olarak anlamsızdır
    (sıfıra bölme) ve kullanıcıya yanlış bir büyüme hissi verir.
    """
    if onceki == 0:
        # Sifira bolme. "Son: 4 / Onceki: 0 / +100%" matematiksel olarak
        # anlamsizdir; tum konularin "+100%" gorunmesi bundandi.
        return Olcum(
            deger=None, yeterli=False, n=0,
            aciklama=(
                "Karşılaştırma için yeterli geçmiş yok"
                + (f" ({etiket})" if etiket else "")
                + " — önceki dönemde bu konuda hiç kayıt yok."
            ),
        )

    degisim = round(100 * (guncel - onceki) / onceki, 1)
    if onceki < MIN_N_PERIOD_COMPARE:
        # Yuzde hesaplanabilir ama az orneklemde oynaktir (2 -> 4 "%100 artis"
        # gorunur). Deger verilir, ama "guvenilir" DENMEZ; arayuz soft gosterir.
        return Olcum(
            deger=degisim, yeterli=False, n=onceki,
            aciklama=(
                f"Az örneklem (önceki dönemde {onceki} kayıt) — yüzde değişim "
                "oynak olabilir, eğilim olarak okuyun."
            ),
        )
    return Olcum(deger=degisim, yeterli=True, n=onceki, aciklama="")


def zaman_serisi(noktalar: list, etiket: str = "") -> Olcum:
    """B10: tek veri noktasıyla çizgi grafik çizilmez.

    Çizgi grafik "değişim" iddiasıdır; tek nokta değişim göstermez. Arayüz
    bunun yerine tekil metrik kartı gösterir.
    """
    n = len(noktalar)
    if n < MIN_POINTS_TIMESERIES:
        return Olcum(
            deger=None, yeterli=False, n=n,
            aciklama=(
                f"Eğilim için en az {MIN_POINTS_TIMESERIES} günlük veri gerekir "
                f"(şu an {n}). Tek değer olarak gösteriliyor."
            ),
        )
    return Olcum(deger=float(n), yeterli=True, n=n, aciklama="")


def siralamaya_girebilir(cagri_sayisi: int) -> tuple[bool, str]:
    """B7: n<5 çağrısı olan temsilci sıralamada ilk sırada görünemez.

    5 çağrıda 95 ortalama tutan bir temsilci, 200 çağrıda 91 tutandan daha iyi
    DEĞİLDİR — yalnızca daha az ölçülmüştür.
    """
    if cagri_sayisi < MIN_CALLS_RANKING:
        return False, (
            f"Yeterli örneklem yok ({cagri_sayisi} çağrı; sıralama için en az "
            f"{MIN_CALLS_RANKING} gerekir)."
        )
    return True, ""
