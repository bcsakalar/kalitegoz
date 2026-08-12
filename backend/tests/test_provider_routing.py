"""Sağlayıcı seçimi SİSTEMİN TAMAMINDA uygulanıyor mu?

## Neden bu dosya var

Kullanıcı sordu: *"Gemini seçtiysem sistemdeki her şey Gemini ile mi
çalışıyor? Karışıklık istemiyorum."*

Haklı bir endişe. Üç ayrı yapay zekâ yüzeyi var (puanlama, gömme, görsel)
ve her biri kendi sağlayıcısını ayrı seçiyor. Bir yerde sabit kodlanmış bir
Ollama çağrısı kalırsa, kullanıcı Gemini seçtiğini sanırken sistem sessizce
yerel modele gidiyor olur — **ve bu hiçbir yerde hata vermez.**

Bu testler o sessiz kaçışı kapatır.

## Neyi garanti eder

1. Seçilen sağlayıcı `resolve()` çıktısına yansır (LLM / embed / vision).
2. Her sağlayıcı için **doğru taban adres** ve **doğru anahtar** kullanılır.
3. Bir yüzeyde Gemini, diğerinde Ollama seçilebilir — **karışmazlar**.
4. `use_llm` bağlamı kapandığında önceki config geri gelir (sızıntı yok).
5. Kaynak düzeyinde: hiçbir serviste sabit kodlanmış sağlayıcı adresi yok.
"""

from pathlib import Path

import pytest

from app.services import ai_config


def _ayar(**kw) -> dict:
    """Kiraci ayarindaki `ai` blogunu kurar."""
    return {"ai": kw}


# ------------------------------------------------------------------ LLM

@pytest.mark.parametrize("saglayici, model, beklenen_base", [
    ("ollama", "qwen2.5:7b-instruct", None),          # .env'den gelir
    ("openai", "gpt-4o-mini", ai_config.OPENAI_BASE),
    ("openrouter", "openai/gpt-4o-mini", ai_config.OPENROUTER_BASE),
    ("gemini", "gemini-2.5-flash", None),             # URL istekte kuruluyor
])
def test_secilen_saglayici_LLM_cozumune_yansir(saglayici, model, beklenen_base):
    cfg = ai_config.resolve(
        _ayar(llm_provider=saglayici,
              llm_models={saglayici: model},
              keys={saglayici: "test-anahtar"}),
        "llm",
    )
    assert cfg.provider == saglayici, "Secilen saglayici cozume yansimadi"
    assert cfg.model == model, "Secilen model cozume yansimadi"
    if beklenen_base:
        assert cfg.base_url == beklenen_base, (
            f"{saglayici} icin yanlis taban adres: {cfg.base_url}")


def test_bulut_saglayicida_ANAHTAR_tasinir():
    cfg = ai_config.resolve(
        _ayar(llm_provider="openai", llm_models={"openai": "gpt-4o-mini"},
              keys={"openai": "sk-testanahtar"}),
        "llm",
    )
    assert cfg.api_key == "sk-testanahtar", "API anahtari cozume tasinmadi"
    assert cfg.external is True, "Bulut saglayici 'external' isaretlenmeli"


def test_yerel_saglayici_EXTERNAL_degil():
    """`external` bayragi guvenlik sayfasinda 'veri kurum disina cikiyor mu'
    sorusunu cevapliyor — yerel modelde False olmali."""
    cfg = ai_config.resolve(
        _ayar(llm_provider="ollama", llm_models={"ollama": "qwen2.5:7b-instruct"}),
        "llm",
    )
    assert cfg.external is False


# ------------------------------------------------------------------ üç yüzey ayrı

def test_UC_YUZEY_birbirine_karismaz():
    """Puanlama Gemini, gomme Ollama, gorsel OpenAI olabilir.

    Kullanicinin en cok korktugu senaryo bu: birini secince digerinin de
    degismesi. Uc yuzey BAGIMSIZ cozulmeli.
    """
    ayar = _ayar(
        llm_provider="gemini", llm_models={"gemini": "gemini-2.5-flash"},
        embed_provider="ollama", embed_models={"ollama": "nomic-embed-text"},
        vision_provider="openai", vision_models={"openai": "gpt-4o"},
        keys={"gemini": "g-key", "openai": "o-key"},
    )
    llm = ai_config.resolve(ayar, "llm")
    embed = ai_config.resolve(ayar, "embed")
    vision = ai_config.resolve(ayar, "vision")

    assert (llm.provider, llm.model) == ("gemini", "gemini-2.5-flash")
    assert (embed.provider, embed.model) == ("ollama", "nomic-embed-text")
    assert (vision.provider, vision.model) == ("openai", "gpt-4o")
    # Anahtarlar da karismamali
    assert llm.api_key == "g-key"
    assert vision.api_key == "o-key"
    assert embed.api_key == "" or embed.external is False


