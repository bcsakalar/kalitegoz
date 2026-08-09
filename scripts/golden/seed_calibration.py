"""FAZ 3.4 doğrulaması — kalibrasyon örneklerini altın setten üret ve etkisini ölç.

## Ne yapar

Altın setin **eğitim yarısındaki** senaryolarda AI ile uzman referansı arasındaki
farkları alır ve bunları `calibration_examples` olarak kaydeder — tıpkı bir
kalitecinin düzeltmesi gibi. Sonra `make eval` yeniden koşulur ve kappa'nın
kapanıp kapanmadığı **ölçülür**.

## Neden bölünmüş set?

Örnekleri tüm altın setten üretip yine tüm altın sette ölçmek, sınavın sorularını
cevap anahtarıyla birlikte vermek olurdu. Bu yüzden senaryolar ikiye ayrılır:

    EĞİTİM (tek indeksli)  -> kalibrasyon örneği üretilir
    SINAV  (çift indeksli) -> metrik BURADAN okunur, örnek görmedi

Rapor edilen kappa/MAE yalnızca sınav yarısından hesaplanır.

Kullanım (container içinde):
    python scripts/golden/seed_calibration.py [--limit N]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, "/srv")

from app.db import SessionLocal  # noqa: E402
from app.models import CalibrationExample, Criterion, Score, Tenant  # noqa: E402
from app.services import review_feedback  # noqa: E402

GOLDEN_DIR = Path("/data/golden")
GOLDEN_TENANT = "__golden__"

# Yalnizca LLM ile puanlanan (oznel) kriterler icin ornek uretilir.
# Deterministik kriterlerin sapmasi zaten sifir; onlara ornek eklemek
# prompt'u gereksiz sisirir.
HEDEF_KRITERLER = {
    "Aktif Dinleme", "İhtiyaç Analizi", "Çözüm / Yönlendirme", "Bilgi Doğruluğu",
}


def split_scenarios() -> tuple[list[str], list[str]]:
    """Senaryolari egitim/sinav olarak ikiye ayir (deterministik)."""
    ids = sorted(p.name for p in GOLDEN_DIR.iterdir() if p.is_dir())
    egitim = [s for i, s in enumerate(ids) if i % 2 == 1]
    sinav = [s for i, s in enumerate(ids) if i % 2 == 0]
    return egitim, sinav


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--clear", action="store_true", help="Once mevcut ornekleri sil")
    args = ap.parse_args()

    db = SessionLocal()
    tenant = db.query(Tenant).filter(Tenant.name == GOLDEN_TENANT).first()
    if tenant is None:
        print("Altin set kiracisi yok — once `make eval` kosun.")
        return 1

    if args.clear:
        n = db.query(CalibrationExample).filter(
            CalibrationExample.tenant_id == tenant.id).delete()
        db.commit()
        print(f"{n} mevcut ornek silindi")

    criteria = {
        c.name: c for c in db.query(Criterion).filter(Criterion.tenant_id == tenant.id)
    }
    egitim, sinav = split_scenarios()
    print(f"egitim: {len(egitim)} senaryo · sinav: {len(sinav)} senaryo")

    uretilen = 0
    for sid in egitim:
        exp_path = GOLDEN_DIR / sid / "expected.json"
        tr_path = GOLDEN_DIR / sid / "transcript.json"
        if not exp_path.exists():
            continue
        exp = json.loads(exp_path.read_text(encoding="utf-8"))
        tr = json.loads(tr_path.read_text(encoding="utf-8"))
        excerpt = " ".join(s["text"] for s in tr["segments"])[
            : review_feedback.EXCERPT_CHARS]

        # Bu senaryonun en son puanlanmis cagrisini bul
        call_row = (
            db.query(Score.call_id)
            .join(Score.call)
            .filter(Score.call.has(filename=f"{sid}.golden"))
            .order_by(Score.call_id.desc())
            .first()
        )
        if call_row is None:
            continue
        scores = {
            s.criterion_name: s
            for s in db.query(Score).filter(Score.call_id == call_row[0])
        }

        for ad, beklenen in exp["scores"].items():
            if ad not in HEDEF_KRITERLER or ad not in criteria:
                continue
            s = scores.get(ad)
            if s is None or s.score is None:
                continue
            fark = s.score - beklenen
            if abs(fark) < 2:
                continue  # kucuk fark ogretici degil, gurultu
            review_feedback.record_correction(
                db, tenant_id=tenant.id, criterion_id=criteria[ad].id,
                call_id=call_row[0], excerpt=excerpt, ai_score=s.score,
                human_score=beklenen,
                reason_code="kriter_yanlis_yorumlandi",
                note=("AI cok comert davrandi" if fark > 0 else "AI cok kati davrandi"),
            )
            uretilen += 1

    db.commit()
    surum = review_feedback.calibration_version(db, tenant.id)
    print(f"{uretilen} kalibrasyon ornegi uretildi · surum: {surum}")

    aktif = 0
    for ad in HEDEF_KRITERLER:
        if ad in criteria:
            n = len(review_feedback.examples_for(db, tenant.id, criteria[ad].id))
            if n:
                aktif += 1
            print(f"  {ad:<24} prompt'a girecek ornek: {n}")
    print(f"{aktif}/{len(HEDEF_KRITERLER)} kriterde few-shot aktif")

    (Path("/data/eval") / "sinav_senaryolari.json").write_text(
        json.dumps({"egitim": egitim, "sinav": sinav}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
