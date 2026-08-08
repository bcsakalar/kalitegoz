"""Agent assist motoru (Dalga 6): temsilciye canli/anlik sufle.

Mimari not — durustce:
Gercek zamanli 'canli sufle' urunleri (Balto, Cresta) streaming STT + <2sn
gecikme ister; bu, ayri bir ses-akisi altyapisidir ve KaliteGoz'un cagri-sonrasi
mimarisiyle ortusmez. Burada, o altyapinin UZERINE oturacak ASIL DEGERI ureten
motoru kuruyoruz: bir ana kadar olan (kismi) transkripti alip temsilciye
oneriler dondurur. Bu motor:
  - kismi metni whatever ureten kaynaktan alir (streaming STT, demo textarea,
    veya post-call review sirasinda "bu noktada ne onerirdin"),
  - deterministik + hizli calisir (LLM'siz de is gorur),
returns: uyum hatirlatmalari, bilgi bankasi onerileri, sonraki-aksiyon ipuclari.

Boylece streaming altyapisi eklendiginde motor hazir olur; eklenmeden de
review ekraninda ve demo'da kullanilabilir (verifiye edilebilir).
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from . import compliance_packs, knowledge


@dataclass
class Suggestion:
    kind: str        # compliance | knowledge | next_action
    severity: str    # bilgi | uyari | kritik
    text: str
    detail: str = ""


# Niyet -> sonraki aksiyon ipuclari (deterministik, hizli). Anahtarlar kismi
# transkriptte aranir (ASCII-katlanmis).
_NEXT_ACTION_HINTS = {
    "iptal": "Musteri iptal sinyali veriyor — once elde tutma (retention) teklifini sun.",
    "iade": "Iade talebi — iade sartlarini ve suresini net soyle, kesin taahhutte bulunma.",
    "sikayet": "Sikayet — once empati kur, sonra somut cozum adimini bildir.",
    "avukat": "Hukuki soylem — sakin kal, ust birime aktarma prosedurunu islet.",
    "sozlesme feshi": "Fesih talebi — cayma bedeli ve alternatifleri (dondurma) acikla.",
    "fatura": "Fatura konusu — kalem kalem incele, itiraz hakkini hatirlat.",
}


def _fold(text: str) -> str:
    from ..schemas import _fold_tr
    return _fold_tr(text)


def compliance_reminders(partial_text: str, active_packs=None) -> list[Suggestion]:
    """Kismi metinde HENUZ yapilmamis zorunlu aciklamalari hatirlat.

    Not: compliance_packs.evaluate 'eksik zorunlu' olanlari doner; canli baglamda
    bunlar 'henuz soylemedin, soyle' hatirlatmasina donusur.
    """
    out = []
    for v in compliance_packs.evaluate(partial_text, active_packs):
        if v["type"] == "missing_required":
            out.append(Suggestion(
                kind="compliance",
                severity="kritik" if v["severity"] == "yuksek" else "uyari",
                text=f"Hatirlatma: {v['description']}",
                detail=f"{v['pack'].upper()} / {v['rule']}",
            ))
        elif v["type"] == "forbidden_present":
            out.append(Suggestion(
                kind="compliance", severity="kritik",
                text=f"DIKKAT: {v['description']}",
                detail=f"{v['pack'].upper()} / {v['rule']}",
            ))
    return out


def next_action_hints(partial_text: str) -> list[Suggestion]:
    folded = _fold(partial_text)
    out = []
    for key, hint in _NEXT_ACTION_HINTS.items():
        if _fold(key) in folded:
            out.append(Suggestion(kind="next_action", severity="bilgi", text=hint))
    return out


def knowledge_suggestions(db: Session, tenant_id: int, partial_text: str,
                          top_k: int = 2) -> list[Suggestion]:
    """Bilgi bankasindan kismi metne en yakin pasajlari oner (RAG).

    Bos bilgi bankasi / embedding hatasi durumunda sessizce bos doner — assist
    her zaman calismali, RAG opsiyonel iyilestirme.
    """
    if not partial_text.strip():
        return []
    try:
        hits = knowledge.search(db, tenant_id, partial_text, top_k=top_k)
    except Exception:
        return []
    out = []
    for chunk, score in hits:
        if score < 0.35:  # alakasizsa gosterme
            continue
        out.append(Suggestion(
            kind="knowledge", severity="bilgi",
            text=chunk.content[:200],
            detail=f"benzerlik {score:.2f}",
        ))
    return out


def suggest(db: Session, tenant_id: int, partial_text: str,
            active_packs=None) -> list[dict]:
    """Tum sufle kaynaklarini birlestirir; oncelik sirasiyla dondurur.

    Siralama: kritik uyum > sonraki aksiyon > bilgi. Boylece temsilci en kritik
    hatirlatmayi en ustte gorur.
    """
    suggestions = (
        compliance_reminders(partial_text, active_packs)
        + next_action_hints(partial_text)
        + knowledge_suggestions(db, tenant_id, partial_text)
    )
    order = {"kritik": 0, "uyari": 1, "bilgi": 2}
    suggestions.sort(key=lambda s: order.get(s.severity, 3))
    return [
        {"kind": s.kind, "severity": s.severity, "text": s.text, "detail": s.detail}
        for s in suggestions
    ]
