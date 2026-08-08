"""KVKK PII maskeleme testleri + harici LLM'e maskeli gitme garantisi."""

from app.services import llm
from app.services.masking import has_pii, mask_text


def test_masks_phone():
    assert "[MASKELI]" in mask_text("Numaram 0532 123 45 67 arayin")
    assert "0532" not in mask_text("0532 123 45 67")


def test_masks_valid_tckn_but_not_random_11_digits():
    # Gecerli TC kimlik (algoritma dogrulamali) maskelenir
    masked = mask_text("TCKN 10000000146 kayitli")
    assert "10000000146" not in masked
    # Gecersiz 11 hane (musteri no olabilir) maskelenmez
    assert mask_text("musteri no 12345678901") == "musteri no 12345678901"


def test_masks_valid_card_luhn():
    # Luhn gecerli kart -> maskeli
    assert "[MASKELI]" in mask_text("kart 4242 4242 4242 4242")
    # Luhn gecersiz 16 hane -> maskelenmez
    assert mask_text("4242 4242 4242 4241") == "4242 4242 4242 4241"


def test_masks_iban_and_email():
    assert "[MASKELI]" in mask_text("IBAN TR33 0006 1005 1978 6457 8413 26")
    assert "[MASKELI]" in mask_text("mail: ali@ornek.com")


def test_has_pii():
    assert has_pii("0532 123 45 67") is True
    assert has_pii("merhaba nasilsiniz") is False


def test_gemini_path_masks_before_send(monkeypatch):
    """LLM_PROVIDER=gemini iken _chat, saglayiciya DAIMA maskeli metin gonderir."""
    captured = {}

    def fake_gemini(cfg, system, user):
        captured["system"] = system
        captured["user"] = user
        return "{}", 0, 0

    monkeypatch.setattr(llm.settings, "llm_provider", "gemini")
    monkeypatch.setattr(llm.settings, "gemini_api_key", "test-key")
    monkeypatch.setattr(llm, "_chat_gemini", fake_gemini)

    llm._chat("Sistem 0532 111 22 33", "Musteri TC 10000000146 ve kart 4242 4242 4242 4242")

    assert "0532 111 22 33" not in captured["user"] + captured["system"]
    assert "10000000146" not in captured["user"]
    assert "4242 4242 4242 4242" not in captured["user"]
    assert "[MASKELI]" in captured["user"]


def test_llm_falls_back_to_ollama_on_primary_failure(monkeypatch):
    """Birincil (gemini) saglayici cokerse generate_json yerel Ollama'ya duser."""
    from pydantic import BaseModel

    from app.services import ai_config

    class _Out(BaseModel):
        ok: bool

    calls = {"gemini": 0, "ollama": 0}

    def fake_gemini(cfg, system, user):
        calls["gemini"] += 1
        raise llm.LLMError("gemini down")

    def fake_ollama(cfg, system, user):
        calls["ollama"] += 1
        return '{"ok": true}', 5, 3

    monkeypatch.setattr(llm, "_chat_gemini", fake_gemini)
    monkeypatch.setattr(llm, "_chat_ollama", fake_ollama)
    # Aktif config gemini (gecerli anahtarli gibi) olsun
    tok = ai_config.set_active(ai_config.AIResolved("gemini", "gemini-2.0-flash", "k", "", "llm", True))
    try:
        out = llm.generate_json(_Out, "sys", "user")
    finally:
        ai_config.reset_active(tok)
    assert out.ok is True
    assert calls["gemini"] >= 1 and calls["ollama"] == 1
