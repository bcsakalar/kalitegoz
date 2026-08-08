"""Vision LLM ciktisi semasi — cikti daima buna zorlanir."""

from pydantic import BaseModel, field_validator

_DOC_TYPES = {"fatura", "ekran_goruntusu", "kimlik", "sozlesme", "diger"}
_RISK = {"dusuk", "orta", "yuksek"}


class VisionResult(BaseModel):
    aciklama: str = ""
    belge_turu: str = "diger"
    kvkk_riski: str = "dusuk"
    hassas_veri: list[str] = []
    ozet_not: str = ""

    @field_validator("belge_turu", mode="before")
    @classmethod
    def _norm_type(cls, v):
        if isinstance(v, str):
            key = v.strip().lower().replace(" ", "_")
            if key in _DOC_TYPES:
                return key
        return "diger"

    @field_validator("kvkk_riski", mode="before")
    @classmethod
    def _norm_risk(cls, v):
        if isinstance(v, str) and v.strip().lower() in _RISK:
            return v.strip().lower()
        return "dusuk"

    @field_validator("hassas_veri", mode="before")
    @classmethod
    def _norm_sensitive(cls, v):
        if not isinstance(v, list):
            return []
        return [str(x).strip().lower() for x in v if str(x).strip()][:10]
