"""Kriter bazli model yonlendirmesi — S2c.

## Neden bu dosyadaki ilk test en onemlisi

`evaluate_all`, `model_for` parametresi None DEGILSE kriterleri gruplamadan
once oznel/nesnel diye ayirir. Ilk uygulamada `scoring.py` her zaman bir
fonksiyon geciyordu (icinde "yonlendirme kapaliysa None don" kontrolu vardi)
— ama fonksiyonun KENDISI None olmadigi icin ayirma her kosumda calisiyordu.

Sonuc: yonlendirmeyi hic kullanmayan kurulumlarda bile grup bilesimi degisti.
Altin sette olculdu: oznel kappa 0.146 -> 0.124. Yani opt-in bir ozellik,
varsayilan davranisi SESSIZCE bozdu.

Bu tur bir regresyon gozle fark edilmez — kod "dogru" gorunur, cunku mantik
dogrudur; yanlis olan, mantigin nerede degerlendirildigidir.
"""

import pytest

from app.services import model_routing, scoring_layers


class _K:
    """Minimal kriter — group_criteria yalnizca name/weight/id kullanir."""

    def __init__(self, id, name, weight=1.0):
        self.id = id
        self.name = name
        self.weight = weight


KRITERLER = [
    _K(1, "Açılış", 2.0),
    _K(2, "KVKK / Aydınlatma", 2.0),
    _K(3, "Aktif Dinleme", 1.0),
    _K(4, "Kapanış", 1.5),
    _K(5, "İhtiyaç Analizi", 1.0),
    _K(6, "Çözüm / Yönlendirme", 1.0),
]


def _gruplari_yakala(monkeypatch):
    """evaluate_all'un urettigi gruplari kaydet (LLM cagrilmadan)."""
    gorulen = []

    def sahte(group, transcript, hint, few_shot="", model_override=None):
        gorulen.append(([c.name for c in group], model_override))
        return []

    monkeypatch.setattr(scoring_layers, "evaluate_group", sahte)
    return gorulen


def test_yonlendirme_KAPALIYKEN_gruplama_degismez(monkeypatch):
    """model_for=None -> gruplar duz agirlik sirasina gore olusur.

    Bu, yonlendirme eklenmeden ONCEKI davranistir ve aynen korunmalidir.
    """
    gorulen = _gruplari_yakala(monkeypatch)
    scoring_layers.evaluate_all(KRITERLER, "transkript", "ipucu", None, None)

    beklenen = [[c.name for c in g] for g in scoring_layers.group_criteria(KRITERLER)]
    assert [g for g, _ in gorulen] == beklenen, (
        "Yonlendirme kapaliyken gruplama degisti — varsayilan yol bozuldu")
    assert all(m is None for _, m in gorulen), "Kapaliyken model gecilmemeli"


def test_yonlendirme_ACIKKEN_oznel_kriterler_AYRI_gruplanir(monkeypatch):
    """Ayrim gruplamadan ONCE yapilmali.

    Aksi halde bir grupta hem oznel hem nesnel kriter olur ve grup tek bir
    modele gitmek zorunda kalir: ya nesnel kriterler gereksiz yere buyuk
    modele gider (yavas), ya da oznel kriterler kucuk modelde kalir (asil
    kazanc kaybolur).
    """
    gorulen = _gruplari_yakala(monkeypatch)

    def model_for(group):
        return "buyuk-model" if any(
            model_routing.is_subjective(c.name) for c in group) else None

    scoring_layers.evaluate_all(KRITERLER, "transkript", "ipucu", None, model_for)

    for adlar, model in gorulen:
        oznel_var = any(model_routing.is_subjective(a) for a in adlar)
        nesnel_var = any(not model_routing.is_subjective(a) for a in adlar)
        assert not (oznel_var and nesnel_var), (
            f"Grup karisik: {adlar} — ayrim gruplamadan once yapilmali")
        assert model == ("buyuk-model" if oznel_var else None)


def test_split_by_model_tum_kriterleri_KORUR():
    """Ayirma sirasinda kriter kaybolmamali."""
    oznel, diger = model_routing.split_by_model(KRITERLER)
    assert len(oznel) + len(diger) == len(KRITERLER)
    assert {c.id for c in oznel} | {c.id for c in diger} == {c.id for c in KRITERLER}
    assert {c.name for c in oznel} == {"Aktif Dinleme", "İhtiyaç Analizi",
                                       "Çözüm / Yönlendirme"}


def test_resolve_for_ayni_saglayiciyi_KORUR():
    """Yalnizca model adi degismeli; saglayici/adres/anahtar aynen kalmali."""
    from app.services.ai_config import AIResolved

    temel = AIResolved(provider="ollama", model="kucuk", base_url="http://x:11434",
                       api_key="", kind="llm", external=False)
    yeni = model_routing.resolve_for(temel, "buyuk")
    assert yeni.model == "buyuk"
    assert (yeni.provider, yeni.base_url, yeni.kind) == (
        temel.provider, temel.base_url, temel.kind)


def test_resolve_for_ayni_model_icin_AYNI_nesneyi_dondurur():
    from app.services.ai_config import AIResolved

    temel = AIResolved(provider="ollama", model="kucuk", base_url="http://x:11434",
                       api_key="", kind="llm", external=False)
    assert model_routing.resolve_for(temel, "kucuk") is temel
    assert model_routing.resolve_for(temel, None) is temel


@pytest.mark.parametrize("ad, beklenen", [
    ("Aktif Dinleme", True),
    ("İhtiyaç Analizi", True),
    ("Ihtiyac Analizi", True),      # ASCII varyant (eski kurulumlar)
    ("Açılış", False),
    ("KVKK / Aydınlatma", False),
    ("", False),
])
def test_is_subjective(ad, beklenen):
    assert model_routing.is_subjective(ad) is beklenen


def test_subjective_model_name_bos_ayari_YOK_sayar():
    assert model_routing.subjective_model_name(None) is None
    assert model_routing.subjective_model_name({}) is None
    assert model_routing.subjective_model_name({"ai": {}}) is None
    assert model_routing.subjective_model_name({"ai": {"subjective_model": "  "}}) is None
    assert model_routing.subjective_model_name(
        {"ai": {"subjective_model": "qwen2.5:14b-instruct"}}) == "qwen2.5:14b-instruct"
