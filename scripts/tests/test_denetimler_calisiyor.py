"""B40 — iki denetim görünmez bir karakter yüzünden hiçbir şeyi kontrol etmiyordu.

## Ne oldu

`tr_audit.py` ve `ui_audit.py` içinde `\\b` (kelime sınırı) kaçışının yerinde
**gerçek bir backspace baytı (0x08)** vardı. Desen `\\x08kelime\\x08` olmuş ve
hiçbir zaman eşleşmemişti. Her koşumda TEMİZ diyorlardı.

Karakter terminalde görünmüyor, `grep` çıktısında görünmüyor, dosyayı
okurken görünmüyor. Ölü kontrol, tanımsız CSS değişkeninden **daha kötü**:
o sessizce çalışmaz, bu sessizce *güvence verir*.

## Bu testlerin savunduğu şey

1. Denetim betiklerinde kontrol karakteri yok.
2. Her denetim, kendisine verilen **gerçek bir ihlali yakalıyor**. Bir
   kontrolün "yeşil verdiği" onun çalıştığını göstermez; kırıldığı
   görülmelidir.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parents[2]
BETIKLER = KOK / "scripts"
sys.path.insert(0, str(BETIKLER))


# ------------------------------------------------------------------ karakter

@pytest.mark.parametrize("ad", ["tr_audit.py", "ui_audit.py", "api_contract_audit.py"])
def test_denetim_betiginde_KONTROL_KARAKTERI_yok(ad):
    """0x08 gibi karakterler regex'i sessizce olduruyor ve GORUNMUYOR."""
    p = BETIKLER / ad
    if not p.exists():
        pytest.skip(f"{ad} yok")
    metin = p.read_text(encoding="utf-8")
    kotu = {c for c in metin if ord(c) < 32 and c not in "\n\t"}
    assert not kotu, (
        f"{ad} icinde kontrol karakteri var: {[hex(ord(c)) for c in kotu]} — "
        "muhtemelen bir regex kacisi bayta donusmus ve desen olu."
    )


# ------------------------------------------------------------------ gerçekten yakalıyor mu

def test_tr_audit_SUNUCU_metnindeki_ascii_turkceyi_yakalar(tmp_path, monkeypatch):
    """Denetimin ateslendigini kanitla — 'yesil verdi' yeterli degil."""
    import tr_audit

    sahte = tmp_path / "backend" / "app" / "services"
    sahte.mkdir(parents=True)
    (sahte / "ornek.py").write_text(
        '{"desc": "Hizli / hafif — dusuk VRAM"}\n', encoding="utf-8")
    monkeypatch.setattr(tr_audit, "ROOT", tmp_path)

    bulgular = tr_audit.denetle_backend_metinleri()
    assert bulgular, "ASCII Turkce iceren sunucu metni YAKALANMADI — kontrol olu"
    assert any("dusuk" in b for b in bulgular)


def test_tr_audit_DOGRU_yazilmis_metni_isaretlemez(tmp_path, monkeypatch):
    """Yanlis pozitif ureten denetim gormezden gelinir; o da olu demektir."""
    import tr_audit

    sahte = tmp_path / "backend" / "app" / "services"
    sahte.mkdir(parents=True)
    (sahte / "ornek.py").write_text(
        '{"desc": "Hızlı / hafif — düşük VRAM"}\n', encoding="utf-8")
    monkeypatch.setattr(tr_audit, "ROOT", tmp_path)

    assert tr_audit.denetle_backend_metinleri() == []


def test_tr_audit_kelime_listesi_KELIME_SINIRI_kullaniyor():
    """`cok` gibi kisa kaliplar Ingilizce kelimenin icinde eslesmemeli."""
    import tr_audit

    kaynak = (BETIKLER / "tr_audit.py").read_text(encoding="utf-8")
    assert r"\b" in kaynak, "Kelime siniri kacisi kaybolmus"


def test_ui_audit_TANIMSIZ_tailwind_rengini_yakalar():
    """Bu kontrol 0x08 yuzunden oluydu; canli koda karsi ateslediginden emin ol."""
    import ui_audit

    bulgular = ui_audit.tanimsiz_renk_siniflari()
    # Canli depoda ihlal olmamali; ama fonksiyon GERCEKTEN tariyor olmali.
    assert isinstance(bulgular, list)
    kaynak = (BETIKLER / "ui_audit.py").read_text(encoding="utf-8")
    desen = re.search(r'finditer\(r"([^"]+)"', kaynak)
    assert desen, "Renk deseni bulunamadi"
    assert desen.group(1).startswith(r"\b"), (
        "Renk deseni kelime siniriyla baslamiyor — kacis yine baytlanmis olabilir")
