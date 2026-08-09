"""İki eval raporunu AYNI senaryo altkümesinde karşılaştır.

FAZ 3.4'ün iddiası ölçülebilir olmalı: "kaliteci düzeltmeleri few-shot olarak
beslendi, kappa kapandı." Bunu dürüst ölçmenin şartı, iki koşumu **aynı
senaryolarda** kıyaslamaktır — aksi halde altküme farkı sonucu taşır.

Kullanım (host'ta):
    python -m scripts.golden.compare ONCE.json SONRA.json [--only sinav.json]
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

BANDS = [(0, 4, "karsilanmadi"), (5, 7, "kismen"), (8, 10, "karsilandi")]


def band(v: int) -> str:
    for lo, hi, name in BANDS:
        if lo <= v <= hi:
            return name
    return "karsilanmadi"


def cohens_kappa(pairs: list[tuple[str, str]]) -> float | None:
    if not pairs:
        return None
    cats = sorted({c for p in pairs for c in p})
    n = len(pairs)
    po = sum(1 for a, b in pairs if a == b) / n
    pe = sum(
        (sum(1 for a, _ in pairs if a == c) / n) * (sum(1 for _, b in pairs if b == c) / n)
        for c in cats
    )
    if pe >= 1.0:
        return 1.0 if po >= 1.0 else 0.0
    return round((po - pe) / (1 - pe), 4)


def metrics_from(report: Path, golden: Path, only: set[str] | None) -> dict:
    """Bir eval raporundan, verilen altküme için metrikleri YENIDEN hesapla."""
    data = json.loads(report.read_text(encoding="utf-8"))
    per: dict[str, list[tuple[int, int]]] = {}
    yetersiz = 0
    puanlanan = 0

    for row in data.get("detay", []):
        sid = row.get("id")
        if only is not None and sid not in only:
            continue
        if "kriterler" not in row:
            continue
        exp_path = golden / sid / "expected.json"
        if not exp_path.exists():
            continue
        exp = json.loads(exp_path.read_text(encoding="utf-8"))["scores"]
        for ad, gelen in row["kriterler"].items():
            if ad not in exp:
                continue
            if gelen is None:
                yetersiz += 1
                continue
            puanlanan += 1
            per.setdefault(ad, []).append((exp[ad], gelen))

    krit = {}
    for ad, pairs in sorted(per.items()):
        banded = [(band(w), band(g)) for w, g in pairs]
        krit[ad] = {
            "n": len(pairs),
            "mae": round(statistics.fmean(abs(w - g) for w, g in pairs), 3),
            "tam": round(sum(1 for w, g in pairs if w == g) / len(pairs), 3),
            "bant": round(sum(1 for a, b in banded if a == b) / len(banded), 3),
            "kappa": cohens_kappa(banded),
            "sapma": round(statistics.fmean(g - w for w, g in pairs), 3),
        }
    kappas = [m["kappa"] for m in krit.values() if m["kappa"] is not None]
    return {
        "kriter_bazli": krit,
        "ozet": {
            "kriter_mae": round(statistics.fmean(m["mae"] for m in krit.values()), 3) if krit else None,
            "kappa_ortalama": round(statistics.fmean(kappas), 4) if kappas else None,
            "bant_isabet": round(statistics.fmean(m["bant"] for m in krit.values()), 3) if krit else None,
            "puanlanan_kriter": puanlanan,
            "yetersiz_kanit": yetersiz,
        },
    }


def _fmt(v) -> str:
    return "—" if v is None else f"{v:.3f}" if isinstance(v, float) else str(v)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("once")
    ap.add_argument("sonra")
    ap.add_argument("--only", default=None)
    ap.add_argument("--golden", default="data/golden")
    args = ap.parse_args()

    only = None
    if args.only:
        only = set(json.loads(Path(args.only).read_text(encoding="utf-8"))["sinav"])

    golden = Path(args.golden)
    a = metrics_from(Path(args.once), golden, only)
    b = metrics_from(Path(args.sonra), golden, only)

    baslik = f"AYNI ALTKUMEDE KARSILASTIRMA ({len(only) if only else 'tum'} senaryo)"
    print("=" * 74)
    print(baslik)
    print("=" * 74)
    print(f"{'metrik':<24}{'once':>12}{'sonra':>12}{'degisim':>14}")
    for k in ("kriter_mae", "kappa_ortalama", "bant_isabet", "yetersiz_kanit"):
        x, y = a["ozet"].get(k), b["ozet"].get(k)
        if x is None or y is None:
            print(f"{k:<24}{_fmt(x):>12}{_fmt(y):>12}{'—':>14}")
            continue
        d = y - x
        yon = "iyilesme" if (d < 0) == (k in ("kriter_mae", "yetersiz_kanit")) else "kotulesme"
        print(f"{k:<24}{_fmt(x):>12}{_fmt(y):>12}{d:>+10.3f} {yon}")

    print("\n" + "-" * 74)
    print(f"{'kriter':<24}{'MAE once':>10}{'MAE sonra':>11}{'kappa once':>12}{'kappa sonra':>13}")
    for ad in sorted(set(a["kriter_bazli"]) | set(b["kriter_bazli"])):
        ma = a["kriter_bazli"].get(ad, {})
        mb = b["kriter_bazli"].get(ad, {})
        print(f"{ad:<24}{_fmt(ma.get('mae')):>10}{_fmt(mb.get('mae')):>11}"
              f"{_fmt(ma.get('kappa')):>12}{_fmt(mb.get('kappa')):>13}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
