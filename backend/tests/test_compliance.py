"""Yasakli kelime motoru + kriz tespiti testleri (kim soyledi dahil)."""

from types import SimpleNamespace

from app.models import BannedWord
from app.services import compliance


def _seg(idx, speaker, text, start=0.0):
    return SimpleNamespace(idx=idx, speaker=speaker, text=text, start_sec=start, end_sec=start + 2)


def _bw(term, match_type="fuzzy", severity="yuksek", category="hakaret"):
    return BannedWord(tenant_id=1, term=term, category=category, severity=severity,
                      match_type=match_type, is_active=True)


def test_detects_banned_word_and_attributes_speaker():
    segs = [
        _seg(0, "temsilci", "Lütfen saçmalamayın beyefendi", 10),
        _seg(1, "musteri", "Bu ne demek şimdi", 12),
    ]
    found = compliance.detect_banned_words(segs, [_bw("saçmalama")])
    assert len(found) == 1
    assert found[0].speaker == "temsilci"
    assert found[0].severity == "yuksek"


def test_customer_banned_word_not_charged_to_agent():
    segs = [
        _seg(0, "musteri", "Sizi aptal yerine koyuyorlar", 5),
        _seg(1, "temsilci", "Anlıyorum efendim, çözelim", 8),
    ]
    found = compliance.detect_banned_words(segs, [_bw("aptal")])
    assert len(found) == 1
    # Musteri soyledi -> temsilci ihlali degil
    assert compliance.agent_violations(found) == []


def test_fuzzy_matches_spelling_variation():
    segs = [_seg(0, "temsilci", "saçmalıyorsunuz resmen", 1)]
    found = compliance.detect_banned_words(segs, [_bw("saçmalama", match_type="fuzzy")])
    assert len(found) == 1


def test_exact_does_not_overmatch():
    segs = [_seg(0, "temsilci", "salakça bir durum yok", 1)]
    # exact 'salak' kelime siniriyla eslesmeli; 'salakça' icinde \b sinirindan gecmez
    found = compliance.detect_banned_words(segs, [_bw("salak", match_type="exact")])
    assert found == []


def test_crisis_detection_from_customer():
    segs = [
        _seg(0, "temsilci", "Size nasıl yardımcı olabilirim", 1),
        _seg(1, "musteri", "Avukatıma danışıp tüketici hakem heyetine gideceğim", 5),
    ]
    is_crisis, evidence, ts = compliance.detect_crisis(segs)
    assert is_crisis is True
    assert ts == 5
