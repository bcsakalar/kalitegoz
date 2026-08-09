"""İnsan referansı ve puanlayıcılar arası uyum (IRR) altyapısı — S2 / S2b.

## Neden bu modül var

Altın setin beklenen puanlarını sistemi geliştiren yapay zekâ asistanı yazdı.
Nesnel kriterlerde bu bir *spesifikasyondur* ve savunulabilir; öznel
kriterlerde **döngüseldir**: prompt'u tasarlayan ile cevap anahtarını yazan
aynı taraftır.

Bu modül döngüyü kırar:

1. **`select`** — insanın elle puanlayacağı 20 senaryoluk temsili alt küme
   seçer ve doldurulacak şablonu üretir.
2. **`compare`** — iki puanlama setini karşılaştırır. Her iki taraf da bir
   JSON dosyası ya da `sentetik` (altın setin mevcut beklenen puanları)
   olabilir. Aynı komut **farklı sorulara** cevap verir:

       # İnsan referansı, sentetik referanstan ne kadar ayrışıyor?
       python -m scripts.golden.human_ref compare --a sentetik --b rio.json

       # İki insan birbirine ne kadar uyuyor? (IRR — öznel hedefi bu belirler)
       python -m scripts.golden.human_ref compare --a rio.json --b uzman2.json

   Çıktı kriter bazında Cohen's kappa, MAE ve bant isabetidir; nesnel ve
   öznel kriterler **ayrı** raporlanır.

## Öznel kriterlerde hedef neden sabit 0.75 değil?

Sabit bir kappa hedefi, kriterin **doğasını** yok sayar. İki deneyimli kalite
uzmanı "aktif dinleme" kriterinde birbiriyle 0.55 uyum yakalıyorsa, yapay
zekâdan 0.75 beklemek bir hedef değil, imkânsız bir şarttır — insanın kendisi
o eşiği geçemiyor.

Sektörde puanlayıcılar arası uyum (IRR) hedefi %85 civarındadır ama bu **genel
uyum yüzdesidir**, kriter bazlı kappa değil. Öznel kriterlerde kappa doğal
olarak düşer.

Bu yüzden öznel kriterlerde **hedef, insan-insan uyumudur**:

    AI hedefi (öznel kriter) = insan-insan kappa × 0.85

Yani yapay zekâdan, iki insanın birbirine olan uyumunun %85'ini yakalaması
beklenir. İnsanlar birbirine 0.60 uyuyorsa AI hedefi 0.51'dir; 0.90 uyuyorsa
hedef 0.77 olur. Hedef, ölçülen gerçeğe bağlanır.

Nesnel/deterministik kriterlerde hedef sabit kalır (**≥ 0.90**): oradaki cevap
tartışmaya açık değildir, iki insan da aynı cevabı vermelidir.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

# Windows konsolu varsayilan olarak cp1254 kullanir ve "≥", "→" gibi
# karakterlerde COKER (UnicodeEncodeError). Betigin ciktisi Turkce oldugu
# icin bu kacinilmaz; cozum ciktiyi UTF-8'e sabitlemek.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


GOLDEN_DIR = Path("data/golden")
HUMAN_DIR = Path("data/human_ref")

# Nesnel/deterministik kriterler — cevabı transkriptte aranarak doğrulanabilir.
NESNEL = {
    "Açılış", "KVKK / Aydınlatma", "Kimlik Doğrulama", "Kapanış",
    "Yasaklı Kelime / Üslup", "Script Uyumu",
}
# Öznel kriterler — yargı gerektirir; hedefleri insan-insan uyumuna bağlanır.
OZNEL = {"Aktif Dinleme", "İhtiyaç Analizi", "Çözüm / Yönlendirme", "Bilgi Doğruluğu"}

# Öznel kriterde AI'dan beklenen: insan-insan uyumunun bu oranı.
OZNEL_HEDEF_ORANI = 0.85
# Nesnel kriterde sabit hedef — cevap tartışmaya açık değil.
NESNEL_HEDEF_KAPPA = 0.90

BANDS = [(0, 4, "karsilanmadi"), (5, 7, "kismen"), (8, 10, "karsilandi")]


def band(v: int | None) -> str | None:
    if v is None:
        return None
    for lo, hi, ad in BANDS:
        if lo <= v <= hi:
            return ad
    return "karsilanmadi"


def cohens_kappa(pairs: list[tuple[str, str]]) -> float | None:
    """Bantlanmış (a, b) çiftleri üzerinde Cohen's kappa."""
    if len(pairs) < 2:
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


# ---------------------------------------------------------------------------
# 1) Alt küme seçimi
# ---------------------------------------------------------------------------

