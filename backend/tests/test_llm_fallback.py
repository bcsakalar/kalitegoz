"""B38 — bulut sağlayıcı düşünce sistem sessizce yerel modele kaçıyordu.

## Ne bulundu

Kullanıcı şunu istedi: *"Gemini ise sistemdeki her şey Gemini ile ...
karışıklık istemiyorum."*

`llm.generate_json` bulut sağlayıcı hata verdiğinde yerel Ollama'ya
düşüyordu. Davranışın kendisi meşru — bulut kesintisi puanlamayı
durdurmasın. Sorun **görünmezliğiydi**:

1. Anahtar `getattr(settings, "llm_fallback_ollama", True)` ile okunuyordu
   ama ayar **hiçbir yerde tanımlı değildi** — ne `config.py`'de ne
   `.env.example`'da. Yani kapatmanın hiçbir yolu yoktu; yapılandırılabilir
   *görünen* bir sabitti.
2. Düşmenin tek izi konteyner log satırıydı. Kullanıcı panelde "Gemini"
   yazdığını görüp, aslında yerel qwen'in verdiği puana bakıyordu.

## Bu testlerin savunduğu şey

- Ayar gerçekten var ve **etkili** (kapalıyken düşülmez).
- Düşme olduğunda `AiUsage`'a gerçek sağlayıcı adıyla yazılır — sayılabilir
  bir iz kalır.
- Yerel sağlayıcı seçiliyken "yedek" diye ikinci bir deneme yapılmaz.
- Anahtarsız bulut sağlayıcı, yedeğe düşmeden önce açık hata verir.
"""

from unittest.mock import patch

import pytest
from pydantic import BaseModel

from app.config import settings
from app.services import ai_config, llm


class _Cikti(BaseModel):
    deger: str


def _bulut() -> ai_config.AIResolved:
    return ai_config.AIResolved(
        provider="gemini", model="gemini-2.5-flash", api_key="k",
        base_url="", kind="llm", external=True,
    )


# ------------------------------------------------------------------ ayar var mı

def test_yedek_ayari_GERCEKTEN_tanimli():
    """`getattr(..., True)` tanimsiz ayari gizler; alan modelde OLMALI.

    Tanimsizsa kullanici .env'e yazar, hicbir sey degismez ve sebebini
    bulamaz — sessiz basarisizlik.
    """
    assert hasattr(settings, "llm_fallback_ollama"), (
        "llm_fallback_ollama Settings'te tanimli degil — .env'e yazilsa da "
        "etkisiz kalir"
    )
    assert isinstance(settings.llm_fallback_ollama, bool)


# ------------------------------------------------------------------ davranış

def test_yedek_KAPALIYKEN_yerele_dusulmez():
    """Kullanici 'sadece sectigim saglayici' dediyse baska model puanlamamali."""
    with patch.object(ai_config, "active_llm", return_value=_bulut()), \
         patch.object(settings, "llm_fallback_ollama", False), \
         patch.object(llm, "_generate_with", side_effect=llm.LLMError("bulut coktu")) as g:
        with pytest.raises(llm.LLMError) as hata:
            llm.generate_json(_Cikti, "s", "u")

    assert g.call_count == 1, "Yedek kapaliyken ikinci deneme yapilmis"
    assert "KAPALI" in str(hata.value), "Hata mesaji sebebini soylemeli"


def test_yedek_ACIKKEN_yerele_dusulur():
    cagrilan: list[str] = []

    def sahte(model_cls, system, user, cfg):
        cagrilan.append(cfg.provider)
        if cfg.provider != "ollama":
            raise llm.LLMError("bulut coktu")
        return _Cikti(deger="yerel")

    with patch.object(ai_config, "active_llm", return_value=_bulut()), \
         patch.object(settings, "llm_fallback_ollama", True), \
         patch.object(llm, "_generate_with", side_effect=sahte):
        sonuc = llm.generate_json(_Cikti, "s", "u")

    assert sonuc.deger == "yerel"
    assert cagrilan == ["gemini", "ollama"], f"Beklenmedik cagri sirasi: {cagrilan}"


def test_YEREL_saglayicida_ikinci_deneme_YOK():
    """Ollama zaten seciliyken 'yedek' ayni sunucuya ikinci kez gitmemeli."""
    yerel = ai_config.ollama_fallback()
    with patch.object(ai_config, "active_llm", return_value=yerel), \
         patch.object(llm, "_generate_with", side_effect=llm.LLMError("yerel coktu")) as g:
        with pytest.raises(llm.LLMError):
            llm.generate_json(_Cikti, "s", "u")
    assert g.call_count == 1, "Yerel saglayicida gereksiz ikinci deneme yapildi"


def test_ANAHTARSIZ_bulut_saglayici_ACIK_hata_verir():
    """Anahtar yoksa sorun yapilandirmadadir; sessizce yerele kacmak onu gizler."""
    cfg = ai_config.AIResolved(provider="openai", model="gpt-4o-mini", api_key="",
                               base_url=ai_config.OPENAI_BASE, kind="llm", external=True)
    with pytest.raises(llm.LLMError) as hata:
        llm._chat("s", "u", cfg)
    metin = str(hata.value)
    assert "openai" in metin and "anahtar" in metin.lower(), (
        f"Hata mesaji ne yapilacagini soylemiyor: {metin}")


# ------------------------------------------------------------------ iz kalıyor mu

def test_dusme_KULLANIM_KAYDINA_gercek_saglayiciyla_yazilir():
    """Panelin sayimi bu kayda dayaniyor; secili degil GERCEK saglayici yazilmali.

    `_record_usage` cfg.provider'i yazar ve yedek cagrisi ollama cfg'siyle
    yapilir — yani dusme kayitta 'ollama' olarak gorunur. Bu test o baglantiyi
    kilitler; biri `_record_usage`'a secili saglayiciyi yazdirmaya kalkarsa
    panel dusmeleri sayamaz hale gelir.
    """
    yazilan: list[str] = []

    with patch.object(ai_config, "usage_meta", return_value={"tenant_id": 1, "kind": "scoring"}), \
         patch("app.db.SessionLocal") as oturum:
        oturum.return_value.add.side_effect = lambda row: yazilan.append(row.provider)
        llm._record_usage(ai_config.ollama_fallback(), 10, 5, 100, True)

    assert yazilan == ["ollama"], (
        f"Kullanim kaydina gercek saglayici yazilmadi: {yazilan}")


def test_panel_ucunda_dusme_sayaci_VAR():
    """Kaynak denetimi: sayac kaldirilirsa uyari bandi sessizce olur."""
    from pathlib import Path

    kaynak = (Path(__file__).resolve().parents[1] / "app" / "api" / "ai_admin.py")
    metin = kaynak.read_text(encoding="utf-8")
    assert "def _yedege_dusme" in metin, "Dusme sayaci kaldirilmis"
    assert '"yedege_dusme"' in metin, "Sayac config yanitina konmamis"
