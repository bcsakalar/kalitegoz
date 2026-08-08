"""Akustik analiz: pitch tespiti, monotonluk, bagirma, sessizlik."""

import numpy as np

from app.services import acoustics

SR = 16000


def _tone(freq: float, sec: float, amp: float = 0.2, sr: int = SR) -> np.ndarray:
    """Sesli harf benzeri periyodik sinyal (harmonikli) — F0 tespiti icin."""
    t = np.linspace(0, sec, int(sr * sec), endpoint=False)
    sig = np.sin(2 * np.pi * freq * t) + 0.5 * np.sin(4 * np.pi * freq * t)
    return (amp * sig / np.abs(sig).max()).astype(np.float32)


def test_detects_pitch_of_pure_tone():
    """200 Hz'lik sinyalde F0 ~200 Hz bulunmali (%10 tolerans)."""
    a = acoustics.analyze_channel(_tone(200, 1.5), SR)
    assert 180 <= a.pitch_mean <= 220, f"beklenen ~200 Hz, bulunan {a.pitch_mean}"


def test_constant_tone_is_monotone():
    """Sabit frekans = monoton konusma."""
    a = acoustics.analyze_channel(_tone(150, 1.5), SR)
    assert a.monotone is True
    assert a.pitch_std < 15


def test_varying_pitch_is_not_monotone():
    """Degisken tonlama monoton SAYILMAMALI."""
    parts = [_tone(f, 0.4) for f in (120, 190, 140, 230, 160)]
    a = acoustics.analyze_channel(np.concatenate(parts), SR)
    assert a.monotone is False
    assert a.pitch_std > 15


def test_silence_produces_no_measurement():
    a = acoustics.analyze_channel(np.zeros(SR, dtype=np.float32), SR)
    assert a.pitch_mean == 0.0
    assert a.voiced_sec == 0.0
    assert a.shout_moments == []


def test_detects_shout_as_loudness_spike():
    """Normal konusma + ani yuksek sesli bolum -> bagirma tespiti."""
    normal = _tone(160, 2.0, amp=0.12)
    shout = _tone(160, 1.0, amp=0.6)   # ~5x enerji
    tail = _tone(160, 1.0, amp=0.12)
    sig = np.concatenate([normal, shout, tail])
    a = acoustics.analyze_channel(sig, SR)
    assert len(a.shout_moments) >= 1, "bagirma tespit edilmeliydi"
    # Bagirma ~2. saniyede baslamali
    assert 1.5 <= a.shout_moments[0] <= 3.0


def test_steady_speech_has_no_false_shout():
    """Sabit seviyeli konusmada YANLIS bagirma alarmi olmamali."""
    a = acoustics.analyze_channel(_tone(160, 4.0, amp=0.15), SR)
    assert a.shout_moments == []


def test_offset_is_applied_to_shout_timestamps():
    """Mono modda segment baslangici bagirma zamanina eklenmeli.

    Not: taban cizgisi konusmacinin KENDI medyani oldugu icin, konusmanin
    cogunlugu normal seviyede olmali (gercek hayatta da oyledir).
    """
    sig = np.concatenate([_tone(160, 3.0, amp=0.1), _tone(160, 1.0, amp=0.6)])
    a = acoustics.analyze_channel(sig, SR, offset_sec=30.0)
    assert a.shout_moments, "bagirma tespit edilmeliydi"
    assert a.shout_moments[0] >= 30.0, "offset uygulanmali"
    assert 32.5 <= a.shout_moments[0] <= 34.0, "bagirma ~3. saniyede baslamali"


def test_shout_needs_majority_normal_baseline():
    """Konusmanin YARISI yuksek sesliyse bu 'normal seviyesi' kabul edilir.

    Medyan tabanli esik bilincli bir tercih: mikrofon/hat seviyesi kisiden
    kisiye degistigi icin mutlak esik kullanilamaz. Surekli yuksek sesle
    konusan biri 'surekli bagiriyor' diye isaretlenmez; ani YUKSELIS aranir.
    """
    sig = np.concatenate([_tone(160, 1.0, amp=0.1), _tone(160, 1.0, amp=0.6)])
    a = acoustics.analyze_channel(sig, SR)
    assert a.shout_moments == []


def test_analyze_missing_file_returns_empty():
    """Dosya yoksa (chat/sentetik kayit) bos doner, patlamaz."""
    assert acoustics.analyze("", []) == {}
    assert acoustics.analyze("/yok/boyle/bir/dosya.wav", []) == {}


def test_acoustic_risky_moments_mapping():
    metrics = {
        "temsilci_bagirma_anlari": [12.0],
        "musteri_bagirma_anlari": [45.0],
    }
    risky = acoustics.acoustic_risky_moments(metrics)
    assert len(risky) == 2
    agent = next(r for r in risky if r["zaman"] == 12.0)
    assert agent["onem"] == "yuksek"          # temsilcinin bagirmasi agir
    cust = next(r for r in risky if r["zaman"] == 45.0)
    assert cust["onem"] == "orta"             # musterinin bagirmasi sinyal


def test_read_wav_mono_reads_ffmpeg_extensible_format(tmp_path):
    """REGRESYON: ffmpeg channelsplit ciktisi WAVE_FORMAT_EXTENSIBLE (65534)
    olur ve Python 'wave' modulu onu 'unknown format: 65534' ile reddederdi;
    akustik analiz de sessizce atlanirdi. Artik ffmpeg fallback ile okunmali.

    ffmpeg gerektirir (Docker test imajinda var); yoksa atlanir.
    """
    import shutil
    import subprocess
    import wave as wave_mod

    from app.services import audio

    if not shutil.which("ffmpeg"):
        import pytest
        pytest.skip("ffmpeg yok")

    # Once standart stereo PCM uret, sonra channelsplit ile extensible'a cevir
    stereo = tmp_path / "stereo.wav"
    with wave_mod.open(str(stereo), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(16000)
        samples = (np.random.rand(16000 * 2) * 1000).astype("<i2")  # 1sn stereo
        w.writeframes(samples.tobytes())

    left, right = audio.split_stereo(stereo, tmp_path)

    # Split ciktisi gercekten extensible mi? (bu testin anlamli olmasi icin)
    import struct
    with open(left, "rb") as f:
        fmt_tag = struct.unpack("<H", f.read(24)[20:22])[0]
    # 65534 = WAVE_FORMAT_EXTENSIBLE; ffmpeg surumune gore 1 de olabilir.
    # Her iki halde de okuma BASARILI olmali:
    x, sr = acoustics._read_wav_mono(left)
    assert sr == 16000
    assert len(x) > 0
    assert x.dtype == np.float32
