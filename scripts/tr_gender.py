"""Turkce ad -> cinsiyet cikarimi (demo seslendirmesi icin).

Neden gerekli?
--------------
Demo diyaloglarinda musteriye metin icinde "Fatma Hanim", "Mehmet Bey" diye
hitap ediliyor. Onceki surumde musteri sesi "temsilcinin ZITTI" kuralina gore
atandigi icin 12 cagrinin 7'sinde ses hitapla CELISIYORDU (ornegin "Fatma
Hanim" erkek sesiyle konusuyordu). Bu modul konusmacinin cinsiyetini metnin
kendisinden cikararak o hatayi ortadan kaldirir.

Sinyal onceligi (guclu -> zayif):
    1. Hitap: "... Bey" / "... Hanim"      — en guvenilir, metnin acik ifadesi
    2. Ad sozlugu: "ayse.yilmaz" -> ayse   — yaygin Turkce adlar
    3. Belirsiz -> None (cagiran karar verir)

KAPSAM UYARISI: burasi YALNIZCA sentetik demo verisi uretmek icindir. Gercek
cagri kaydindan/sesten cinsiyet TAHMINI YAPILMAZ; boyle bir cikarim hem hatali
hem de adalet acisindan sakincali olurdu. Sistemde sesten cinsiyet tahmini
yoktur ve eklenmemelidir.
"""

from __future__ import annotations

import re
import unicodedata

__all__ = ["gender_from_name", "gender_from_honorific", "infer_speaker_gender",
           "FEMALE_NAMES", "MALE_NAMES"]

FEMALE_NAMES = {
    "ayse", "fatma", "emine", "hatice", "zeynep", "elif", "meryem", "sultan",
    "zehra", "hanife", "havva", "esra", "merve", "busra", "seda", "selin",
    "gizem", "pelin", "deniz", "ozlem", "hulya", "sevgi", "aylin", "burcu",
    "ceren", "damla", "derya", "dilek", "ebru", "eda", "ecem", "figen",
    "filiz", "gamze", "gul", "gulsen", "hande", "ilknur", "irem", "kubra",
    "leyla", "melek", "melis", "nazli", "nesrin", "nilufer", "nur", "nurcan",
    "pinar", "rabia", "sibel", "simge", "sevda", "sena", "tugba", "tuba",
    "yasemin", "yildiz", "ayten", "aysegul", "banu", "bahar", "basak",
    "belgin", "berna", "betul", "beyza", "bilge", "canan", "cansu", "cigdem",
    "duygu", "elmas", "eylul", "gonca", "gulay", "hilal", "ilayda", "ipek",
    "kader", "kevser", "lale", "mine", "muge", "neslihan", "nihan", "nilay",
    "oznur", "perihan", "reyhan", "saadet", "sedef", "sefika", "semra",
    "senay", "serpil", "sevil", "sevim", "sila", "songul", "sule", "tulay",
    "ummuhan", "yagmur", "zerrin", "zuhal", "asli", "aysel", "arzu", "aycan",
    "bengu", "buse", "ceyda", "defne", "dilara", "ela", "esin", "eylem",
    "fadime", "feride", "gulcan", "gulden", "gulhan", "handan", "hicran",
    "kumru", "melda", "nagehan", "nazan", "nazmiye",
    "nesibe", "nevin", "nuray", "oya", "ozge", "rukiye", "sabriye", "sanem",
    "sare", "sema", "sevinc", "sinem", "suheyla", "tugce", "ulku",
    "vildan", "yeliz", "yesim", "zeliha", "zubeyde",
}

