"""Altin set yazarlik yardimcilari.

Senaryolar transkript seviyesinde yazilir (ses degil). Gerekce:

1. Puanlama motorunun dogrulugunu olcmek istiyoruz. Ses hattini (Whisper + kanal
   ayrimi) karistirirsak, olculen sapmanin ne kadarinin STT'den ne kadarinin
   yargidan geldigini ayirt edemeyiz. Bunlar AYRI olculmesi gereken iki sey.
2. docs/internal/01-KOK-NEDEN.md §D'de olculdugu gibi mevcut stereo hatti zaman
   damgalarini bozuyor. Bozuk ciktiyi referans almak, hatayi altin sete
   gomerdi.
3. Hiz: 46 senaryo x 3 tekrar bir de STT bekleyemez.

Ses hattinin dogrulugu FAZ 2'de AYRI bir diarizasyon regresyonuyla olculecek.

Zamanlama modeli: her replik, kelime sayisina gore gercekci bir sure alir ve
konusmalar UST USTE BINMEZ (aksi belirtilmedikce). Bu, mevcut sistemin uretmeyi
BASARAMADIGI dogru zaman yapisidir; altin set beklenen dogruyu temsil eder.
Bilincli soz kesme, `overlap` parametresiyle acikca modellenir.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

# Turkce icin gercekci konusma hizi: ~150 kelime/dk = 2.5 kelime/sn
WORDS_PER_SEC = 2.5
MIN_TURN_SEC = 1.2
GAP_SEC = 0.35  # replikler arasi dogal bosluk


@dataclass
class Turn:
    speaker: str  # temsilci | musteri
    text: str
    # Bu replik bir onceki repligi KESIYORSA kac saniye once giriyor.
    # 0 = kesme yok. Soz kesme senaryolari bunu acikca kullanir.
    overlap: float = 0.0


@dataclass
class Expected:
    """Uzman referansi. Kriter adlari rubrikteki `criteria.name` ile birebir ayni."""

    scores: dict[str, int]  # kriter adi -> beklenen puan (0-10)
    zeroed: bool
    zeroing_criterion: str | None = None
    # Beklenen alarm tipleri: zeroing | crisis | banned_word | low_score
    alerts: list[str] = field(default_factory=list)
    # Belirli kriterler icin transkriptte GECMESI gereken kanit cumlesi (alt-dize)
    evidence_must_contain: dict[str, str] = field(default_factory=dict)
    # Bu kriterlerde AI'nin ceza vermesi YASAK (kanit yok / musteri kaynakli)
    must_not_penalize: list[str] = field(default_factory=list)
    notes: str = ""


@dataclass
class Scenario:
    id: str
    title: str
    bucket: str  # yuksek | orta | dusuk | sifirlayici | kriz | tuzak | ses_kalitesi | regresyon
    tags: list[str]
    turns: list[Turn]
    expected: Expected
    # B1-B6 regresyon vakalari icin: hangi hataya birebir karsilik geliyor
    regression_for: str | None = None


def _dur(text: str) -> float:
    return max(MIN_TURN_SEC, round(len(text.split()) / WORDS_PER_SEC, 2))


def build_segments(turns: list[Turn]) -> list[dict]:
    """Repliklere gercekci, UST USTE BINMEYEN zaman damgalari ver.

    `overlap > 0` olan replik, bir oncekinin bitisinden o kadar ONCE baslar —
    yani bilincli soz kesme. Bu tek istisna disinda segmentler ardisiktir.
    """
    segs: list[dict] = []
    cursor = 1.0
    prev_end = 0.0
    for idx, t in enumerate(turns):
        start = cursor if not t.overlap else max(0.0, prev_end - t.overlap)
        end = round(start + _dur(t.text), 2)
        segs.append(
            {
                "idx": idx,
                "speaker": t.speaker,
                "start": round(start, 2),
                "end": end,
                "text": t.text,
            }
        )
        prev_end = end
        cursor = round(end + GAP_SEC, 2)
    return segs


SCRIPT_PARTS = ("Açılış", "KVKK / Aydınlatma", "Kimlik Doğrulama", "Kapanış")


def derive_script_uyumu(scores: dict) -> dict:
    """"Script Uyumu" kriterini tanimindan TURET.

    Bu kriter, zorunlu akisin dort adiminin (acilis, KVKK, kimlik, kapanis)
    bilesimi olarak TANIMLANDI — ayri bir olgu degil. Dolayisiyla beklenen
    puani da elle yazilmaz, tanimdan cikar. Elle yazmak iki kaynagin
    birbirinden sapmasina yol acardi.
    """
    parts = [scores[c] for c in SCRIPT_PARTS if c in scores]
    if not parts:
        return scores
    return {**scores, "Script Uyumu": round(sum(parts) / len(parts))}


def write_scenario(root: Path, sc: Scenario) -> None:
    d = root / sc.id
    d.mkdir(parents=True, exist_ok=True)
    segments = build_segments(sc.turns)
    duration = round(segments[-1]["end"] + 1.0, 2) if segments else 0.0

    (d / "transcript.json").write_text(
        json.dumps(
            {
                "id": sc.id,
                "title": sc.title,
                "bucket": sc.bucket,
                "tags": sc.tags,
                "duration_sec": duration,
                "segments": segments,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    exp = asdict(sc.expected)
    exp["scenario_id"] = sc.id
    exp["regression_for"] = sc.regression_for
    (d / "expected.json").write_text(
        json.dumps(exp, ensure_ascii=False, indent=2), encoding="utf-8"
    )
