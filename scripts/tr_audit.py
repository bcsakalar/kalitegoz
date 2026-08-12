"""FAZ 6 — Türkçe karakter ve jargon denetimi.

## Neden bir betik?

B15/B16/B17 tek seferlik bir düzeltme değil, **sürekli bir kural**: yeni yazılan
her kullanıcı metni Türkçe karakter taşımalı ve geliştirici jargonu içermemeli.
Elle gözden geçirmek bu kuralı ilk hafta unutturur. Bu yüzden denetim
otomatikleştirildi ve CI'a bağlandı.

## Ne denetler

1. **ASCII'ye düşürülmüş Türkçe** — "Acilis", "Kapanis", "Dogrulama" gibi
   kelimeler kullanıcıya gösterilen metinlerde geçemez.
2. **Geliştirici jargonu** — `assigned`, `in_review`, `bare_name`, `zero=`,
   `yasak_vaat` gibi sistem içi kimlikler arayüze sızamaz.

## Neden kod yorumları hariç?

Kod yorumları ve değişken adları geliştiriciye aittir; onların ASCII olması
sorun değil (hatta kaynak kodda tutarlılık için tercih edilir). Denetim
yalnızca **kullanıcıya gösterilen** metinleri hedefler: i18n sözlükleri,
JSX metin düğümleri, DB'deki kriter adları.

Kullanım:
    python scripts/tr_audit.py            # denetle, ihlal varsa 1 don
    python scripts/tr_audit.py --fix-db   # DB'deki kriter adlarini duzelt
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# ASCII'ye dusurulmus Turkce kelimeler -> dogrusu.
# Yalnizca KULLANICIYA GORUNEN metinlerde aranir.
ASCII_TR = {
    "Acilis": "Açılış",
    "Kapanis": "Kapanış",
    "Bilgi Dogrulugu": "Bilgi Doğruluğu",
    "Kimlik Dogrulama": "Kimlik Doğrulama",
    "Cozum / Yonlendirme": "Çözüm / Yönlendirme",
    "Yasakli Kelime / Uslup": "Yasaklı Kelime / Üslup",
    "Ihtiyac Analizi": "İhtiyaç Analizi",
    "Iletisim Kalitesi": "İletişim Kalitesi",
    "Musteri Odagi": "Müşteri Odağı",
    "Iletisim": "İletişim",
    "Sifirlayici": "Sıfırlayıcı",
    "Gorusme": "Görüşme",
    "Temsilci agir": "Temsilci ağır",
}


# Diakritigi soyulmus TURKCE KELIMELER.
#
# ASCII_TR (yukarida) rubrik kriter ADLARI icin yazilmis, 13 maddelik bir
# ifade listesi. Genel bir dedektor degil ve oyle davranmiyor: "Hizli /
# hafif — dusuk VRAM" gibi bir aciklama o listeden gecip gidiyordu.
#
# Bu liste KELIME duzeyinde calisir ve kelime siniriyla eslesir; boylece
# Ingilizce metnin icinde tesadufen gecen harf dizileri yakalanmaz.
# Kapsayici degil, YAYGIN olani yakalar — eksigi cikarsa buraya eklenir.
ASCII_TR_KELIME = {
    "hizli": "hızlı", "dusuk": "düşük", "yuksek": "yüksek", "guclu": "güçlü",
    "cok": "çok", "saglam": "sağlam", "gorsel": "görsel", "dokuman": "doküman",
    "Turkce": "Türkçe", "Ingilizce": "İngilizce", "agirlikli": "ağırlıklı",
    "varsayilan": "varsayılan", "onerilen": "önerilen", "sigar": "sığar",
    "kullanici": "kullanıcı", "baglanti": "bağlantı", "gecersiz": "geçersiz",
    "yanlis": "yanlış", "olcum": "ölçüm", "degistir": "değiştir",
    "secim": "seçim", "cagri": "çağrı", "puanlama": None, "gunluk": "günlük",
    "acik": "açık", "kapali": "kapalı", "baslat": "başlat", "durdur": None,
    "sifirla": "sıfırla", "gecmis": "geçmiş", "ayrinti": "ayrıntı",
    "aciklama": "açıklama", "ozet": "özet", "gorusme": "görüşme",
    "musteri": "müşteri", "temsilci": None, "kalitesi": None,
}
# Degeri None olanlar zaten diakritiksiz dogru yazilir — listede yer
# tutuyorlar ki biri yanlislikla eklemesin.
ASCII_TR_KELIME = {k: v for k, v in ASCII_TR_KELIME.items() if v}

# Gelistirici jargonu -> kullaniciya gosterilecek karsiligi (bos = hic gosterilmez)
JARGON = {
    "assigned": "Atandı",
    "in_review": "İnceleniyor",
    "completed": "Tamamlandı",
    "bare_name": "",
    "zero=": "",
    "yasak_vaat": "Yasak vaat",
    "insufficient_evidence": "Yetersiz kanıt",
    "not_met": "Karşılanmadı",
    "partially_met": "Kısmen karşılandı",
}

# Bu dosyalarda kullaniciya gorunen metin YOK (kod/test/veri)
SKIP_DIRS = {
    "node_modules", ".next", ".git", ".venv", "__pycache__", "data",
    "docs", ".claude", "scripts",
}


def _tr_sozlugu() -> dict:
    """frontend/lib/i18n.ts icindeki TR sozlugunun deger kismini cikar."""
    p = ROOT / "frontend" / "lib" / "i18n.ts"
    if not p.exists():
        return {}
    text = p.read_text(encoding="utf-8")
    # "anahtar": "deger" ciftlerini yakala (TR bolumu dosyanin ilk yarisi)
    yarim = text[: len(text) // 2]
    return dict(re.findall(r'"([\w.\-]+)"\s*:\s*"((?:[^"\\]|\\.)*)"', yarim))


def denetle_i18n() -> list[str]:
    ihlaller = []
    for anahtar, deger in _tr_sozlugu().items():
        for ascii_hali, dogrusu in ASCII_TR.items():
            if ascii_hali in deger:
                ihlaller.append(
                    f"i18n.ts [{anahtar}] ASCII Turkce: {ascii_hali!r} -> {dogrusu!r}"
                )
    return ihlaller


def denetle_jsx() -> list[str]:
    """JSX metin dugumlerinde jargon ara."""
    ihlaller = []
    fe = ROOT / "frontend"
    if not fe.exists():
        return ihlaller
    for p in fe.rglob("*.tsx"):
        if any(d in p.parts for d in SKIP_DIRS):
            continue
        for i, satir in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            kirpik = satir.strip()
            if kirpik.startswith("//") or kirpik.startswith("*"):
                continue
            # >metin< bicimindeki JSX metin dugumleri
            for metin in re.findall(r">\s*([^<>{}\n]{3,})\s*<", satir):
                for jargon in JARGON:
                    if re.search(rf"\b{re.escape(jargon)}\b", metin):
                        ihlaller.append(
                            f"{p.relative_to(ROOT)}:{i} arayuzde jargon: {jargon!r}"
                        )
    return ihlaller


def denetle_db_kriterleri() -> list[str]:
    """seed.py'deki varsayilan kriter adlarini denetle."""
    ihlaller = []
    p = ROOT / "backend" / "app" / "seed.py"
    if not p.exists():
        return ihlaller
    text = p.read_text(encoding="utf-8")
    for ad in re.findall(r'"name":\s*"([^"]+)"', text):
        for ascii_hali, dogrusu in ASCII_TR.items():
            if ascii_hali == ad or ascii_hali in ad:
                ihlaller.append(f"seed.py kriter adi ASCII: {ad!r} -> {dogrusu!r}")
                break
    return ihlaller


