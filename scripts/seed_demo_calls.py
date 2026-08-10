"""Kurulumla gelen 20 örnek çağrıyı üretir — "bekliyor" durumunda.

## Ne yapar, ne YAPMAZ

**Yapar:** 20 senaryonun sesini üretir (`data/inbox/`'a stereo WAV yazar) ve
sistemin bunları "bekliyor" durumunda alması için bırakır.

**Yapmaz:** Puanlama, transkript, alarm ÜRETMEZ. Bunları siz Yönetim →
İşleme ekranından "İşlemeyi başlat" diyerek çalıştırırsınız — ürünün gerçek
akışını, kısayol olmadan görürsünüz.

## Neden ses üretiliyor da doğrudan DB'ye yazılmıyor?

Doğrudan DB'ye puanlı çağrı yazmak (satış demosunun yaptığı) ürünü **anlatır**
ama **göstermez**. Ses dosyası bırakmak, STT'den puanlamaya kadar bütün hattın
gerçekten çalıştığını kanıtlar. Bir demo, en çok "bu gerçekten çalışıyor mu?"
sorusuna cevap verdiğinde işe yarar.

## Sesler

Temsilci cinsiyeti kadrodan, müşterininki metindeki hitaptan ("Fatma Hanım")
çıkarılır — ses her zaman metinle tutarlıdır. 8 kHz **stereo**: SOL kanal
müşteri, SAĞ kanal temsilci. Bu, konuşmacı ayrımını (diarization) bedavaya
getirir; mono kayıtta HF_TOKEN'lı pyannote gerekir.

Kullanım:
    python scripts/seed_demo_calls.py                 # data/inbox'a yazar
    python scripts/seed_demo_calls.py --temizle       # once mevcut demo sesleri siler
    python scripts/seed_demo_calls.py --tts-engine piper   # cevrimdisi
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

KOK = Path(__file__).resolve().parent
sys.path.insert(0, str(KOK))

from demo_dialogs import DEMO_CALLS, dagilim  # noqa: E402
from generate_demo import (  # noqa: E402
    FEMALE_AGENTS,
    build_stereo_call,
    customer_gender,
    write_wav,
)
from tts_engines import make_engine  # noqa: E402

VERI = KOK.parent / "data"
INBOX = VERI / "inbox"
SESLER = VERI / "voices"        # piper modeli (cevrimdisi seslendirme)
TTS_ONBELLEK = VERI / "tts_cache"  # edge-tts parca onbellegi


def _cinsiyetler(d: dict, rng: random.Random) -> dict[str, str]:
    """Temsilci kadrodan, musteri metindeki hitaptan.

    `customer_gender` generate_demo'da zaten bu is icin yazilmis ve gerekcesi
    orada belgeli: musteriyi "temsilcinin ziddi" yapmak, 12 cagrinin 7'sinde
    sesi metinle celiskiye dusurmustu ("Fatma Hanim" erkek sesiyle konusuyordu).
    Kendi surumumu yazmak yerine onu kullaniyorum.
    """
    t = "kadin" if d["agent"] in FEMALE_AGENTS else "erkek"
    return {"t": t, "m": customer_gender(d["turns"], rng)}


def uret(motor_adi: str, temizle: bool) -> int:
    INBOX.mkdir(parents=True, exist_ok=True)

    if temizle:
        silinen = 0
        for p in INBOX.glob("demo-*.wav"):
            p.unlink()
            silinen += 1
        if silinen:
            print(f"  {silinen} eski demo sesi silindi")

    synth = make_engine(motor_adi, SESLER, TTS_ONBELLEK)
    rng = random.Random(20260810)  # deterministik: ayni kurulum ayni sesi uretir

    yazilan = 0
    for i, d in enumerate(DEMO_CALLS, 1):
        # Adlandirma kurali MEVCUT olani izler: ingest, temsilci adini ilk
        # "_" oncesinden okur (`parse_agent_from_filename`). Kendi kuralimi
        # uydurup cozumleyiciyi degistirmek yerine calisan kurala uyuyorum —
        # aksi halde temsilci sutunu bos kalir.
        # "demo-" oneki senaryo adinda durur; is_demo tespiti onu arar.
        ad = f"{d['agent']}_demo-{d['id']}.wav"
        hedef = INBOX / ad
        if hedef.exists():
            print(f"  [{i:2}/20] {d['id']:<28} zaten var, atlandi")
            yazilan += 1
            continue

        try:
            stereo = build_stereo_call(
                turns=d["turns"],
                synth=synth,
                genders=_cinsiyetler(d, rng),
                speakers={"t": d["agent"], "m": f"cust-{i}"},
                rng=rng,
            )
            write_wav(hedef, stereo)
            sn = len(stereo) / 8000
            print(f"  [{i:2}/20] {d['id']:<28} {d['bucket']:<12} {sn:5.1f} sn")
            yazilan += 1
        except Exception as exc:  # noqa: BLE001
            print(f"  [{i:2}/20] {d['id']:<28} HATA: {str(exc)[:70]}")

    return yazilan


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tts-engine", default="auto",
                    help="auto | edge | piper — piper cevrimdisi calisir")
    ap.add_argument("--temizle", action="store_true",
                    help="Once data/inbox icindeki demo-*.wav dosyalarini sil")
    args = ap.parse_args()

    print()
    print("=" * 64)
    print("ORNEK CAGRILAR — ses uretimi")
    print("=" * 64)
    print(f"  dagilim: {dagilim()}")
    print(f"  hedef  : {INBOX}")
    print("-" * 64)

    n = uret(args.tts_engine, args.temizle)

    print("-" * 64)
    print(f"  {n}/20 ses hazir")
    print()
    print("  Sonraki adim: servisler ayaktayken watcher bu dosyalari alir ve")
    print("  cagrilari BEKLIYOR durumunda olusturur. Puanlama BASLAMAZ —")
    print("  Yonetim > Isleme ekranindan 'Islemeyi baslat' demeniz gerekir.")
    print()
    return 0 if n == 20 else 1


if __name__ == "__main__":
    raise SystemExit(main())
