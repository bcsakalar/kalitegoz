"""Uyum paketleri: birden fazla regulasyonun yapilandirilabilir kural setleri.

Mevcut sistem KVKK'ya ozel (kriz + aydinlatma). Bu modul onu GENELLESTIRIR:
her paket, cagri transkriptinde ARANMASI GEREKEN ifadeler (zorunlu aciklamalar)
ve BULUNMAMASI gereken ifadeler (yasak) tanimlar. Eksik zorunlu aciklama bir
uyum ihlalidir.

Paketler kod icinde built-in gelir (tenant bunlari acar/kapatir); her paket
Turkce cagri merkezi baglamina gore yazildi. Ileride DB'den yapilandirilabilir
hale getirmek kolay — arayuz ayni JSON'i uretir.

NOT: 'ifade var mi' kontrolu Turkce ek/cekim toleransli olsun diye kok-onek
eslesmesi kullanir (compliance.py'daki mantikla ayni ruh).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..schemas import _fold_tr


@dataclass(frozen=True)
class ComplianceRule:
    key: str
    description: str
    # Zorunlu aciklama: bu kaliplardan EN AZ BIRI temsilci repliginde gecmeli
    required_any: tuple[str, ...] = ()
    # Yasak: bu kaliplardan HERHANGI BIRI gecerse ihlal
    forbidden_any: tuple[str, ...] = ()
    severity: str = "orta"


@dataclass(frozen=True)
class CompliancePack:
    key: str
    name: str
    description: str
    rules: tuple[ComplianceRule, ...] = field(default_factory=tuple)


# --- Built-in paketler ---------------------------------------------------
PACKS: dict[str, CompliancePack] = {
    "kvkk": CompliancePack(
        key="kvkk", name="KVKK (Kisisel Verilerin Korunmasi)",
        description="Aydinlatma ve kayit bildirimi zorunlulugu.",
        rules=(
            ComplianceRule(
                key="kayit_bildirimi",
                description="Gorusmenin kayit altina alindigi bildirilmeli.",
                required_any=("kayit alt", "kayit edil", "kaydedilmekte", "kayit altina"),
                severity="yuksek",
            ),
            ComplianceRule(
                key="aydinlatma",
                description="Kisisel verilerin islendigi/KVKK bildirilmeli.",
                required_any=("kvkk", "kisisel veri", "aydinlatma"),
                severity="yuksek",
            ),
        ),
    ),
    "pci": CompliancePack(
        key="pci", name="PCI-DSS (Kart Guvenligi)",
        description="Kart bilgisi guvenligi: tam kart numarasi sesli istenmemeli.",
        rules=(
            ComplianceRule(
                key="tam_kart_isteme",
                description="Temsilci musteriden tam kart numarasini sesli okumasini ISTEMEMELI.",
                forbidden_any=("kart numaranizi soyle", "kart numaranizi okuy",
                               "16 haneli", "guvenlik kodu", "cvv", "son kullanma tarih"),
                severity="yuksek",
            ),
        ),
    ),
    "kayit_ifsa": CompliancePack(
        key="kayit_ifsa", name="Kayit & Sikayet Hakki Bildirimi",
        description="Musteriye sikayet/itiraz haklari ve kayit suresi bildirilmeli.",
        rules=(
            ComplianceRule(
                key="sikayet_hakki",
                description="Musteriye sikayet/itiraz yolu bildirilmeli (talep halinde).",
                required_any=("sikayet", "itiraz", "musteri hizmet", "basvuru"),
                severity="dusuk",
            ),
        ),
    ),
}

DEFAULT_ACTIVE = ("kvkk",)  # tenant ayari yoksa yalnizca KVKK aktif


def _matches(patterns: tuple[str, ...], text_folded: str) -> bool:
    """Kaliplardan herhangi biri metinde (ASCII-katlanmis) geciyor mu?

    Kelime sinirina bakmadan alt-dizi arar; kaliplar zaten cok karakterli
    ifadeler oldugu icin yanlis pozitif riski dusuk. Turkce eklere tolerans
    icin kaliplar KOK olarak yazilir ('kayit alt' -> 'kayit altina alinmaktadir').
    """
    return any(_fold_tr(p) in text_folded for p in patterns)


def check_pack(pack: CompliancePack, agent_text: str) -> list[dict]:
    """Bir paketin kurallarini temsilci metnine uygular; ihlal listesi doner."""
    folded = _fold_tr(agent_text)
    violations = []
    for rule in pack.rules:
        # Zorunlu aciklama eksik mi?
        if rule.required_any and not _matches(rule.required_any, folded):
            violations.append({
                "pack": pack.key, "rule": rule.key, "type": "missing_required",
                "description": rule.description, "severity": rule.severity,
            })
        # Yasak ifade var mi?
        if rule.forbidden_any and _matches(rule.forbidden_any, folded):
            violations.append({
                "pack": pack.key, "rule": rule.key, "type": "forbidden_present",
                "description": rule.description, "severity": rule.severity,
            })
    return violations


def evaluate(agent_text: str, active_packs: tuple[str, ...] | None = None) -> list[dict]:
    """Aktif tum paketleri temsilci metnine uygular.

    active_packs None ise DEFAULT_ACTIVE kullanilir. Bilinmeyen paket anahtarlari
    sessizce atlanir (tenant ayari eskise bile patlamaz).
    """
    active = active_packs if active_packs is not None else DEFAULT_ACTIVE
    out = []
    for key in active:
        pack = PACKS.get(key)
        if pack is None:
            continue
        out.extend(check_pack(pack, agent_text))
    return out


def list_packs() -> list[dict]:
    """Tum built-in paketleri (arayuzde acip kapatmak icin) listeler."""
    return [
        {
            "key": p.key, "name": p.name, "description": p.description,
            "rules": [
                {"key": r.key, "description": r.description, "severity": r.severity,
                 "kind": "required" if r.required_any else "forbidden"}
                for r in p.rules
            ],
        }
        for p in PACKS.values()
    ]
