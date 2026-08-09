"""KATMAN B + C — kanıt zorunlu LLM değerlendirmesi ve sunucu doğrulaması.

## Katman B — kanıt zorunlu LLM
- Kriterler **3-4'lük gruplara** bölünür, her grup AYRI LLM çağrısıdır.
  Tek dev prompt'ta 10-12 kriter değerlendirmek modelin dikkatini bölüyordu
  (prompt "asla yapma" #3; FAZ 1'de ölçüldü: kappa 0.32).
- Bias azaltıcıları (arXiv 2506.22316):
  * `temperature=0`, sabit prompt sürümü
  * kriterler **azalan ağırlık** sırasıyla sunulur (sayısal id sırası bias yaratıyor)
  * kriter kimliği **harf** ile verilir (A, B, C…), sayı değil
  * uzunluk bias'ına karşı prompt'ta açık uyarı

## Katman C — sunucu doğrulaması
- Her `quote` normalize transkriptte **gerçekten aranır**. Bulunamazsa kanıt
  reddedilir, kriter `insufficient_evidence` olur, `evidence_verification_failed`
  loglanır. FAZ 1'de ölçüldü: kanıtların **%43.9'u transkriptte yoktu**.
- Puan aritmetiği **kodda**; LLM'e toplam puan sordurulmaz.
- `insufficient_evidence` kriterler ortalamaya **katılmaz** (kanıtsız ceza yok).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from ..config import settings
from ..schemas import LLMKriterGrubu, LLMKriterKarari
from .llm import generate_json
from .text_tr import contains_verbatim

logger = logging.getLogger(__name__)

GROUP_SIZE = 3          # kriter grubu basina LLM cagrisi
PROMPT_VERSION = "v2.0"  # surumlenir; kalibrasyon bunu kaydeder
LOW_CONFIDENCE = 0.70    # bu esigin altinda insan kuyruguna

SYSTEM_PROMPT = (
    "Sen kidemli bir cagri merkezi kalite guvence (QA) uzmanisin. Sana zaman "
    "damgali, konusmaci etiketli Turkce transkript ve BIRKAC kriter verilir. "
    "Yalnizca TEMSILCININ performansini degerlendirirsin.\n"
    "MUTLAK KURALLAR:\n"
    "1) KANIT ZORUNLU. Her karar icin transkriptten BIREBIR alinti vereceksin. "
    "Alintiyi kelimesi kelimesine kopyala; ozetleme, duzeltme, tamamlama.\n"
    "2) KANIT YOKSA CEZA YOK. Bir kriteri degerlendirecek kanit bulamazsan "
    "karar 'insufficient_evidence' olur ve puan bos birakilir. ASLA tahminle "
    "dusuk puan verme.\n"
    "3) MUSTERININ davranisi (bagirma, kufur, sabirsizlik, anlamama, aksan) "
    "temsilciyi CEZALANDIRMAZ. Yalnizca temsilcinin buna verdigi tepkiyi degerlendir.\n"
    "4) UZUNLUK ONEMSIZ. Uzun cagri iyi cagri demek degildir; kisa ve cozen bir "
    "cagri tam puan alabilir.\n"
    "5) GEREKCE ile PUAN tutarli olmali. Gerekcede eksik belirtiyorsan puan bunu "
    "yansitmali; overek dusuk, elestirip yuksek puan verme.\n"
    "6) [anlasilmadi] veya [dusuk ses kalitesi] isaretli bolumlere DAYANARAK ceza "
    "veremezsin; o kriter icin kanit yetersizdir.\n"
    "Yanitin HER ZAMAN sadece gecerli JSON olur."
)


# Karar ile puanin TUTARLI olmasi zorunlu. Model "kriter karsilandi" deyip 5
# puan veremez; "karsilanmadi" deyip 8 veremez. Prompt'ta bu kural yaziliydi ama
# hicbir yerde ZORLANMIYORDU — ve tek yonlu bir kalibrasyon kaydirmasi, modelin
# dogru "met" kararlarini "kismen" bandina itip yeni hata uretiyordu (olculdu:
# must_not_penalize ihlali 0 -> 8). Bant kelepcesi ikisini birden cozer.
DECISION_BANDS: dict[str, tuple[int, int]] = {
    "met": (8, 10),
    "partially_met": (5, 7),
    "not_met": (0, 4),
}


def clamp_to_band(decision: str, score: int | None) -> int | None:
    """Puani, kararin ima ettigi banda kelepcele."""
    if score is None:
        return None
    band = DECISION_BANDS.get(decision)
    if band is None:
        return score
    lo, hi = band
    return max(lo, min(hi, score))


@dataclass
class CriterionDecision:
    """Katman C'den gecmis nihai kriter karari."""

    criterion_id: int
    decision: str
    score: int | None
    rationale: str
    evidence_quote: str
    evidence_ts: float | None
    evidence_speaker: str
    confidence: float
    evidence_verified: bool
    source_layer: str  # "A" | "B"

    @property
    def counts_toward_total(self) -> bool:
        """Ortalamaya katiliyor mu? Kanitsiz/uygulanamaz kriterler katilmaz."""
        return self.score is not None and self.decision not in (
            "insufficient_evidence", "not_applicable"
        )

    @property
    def needs_human(self) -> bool:
        return (
            self.decision == "insufficient_evidence"
            or self.confidence < LOW_CONFIDENCE
        )


