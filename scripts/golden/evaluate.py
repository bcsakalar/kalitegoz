"""Altin set regresyon kosumu — `make eval`.

Bu betik API container'i icinde calisir (uygulama kodu + DB erisimi orada).

Ne yapar:
1. Izole bir `__golden__` kiracisi kurar (gercek veriyle KARISMAZ).
   Rubrik kriterleri ve yasakli kelimeler kaynak kiracidan birebir kopyalanir.
2. Her senaryonun transkriptini Call + Segment olarak yazar ve GERCEK puanlama
   motorunu (`scoring.run_scoring`) calistirir — sahte katman yok.
3. Metrikleri hesaplar ve docs/v2/eval/<tarih>.json olarak saklar.
4. Esikler saglanmazsa cikis kodu 1 doner (CI build'i kirar).

Kullanim (container icinde):
    python scripts/golden/evaluate.py [--limit N] [--repeat-n N] [--no-gate]
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, "/srv")  # backend imaji kodu /srv altina koyuyor

from app.db import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    Agent, BannedWord, Call, CallStatus, Channel, Criterion, Score, Segment, Tenant, Violation,
)
from app.services import scoring  # noqa: E402
from app.services.compliance import _normalize  # noqa: E402
from app.services.text_tr import contains_verbatim  # noqa: E402

GOLDEN_TENANT = "__golden__"
GOLDEN_DIR = Path("/data/golden")
# ./data host'a bagli (compose volume). Makefile buradan docs/v2/eval/ altina kopyalar.
OUT_DIR = Path("/data/eval")

# Puan bantlari — Cohen's kappa ordinal 0-10 uzerinde anlamli calismaz.
# Cagri merkezi QA pratiginde karar bantlari uctur:
#   0-4  karsilanmadi | 5-7 kismen karsilandi | 8-10 karsilandi
BANDS = [(0, 4, "karsilanmadi"), (5, 7, "kismen"), (8, 10, "karsilandi")]

# S10: metrikler NESNEL ve OZNEL kriterler icin AYRI raporlanir.
#
# Ikisini tek ortalamada birlestirmek, urunun en guclu yanini (nesnel
# kriterlerde kappa 0.94-1.00) en zayif yaniyla (oznel kriterlerde 0.08-0.20)
# ortalayip ikisini de yanlis gosteriyordu. "%100 kapsam" iddiasi da yalnizca
# nesnel kriterler icin kurulabilir.
NESNEL_KRITERLER = {
    "Açılış", "KVKK / Aydınlatma", "Kimlik Doğrulama", "Kapanış",
    "Yasaklı Kelime / Üslup", "Script Uyumu",
}
OZNEL_KRITERLER = {
    "Aktif Dinleme", "İhtiyaç Analizi", "Çözüm / Yönlendirme", "Bilgi Doğruluğu",
}


def kriter_turu(ad: str) -> str:
    if ad in NESNEL_KRITERLER:
        return "nesnel"
    if ad in OZNEL_KRITERLER:
        return "oznel"
    return "diger"

# Kabul esikleri (FAZ 2 DoD). FAZ 1'de taban cizgisi olculur, kapi KAPALI olabilir.
GATES = {
    "sifirlayici_yanlis_pozitif_orani": 0.0,   # <= (en kritik metrik)
    "kriter_mae": 1.0,                          # <=
    # S2b: oznel kriterlerde SABIT kappa hedefi KOYULMAZ — hedef insan-insan
    # uyumuna baglanir (bkz. scripts/golden/human_ref.py). Kapi yalnizca
    # NESNEL kriterleri denetler; oznel kriterler raporlanir ama kapi degil.
    "nesnel_kappa": 0.90,                       # >=
    "kanit_dogrulanabilirlik": 0.95,            # >=
    "tekrarlanabilirlik_std": 1.5,              # <=
    "must_not_penalize_ihlali": 0,              # <=
}


def band(score: float) -> str:
    for lo, hi, name in BANDS:
        if lo <= score <= hi:
            return name
    return "karsilanmadi"


def cohens_kappa(pairs: list[tuple[str, str]]) -> float | None:
    """Bantlanmis (beklenen, gercek) ciftleri uzerinde Cohen's kappa."""
    if not pairs:
        return None
    cats = sorted({c for p in pairs for c in p})
    n = len(pairs)
    po = sum(1 for a, b in pairs if a == b) / n
    pe = 0.0
    for c in cats:
        pa = sum(1 for a, _ in pairs if a == c) / n
        pb = sum(1 for _, b in pairs if b == c) / n
        pe += pa * pb
    if pe >= 1.0:
        return 1.0 if po >= 1.0 else 0.0
    return round((po - pe) / (1 - pe), 4)


