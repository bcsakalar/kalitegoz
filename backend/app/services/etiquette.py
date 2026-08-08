"""Hitap ve nezaket kurallari (Turkce'ye ozgu).

Cagri merkezinde Turkce hitap kurallari nettir ve ihlali musteri tarafindan
ANINDA hissedilir:
- Musteriye "sen" denmez, DAIMA "siz" (2. tekil sahis eki ihlali).
- Musteriye adiyla hitap ediliyorsa "Bey/Hanim" eklenir ("Ahmet" degil "Ahmet Bey").
- Samimiyet/argo ("canim", "kardesim", "abi") profesyonel degildir.
- Nezaket kaliplari ("rica ederim", "tesekkur ederim", "buyurun") beklenir.

Neden LLM degil kural motoru: bu kurallar deterministik ve dilbilgiseldir; LLM'e
sormak hem yavas hem tutarsizdir (ayni cagriyi iki kez farkli puanlayabilir).
Kural motoru kesin ve aciklanabilir sonuc verir; LLM'e ise BULGU olarak iletilir.

Not: 2. tekil sahis tespiti Turkce'nin cekim zenginligi nedeniyle tam degildir;
yuksek kesinlikli kaliplar secilmistir (yanlis pozitif, kacirmaya tercih edilir —
temsilciyi haksiz yere suclamamak icin).
"""

import re
import unicodedata
from dataclasses import dataclass


def _norm(text: str) -> str:
    text = text.lower()
    text = text.translate(str.maketrans("ıİişŞğĞüÜöÖçÇ", "iiissgguuoocc"))
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c))


# --- 2. tekil sahis (sen) kaliplari: yuksek kesinlikli, yaygin fiiller ---
# "yapabilirsin", "biliyorsun", "gonderdin", "sen" (bagimsiz zamir)
_INFORMAL_PATTERNS = [
    r"\bsen\b", r"\bsana\b", r"\bseni\b", r"\bsenin\b", r"\bsende\b", r"\bsenden\b",
    r"\w+(abilirsin|ebilirsin)\b",
    r"\w+(iyorsun|iyorsun|uyorsun|uyorsun|yorsun)\b",
    r"\w+(malisin|melisin)\b",
    r"\w+(acaksin|ecekisn|eceksin)\b",
    r"\w+(din|tin|dun|tun)\b(?=\s|$|[.,!?])",  # gonderdin/aldin (zayif, asagida filtreli)
]
# Yukaridaki son kalip yanlis pozitif uretebilir (ornek: "benim", "yarin").
# Bu yuzden yalnizca bilinen fiil koklerinde kabul edilir.
_INFORMAL_VERB_STEMS = {
    "gonderdin", "aldin", "yaptin", "dedin", "gordun", "buldun", "verdin",
    "geldin", "gittin", "bildin", "actin", "kapattin", "odedin",
}

_INFORMAL_RE = re.compile("|".join(_INFORMAL_PATTERNS[:-1]))

# --- Argo / asiri samimiyet ---
_SLANG = ["canim", "kardesim", "abi", "abla", "kanka", "dostum", "yavrum", "guzelim"]

# --- Nezaket kaliplari (varligi olumlu) ---
_COURTESY = [
    "rica ederim", "tesekkur ed", "buyurun", "memnuniyetle", "elbette",
    "tabii ki", "yardimci olabilir", "ozur dilerim", "anlayisiniz icin",
]

# --- Hitap ekleri ---
_HONORIFIC_RE = re.compile(r"\b(bey|hanim|beyefendi|hanimefendi)\b")
# "Ahmet Bey" gibi: buyuk harfle baslayan isim + Bey/Hanim
_NAME_WITH_HONORIFIC = re.compile(
    r"\b[A-ZÇĞİÖŞÜ][a-zçğıöşü]{2,}\s+(Bey|Hanım|Beyefendi|Hanımefendi)\b"
)
# Buyuk harfle baslayan isim, ARDINDAN Bey/Hanim GELMEYEN (cumle basi haric)
_BARE_NAME = re.compile(
    r"(?<![.!?]\s)(?<!^)\b([A-ZÇĞİÖŞÜ][a-zçğıöşü]{2,})\b(?!\s+(Bey|Hanım|Beyefendi|Hanımefendi))"
)


