"""B16 — Yapay zekâ çıktısı metinlerin Türkçe kalite denetimi.

Koçluk önerisi, çağrı özeti ve alarm açıklaması **kullanıcıya gösterilen**
metinlerdir; "Temsilci agir yasakli ifade kullandi" gibi ASCII bir cümle,
ürünün Türkçe olmadığı izlenimi verir.

Prompt'ta "Türkçe karakter kullan" demek yeterli değildir — model bazen yine
ASCII üretir. Bu yüzden çıktı **ölçülür**: Türkçe metinde beklenen diakritik
yoğunluğu yoksa metin reddedilir ve yeniden istenir.

## Nasıl ölçülür?

Türkçe metinde `ç ğ ı ö ş ü İ` karakterleri doğal olarak sık geçer. 40+
karakterlik bir Türkçe cümlede hiç diakritik yoksa, metin ya ASCII'ye
düşürülmüştür ya da Türkçe değildir. Eşik muhafazakâr tutuldu: kısa
cümlelerde ("Tamam." gibi) yanlış alarm vermemeli.
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

TR_DIAKRITIK = set("çÇğĞıİöÖşŞüÜâîû")

# Bu uzunlugun altindaki metinlerde diakritik olmamasi normaldir.
MIN_UZUNLUK = 40

# ASCII'ye dusurulmus Turkce'nin parmak izi: Turkce'de sik gecen ama
# diakritiksiz yazildiginda ortaya cikan kelimeler.
ASCII_TR_IPUCLARI = (
    r"\bicin\b", r"\bcok\b", r"\bdegil\b", r"\bgorusme\b", r"\bmusteri\b",
    r"\btemsilci\b", r"\bcagri\b", r"\bkullandi\b", r"\byapmadi\b",
    r"\bgerekli\b", r"\bcozum\b", r"\bacilis\b", r"\bkapanis\b",
    r"\bsoyledi\b", r"\bbilgi verdi\b", r"\bdogru\b", r"\byanlis\b",
)
_IPUCU_RE = re.compile("|".join(ASCII_TR_IPUCLARI), re.IGNORECASE)


def diakritik_orani(text: str) -> float:
    harf = [c for c in text if c.isalpha()]
    if not harf:
        return 0.0
    return sum(1 for c in harf if c in TR_DIAKRITIK) / len(harf)


def ascii_turkce_mi(text: str) -> bool:
    """Metin ASCII'ye düşürülmüş Türkçe mi?

    İki koşul birden aranır: yeterince uzun **ve** hiç diakritik yok **ve**
    ASCII-Türkçe parmak izi taşıyor. Üçü birden olmadan karar verilmez —
    tek başına "diakritik yok" İngilizce bir alıntı için de doğru olabilir.
    """
    t = (text or "").strip()
    if len(t) < MIN_UZUNLUK:
        return False
    if any(c in TR_DIAKRITIK for c in t):
        return False
    return bool(_IPUCU_RE.search(t))


def denetle(metinler: dict[str, str]) -> list[str]:
    """{alan_adi: metin} → sorunlu alan adları."""
    return [ad for ad, m in metinler.items() if ascii_turkce_mi(m)]


def duzeltme_istegi(sorunlu: list[str]) -> str:
    """Modele gönderilecek düzeltme talimatı."""
    return (
        "\n## TURKCE KARAKTER DUZELTMESI\n"
        f"Su alanlar Turkce karakter icermiyor: {', '.join(sorunlu)}.\n"
        "Bu metinleri TAM TURKCE karakterlerle (ç, ğ, ı, İ, ö, ş, ü) yeniden yaz. "
        "Anlami degistirme, yalnizca dogru Turkce yaz. Ornek: "
        "'Temsilci agir yasakli ifade kullandi' -> "
        "'Temsilci ağır yasaklı ifade kullandı'.\n"
    )