# --------------------------------------------------------------------------
# Izole kiraci kurulumu
# --------------------------------------------------------------------------

_SUBJECTIVE_MODEL: str | None = None


def ensure_golden_tenant(db) -> tuple[Tenant, Agent]:
    """Altin set kiracisini kur; rubrigi kaynak kiracidan birebir kopyala."""
    t = db.query(Tenant).filter(Tenant.name == GOLDEN_TENANT).first()
    src = db.query(Tenant).filter(Tenant.name != GOLDEN_TENANT).order_by(Tenant.id).first()
    if src is None:
        raise RuntimeError("Kaynak kiraci yok — once seed calistirin")

    # Senaryolardaki kurum adi. Katman A acilis kontrolu bunu arar; kiraci
    # ayarinda yoksa "kurum adi soylenmedi" der ve TUM senaryolarda Acilis
    # haksiz yere dusuk cikar (ilk FAZ 2 kosumunda bizzat yasandi: MAE 4.8).
    golden_settings = dict(src.settings or {})
    golden_settings["brand_names"] = ["Netik İletişim", "Netik"]

    # S2c: oznel kriterler icin model yonlendirmesi. Kaynak kiracinin ayari her
    # kosumda kopyalandigi icin buraya yazilir; deney bayraktan kontrol edilir.
    if _SUBJECTIVE_MODEL:
        ai = dict(golden_settings.get("ai") or {})
        ai["subjective_model"] = _SUBJECTIVE_MODEL
        golden_settings["ai"] = ai

    if t is None:
        t = Tenant(name=GOLDEN_TENANT, slug="golden", brand_name="Netik İletişim",
                   settings=golden_settings)
        db.add(t)
        db.flush()
    else:
        # Kaynak rubrik degistiyse ayni kalsin diye her kosumda yenilenir
        db.query(Criterion).filter(Criterion.tenant_id == t.id).delete()
        db.query(BannedWord).filter(BannedWord.tenant_id == t.id).delete()
        t.settings = golden_settings
        t.brand_name = "Netik İletişim"
        db.flush()

    for c in db.query(Criterion).filter(Criterion.tenant_id == src.id).order_by(Criterion.id):
        db.add(Criterion(
            tenant_id=t.id, name=c.name, group=c.group, description=c.description,
            weight=c.weight, is_critical=c.is_critical,
            critical_threshold=c.critical_threshold, is_active=c.is_active,
            channel_scope=c.channel_scope, campaign_id=None,
            # FAZ 2 alanlari da kopyalanmali; aksi halde altin set kiracisinda
            # capalar kaybolur ve Katman B prompt'u kaynak kiracidakinden
            # FARKLI olur — olctugumuz sey uretimdeki sistem olmaz.
            evaluation_mode=c.evaluation_mode, check_key=c.check_key,
            anchor_10=c.anchor_10, anchor_0=c.anchor_0,
        ))
    for b in db.query(BannedWord).filter(BannedWord.tenant_id == src.id):
        db.add(BannedWord(
            tenant_id=t.id, term=b.term, category=b.category, severity=b.severity,
            match_type=b.match_type, is_active=b.is_active,
        ))

    a = db.query(Agent).filter(Agent.tenant_id == t.id).first()
    if a is None:
        a = Agent(tenant_id=t.id, name="golden.agent")
        db.add(a)
    db.commit()
    return t, a


_ONLY: set[str] | None = None


def load_scenarios(limit: int | None) -> list[dict]:
    out = []
    for d in sorted(p for p in GOLDEN_DIR.iterdir() if p.is_dir()):
        tr = d / "transcript.json"
        ex = d / "expected.json"
        if _ONLY is not None and d.name not in _ONLY:
            continue
        if tr.exists() and ex.exists():
            out.append({
                "transcript": json.loads(tr.read_text(encoding="utf-8")),
                "expected": json.loads(ex.read_text(encoding="utf-8")),
            })
    return out[:limit] if limit else out