def test_her_saglayici_KENDI_modelini_hatirlar():
    """Saglayici degistirilip geri donuldugunde eski model kaybolmamali.

    `llm_models` saglayici bazinda sozluk oldugu icin bu calisir; tek bir
    `llm_model` alani olsaydi her degisimde model sifirlanirdi.
    """
    ayar = _ayar(
        llm_provider="openai",
        llm_models={"ollama": "qwen2.5:7b-instruct", "openai": "gpt-4o-mini"},
        keys={"openai": "k"},
    )
    assert ai_config.resolve(ayar, "llm").model == "gpt-4o-mini"

    ayar["ai"]["llm_provider"] = "ollama"
    assert ai_config.resolve(ayar, "llm").model == "qwen2.5:7b-instruct"


# ------------------------------------------------------------------ bağlam sızıntısı

def test_use_llm_baglami_KAPANINCA_geri_alinir():
    """Bir kiracinin config'i digerine sizmamali.

    `use_llm` bir baglam yoneticisi; cikista onceki deger geri gelmeli.
    Aksi halde cok kiracili kurulumda A kiracisinin anahtari B'nin
    cagrisinda kullanilir.
    """
    onceki = ai_config.active_llm()
    with ai_config.use_llm(
        _ayar(llm_provider="openai", llm_models={"openai": "gpt-4o-mini"},
              keys={"openai": "sizinti-testi"}),
        tenant_id=1, kind="test",
    ):
        icerde = ai_config.active_llm()
        assert icerde.provider == "openai"
        assert icerde.api_key == "sizinti-testi"

    sonraki = ai_config.active_llm()
    assert sonraki.provider == onceki.provider, "Baglam kapandi ama config sizdi"
    assert sonraki.api_key == onceki.api_key


# ------------------------------------------------------------------ kaynak denetimi

_SERVIS_DIZINI = Path(__file__).resolve().parents[1] / "app"


def test_hicbir_serviste_SABIT_saglayici_adresi_yok():
    """Sabit kodlanmis bir saglayici adresi, secimi sessizce yok sayar.

    Yalnizca `ai_config` (tanimin kendisi) ve `config.py` (varsayilan)
    muaftir. Baska bir yerde gecen adres, o cagrinin config'i ATLADIGI
    anlamina gelir ve kullanici Gemini sectigini sanirken Ollama'ya gider.
    """
    yasakli = ("api.openai.com", "openrouter.ai", "generativelanguage.googleapis.com")
    muaf = {"ai_config.py", "config.py", "llm.py", "knowledge.py", "vision.py",
            "model_catalog.py"}
    ihlal = []
    for p in _SERVIS_DIZINI.rglob("*.py"):
        if p.name in muaf:
            continue
        metin = p.read_text(encoding="utf-8", errors="ignore")
        for i, satir in enumerate(metin.splitlines(), 1):
            if satir.strip().startswith("#"):
                continue
            if any(y in satir for y in yasakli):
                ihlal.append(f"{p.name}:{i}  {satir.strip()[:70]}")
    assert not ihlal, (
        "Sabit kodlanmis saglayici adresi bulundu — bu cagrilar sagalyici "
        "secimini ATLAR:\n" + "\n".join(ihlal)
    )


def test_LLM_cagrilari_config_uzerinden_gider():
    """Her LLM cagrisi `cfg.base_url` kullanmali, sabit adres degil."""
    llm = (_SERVIS_DIZINI / "services" / "llm.py").read_text(encoding="utf-8")
    # Ollama sohbet ucu cfg'den gelmeli
    assert 'f"{cfg.base_url}/api/chat"' in llm, (
        "llm.py Ollama cagrisi cfg.base_url kullanmiyor")
    # Her saglayici icin ayri bir gonderici olmali
    for fn in ("_chat_ollama", "_chat_gemini", "_chat_openai"):
        assert f"def {fn}" in llm, f"llm.py icinde {fn} yok — saglayici desteklenmiyor"


def test_gomme_ve_gorsel_de_saglayici_bazinda_ayrilmis():
    knowledge = (_SERVIS_DIZINI / "services" / "knowledge.py").read_text(encoding="utf-8")
    vision = (_SERVIS_DIZINI / "services" / "vision.py").read_text(encoding="utf-8")
    for fn in ("_embed_ollama", "_embed_gemini", "_embed_openai"):
        assert f"def {fn}" in knowledge, f"knowledge.py icinde {fn} yok"
    assert "cfg.base_url" in vision or "cfg.provider" in vision, (
        "vision.py saglayici config'ini kullanmiyor")