# ---------------------------------------------------------------------------
# Katman B — prompt kurulumu
# ---------------------------------------------------------------------------

_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def group_criteria(criteria: list) -> list[list]:
    """Kriterleri AZALAN AGIRLIK sirasinda 3'lu gruplara bol.

    Azalan sira, literaturde olculmus pozisyon bias'ini azaltir; ayrica agirligi
    yuksek kriterler her grubun basina denk gelir.
    """
    ordered = sorted(criteria, key=lambda c: (-c.weight, c.id))
    return [ordered[i:i + GROUP_SIZE] for i in range(0, len(ordered), GROUP_SIZE)]


def _criteria_block(group: list) -> tuple[str, dict[str, int]]:
    """Kriterleri HARF kimlikle sun; harf -> kriter_id haritasini da dondur."""
    lines, mapping = [], {}
    for i, c in enumerate(group):
        letter = _LETTERS[i]
        mapping[letter] = c.id
        anchors = ""
        if getattr(c, "anchor_10", ""):
            anchors += f"\n  10 PUAN: {c.anchor_10}"
        if getattr(c, "anchor_0", ""):
            anchors += f"\n  0 PUAN: {c.anchor_0}"
        lines.append(f"[{letter}] {c.name}\n  {c.description}{anchors}")
    return "\n\n".join(lines), mapping


def _prompt(group: list, transcript: str, hint: str, mapping_block: str) -> str:
    return f"""## DEGERLENDIRILECEK KRITERLER
{mapping_block}

## CAGRI TRANSKRIPTI
Format: [dakika:saniye | saniye] KONUSMACI: metin
{transcript}
{hint}
## PUANLAMA OLCEGI (0-10)
9-10: Kusursuz — kriterin tum unsurlari eksiksiz karsilandi.
7-8 : Iyi — kucuk bir eksik var, kriter buyuk olcude karsilandi.
5-6 : Orta — onemli bir unsur eksik veya kismen yanlis yapildi.
3-4 : Zayif — kriterin buyuk kismi karsilanmadi.
0-2 : Basarisiz — kriter hic karsilanmadi veya agir ihlal var.

## GOREV
Yukaridaki HER kriter icin bir karar uret:
- "kriter_harf": kriterin harfi (A, B, C...)
- "karar": met | partially_met | not_met | not_applicable | insufficient_evidence
- "puan": 0-10 arasi tam sayi. Karar 'insufficient_evidence' veya
  'not_applicable' ise puani null birak.
- "kanitlar": transkriptten BIREBIR alinti listesi. Her alinti icin konusmaci ve
  saniye. Kanit bulamazsan bos liste ver ve karari 'insufficient_evidence' yap.
- "gerekce": son kullanici diliyle TEK cumle, dogal Turkce.
- "guven": 0.0-1.0 arasi, karara ne kadar emin oldugun.

SADECE su semada gecerli JSON dondur:
{{
  "kararlar": [
    {{
      "kriter_harf": "A",
      "karar": "met",
      "puan": 9,
      "kanitlar": [
        {{"speaker": "temsilci", "start_sec": 12.5,
          "quote": "<<BURAYA transkriptten kelimesi kelimesine kopyalanmis gercek cumle>>"}}
      ],
      "gerekce": "...",
      "guven": 0.9
    }}
  ]
}}"""