def score_scenario(db, tenant: Tenant, agent: Agent, tr: dict) -> dict:
    """Senaryoyu gercek puanlama motorundan gecir, sonucu topla."""
    call = Call(
        tenant_id=tenant.id, agent_id=agent.id, filename=f"{tr['id']}.golden",
        channel=Channel.voice, status=CallStatus.scoring,
        duration_sec=tr["duration_sec"],
        # Altin set transkript seviyesinde calisir; ses dosyasi yok.
        # Kolon NOT NULL oldugu icin sentinel yol yazilir (hicbir yerde okunmaz).
        audio_path=f"golden://{tr['id']}",
    )
    db.add(call)
    db.flush()

    seg_dicts = []
    for s in tr["segments"]:
        db.add(Segment(
            call_id=call.id, idx=s["idx"], speaker=s["speaker"],
            start_sec=s["start"], end_sec=s["end"], text=s["text"],
        ))
        seg_dicts.append({"speaker": s["speaker"], "start": s["start"],
                          "end": s["end"], "text": s["text"]})
    from app.services import metrics as metrics_svc
    call.metrics = metrics_svc.compute_metrics(seg_dicts, tr["duration_sec"])
    db.flush()

    outcome = scoring.run_scoring(db, call)
    call.status = CallStatus.done
    db.commit()

    rows = db.query(Score).filter(Score.call_id == call.id).all()
    viol = db.query(Violation).filter(Violation.call_id == call.id).all()
    return {
        "call_id": call.id,
        "scores": [{"name": r.criterion_name, "score": r.score,
                    "evidence": r.evidence or "", "rationale": r.rationale or "",
                    "decision": r.decision, "source_layer": r.source_layer,
                    "confidence": r.confidence} for r in rows],
        "total": call.total_score,
        "zeroed": bool(call.zeroed),
        "is_crisis": bool(call.is_crisis),
        # FAZ 4'ten beri outcome.alerts bir AlertDraft listesi (eskiden tuple'di).
        # Bu satir guncellenmedigi icin FAZ 4 sonrasi ilk kosumda TUM senaryolar
        # "'AlertDraft' object is not subscriptable" ile dustu — eval'i her faz
        # sonunda kosmamanin bedeli.
        "alerts": [d.type.value for d in outcome.alerts],
        "alert_rules": [d.rule_id for d in outcome.alerts],
        "violations": [{"kind": v.kind, "term": v.term, "speaker": v.speaker} for v in viol],
        "duplicate_criteria": len(rows) - len({r.criterion_id for r in rows}),
    }


def evidence_found(evidence: str, transcript_text: str) -> bool:
    """Kanit, transkriptte GERCEKTEN geciyor mu?

    URETIMDEKI dogrulayicinin ta kendisi kullanilir (`text_tr.contains_verbatim`).
    Ayri bir kopyasini yazmak, motoru degil "iki dogrulayici arasindaki farki"
    olcmek olurdu — nitekim ilk surumde tam bu oldu: Katman C'nin kabul ettigi
    alintilarin %29.5'ini degerlendiricinin kendi kopyasi reddediyordu.
    """
    ev = (evidence or "").strip()
    if not ev:
        return False
    # Sistem kanitin basina "[00:01 | 1sn] TEMSILCI: " on eki koyabiliyor
    if "]" in ev and ":" in ev.split("]", 1)[1][:20]:
        ev = ev.split(":", 2)[-1]
    return contains_verbatim(transcript_text, ev)


def _tur_ozeti(crit_metrics: dict, tur: str) -> dict:
    """Bir kriter turunun (nesnel/oznel) ortalama metrikleri."""
    secili = [m for m in crit_metrics.values() if m.get("tur") == tur]
    if not secili:
        return {"kriter_sayisi": 0, "kappa": None, "mae": None, "bant_isabet": None}
    kappas = [m["kappa"] for m in secili if m["kappa"] is not None]
    return {
        "kriter_sayisi": len(secili),
        "kappa": round(statistics.fmean(kappas), 4) if kappas else None,
        "mae": round(statistics.fmean(m["mae"] for m in secili), 3),
        "bant_isabet": round(statistics.fmean(m["band_isabet"] for m in secili), 3),
        "tam_isabet": round(statistics.fmean(m["tam_isabet"] for m in secili), 3),
    }


