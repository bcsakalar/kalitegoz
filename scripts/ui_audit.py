"""Keskin köşe denetimi — arayüzde hiçbir yerde yuvarlak köşe kalmasın.

## Neden bir betik?

"border-radius her yerde 0" tek seferlik bir düzeltme değil, **sürekli bir
kural**. Bugün temizlenen markup'ta yarın yazılacak bir bileşende `rounded-lg`
yeniden belirir ve kimse fark etmez.

İki katmanlı savunma var:

1. **Tailwind ölçeği tokena bağlı** (`tailwind.config.ts`) — `rounded-*`
   yazılsa bile sonuç `var(--radius)`, yani 0. Kural kodun içinde.
2. **Bu betik** — kuralın *okunabilirliğini* korur. Ölçek doğru olsa bile
   markup'ta `rounded-lg` durması, sonraki geliştiriciye "burada yuvarlak
   köşe var" der. Yanlış bilgi de bir hatadır.

## Ne denetler

| Kontrol | Neden |
|---|---|
| Tailwind `rounded-*` sınıfı | İşlevsiz ama yanıltıcı |
| Inline `borderRadius` (0 dışı) | Token'ı atlar |
| CSS `border-radius` (token dışı) | Tek kaynak kuralını bozar |
| SVG `rx` / `ry` özniteliği | Grafiklerde yuvarlak köşe |
| SVG `strokeLinecap/Linejoin="round"` | Çizgi uçlarında yuvarlaklık |

**Yorum satırları hariç tutulur:** bir yorumda "`rounded-lg` yazsan bile 0
olur" demek ihlal değil, açıklamadır.

Kullanım:
    python scripts/ui_audit.py           # denetle, ihlal varsa 1 don
    python scripts/ui_audit.py --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
FE = ROOT / "frontend"

# Onemli: `\s*` yerine `[ \t]*` + acik negatif bakis kullaniliyor. `\s*` sifir
# genislige geri donebildigi icin "border-radius: var(--radius)" satirini bile
# ihlal sayiyordu (bizzat yasandi).
KONTROLLER: dict[str, re.Pattern] = {
    "Tailwind rounded-* sinifi": re.compile(r'\brounded(?:-[a-z0-9]+)*\b'),
    "inline borderRadius (0 disi)": re.compile(r'borderRadius:[ \t]*(?!0\b)\S'),
    "CSS border-radius (token disi)": re.compile(r'border-radius:[ \t]*(?!var\(--radius\))\S'),
    "SVG rx/ry ozniteligi": re.compile(r'\s(?:rx|ry)=["{]'),
    "SVG yuvarlak uc": re.compile(r'stroke(?:Linecap|Linejoin)="round"'),
}

UZANTILAR = {".tsx", ".ts", ".css"}
ATLA = {"node_modules", ".next", "dist", "build"}

# Kuralin TANIMLANDIGI dosyalar denetimden muaf: tailwind.config.ts icindeki
# `borderRadius` anahtari ihlal degil, tek kaynagin kendisidir. Muafiyet
# dosya+kontrol ciftine baglanir ki genel bir kacamak olusmasin.
MUAFIYET = {
    ("frontend/tailwind.config.ts", "inline borderRadius (0 disi)"),
    ("frontend/app/globals.css", "CSS border-radius (token disi)"),
}


def _yorum_mu(satir: str, css: bool) -> bool:
    """Satir bir yorum mu? Yorumdaki 'rounded' ihlal degil, aciklamadir."""
    k = satir.strip()
    if k.startswith("//") or k.startswith("*") or k.startswith("/*"):
        return True
    # CSS'te cok satirli yorum blogu icindeki duz metin satirlari
    if css and not k.endswith((";", "{", "}")) and ":" not in k:
        return True
    return False


def dosyalar() -> list[Path]:
    if not FE.exists():
        return []
    return sorted(
        p for p in FE.rglob("*")
        if p.suffix in UZANTILAR and not any(d in p.parts for d in ATLA)
    )


def tanimsiz_degiskenler() -> list[str]:
    """globals.css'te TANIMSIZ olan `var(--x)` kullanimlarini bul.

    Neden ayri bir kontrol: tanimsiz bir CSS degiskeni HATA VERMEZ, sadece
    renk hic uygulanmaz. Yani "durum yesil" gostergesi sessizce renksiz kalir
    ve kimse fark etmez. Ilk denetimde 33 boyle kullanim bulundu
    (--status-ok, --status-warn, --series); dogrulari --status-good,
    --status-warning, --series-1 idi.
    """
    css_yolu = FE / "app" / "globals.css"
    if not css_yolu.exists():
        return []
    tanimli = set(re.findall(r"^\s*(--[a-z0-9-]+)\s*:", css_yolu.read_text(encoding="utf-8"), re.M))

    bulgular = []
    for p in dosyalar():
        if p.suffix == ".css":
            continue
        metin = p.read_text(encoding="utf-8")
        # Bilesenin kendi icinde inline tanimladiklari (or. style={{"--pad": ...}})
        yerel = set(re.findall(r'"(--[a-z0-9-]+)"\s*:', metin))
        for i, satir in enumerate(metin.splitlines(), 1):
            for v in re.findall(r"var\((--[a-z0-9-]+)\)", satir):
                if v not in tanimli and v not in yerel:
                    bulgular.append(f"{p.relative_to(ROOT).as_posix()}:{i}  {v}")
    return bulgular


def tanimsiz_renk_siniflari() -> list[str]:
    """Tailwind config'te TANIMLI OLMAYAN ozel renk sinifi kullanimlari.

    Tanimsiz bir Tailwind sinifi hata vermez — sessizce atlanir. `bg-surface2`
    boyleydi: 10 yerde kullaniliyordu ama config'te yoktu, native <select>
    tarayici varsayilanina dusuyor ve KOYU TEMADA BEYAZ KUTU goruntusu
    veriyordu. Gorsel denetimde yakalandi; bu kontrol tekrarini onler.
    """
    cfg_yolu = FE / "tailwind.config.ts"
    if not cfg_yolu.exists():
        return []
    ozel = set(re.findall(r'^\s+"?([a-z0-9-]+)"?:\s*"var\(', cfg_yolu.read_text(encoding="utf-8"), re.M))

    # Tailwind'in kendi renk aileleri + yapisal yardimci sonekleri
    standart = {
        "inherit", "current", "transparent", "black", "white", "slate", "gray",
        "zinc", "neutral", "stone", "red", "orange", "amber", "yellow", "lime",
        "green", "emerald", "teal", "cyan", "sky", "blue", "indigo", "violet",
        "purple", "fuchsia", "pink", "rose",
    }
    yapisal = re.compile(
        r"^(?:\d+|xs|sm|base|lg|xl|\dxl|t|b|l|r|x|y|none|solid|dashed|dotted|"
        r"double|hidden|collapse|separate|clip|cover|contain|auto|fixed|local|"
        r"scroll|repeat|left|right|center|justify|start|end|top|bottom|nowrap|"
        r"wrap|balance|pretty|ellipsis|opacity|offset|width|spacing|indent)(?:-|$)")

    bulgular = []
    for p in dosyalar():
        if p.suffix == ".css":
            continue
        # Renkleri TANIMLAYAN dosyayi sinif KULLANIMI icin taramak anlamsiz:
        # `"hairline-strong": "var(--border-strong)"` satirindaki
        # `border-strong` bir sinif degil, degisken adinin parcasi.
        if p.relative_to(ROOT).as_posix() == "frontend/tailwind.config.ts":
            continue
        for i, satir in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            for m in re.finditer(r"\b(bg|text|border|fill|stroke|ring|divide)-([a-zA-Z][a-zA-Z0-9-]*)\b", satir):
                ad = m.group(2)
                if yapisal.match(ad):
                    continue
                if ad.split("-")[0] in standart or ad in ozel or ad.split("-")[0] in ozel:
                    continue
                bulgular.append(f"{p.relative_to(ROOT).as_posix()}:{i}  {m.group(0)}")
    return bulgular


def denetle() -> dict[str, list[str]]:
    bulgular: dict[str, list[str]] = {ad: [] for ad in KONTROLLER}
    for p in dosyalar():
        css = p.suffix == ".css"
        try:
            satirlar = p.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        icinde_blok_yorum = False
        for i, satir in enumerate(satirlar, 1):
            if css:
                if "/*" in satir and "*/" not in satir:
                    icinde_blok_yorum = True
                elif "*/" in satir:
                    icinde_blok_yorum = False
                    continue
                if icinde_blok_yorum:
                    continue
            if _yorum_mu(satir, css):
                continue
            gorece = p.relative_to(ROOT).as_posix()
            for ad, desen in KONTROLLER.items():
                if (gorece, ad) in MUAFIYET:
                    continue
                if desen.search(satir):
                    bulgular[ad].append(f"{p.relative_to(ROOT).as_posix()}:{i}  {satir.strip()[:70]}")
    bulgular["tanimsiz CSS degiskeni"] = tanimsiz_degiskenler()
    bulgular["tanimsiz Tailwind rengi"] = tanimsiz_renk_siniflari()
    return bulgular


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    bulgular = denetle()
    toplam = sum(len(v) for v in bulgular.values())

    if args.json:
        print(json.dumps({"toplam": toplam, "bulgular": bulgular},
                         ensure_ascii=False, indent=2))
        return 0 if toplam == 0 else 1

    print("=" * 66)
    print("ARAYUZ DENETIMI  (keskin kose + tanimli renk degiskenleri)")
    print("=" * 66)
    print(f"  taranan dosya: {len(dosyalar())}")
    print("-" * 66)
    for ad, liste in bulgular.items():
        durum = "TEMIZ" if not liste else f"{len(liste)} IHLAL"
        print(f"  {ad:<34} {durum}")
        for x in liste[:10]:
            print(f"      - {x}")
        if len(liste) > 10:
            print(f"      … {len(liste) - 10} tane daha")
    print("-" * 66)
    print(f"  TOPLAM: {toplam}")
    if toplam == 0:
        print("\n  Tek kaynak: frontend/app/globals.css  --radius")
        print("  Tailwind olcegi: frontend/tailwind.config.ts  borderRadius")
    return 0 if toplam == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