def select(n: int = 20) -> list[str]:
    """İnsanın puanlayacağı TEMSİLİ alt kümeyi seç.

    Rastgele seçim, 20 senaryoda kovaları dengesiz doldurabilir (6 sıfırlayıcı
    senaryonun hiçbiri gelmeyebilir). Bu yüzden her kovadan **oranlı** seçim
    yapılır ve seçim deterministiktir (aynı liste her koşumda gelir).
    """
    index = json.loads((GOLDEN_DIR / "index.json").read_text(encoding="utf-8"))
    senaryolar = index["senaryolar"]

    kovalar: dict[str, list[str]] = {}
    for s in senaryolar:
        kovalar.setdefault(s["bucket"], []).append(s["id"])

    toplam = len(senaryolar)
    secim: list[str] = []
    for kova in sorted(kovalar):
        idler = sorted(kovalar[kova])
        pay = max(1, round(n * len(idler) / toplam))
        # Kova içinden eşit aralıklı seç — baştan sona temsil edilsin
        adim = max(1, len(idler) // pay)
        secim.extend(idler[::adim][:pay])

    # Regresyon vakaları (B1-B6, B29-B32) MUTLAKA dahil: en kritik olanlar
    regresyon = [s["id"] for s in senaryolar if s.get("regression_for")]
    for r in regresyon[:6]:
        if r not in secim:
            secim.append(r)

    return sorted(set(secim))[:n]


def make_template(ids: list[str]) -> dict:
    """İnsanın dolduracağı şablonu üret — puanlar BOŞ, transkript dahil."""
    out: dict = {
        "_aciklama": (
            "Her senaryonun transkriptini okuyup her kriteri 0-10 arası puanlayın. "
            "Sentetik referansın puanları BİLİNÇLİ OLARAK GÖSTERİLMİYOR — "
            "yanlılık olmaması için. Emin olamadığınız kriteri null bırakın."
        ),
        "_olcek": {
            "9-10": "Kusursuz — kriterin tüm unsurları eksiksiz karşılandı",
            "7-8": "İyi — küçük bir eksik var",
            "5-6": "Orta — önemli bir unsur eksik",
            "3-4": "Zayıf — kriterin büyük kısmı karşılanmadı",
            "0-2": "Başarısız — kriter hiç karşılanmadı veya ağır ihlal",
            "null": "Bu kriteri değerlendirecek yeterli bilgi yok",
        },
        "puanlayici": "",
        "tarih": "",
        "senaryolar": {},
    }
    for sid in ids:
        tr = json.loads((GOLDEN_DIR / sid / "transcript.json").read_text(encoding="utf-8"))
        exp = json.loads((GOLDEN_DIR / sid / "expected.json").read_text(encoding="utf-8"))
        out["senaryolar"][sid] = {
            "baslik": tr["title"],
            "transkript": [
                f"[{int(s['start'] // 60):02d}:{int(s['start'] % 60):02d}] "
                f"{'TEMSİLCİ' if s['speaker'] == 'temsilci' else 'MÜŞTERİ' if s['speaker'] == 'musteri' else 'KONUŞMACI'}: "
                f"{s['text']}"
                for s in tr["segments"]
            ],
            "puanlar": {k: None for k in sorted(exp["scores"])},
            "sifirlanmali_mi": None,
            "not": "",
        }
    return out


# ---------------------------------------------------------------------------
# 2) İnsan referansını yükle
# ---------------------------------------------------------------------------

def load_human(path: Path) -> dict[str, dict[str, int | None]]:
    """{senaryo_id: {kriter: puan}} — doldurulmamış alanlar atlanır."""
    if not path.exists():
        return {}
    veri = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, dict[str, int | None]] = {}
    for sid, s in (veri.get("senaryolar") or {}).items():
        puanlar = {k: v for k, v in (s.get("puanlar") or {}).items() if v is not None}
        if puanlar:
            out[sid] = puanlar
    return out


def load_synthetic(ids: list[str] | None = None) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for d in sorted(p for p in GOLDEN_DIR.iterdir() if p.is_dir()):
        if ids is not None and d.name not in ids:
            continue
        f = d / "expected.json"
        if f.exists():
            out[d.name] = json.loads(f.read_text(encoding="utf-8"))["scores"]
    return out


# ---------------------------------------------------------------------------
# 3) İki puanlama setini karşılaştır (IRR)
# ---------------------------------------------------------------------------