def evaluate(limit: int | None, repeat_n: int) -> dict:
    db = SessionLocal()
    tenant, agent = ensure_golden_tenant(db)
    # Onceki kosumun cagrilarini temizle (izole kiraci — gercek veriye dokunmaz)
    old = db.query(Call).filter(Call.tenant_id == tenant.id).all()
    for c in old:
        db.delete(c)
    db.commit()

    scenarios = load_scenarios(limit)
    print(f"{len(scenarios)} senaryo degerlendiriliyor...", flush=True)

    per_criterion: dict[str, list[tuple[int, float]]] = {}
    evidence_total = evidence_ok = 0
    # FAZ 2: 'insufficient_evidence' birinci sinif bir sonuc. Yanlis puan DEGIL —
    # sistemin "bilmiyorum, insana soralim" demesi. Ayri olculur; cok yuksek olmasi
    # da bir sorundur (kapsam duser), ama yanlis puandan iyidir.
    insufficient_total = 0
    insufficient_by_crit: dict[str, int] = {}
    scored_total = 0
    evidence_fabricated: list[dict] = []
    zero_fp: list[str] = []
    zero_fn: list[str] = []
    penalize_violations: list[dict] = []
    evidence_content_fail: list[dict] = []
    crisis_miss: list[str] = []
    duplicate_calls: list[str] = []
    details = []

    for i, item in enumerate(scenarios, 1):
        tr, exp = item["transcript"], item["expected"]
        blob = " ".join(s["text"] for s in tr["segments"])
        try:
            got = score_scenario(db, tenant, agent, tr)
        except Exception as exc:  # noqa: BLE001
            # Bir senaryonun patlamasi kalan senaryolari dusurmemeli
            db.rollback()
            print(f"  [{i}/{len(scenarios)}] {tr['id']}: HATA {str(exc)[:160]}", flush=True)
            details.append({"id": tr["id"], "error": str(exc)[:400]})
            continue

        by_name = {s["name"]: s for s in got["scores"]}
        for crit, want in exp["scores"].items():
            s = by_name.get(crit)
            if s is None:
                continue
            # FAZ 2: puan None ise kriter 'yetersiz kanit' — ne dogru ne yanlis,
            # insan kuyruguna dusmus demektir. MAE/kappa'ya KATILMAZ; ayri olculur.
            if s["score"] is None:
                insufficient_total += 1
                insufficient_by_crit[crit] = insufficient_by_crit.get(crit, 0) + 1
                continue
            per_criterion.setdefault(crit, []).append((want, s["score"]))

        # Kanit dogrulanabilirligi, "sistem transkriptten alinti diye ne
        # gosteriyorsa gercekten orada mi?" sorusudur. Yalnizca Katman B
        # (LLM'in iddia ettigi alinti) olculur:
        #   * Katman A'nin kaniti kodun kendisi urettigi icin yapisi geregi
        #     dogrudur; "yokluk kaniti" ise bir alinti DEGILDIR
        #     ("12 replik tarandi, bulunamadi") ve transkriptte aranamaz.
        #   * Puanlanmamis (yetersiz kanit) kriterlerde ortada iddia yoktur.
        for s in got["scores"]:
            if s["score"] is None or s.get("source_layer") != "B":
                continue
            evidence_total += 1
            if evidence_found(s["evidence"], blob):
                evidence_ok += 1
            else:
                evidence_fabricated.append({
                    "id": tr["id"], "kriter": s["name"],
                    "karar": s.get("decision"), "alinti": (s["evidence"] or "")[:90],
                })

        if got["zeroed"] and not exp["zeroed"]:
            zero_fp.append(tr["id"])
        if exp["zeroed"] and not got["zeroed"]:
            zero_fn.append(tr["id"])

        scored_total += sum(1 for s in got["scores"] if s["score"] is not None)

        for crit in exp.get("must_not_penalize", []):
            actual = by_name.get(crit, {}).get("score")
            if actual is not None and actual < 8:
                penalize_violations.append({"id": tr["id"], "kriter": crit, "puan": actual})

        for crit, frag in (exp.get("evidence_must_contain") or {}).items():
            ev = by_name.get(crit, {}).get("evidence") or ""
            if _normalize(frag) not in _normalize(ev):
                evidence_content_fail.append({"id": tr["id"], "kriter": crit,
                                              "beklenen": frag, "gelen": ev[:70]})

        if "crisis" in exp.get("alerts", []) and not got["is_crisis"]:
            crisis_miss.append(tr["id"])
        if got["duplicate_criteria"]:
            duplicate_calls.append(tr["id"])

        details.append({
            "id": tr["id"], "bucket": tr["bucket"], "regression_for": exp.get("regression_for"),
            "beklenen_zeroed": exp["zeroed"], "gelen_zeroed": got["zeroed"],
            "toplam": got["total"],
            "kriterler": {s["name"]: s["score"] for s in got["scores"]},
        })
        flag = ""
        if got["zeroed"] != exp["zeroed"]:
            flag = "  <-- SIFIRLAMA UYUSMAZLIGI"
        print(f"  [{i}/{len(scenarios)}] {tr['id']:<34} toplam={got['total']:>5} "
              f"zeroed={got['zeroed']}{flag}", flush=True)

    # --- Tekrarlanabilirlik: secilmis senaryolar 3 kez -------------------
    repeat_ids = ["reg-b1-acilis-tam", "yuksek-01-fatura-itiraz", "orta-01-kapanis-eksik"]
    repeat_scen = [s for s in scenarios if s["transcript"]["id"] in repeat_ids]
    repeat_res = {}
    if repeat_n > 1 and repeat_scen:
        print(f"Tekrarlanabilirlik: {len(repeat_scen)} senaryo x {repeat_n} kosum...", flush=True)
        for item in repeat_scen:
            totals = []
            for _ in range(repeat_n):
                try:
                    totals.append(score_scenario(db, tenant, agent, item["transcript"])["total"])
                except Exception:  # noqa: BLE001
                    pass
            if len(totals) > 1:
                repeat_res[item["transcript"]["id"]] = {
                    "puanlar": totals,
                    "std": round(statistics.stdev(totals), 2),
                    "aralik": round(max(totals) - min(totals), 2),
                }
                print(f"  {item['transcript']['id']}: {totals} std={repeat_res[item['transcript']['id']]['std']}",
                      flush=True)

    db.close()

    # --- Metrikler -------------------------------------------------------
    crit_metrics = {}
    all_pairs: list[tuple[str, str]] = []
    for crit, pairs in sorted(per_criterion.items()):
        mae = round(statistics.fmean(abs(w - g) for w, g in pairs), 3)
        exact = round(sum(1 for w, g in pairs if w == g) / len(pairs), 3)
        banded = [(band(w), band(g)) for w, g in pairs]
        all_pairs.extend(banded)
        crit_metrics[crit] = {
            "tur": kriter_turu(crit),
            "n": len(pairs), "mae": mae, "tam_isabet": exact,
            "band_isabet": round(sum(1 for a, b in banded if a == b) / len(banded), 3),
            "kappa": cohens_kappa(banded),
            "ortalama_sapma": round(statistics.fmean(g - w for w, g in pairs), 3),
        }

    n_not_zero = sum(1 for s in scenarios if not s["expected"]["zeroed"])
    n_zero = sum(1 for s in scenarios if s["expected"]["zeroed"])
    kappas = [m["kappa"] for m in crit_metrics.values() if m["kappa"] is not None]
    stds = [r["std"] for r in repeat_res.values()]

    summary = {
        "kriter_mae": round(statistics.fmean(m["mae"] for m in crit_metrics.values()), 3) if crit_metrics else None,
        "tam_isabet_orani": round(statistics.fmean(m["tam_isabet"] for m in crit_metrics.values()), 3) if crit_metrics else None,
        "band_isabet_orani": round(statistics.fmean(m["band_isabet"] for m in crit_metrics.values()), 3) if crit_metrics else None,
        "kappa_ortalama": round(statistics.fmean(kappas), 4) if kappas else None,
        "sifirlayici_yanlis_pozitif_orani": round(len(zero_fp) / n_not_zero, 4) if n_not_zero else 0.0,
        "sifirlayici_yanlis_negatif_orani": round(len(zero_fn) / n_zero, 4) if n_zero else 0.0,
        "kanit_dogrulanabilirlik": round(evidence_ok / evidence_total, 4) if evidence_total else 0.0,
        "tekrarlanabilirlik_std": round(max(stds), 2) if stds else None,
        "must_not_penalize_ihlali": len(penalize_violations),
        # S10: nesnel/oznel kirilimi — tek ortalama iki farkli gercegi gizliyordu
        "nesnel": _tur_ozeti(crit_metrics, "nesnel"),
        "oznel": _tur_ozeti(crit_metrics, "oznel"),
        # Kapsam: kriterlerin ne kadari AI tarafindan puanlandi (gerisi insana gitti)
        "yetersiz_kanit_orani": round(
            insufficient_total / (insufficient_total + scored_total), 4
        ) if (insufficient_total + scored_total) else 0.0,
        "puanlanan_kriter": scored_total,
        "yetersiz_kanitli_kriter": insufficient_total,
    }

    return {
        "tarih": datetime.now().isoformat(timespec="seconds"),
        "senaryo_sayisi": len(scenarios),
        "ozet": summary,
        "kriter_bazli": crit_metrics,
        "yetersiz_kanit_kriter_bazli": insufficient_by_crit,
        "sifirlayici_yanlis_pozitif": zero_fp,
        "sifirlayici_yanlis_negatif": zero_fn,
        "kanitsiz_ceza_ihlalleri": penalize_violations,
        "kanit_icerigi_tutmayan": evidence_content_fail,
        "dogrulanamayan_alintilar": evidence_fabricated,
        "kacirilan_kriz": crisis_miss,
        "tekrarlanan_kriter_ureten_cagrilar": duplicate_calls,
        "tekrarlanabilirlik": repeat_res,
        "detay": details,
    }


