"""Türkçe metin işleme temeli — sistemdeki TEK normalizasyon kaynağı.

Bu modülden önce iki ayrı, uyumsuz normalizasyon vardı:
`compliance._normalize()` (NFKD + combining temizliği) ve `schemas._fold_tr()`
(düz translate). Aynı metin iki farklı sonuç veriyordu.

## İki ayrı iş, iki ayrı fonksiyon

- `lower_tr()`   — Türkçe'ye DOĞRU küçük harf. `I→ı`, `İ→i`. Gösterimde kullanılabilir.
- `fold_tr()`    — KARŞILAŞTIRMA için ASCII'ye indirger. **Kullanıcıya asla gösterilmez.**

## Altın kural
Karşılaştırma normalize metin üzerinde yapılır, **gösterim her zaman orijinal metin
üzerinde**. Kullanıcıya ASCII'ye düşürülmüş Türkçe gösterilmez (prompt "asla yapma" #7).
Bu yüzden eşleşme fonksiyonları, orijinal metindeki **konumu** döndürür — böylece
çağıran taraf alıntıyı orijinalden kesebilir.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# Python'un str.lower()'ı Türkçe bilmez:
#   "I".lower() -> "i"   (Türkçe'de "ı" olmalı)
#   "İ".lower() -> "i̇"   (i + U+0307 birleşik nokta; eşleşmeleri kaçırır)
_LOWER_MAP = str.maketrans({"I": "ı", "İ": "i"})

# Karşılaştırma için ASCII katlama. SADECE eşleşmede kullanılır.
_FOLD_MAP = str.maketrans(
    {"ı": "i", "ş": "s", "ğ": "g", "ü": "u", "ö": "o", "ç": "c",
     "â": "a", "î": "i", "û": "u", "ê": "e", "ô": "o"}
)

_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_WS_RE = re.compile(r"\s+")
_DIGIT_RUN_RE = re.compile(r"\d{3,}")


def lower_tr(text: str) -> str:
    """Türkçe'ye doğru küçük harf dönüşümü. Gösterimde güvenle kullanılabilir."""
    return text.translate(_LOWER_MAP).lower()


def fold_tr(text: str) -> str:
    """Karşılaştırma için ASCII katlanmış hâl. KULLANICIYA GÖSTERİLMEZ."""
    text = lower_tr(text).translate(_FOLD_MAP)
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c))


def normalize_tr(
    text: str,
    *,
    strip_punct: bool = True,
    mask_digits: bool = False,
) -> str:
    """Eşleşme için tam normalizasyon: küçük harf + ASCII katlama + noktalama +
    çoklu boşluk.

    `mask_digits=True` uzun rakam dizilerini (telefon, müşteri no, TCKN) `#` ile
    değiştirir — kalıp eşleşmesinde sayıların gürültü yapmasını engeller.
    """
    out = fold_tr(text)
    if strip_punct:
        out = _PUNCT_RE.sub(" ", out)
    # Maskeleme noktalama temizliginden SONRA: '#' bir noktalama karakteridir,
    # once maskelersek _PUNCT_RE onu da siler.
    if mask_digits:
        out = _DIGIT_RUN_RE.sub("#", out)
    return _WS_RE.sub(" ", out).strip()


# ---------------------------------------------------------------------------
# Kalıp eşleşmesi — Türkçe ek toleranslı, kelime sınırına saygılı
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PhraseHit:
    """Eşleşme sonucu. `quote` ORİJİNAL metinden kesilir — gösterime hazırdır."""

    pattern: str
    quote: str
    start: int  # orijinal metindeki karakter konumu
    end: int


def _token_spans(text: str) -> list[tuple[int, int, str]]:
    """Orijinal metnin kelimelerini (başlangıç, bitiş, normalize hâl) olarak ver.

    Konumlar ORİJİNAL metne aittir; alıntı buradan kesilir.
    """
    spans = []
    for m in re.finditer(r"\w+", text, re.UNICODE):
        spans.append((m.start(), m.end(), normalize_tr(m.group(), strip_punct=False)))
    return spans


MAX_SUFFIX = 6  # "alinmaktadir" gibi uzun Turkce eklere yer birak


def _common_prefix_len(a: str, b: str) -> int:
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