def _resolve_letters(
    kararlar: list[LLMKriterKarari], mapping: dict[str, int], group: list
) -> list[LLMKriterKarari]:
    """Harf kimliklerini kriter_id'ye cevir; cozulemeyenleri at.

    Model harfi karistirsa bile grup tek kriterlikse tereddut yok; birden
    fazlaysa harfsiz karar guvenilmez sayilip atilir (uydurma id uretmektense
    kriteri 'degerlendirilemedi' birakmak dogru davranistir).
    """
    out = []
    for k in kararlar:
        letter = (k.kriter_harf or "").strip().upper()[:1]
        cid = mapping.get(letter)
        if cid is None and len(group) == 1:
            cid = group[0].id
        if cid is None:
            logger.warning("Kriter harfi cozulemedi: %r", k.kriter_harf)
            continue
        k.kriter_id = cid
        out.append(k)
    return out


def evaluate_group(
    group: list, transcript: str, hint: str, few_shot: str = ""
) -> list[LLMKriterKarari]:
    """Bir kriter grubunu tek LLM cagrisiyla degerlendir (Katman B).

    `few_shot`: kalite uzmaninin onceki duzeltmelerinden uretilmis ornek blogu
    (review_feedback.build_block). Bos ise davranis degismez.
    """
    block, mapping = _criteria_block(group)
    prompt = _prompt(group, transcript, hint + few_shot, block)
    try:
        result = generate_json(LLMKriterGrubu, SYSTEM_PROMPT, prompt)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Kriter grubu degerlendirilemedi: %s", exc)
        return []
    return _resolve_letters(result.kararlar, mapping, group)


def evaluate_all(
    criteria: list, transcript: str, hint: str, few_shot_for=None
) -> list[LLMKriterKarari]:
    """Tum LLM kriterlerini gruplar halinde degerlendir.

    Degerlendirilemeyen kriter icin UYDURMA PUAN URETILMEZ (B28): eksik kalan
    kriter `insufficient_evidence` olarak isaretlenir ve insan kuyruguna duser.

    `few_shot_for(group) -> str`: o gruba ait kalibrasyon orneklerini uretir.
    """
    got: dict[int, LLMKriterKarari] = {}
    for group in group_criteria(criteria):
        shots = few_shot_for(group) if few_shot_for else ""
        for k in evaluate_group(group, transcript, hint, shots):
            if k.kriter_id is not None and k.kriter_id not in got:
                got[k.kriter_id] = k  # B27: ilk karar gecerli, tekrar elenir

    for c in criteria:
        if c.id not in got:
            logger.warning("Kriter degerlendirilemedi, yetersiz kanit: %s", c.name)
            got[c.id] = LLMKriterKarari(
                kriter_id=c.id, karar="insufficient_evidence", puan=None,
                gerekce=f"'{c.name}' kriteri degerlendirilemedi; insan onayi gerekiyor.",
                guven=0.0,
            )
    return list(got.values())


# ---------------------------------------------------------------------------
# Katman C — kanit dogrulama
# ---------------------------------------------------------------------------

def verify(karar: LLMKriterKarari, transcript_blob: str) -> CriterionDecision:
    """LLM kararini sunucu tarafinda dogrula.

    Kanit transkriptte bulunamazsa karar `insufficient_evidence`e dusurulur —
    kriter dusuk puan ALMAZ, insan kuyruguna gider.
    """
    verified = None
    for k in karar.kanitlar:
        if k.quote and contains_verbatim(transcript_blob, k.quote):
            verified = k
            break

    if karar.karar in ("insufficient_evidence", "not_applicable"):
        return CriterionDecision(
            criterion_id=karar.kriter_id, decision=karar.karar, score=None,
            rationale=karar.gerekce or "Bu kriteri degerlendirecek kanit bulunamadi.",
            evidence_quote="", evidence_ts=None, evidence_speaker="",
            confidence=karar.guven, evidence_verified=False, source_layer="B",
        )

    if verified is None:
        failed = karar.kanitlar[0].quote[:80] if karar.kanitlar else "(kanit verilmedi)"
        logger.warning(
            "evidence_verification_failed kriter=%s karar=%s alinti=%r",
            karar.kriter_id, karar.karar, failed,
        )
        return CriterionDecision(
            criterion_id=karar.kriter_id, decision="insufficient_evidence", score=None,
            rationale=(
                "Bu kriter icin gosterilen kanit transkriptte dogrulanamadi; "
                "puanlama insan onayina birakildi."
            ),
            evidence_quote="", evidence_ts=None, evidence_speaker="",
            confidence=min(karar.guven, 0.3), evidence_verified=False, source_layer="B",
        )

    return CriterionDecision(
        criterion_id=karar.kriter_id, decision=karar.karar,
        score=clamp_to_band(karar.karar, karar.puan),
        rationale=karar.gerekce, evidence_quote=verified.quote,
        evidence_ts=verified.start_sec, evidence_speaker=verified.speaker,
        confidence=karar.guven, evidence_verified=True, source_layer="B",
    )