def check_gates(summary: dict) -> list[str]:
    fails = []
    duz = dict(summary)
    duz["nesnel_kappa"] = (summary.get("nesnel") or {}).get("kappa")
    for key, limit in GATES.items():
        val = duz.get(key)
        if val is None:
            continue
        higher_is_better = key in ("nesnel_kappa", "kanit_dogrulanabilirlik")
        if higher_is_better and val < limit:
            fails.append(f"{key}: {val} < hedef {limit}")
        elif not higher_is_better and val > limit:
            fails.append(f"{key}: {val} > hedef {limit}")
    return fails


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--repeat-n", type=int, default=3)
    ap.add_argument("--no-gate", action="store_true",
                    help="Esikleri kontrol etme (FAZ 1 taban cizgisi icin)")
    ap.add_argument("--only", default=None,
                    help="Yalniz bu dosyadaki senaryolari kosur (sinav altkumesi)")
    ap.add_argument("--subjective-model", default=None,
                    help="S2c: oznel kriterleri bu modelle kosur (or. qwen2.5:14b-instruct)")
    ap.add_argument("--etiket", default=None,
                    help="Rapor dosya adina eklenecek etiket (kosumlari ayirmak icin)")
    args = ap.parse_args()

    if args.subjective_model:
        global _SUBJECTIVE_MODEL
        _SUBJECTIVE_MODEL = args.subjective_model
        print(f"Oznel kriter modeli: {args.subjective_model}")

    if args.only:
        import json as _json
        sel = set(_json.loads(Path(args.only).read_text(encoding='utf-8'))['sinav'])
        global _ONLY
        _ONLY = sel
        print(f'Yalniz sinav altkumesi: {len(sel)} senaryo')
    report = evaluate(args.limit, args.repeat_n)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    report["kosum"] = {
        "tarih": date.today().isoformat(),
        "oznel_model": _SUBJECTIVE_MODEL or "(varsayilan)",
        "etiket": args.etiket or "",
    }
    ad = date.today().isoformat() + (f"-{args.etiket}" if args.etiket else "")
    path = OUT_DIR / f"{ad}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    s = report["ozet"]
    print("\n" + "=" * 62)
    print("ALTIN SET SONUCU")
    print("=" * 62)
    for k, v in s.items():
        print(f"  {k:<38} {v}")
    print("-" * 62)
    for tur in ("nesnel", "oznel"):
        t = s.get(tur) or {}
        print(f"  {tur.upper():<8} ({t.get('kriter_sayisi', 0)} kriter)  "
              f"kappa={t.get('kappa')}  MAE={t.get('mae')}  "
              f"bant={t.get('bant_isabet')}")
    print("-" * 62)
    print(f"  sifirlayici yanlis pozitif : {report['sifirlayici_yanlis_pozitif']}")
    print(f"  sifirlayici yanlis negatif : {report['sifirlayici_yanlis_negatif']}")
    print(f"  kanitsiz ceza ihlali       : {len(report['kanitsiz_ceza_ihlalleri'])}")
    print(f"  kacirilan kriz             : {report['kacirilan_kriz']}")
    print(f"\nRapor: {path}")

    fails = check_gates(s)
    if fails:
        print("\nESIK IHLALLERI:")
        for f in fails:
            print("  -", f)
        if not args.no_gate:
            return 1
        print("  (--no-gate: taban cizgisi kosumu, build kirilmadi)")
    else:
        print("\nTum esikler saglandi.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