def compare(
    a: dict[str, dict], b: dict[str, dict], a_ad: str = "A", b_ad: str = "B"
) -> dict:
    """Kriter bazında kappa + MAE + tam isabet."""
    ortak = sorted(set(a) & set(b))
    per: dict[str, list[tuple[int, int]]] = {}
    for sid in ortak:
        for kriter, pa in a[sid].items():
            pb = b[sid].get(kriter)
            if pa is None or pb is None:
                continue
            per.setdefault(kriter, []).append((int(pa), int(pb)))

    kriterler = {}
    for kriter, ciftler in sorted(per.items()):
        banded = [(band(x), band(y)) for x, y in ciftler]
        banded = [(x, y) for x, y in banded if x and y]
        kriterler[kriter] = {
            "n": len(ciftler),
            "kappa": cohens_kappa(banded),
            "mae": round(statistics.fmean(abs(x - y) for x, y in ciftler), 3),
            "tam_isabet": round(sum(1 for x, y in ciftler if x == y) / len(ciftler), 3),
            "bant_isabet": (round(sum(1 for x, y in banded if x == y) / len(banded), 3)
                            if banded else None),
            "tur": "nesnel" if kriter in NESNEL else ("oznel" if kriter in OZNEL else "diger"),
        }

    def _ort(tur: str, alan: str) -> float | None:
        d = [m[alan] for m in kriterler.values() if m["tur"] == tur and m[alan] is not None]
        return round(statistics.fmean(d), 4) if d else None

    return {
        "a": a_ad, "b": b_ad, "ortak_senaryo": len(ortak),
        "kriter_bazli": kriterler,
        "nesnel": {"kappa": _ort("nesnel", "kappa"), "mae": _ort("nesnel", "mae")},
        "oznel": {"kappa": _ort("oznel", "kappa"), "mae": _ort("oznel", "mae")},
    }


def hedefler(irr: dict | None) -> dict:
    """Kriter türüne göre AI hedefi.

    Nesnel: sabit 0.90.
    Öznel : insan-insan kappa'sının %85'i. IRR ölçülmediyse None —
            **hedef uydurulmaz**, "henüz ölçülmedi" denir.
    """
    oznel_hedef = None
    if irr and irr.get("oznel", {}).get("kappa") is not None:
        oznel_hedef = round(irr["oznel"]["kappa"] * OZNEL_HEDEF_ORANI, 4)
    return {
        "nesnel_kappa_hedefi": NESNEL_HEDEF_KAPPA,
        "oznel_kappa_hedefi": oznel_hedef,
        "oznel_hedef_aciklama": (
            f"İnsan-insan uyumunun %{OZNEL_HEDEF_ORANI * 100:.0f}'i"
            if oznel_hedef is not None
            else "İnsan-insan IRR henüz ölçülmedi; öznel kriterlerde sabit hedef "
                 "KOYULMUYOR (bkz. human_ref.py modül notu)."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("select", help="Insan icin alt kume sec ve sablon uret")
    s.add_argument("-n", type=int, default=20)
    s.add_argument("--out", default="data/human_ref/sablon.json")

    c = sub.add_parser("compare", help="Iki puanlama setini karsilastir")
    c.add_argument("--a", required=True, help="A seti (json) veya 'sentetik'")
    c.add_argument("--b", required=True, help="B seti (json) veya 'sentetik'")

    args = ap.parse_args()

    if args.cmd == "select":
        ids = select(args.n)
        HUMAN_DIR.mkdir(parents=True, exist_ok=True)
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(make_template(ids), ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"{len(ids)} senaryo secildi -> {out}")
        for i in ids:
            print("  -", i)
        return 0

    def _yukle(yol: str):
        if yol == "sentetik":
            return load_synthetic(), "sentetik referans"
        return load_human(Path(yol)), Path(yol).stem

    a, a_ad = _yukle(args.a)
    b, b_ad = _yukle(args.b)
    if not a or not b:
        print("En az bir set bos — karsilastirma yapilamaz.")
        return 1

    # Ortak senaryolara indir
    ortak = set(a) & set(b)
    a = {k: v for k, v in a.items() if k in ortak}
    b = {k: v for k, v in b.items() if k in ortak}

    rapor = compare(a, b, a_ad, b_ad)
    print("=" * 70)
    print(f"KARSILASTIRMA: {a_ad}  vs  {b_ad}   ({rapor['ortak_senaryo']} ortak senaryo)")
    print("=" * 70)
    print(f"{'kriter':<26}{'tur':>8}{'n':>4}{'kappa':>9}{'MAE':>7}{'bant':>7}")
    for k, m in rapor["kriter_bazli"].items():
        print(f"{k:<26}{m['tur']:>8}{m['n']:>4}{str(m['kappa']):>9}"
              f"{m['mae']:>7}{str(m['bant_isabet']):>7}")
    print("-" * 70)
    print(f"  nesnel  kappa={rapor['nesnel']['kappa']}  MAE={rapor['nesnel']['mae']}")
    print(f"  oznel   kappa={rapor['oznel']['kappa']}  MAE={rapor['oznel']['mae']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
