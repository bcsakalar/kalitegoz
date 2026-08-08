"""Uyum motoru: yasakli kelime tespiti + sifirlayici ihlal mantigi.

Yasakli kelimeler tenant bazli DB listesinden gelir (admin panelinden yonetilir).
Eslesme: exact | fuzzy (rapidfuzz) | regex. Her ihlal, diarization'dan gelen
konusmaci bilgisiyle "kim soyledi"ye baglanir — yalnizca TEMSILCININ soyledigi
ihlaller cagriyi cezalandirir (musteri kufrederse temsilci sorumlu degildir).
"""

import re
import unicodedata
from dataclasses import dataclass

from rapidfuzz import fuzz

from ..models import BannedWord, Segment

# Kriz/eskalasyon sinyali iceren kalip ve kelimeler (metin tarafi)
CRISIS_PATTERNS = [
    r"avukat",
    r"t[uü]ketici hakem",
    r"savc[ıi]l[ıi]k",
    r"mahkeme",
    r"dava a[çc]",
    r"sikayet ed",
    r"şikayet ed",
    r"iptal ed",
    r"medyaya",
    r"sosyal medya",
    r"rezil ed",
]
_CRISIS_RE = re.compile("|".join(CRISIS_PATTERNS), re.IGNORECASE)


def _normalize(text: str) -> str:
    """TR karakterleri sadeleştir + kucuk harf (fuzzy/exact eslesme icin)."""
    text = text.lower()
    trmap = str.maketrans("ıİişŞğĞüÜöÖçÇ", "iiissgguuoocc")
    text = text.translate(trmap)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text


@dataclass
class DetectedViolation:
    kind: str  # banned_word
    category: str
    severity: str
    term: str
    speaker: str
    evidence: str
    ts_sec: float | None


def _match_in(segment_norm: str, bw: BannedWord) -> bool:
    term = bw.term.strip()
    if not term:
        return False
    if bw.match_type == "regex":
        try:
            return re.search(term, segment_norm, re.IGNORECASE) is not None
        except re.error:
            return False
    term_norm = _normalize(term)
    if bw.match_type == "exact":
        return re.search(rf"\b{re.escape(term_norm)}\b", segment_norm) is not None
    # fuzzy: yazim ve TR cekim varyasyonlarini yakalar
    if term_norm in segment_norm:
        return True
    stem = term_norm[:5]  # TR cekim ekleri koku korur (sacmalama -> sacmal...)
    for word in segment_norm.split():
        if fuzz.ratio(term_norm, word) >= 85:
            return True
        # kok-onek eslesmesi: kelime terimin koku ile basliyorsa (>=5 harf)
        if len(term_norm) >= 5 and word.startswith(stem) and fuzz.partial_ratio(term_norm, word) >= 60:
            return True
    # cok kelimeli terimlerde tum ifade icin partial_ratio
    if " " in term_norm and fuzz.partial_ratio(term_norm, segment_norm) >= 90:
        return True
    return False


def detect_banned_words(
    segments: list[Segment], banned: list[BannedWord]
) -> list[DetectedViolation]:
    """Segmentlerde yasakli kelime ara; her eslesmeyi konusmaciya bagla."""
    active = [b for b in banned if b.is_active]
    found: list[DetectedViolation] = []
    for seg in segments:
        seg_norm = _normalize(seg.text)
        for bw in active:
            if _match_in(seg_norm, bw):
                found.append(
                    DetectedViolation(
                        kind="banned_word",
                        category=bw.category,
                        severity=bw.severity,
                        term=bw.term,
                        speaker=seg.speaker,
                        evidence=seg.text.strip(),
                        ts_sec=seg.start_sec,
                    )
                )
    return found


def detect_crisis(segments: list[Segment]) -> tuple[bool, str | None, float | None]:
    """Metin tarafinda kriz sinyali (musteri tehdit/hukuki soylem) ara."""
    for seg in segments:
        if seg.speaker == "temsilci":
            continue
        m = _CRISIS_RE.search(seg.text)
        if m:
            return True, seg.text.strip(), seg.start_sec
    return False, None, None


def agent_violations(violations: list[DetectedViolation]) -> list[DetectedViolation]:
    """Yalnizca temsilcinin yaptigi ihlaller (cagriyi cezalandiranlar)."""
    return [v for v in violations if v.speaker == "temsilci"]
