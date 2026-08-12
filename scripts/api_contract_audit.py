"""API sözleşme denetimi — frontend'in beklediği şekil ile API'nin döndürdüğü uyuşuyor mu?

## Neden bu betik var

Analitik sayfası `d.map is not a function` ile çöktü. Sebep:

    backend  ->  {"noktalar": [...], "grafik_cizilebilir": false, ...}
    frontend ->  request<TimeseriesPoint[]>(...)  ardından  ts.map(...)

Backend "dürüst istatistik" sarmalayıcısı eklerken düz diziyi nesneye
çevirmiş, frontend güncellenmemişti.

**TypeScript bunu yakalayamaz.** `request<T>()` gelen JSON'u doğrulamadan
`T` diye kabul eder — yani tip bir *iddia*, kontrol değil. Derleme temiz
geçer, sayfa çalışma anında çöker.

Bu B36 ile aynı sınıf: **üretici biçim değiştirdi, tüketici güncellenmedi.**

## Ne denetler

`frontend/lib/api.ts` içindeki her GET çağrısı için:

1. İstemcinin beyan ettiği tip dizi mi (`T[]`) yoksa nesne mi?
2. API gerçekte ne döndürüyor?
3. İkisi uyuşuyor mu?

Boş veriyle koşulması önemlidir: çoğu uyuşmazlık ancak sistem boşken
görünür, çünkü doluyken de yanlış ama "çalışıyor gibi" görünebilir.

Kullanım:
    python scripts/api_contract_audit.py
    python scripts/api_contract_audit.py --api http://localhost:8000
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

KOK = Path(__file__).resolve().parents[1]
API_TS = KOK / "frontend" / "lib" / "api.ts"

# request<TIP>(`/yol?...`)  — sablon literali ya da duz string.
# Yolun ARDINDAN gelen karakteri de yakalariz: ")" ise GET, "," ise
# ikinci argüman (json/method) var demektir ve GET DEGILDIR.
#
# Bu ayrim sart: ilk surumde POST cagrilari da denetleniyordu ve 12 yanlis
# pozitif uretti ("request<Team>('/admin/teams', json(body))" bir POST'tur;
# ayni yolun GET'i dizi doner, uyusmazlik degil). Yanlis pozitif ureten bir
# denetim kisa surede gormezden gelinir.
_CAGRI = re.compile(
    r"request<([^>]+)>\(\s*[`\"']([^`\"']+)[`\"']\s*(.)",
)

# Yol icindeki ${...} yer tutucularini ornek degerle doldur
_YER_TUTUCU = re.compile(r"\$\{([^}]+)\}")

# Bu yollar denetlenmez: yan etkili (POST benzeri GET yok), indirme, WS,
# ya da yol parametresi olmadan anlamsiz olanlar.
ATLA = (
    "/auth/", "/events", "/ws", "/export", "/download", "/audio", "/pdf",
    "/report", "/assist/", "/ingest",
)


# Yer tutucu adina gore makul ornek deger. Rastgele "1" koymak,
# pattern dogrulamasi olan parametrelerde 422 uretiyor ve uc denetlenemiyordu
# (timeseries tam boyle atlanmisti — asil hatanin oldugu uc).
_ORNEKLER = {
    "metric": "score", "bucket": "day", "dimension": "team",
    "days": "30", "gunler": "30", "period": "30", "limit": "10",
    "q": "test", "query": "test", "status": "", "role": "",
}


def _ornek_deger(yol: str) -> str:
    def _degistir(m: re.Match) -> str:
        ifade = m.group(1).strip()
        for anahtar, deger in _ORNEKLER.items():
            if anahtar in ifade.lower():
                return deger
        return "1"
    return _YER_TUTUCU.sub(_degistir, yol)


def istemci_cagrilari() -> list[tuple[str, str]]:
    """(beyan_edilen_tip, yol) ciftleri."""
    if not API_TS.exists():
        return []
    metin = API_TS.read_text(encoding="utf-8")
    out = []
    for tip, yol, sonraki in _CAGRI.findall(metin):
        # Yolun ardindan virgul geliyorsa ikinci argüman var -> POST/PUT/DELETE
        if sonraki.strip() == ",":
            continue
        yol = yol.strip()
        if not yol.startswith("/"):
            continue
        if any(a in yol for a in ATLA):
            continue
        out.append((tip.strip(), _ornek_deger(yol)))
    # Tekrarlari ele
    return sorted(set(out), key=lambda x: x[1])


def _istek(url: str, token: str) -> tuple[int, object]:
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception:  # noqa: BLE001 — ag/parse hatasi denetimi durdurmasin
        return 0, None


def giris(api: str) -> str:
    env = (KOK / ".env").read_text(encoding="utf-8")
    pw = re.search(r"^ADMIN_PASSWORD=(.*)$", env, re.M)
    if not pw:
        raise SystemExit("HATA: .env icinde ADMIN_PASSWORD yok")
    govde = json.dumps({
        "email": "admin@demo.local",
        "password": pw.group(1).strip(),
        "tenant_slug": "demo",
    }).encode()
    req = urllib.request.Request(
        f"{api}/api/v1/auth/login", data=govde,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode("utf-8"))["access_token"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://localhost:8000")
    args = ap.parse_args()

    cagrilar = istemci_cagrilari()
    if not cagrilar:
        print("api.ts icinde GET cagrisi bulunamadi")
        return 0

    print("=" * 78)
    print("API SOZLESME DENETIMI  (frontend tipi  vs  gercek yanit)")
    print("=" * 78)
    print(f"  denetlenen uc : {len(cagrilar)}")
    print(f"  api           : {args.api}")
    print("-" * 78)

    try:
        token = giris(args.api)
    except Exception as exc:  # noqa: BLE001
        print(f"HATA: giris yapilamadi ({exc}). Servisler ayakta mi?")
        return 1

    uyusmaz, erisilemedi = [], []
    for tip, yol in cagrilar:
        durum, veri = _istek(f"{args.api}/api/v1{yol}", token)
        if durum != 200 or veri is None:
            erisilemedi.append((yol, durum))
            continue

        dizi_bekleniyor = tip.rstrip().endswith("[]") or tip.startswith("Array<")
        dizi_geldi = isinstance(veri, list)
        if dizi_bekleniyor != dizi_geldi:
            uyusmaz.append({
                "yol": yol,
                "beyan": tip,
                "beklenen": "dizi" if dizi_bekleniyor else "nesne",
                "gelen": "dizi" if dizi_geldi else type(veri).__name__,
                "anahtarlar": list(veri)[:6] if isinstance(veri, dict) else [],
            })

    if uyusmaz:
        print(f"  SOZLESME UYUSMAZLIGI: {len(uyusmaz)}\n")
        for u in uyusmaz:
            print(f"  {u['yol']}")
            print(f"      frontend beyani : {u['beyan']}  ({u['beklenen']})")
            print(f"      gercek yanit    : {u['gelen']}")
            if u["anahtarlar"]:
                print(f"      yanit anahtarlari: {u['anahtarlar']}")
            print()
    else:
        print("  Tum uclarda dizi/nesne sozlesmesi UYUMLU.")

    if erisilemedi:
        print(f"\n  (denetlenemedi: {len(erisilemedi)} uc — 200 disi yanit)")
        for yol, durum in erisilemedi[:8]:
            print(f"      {durum or 'baglanamadi'}  {yol}")

    print("-" * 78)
    print(f"  TOPLAM UYUSMAZLIK: {len(uyusmaz)}")
    return 0 if not uyusmaz else 1


if __name__ == "__main__":
    raise SystemExit(main())
