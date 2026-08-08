"""Kalibrasyon: uzmanlar arasi uyum (inter-rater reliability) hesabi.

Sektor pratigi: ayni cagriyi 2+ kalite uzmani BAGIMSIZ puanlar; uyum olculur.
Hedef >= %85. Uyum dusukse sorun genelde uzmanda degil RUBRIKTE'dir — kriter
aciklamasi mugalaksa herkes farkli yorumlar. Bu yuzden rapor, en cok ayrisilan
KRITERI one cikarir: duzeltilmesi gereken sey odur.

Uyum tanimi: bir kriterde tum uzmanlarin puani birbirinden en fazla
AGREEMENT_TOLERANCE kadar farkliysa "uyumlu" sayilir. Cagri merkezi QA'sinde
kabul edilen olcum "tam esitlik" degil "±1 puan icinde" olmasidir — 7 ile 8
arasindaki fark pratikte anlamsizdir, 4 ile 9 arasindaki fark ciddidir.
"""

from collections import defaultdict

# Bu farka kadar puanlar "ayni" sayilir (0-10 olceginde)
AGREEMENT_TOLERANCE = 1
# Sektor hedefi
TARGET_AGREEMENT = 85.0


def compute_agreement(evaluations: list[dict], ai_scores: dict[int, int] | None = None) -> dict:
    """Uzman degerlendirmelerinden uyum raporu uret.

    evaluations: [{"evaluator_id": 1, "evaluator_name": "...",
                   "scores": [{"criterion_id": 1, "criterion_name": "...", "score": 8}]}]
    ai_scores: {criterion_id: puan} — AI ile karsilastirma icin (opsiyonel)

    Doner: {agreement_pct, criteria: [...], evaluator_count, most_divergent}
    """
    if len(evaluations) < 2:
        return {
            "agreement_pct": None,
            "evaluator_count": len(evaluations),
            "criteria": [],
            "most_divergent": None,
            "meets_target": None,
        }

    # kriter -> [(evaluator_name, puan)]
    by_criterion: dict[int, list[tuple[str, int]]] = defaultdict(list)
    names: dict[int, str] = {}
    for ev in evaluations:
        for s in ev.get("scores", []):
            cid = s.get("criterion_id")
            if cid is None:
                continue
            by_criterion[cid].append((ev.get("evaluator_name", "?"), int(s.get("score", 0))))
            names[cid] = s.get("criterion_name", "")

    rows = []
    agreed = 0
    for cid, pairs in by_criterion.items():
        vals = [p[1] for p in pairs]
        if len(vals) < 2:
            continue  # tek uzman puanladiysa uyumdan bahsedilemez
        spread = max(vals) - min(vals)
        is_agreed = spread <= AGREEMENT_TOLERANCE
        if is_agreed:
            agreed += 1
        rows.append({
            "criterion_id": cid,
            "criterion_name": names.get(cid, ""),
            "scores": [{"evaluator": n, "score": v} for n, v in pairs],
            "min": min(vals),
            "max": max(vals),
            "spread": spread,
            "avg": round(sum(vals) / len(vals), 1),
            "agreed": is_agreed,
            "ai_score": (ai_scores or {}).get(cid),
        })

    if not rows:
        return {
            "agreement_pct": None, "evaluator_count": len(evaluations),
            "criteria": [], "most_divergent": None, "meets_target": None,
        }

    rows.sort(key=lambda r: r["spread"], reverse=True)
    pct = round(agreed / len(rows) * 100, 1)
    worst = rows[0] if rows[0]["spread"] > AGREEMENT_TOLERANCE else None

    return {
        "agreement_pct": pct,
        "evaluator_count": len(evaluations),
        "criteria": rows,
        # En cok ayrisilan kriter = rubrikte netlestirilmesi gereken kriter
        "most_divergent": worst["criterion_name"] if worst else None,
        "meets_target": pct >= TARGET_AGREEMENT,
    }


def compute_total(scores: list[dict], weights: dict[int, float]) -> float:
    """Manuel degerlendirmenin agirlikli toplami (AI ile ayni formul: 0-100)."""
    if not scores:
        return 0.0
    total_w = sum(weights.get(s.get("criterion_id"), 1.0) for s in scores)
    if total_w <= 0:
        return 0.0
    raw = sum(int(s.get("score", 0)) * weights.get(s.get("criterion_id"), 1.0) for s in scores)
    return round(raw / (total_w * 10) * 100, 1)