MALE_NAMES = {
    "mehmet", "mustafa", "ahmet", "ali", "huseyin", "hasan", "ibrahim",
    "ismail", "osman", "yusuf", "murat", "omer", "ramazan", "erdal", "salih",
    "abdullah", "yasar", "recep", "adem", "halil", "bekir", "riza", "suleyman",
    "kemal", "emre", "burak", "caner", "okan", "serkan", "kerem", "orhan",
    "engin", "ergun", "erol", "ertan", "fatih", "ferhat", "gokhan", "gurkan",
    "hakan", "halim", "harun", "ilhan", "ismet", "kadir", "levent", "mahmut",
    "melih", "metin", "muhammed", "murat", "necati", "nihat", "nuri", "oguz",
    "onur", "ozan", "polat", "sedat", "selcuk", "selim", "sinan", "tamer",
    "tarik", "taner", "tolga", "tuncay", "turgut", "ufuk", "ugur", "umit",
    "veli", "volkan", "yavuz", "yilmaz", "zafer", "zeki", "alper", "arda",
    "baris", "batuhan", "berk", "berkay", "bulent", "cem", "cenk", "cihan",
    "davut", "dogan", "efe", "ekrem", "emin", "enes", "eren", "ersin",
    "faruk", "furkan", "galip", "hamza", "idris", "ilker", "kaan", "kayhan",
    "koray", "mert", "muhsin", "mucahit", "nedim", "nurettin", "okay",
    "oktay", "olcay", "onder", "rahmi", "rasim", "sabri", "sami", "savas",
    "seref", "serhat", "sertac", "sevket", "soner", "suat", "sukru", "talip",
    "tayfun", "temel", "tevfik", "tuncer", "vedat", "yakup", "yalcin",
    "yunus", "yusuf", "zekeriya", "aykut", "cagri", "deniz", "hikmet",
}

# Turkce'de gercekten iki cinsiyette de kullanilan adlar. Bunlar icin sozluk
# sinyali GECERSIZ sayilir: cagiran ya hitaptan karar verir ya da acik roster
# kullanir. Listeler arasi kazara olusan kesisim de (yazim hatasi olabilir)
# ayni sekilde belirsiz kabul edilir — sessizce yanlis cinsiyet vermektense
# karari yukari tasimak dogrusu.
_EXPLICIT_UNISEX = {
    "deniz", "ozgur", "safak", "evren", "cemre", "toprak", "ulas", "umut",
    "aytac", "sezin", "yucel", "bilge", "nur", "sevgi", "cagri", "ilkay",
    "olcay", "kader", "gul",
}
UNISEX_NAMES = _EXPLICIT_UNISEX | (FEMALE_NAMES & MALE_NAMES)


def _normalize(text: str) -> str:
    """Turkce karakterleri ASCII'ye indirger, kucuk harfe cevirir.

    Not: Python'un lower()'i 'I' -> 'i' yapar (Turkce'de 'ı' olmali) ama
    ASCII katlamasi zaten ikisini de 'i' yaptigi icin sonuc dogru cikar.
    """
    text = text.replace("ı", "i").replace("I", "i").replace("İ", "i")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text.lower().strip()


def gender_from_name(name: str) -> str | None:
    """'ayse.yilmaz' / 'Ayse Yilmaz' / 'Ayşe' -> 'kadin' | 'erkek' | None."""
    if not name:
        return None
    first = re.split(r"[.\s_-]+", name.strip())[0]
    key = _normalize(first)
    if not key or key in UNISEX_NAMES:
        return None
    if key in FEMALE_NAMES:
        return "kadin"
    if key in MALE_NAMES:
        return "erkek"
    return None


_HONORIFIC = re.compile(r"\b([A-Za-zÇĞİÖŞÜçğıöşü]{2,})\s+(Bey|Hanım|Hanim)\b")


def gender_from_honorific(text: str) -> str | None:
    """Metindeki ilk 'X Bey' / 'X Hanım' hitabindan cinsiyet cikarir."""
    m = _HONORIFIC.search(text or "")
    if not m:
        return None
    return "erkek" if _normalize(m.group(2)) == "bey" else "kadin"


def infer_speaker_gender(
    text: str = "", name: str = "", default: str | None = None
) -> str | None:
    """Hitap > ad sozlugu > default sirasiyla cinsiyet belirler."""
    return (
        gender_from_honorific(text)
        or gender_from_name(name)
        or default
    )
