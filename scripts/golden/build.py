"""Altin seti data/golden/ altina yaz.

Kullanim:  python -m scripts.golden.build [cikis_dizini]
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

from ._authoring import write_scenario
from .scenarios import CRITERIA, SCENARIOS

DEFAULT_OUT = Path(__file__).resolve().parents[2] / "data" / "golden"


def validate() -> list[str]:
    """Senaryolarin kendi icinde tutarli olup olmadigini denetle."""
    errors: list[str] = []
    seen: set[str] = set()
    for s in SCENARIOS:
        if s.id in seen:
            errors.append(f"{s.id}: tekrarlanan senaryo id")
        seen.add(s.id)

        unknown = set(s.expected.scores) - set(CRITERIA)
        if unknown:
            errors.append(f"{s.id}: rubrikte olmayan kriter {sorted(unknown)}")
        missing = set(CRITERIA) - set(s.expected.scores)
        if missing:
            errors.append(f"{s.id}: beklenen puani verilmemis kriter {sorted(missing)}")

        for c, v in s.expected.scores.items():
            if not (0 <= v <= 10):
                errors.append(f"{s.id}: {c} puani 0-10 disinda ({v})")

        if s.expected.zeroed and not s.expected.zeroing_criterion:
            errors.append(f"{s.id}: zeroed=True ama zeroing_criterion bos")
        if s.expected.zeroed and "zeroing" not in s.expected.alerts:
            errors.append(f"{s.id}: zeroed=True ama beklenen alarmlarda 'zeroing' yok")

        # Kanit alt-dizesi transkriptte GERCEKTEN gecmeli
        blob = " ".join(t.text for t in s.turns)
        for crit, frag in s.expected.evidence_must_contain.items():
            if frag not in blob:
                errors.append(f"{s.id}: beklenen kanit '{frag}' transkriptte yok ({crit})")

        if not s.turns:
            errors.append(f"{s.id}: replik yok")

        # Sifirlama beklentisi, kritik kriter beklentileriyle TUTARLI olmali.
        # (Rubrikte kritik olanlar: KVKK, Kimlik Dogrulama, Yasakli Kelime / Uslup)
        kritik = ("KVKK / Aydinlatma", "Kimlik Dogrulama", "Yasakli Kelime / Uslup")
        esik_alti = [c for c in kritik if s.expected.scores.get(c, 10) < 3]
        if s.expected.zeroed and not esik_alti:
            errors.append(
                f"{s.id}: zeroed=True ama hicbir kritik kriter esik altinda degil "
                f"({ {c: s.expected.scores.get(c) for c in kritik} })"
            )
        if not s.expected.zeroed and esik_alti:
            errors.append(
                f"{s.id}: zeroed=False ama kritik kriter(ler) esik altinda: {esik_alti}"
            )
    return errors


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT

    errors = validate()
    if errors:
        print("ALTIN SET TUTARSIZ:")
        for e in errors:
            print("  -", e)
        return 1

    out.mkdir(parents=True, exist_ok=True)
    for s in SCENARIOS:
        write_scenario(out, s)

    buckets = Counter(s.bucket for s in SCENARIOS)
    index = {
        "toplam": len(SCENARIOS),
        "kovalar": dict(buckets),
        "regresyon_vakalari": {
            s.regression_for: s.id for s in SCENARIOS if s.regression_for
        },
        "sifirlanmasi_beklenen": [s.id for s in SCENARIOS if s.expected.zeroed],
        "kriterler": CRITERIA,
        "senaryolar": [
            {"id": s.id, "bucket": s.bucket, "title": s.title,
             "zeroed": s.expected.zeroed, "regression_for": s.regression_for}
            for s in SCENARIOS
        ],
    }
    (out / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"{len(SCENARIOS)} senaryo yazildi -> {out}")
    for b, n in sorted(buckets.items()):
        print(f"  {b:<14} {n}")
    print(f"  sifirlanmasi beklenen: {len(index['sifirlanmasi_beklenen'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