@dataclass
class EtiquetteFinding:
    kind: str        # informal_sen | slang | bare_name
    severity: str    # dusuk | orta | yuksek
    evidence: str
    ts_sec: float | None
    detail: str = ""


def _has_informal(text_norm: str) -> bool:
    if _INFORMAL_RE.search(text_norm):
        return True
    return any(w in text_norm.split() for w in _INFORMAL_VERB_STEMS)


def analyze(segments: list) -> dict:
    """Temsilcinin hitap/nezaket kullanimini olc.

    segments: Segment ORM nesneleri veya {speaker, text, start_sec} dict'leri.
    Doner: {bulgular: [...], nezaket_sayisi, hitap_sayisi, sen_kullanimi, argo_kullanimi}
    """
    findings: list[EtiquetteFinding] = []
    courtesy = 0
    honorific = 0

    for seg in segments:
        speaker = getattr(seg, "speaker", None) or (seg.get("speaker") if isinstance(seg, dict) else None)
        if speaker != "temsilci":
            continue
        raw = getattr(seg, "text", None) or (seg.get("text", "") if isinstance(seg, dict) else "")
        ts = getattr(seg, "start_sec", None)
        if ts is None and isinstance(seg, dict):
            ts = seg.get("start_sec", seg.get("start"))
        norm = _norm(raw)

        # Nezaket kaliplari
        courtesy += sum(1 for c in _COURTESY if c in norm)
        honorific += len(_HONORIFIC_RE.findall(norm))

        # "sen" kullanimi — musteriye saygisizlik
        if _has_informal(norm):
            findings.append(EtiquetteFinding(
                kind="informal_sen", severity="yuksek", evidence=raw.strip(), ts_sec=ts,
                detail="Musteriye 2. tekil sahis ('sen') ile hitap edilmis; 'siz' kullanilmali.",
            ))

        # Argo / asiri samimiyet
        for w in _SLANG:
            if re.search(rf"\b{w}\b", norm):
                findings.append(EtiquetteFinding(
                    kind="slang", severity="orta", evidence=raw.strip(), ts_sec=ts,
                    detail=f"Asiri samimi/argo hitap: '{w}'.",
                ))
                break

        # Bey/Hanim'siz isim kullanimi
        if _NAME_WITH_HONORIFIC.search(raw):
            pass  # dogru kullanim
        else:
            bare = _BARE_NAME.search(raw)
            if bare and not _HONORIFIC_RE.search(norm):
                findings.append(EtiquetteFinding(
                    kind="bare_name", severity="dusuk", evidence=raw.strip(), ts_sec=ts,
                    detail=f"'{bare.group(1)}' ismine Bey/Hanim eklenmemis olabilir.",
                ))

    return {
        "bulgular": [
            {"tur": f.kind, "onem": f.severity, "kanit": f.evidence,
             "zaman": f.ts_sec, "aciklama": f.detail}
            for f in findings
        ],
        "nezaket_sayisi": courtesy,
        "hitap_sayisi": honorific,
        "sen_kullanimi": sum(1 for f in findings if f.kind == "informal_sen"),
        "argo_kullanimi": sum(1 for f in findings if f.kind == "slang"),
    }


def hint(result: dict) -> str:
    """Bulgulari LLM prompt'una nesnel ipucu olarak cevir."""
    if not result:
        return ""
    lines = []
    if result.get("sen_kullanimi"):
        lines.append(
            f"- Temsilci {result['sen_kullanimi']} kez musteriye 'SEN' diye hitap etti "
            f"(Turkce cagri merkezinde ciddi nezaket ihlali; 'siz' kullanilmali)"
        )
    if result.get("argo_kullanimi"):
        lines.append(f"- Temsilci {result['argo_kullanimi']} kez argo/asiri samimi hitap kullandi")
    if result.get("nezaket_sayisi"):
        lines.append(f"- Nezaket kalibi kullanimi: {result['nezaket_sayisi']} kez (olumlu)")
    if result.get("hitap_sayisi"):
        lines.append(f"- 'Bey/Hanim' hitabi: {result['hitap_sayisi']} kez (olumlu)")
    if not lines:
        return ""
    return (
        "\n### Hitap & nezaket (kural motoru — kesin tespit):\n"
        + "\n".join(lines)
        + "\nBunlari 'Iletisim Kalitesi' ve 'Yasakli Kelime / Uslup' kriterlerinde dikkate al.\n"
    )