def from_finding(criterion_id: int, finding) -> CriterionDecision:
    """Katman A bulgusunu ortak karar tipine cevir. Kanit kod tarafindan
    uretildigi icin dogrulanmis sayilir."""
    return CriterionDecision(
        criterion_id=criterion_id, decision=finding.decision, score=finding.score,
        rationale=finding.rationale_tr, evidence_quote=finding.evidence_quote,
        evidence_ts=finding.evidence_ts, evidence_speaker=finding.evidence_speaker,
        confidence=finding.confidence,
        evidence_verified=bool(finding.evidence_quote), source_layer="A",
    )


# ---------------------------------------------------------------------------
# Puan aritmetigi — KODDA, LLM'de degil
# ---------------------------------------------------------------------------

def compute_total(decisions: list[CriterionDecision], criteria: list) -> float | None:
    """toplam = Σ(kriter_puani × agirlik) / Σ(agirlik) × 10 → 0-100.

    Yalnizca `counts_toward_total` olan kriterler katilir. Hicbiri katilmiyorsa
    None doner (puan uretilemez — cagri tamamen insan kuyruguna gider).
    """
    weights = {c.id: c.weight for c in criteria}
    seen: set[int] = set()
    num = den = 0.0
    for d in decisions:
        if not d.counts_toward_total or d.criterion_id in seen:
            continue  # B27: ayni kriter iki kez sayilamaz
        seen.add(d.criterion_id)
        w = weights.get(d.criterion_id, 1.0)
        num += d.score * w
        den += w
    if den <= 0:
        return None
    return round(num / (den * 10) * 100, 1)


@dataclass
class ZeroingResult:
    zeroed: bool
    reason: str | None = None
    evidence: str | None = None
    evidence_ts: float | None = None
    criterion_id: int | None = None


def decide_zeroing(decisions: list[CriterionDecision], criteria: list) -> ZeroingResult:
    """Sifirlayici ihlal karari — TEK YERDE.

    Kurallar:
    - Kritik kriter esigin ALTINDAysa cagri sifirlanir.
    - `insufficient_evidence` kriter ASLA sifirlama tetiklemez (kanitsiz ceza yok).
    - Sifirlama gerekcesi VE kanidi zorunludur; kanitsiz sifirlama bir sistem
      hatasidir ve cagiran tarafta ValueError olarak firlatilir.
    """
    by_id = {c.id: c for c in criteria}
    for d in decisions:
        c = by_id.get(d.criterion_id)
        if c is None or not c.is_critical:
            continue
        if d.score is None:  # yetersiz kanit -> sifirlama YOK
            continue
        if d.score < c.critical_threshold:
            # Kanit: ya transkriptten alinti, ya da Katman A'nin "yokluk kaniti"
            # (bir seyin OLMADIGINI gostermenin kaniti aramanin kendisidir).
            # Katman B'den gelen bir karar kanitsiz sifirlama YAPAMAZ — Katman C
            # zaten kanitsizi insufficient_evidence'a dusuruyor.
            return ZeroingResult(
                zeroed=True,
                reason=f"{c.name}: {d.rationale}",
                evidence=d.evidence_quote or None,
                evidence_ts=d.evidence_ts,
                criterion_id=c.id,
            )
    return ZeroingResult(zeroed=False)