def denetle_backend_metinleri() -> list[str]:
    """Sunucudan gelen KULLANICIYA GORUNEN Turkce metinde ASCII var mi?

    ## Neden bu kontrol sonradan eklendi

    Denetim yalnizca `i18n.ts`'i tariyordu. Ama panelde gorunen her metin
    orada degil: model katalogu aciklamalari, hata mesajlari ve durum
    metinleri sunucudan geliyor ve arayuz onlari **oldugu gibi basiyor**.

    Sonuc: "Turkce guclu, hizli" ve "dusuk VRAM" gibi diakritigi soyulmus
    on aciklama aylarca panelde durdu ve denetim her kosuda YESIL dedi.
    Kural yaziliydi (CLAUDE.md), denetim uyguladigini soyluyordu, kapsami
    disindaydi.

    ## Kapsam

    Goruntuleme alani oldugu ADINDAN belli olan sozluk anahtarlari taranir:
    `desc`, `label`, `aciklama`, `mesaj`, `baslik`, `title`, `ozet`.
    Docstring ve log mesajlari KAPSAM DISI — onlar kullaniciya gitmiyor ve
    bu depoda bilincli olarak ASCII yaziliyor.
    """
    ihlaller = []
    be = ROOT / "backend" / "app"
    if not be.exists():
        return ihlaller
    alan = re.compile(
        r'"(desc|label|aciklama|mesaj|baslik|title|ozet)"\s*:\s*"((?:[^"\\]|\\.)*)"')
    for p in be.rglob("*.py"):
        if any(d in p.parts for d in SKIP_DIRS):
            continue
        for i, satir in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if satir.strip().startswith("#"):
                continue
            for _, deger in alan.findall(satir):
                for ascii_hali, dogrusu in ASCII_TR_KELIME.items():
                    if re.search(rf"\b{re.escape(ascii_hali)}\b", deger):
                        ihlaller.append(
                            f"{p.relative_to(ROOT)}:{i} ASCII Turkce: "
                            f"{ascii_hali!r} -> {dogrusu!r}  ({deger[:50]})")
    return ihlaller


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    gruplar = {
        "i18n sozlugu": denetle_i18n(),
        "arayuz jargonu": denetle_jsx(),
        "rubrik kriter adlari": denetle_db_kriterleri(),
        "sunucu metinleri": denetle_backend_metinleri(),
    }
    toplam = sum(len(v) for v in gruplar.values())

    if args.json:
        print(json.dumps({"toplam": toplam, "gruplar": gruplar}, ensure_ascii=False, indent=2))
        return 0 if toplam == 0 else 1

    print("=" * 62)
    print("TURKCE VE JARGON DENETIMI")
    print("=" * 62)
    for ad, ihlaller in gruplar.items():
        durum = "TEMIZ" if not ihlaller else f"{len(ihlaller)} IHLAL"
        print(f"  {ad:<28} {durum}")
        for x in ihlaller[:12]:
            print(f"      - {x}")
        if len(ihlaller) > 12:
            print(f"      … {len(ihlaller) - 12} tane daha")
    print("-" * 62)
    print(f"  TOPLAM: {toplam}")
    return 0 if toplam == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