def _word_matches(word: str, pw: str, *, multiword: bool, is_last: bool) -> bool:
    """Metindeki bir kelime, kalıp kelimesiyle eşleşiyor mu?

    Üç kademe — her biri bir öncekinden gevşek, ama gevşeklik yalnızca
    ÇOK KELİMELİ kalıplarda açılır. Çok kelimeli kalıpta diğer kelimeler
    bağlamı taşıdığı için gevşeme güvenlidir; tek kelimede taşımaz.
    """
    if word == pw:
        return True

    # 1) Önek eşleşmesi — Türkçe çekim eki: "alt" -> "altina"
    #    Tek kelimeli kalıpta en az 4 harf şartı (yanlış pozitif kalkanı),
    #    çok kelimelide 3 (kalıplar bilinçli kısaltılmış kök olabilir: "kayit alt").
    min_stem = 3 if multiword else 4
    if len(pw) >= min_stem and word.startswith(pw) and len(word) - len(pw) <= MAX_SUFFIX:
        return True

    # 2) Ortak kök — yalnızca çok kelimeli kalıbın SON kelimesinde.
    #    "kesin çözülür" kalıbı "kesin çözülecek" ile eşleşmeli: çöz-ül ortak.
    #    Tek kelimede AÇILMAZ; açılsaydı "kesin" -> "kesinlikle" olurdu (B4).
    if multiword and is_last and len(pw) >= 5:
        common = _common_prefix_len(word, pw)
        if common >= 5 and len(word) - common <= MAX_SUFFIX and len(pw) - common <= MAX_SUFFIX:
            return True

    return False


def find_phrase(
    text: str,
    pattern: str,
    *,
    suffix_tolerant: bool = True,
) -> PhraseHit | None:
    """Bir kalıbı metinde ara; bulursa ORİJİNAL alıntıyı döndür.

    - Kalıbın **her kelimesi sırayla** eşleşmeli; araya kelime giremez.
    - Kelime SINIRINA saygılıdır: tek kelimelik "kesin" kalıbı asla "kesinlikle"
      ile eşleşmez.
    - Türkçe ek toleransı `_word_matches`'te kademeli açılır (bkz. oradaki not).

    Bu, eski `compliance._match_in()`'in `stem = term[:5]` + `partial_ratio >= 60`
    kısayolunun yerini alır — o kısayol "Kesinlikle haklısınız"ı "kesin çözülür"
    yasak vaadi sanıp **çağrıyı sıfırlıyordu** (B4).
    """
    pat_words = normalize_tr(pattern).split()
    if not pat_words:
        return None
    spans = _token_spans(text)
    n = len(pat_words)
    multiword = n > 1

    for i in range(len(spans) - n + 1):
        ok = True
        for j, pw in enumerate(pat_words):
            word = spans[i + j][2]
            if word == pw:
                continue
            if not suffix_tolerant:
                ok = False
                break
            if not _word_matches(word, pw, multiword=multiword, is_last=(j == n - 1)):
                ok = False
                break
        if ok:
            start, end = spans[i][0], spans[i + n - 1][1]
            return PhraseHit(pattern=pattern, quote=text[start:end], start=start, end=end)
    return None


def find_any(text: str, patterns: tuple[str, ...] | list[str], **kw) -> PhraseHit | None:
    """Kalıplardan ilk eşleşeni döndür (anlam kümesi eşleşmesi)."""
    for p in patterns:
        hit = find_phrase(text, p, **kw)
        if hit:
            return hit
    return None


def contains_verbatim(haystack: str, needle: str, *, min_words: int = 5) -> bool:
    """Bir alıntının metinde GERÇEKTEN geçip geçmediğini doğrula (Katman C).

    Tam eşleşme aranır; bulunamazsa alıntının `min_words` kelimelik en uzun
    penceresi aranır (LLM alıntıyı bir iki kelime kırpmış olabilir, ama uydurmuş
    olamaz).
    """
    hay = normalize_tr(haystack)
    ned = normalize_tr(needle)
    if len(ned) < 8:
        return False
    if ned in hay:
        return True
    words = ned.split()
    if len(words) < min_words:
        return False
    for size in (len(words), 8, min_words):
        if size > len(words):
            continue
        for i in range(len(words) - size + 1):
            if " ".join(words[i:i + size]) in hay:
                return True
    return False
