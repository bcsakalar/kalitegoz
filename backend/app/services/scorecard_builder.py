"""No-code AI puan karti (scorecard) uretici.

Kullanici dogal dille "sunu degerlendirmek istiyorum" der; LLM bundan yapisal
bir rubrik (kriter listesi) uretir. Yonetici taslagi gozden gecirip kaydeder.

Sektorde (Verint/Calabrio 2026) one cikan "GenAI scorecard" ozelliginin yerel,
KVKK-uyumlu karsiligidir. Cikti DAIMA pydantic ile dogrulanir.
"""

from pydantic import BaseModel, Field

from ..models import CRITERION_GROUPS
from ..schemas import DraftCriterion, ScorecardDraft
from .llm import generate_json


class _LLMCriterion(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str = Field(min_length=5, max_length=600)
    group: str = "Iletisim Kalitesi"
    weight: float = 1.0
    is_critical: bool = False


class _LLMScorecard(BaseModel):
    criteria: list[_LLMCriterion] = Field(min_length=1)


_SYSTEM = (
    "Sen deneyimli bir cagri merkezi kalite yonetim uzmanisin. Gorevin, "
    "kullanicinin tarif ettigi degerlendirme ihtiyacindan somut, olculebilir bir "
    "puanlama rubrigi (scorecard) uretmek. Her kriter net, tek bir davranisi "
    "olcen ve bir kalite uzmaninin '0-10 arasi' puanlayabilecegi netlikte olmali. "
    "Yalnizca gecerli JSON dondur."
)


def build(prompt: str, channel: str = "all", max_criteria: int = 8) -> ScorecardDraft:
    """Dogal dil aciklamasindan rubrik taslagi uret."""
    groups = ", ".join(CRITERION_GROUPS)
    user = (
        f"Kullanicinin ihtiyaci:\n{prompt.strip()}\n\n"
        f"En fazla {max_criteria} kriter uret. Her kriter icin:\n"
        "- name: kisa baslik (orn. 'Kimlik dogrulama')\n"
        "- description: puanlama uzmanina rehber olacak net aciklama\n"
        f"- group: sunlardan biri: {groups}\n"
        "- weight: onem agirligi (0.5-3.0 arasi; kritik olanlar daha yuksek)\n"
        "- is_critical: bu kriter cok kotuyse tum cagri sifirlanmali mi (true/false)\n\n"
        'JSON bicimi: {"criteria": [{"name": "...", "description": "...", '
        '"group": "...", "weight": 1.0, "is_critical": false}]}'
    )
    draft = generate_json(_LLMScorecard, _SYSTEM, user)

    scope = channel if channel in ("voice", "chat", "all") else "all"
    valid_groups = set(CRITERION_GROUPS)
    out: list[DraftCriterion] = []
    for c in draft.criteria[:max_criteria]:
        out.append(DraftCriterion(
            name=c.name.strip()[:120],
            description=c.description.strip(),
            group=c.group if c.group in valid_groups else "Iletisim Kalitesi",
            weight=max(0.5, min(3.0, round(c.weight, 2))),
            is_critical=bool(c.is_critical),
            critical_threshold=3,
            channel_scope=scope,
        ))
    return ScorecardDraft(
        criteria=out,
        note=f"{len(out)} kriter LLM ile uretildi — kaydetmeden once gozden gecirin.",
    )
