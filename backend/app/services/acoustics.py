"""Akustik analiz: ses tonu (pitch), yukseklik (enerji), bagirma ve monotonluk.

Metin analizi "ne dedi"yi olcer; akustik analiz "NASIL dedi"yi olcer. Cagri
merkezinde kritik: temsilci sakin mi kaldi, sesini yukseltti mi, monoton
(robotik) mi konusuyor, musteri bagiriyor mu?

Neden librosa/praat degil: ikisi de agir bagimlilik (numba/llvmlite veya praat
ikilisi) ve imaji ~200 MB buyutur. Ihtiyacimiz olan olcumler (RMS enerji,
otokorelasyonla F0, sessizlik) numpy ile dogrudan hesaplanabiliyor.

Kanal stratejisi audio.py ile ayni:
- Stereo: sol=musteri, sag=temsilci -> her kanal ayri analiz edilir (temiz).
- Mono : diarization segmentlerinin zaman araliklari kullanilir.
"""

import logging
import wave
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from . import audio

logger = logging.getLogger(__name__)

FRAME_MS = 32
HOP_MS = 16
# Insan sesi temel frekans araligi (Hz) — bu araligin disi gurultu/ıslık sayilir
F0_MIN, F0_MAX = 70, 400
# Bir cercevenin "konusma" sayilmasi icin gereken minimum enerji (sessizlik esigi)
SILENCE_RMS = 0.012
# Bagirma: konusmacinin kendi normalinin bu kati ustundeki enerji
SHOUT_RATIO = 2.2
# Bagirma sayilmasi icin ust uste en az bu kadar cerceve (~0.4 sn)
SHOUT_MIN_FRAMES = 25


@dataclass
class SpeakerAcoustics:
    pitch_mean: float = 0.0      # Hz — ses tonu ortalamasi
    pitch_std: float = 0.0       # Hz — tonlama cesitliligi (dusuk => monoton)
    loudness_mean: float = 0.0   # 0-1 RMS
    loudness_max: float = 0.0
    shout_moments: list[float] = field(default_factory=list)  # saniye
    monotone: bool = False
    voiced_sec: float = 0.0


def _read_wav_mono(path: Path) -> tuple[np.ndarray, int]:
    """Ses dosyasini mono float32'ye cozer.

    Once hizli yol: Python `wave` (standart PCM icin yeterli, ekstra process yok).
    Basarisizsa ffmpeg'e dus: ffmpeg channelsplit ciktisi WAVE_FORMAT_EXTENSIBLE
    (format 65534) olabilir ve `wave` bunu okuyamaz — eskiden akustik analiz bu
    yuzden sessizce atlaniyordu. Bkz. audio.read_mono_f32.
    """
    try:
        with wave.open(str(path), "rb") as w:
            sr = w.getframerate()
            n_ch = w.getnchannels()
            data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
        if n_ch > 1:
            data = data.reshape(-1, n_ch).mean(axis=1)
        return data.astype(np.float32) / 32768.0, sr
    except (wave.Error, EOFError):
        return audio.read_mono_f32(path)


def _frames(x: np.ndarray, sr: int) -> tuple[np.ndarray, int]:
    """Sinyali ortusmeli cercevelere bol -> (n_frames, frame_len)."""
    flen = max(1, int(sr * FRAME_MS / 1000))
    hop = max(1, int(sr * HOP_MS / 1000))
    if len(x) < flen:
        return np.empty((0, flen), dtype=np.float32), hop
    n = 1 + (len(x) - flen) // hop
    idx = np.arange(flen)[None, :] + hop * np.arange(n)[:, None]
    return x[idx], hop


def _f0_autocorr(frame: np.ndarray, sr: int) -> float:
    """Tek cercevenin temel frekansi (Hz). Otokorelasyon tepe noktasi yontemi."""
    frame = frame - frame.mean()
    if not np.any(frame):
        return 0.0
    corr = np.correlate(frame, frame, mode="full")[len(frame) - 1:]
    if corr[0] <= 0:
        return 0.0
    lag_min = int(sr / F0_MAX)
    lag_max = min(int(sr / F0_MIN), len(corr) - 1)
    if lag_max <= lag_min:
        return 0.0
    segment = corr[lag_min:lag_max]
    peak = int(np.argmax(segment)) + lag_min
    # Zayif periyodiklik => sesli harf degil (gurultu/sessiz)
    if corr[peak] < 0.3 * corr[0]:
        return 0.0
    return sr / peak


def analyze_channel(x: np.ndarray, sr: int, offset_sec: float = 0.0) -> SpeakerAcoustics:
    """Tek konusmacinin sinyalinden akustik olcumler cikar."""
    out = SpeakerAcoustics()
    frames, hop = _frames(x, sr)
    if len(frames) == 0:
        return out

    rms = np.sqrt(np.mean(frames**2, axis=1))
    voiced = rms > SILENCE_RMS
    if not voiced.any():
        return out

    out.voiced_sec = round(float(voiced.sum()) * hop / sr, 1)
    out.loudness_mean = round(float(rms[voiced].mean()), 4)
    out.loudness_max = round(float(rms.max()), 4)

    # Pitch yalnizca sesli cercevelerde (her cerceve pahali; seyrek ornekle)
    step = max(1, len(frames) // 400)
    f0s = []
    for i in range(0, len(frames), step):
        if voiced[i]:
            f0 = _f0_autocorr(frames[i], sr)
            if F0_MIN <= f0 <= F0_MAX:
                f0s.append(f0)
    if f0s:
        arr = np.array(f0s)
        out.pitch_mean = round(float(arr.mean()), 1)
        out.pitch_std = round(float(arr.std()), 1)
        # Monotonluk: tonlama sapmasi ortalamanin %8'inden azsa robotik/duz konusma
        out.monotone = bool(out.pitch_std < max(8.0, out.pitch_mean * 0.08))

    # Bagirma: konusmacinin KENDI normaline gore (mutlak esik degil — mikrofon/
    # hat seviyesi kisiye gore degisir)
    baseline = float(np.median(rms[voiced]))
    if baseline > 0:
        loud = rms > baseline * SHOUT_RATIO
        run = 0
        for i, is_loud in enumerate(loud):
            if is_loud and voiced[i]:
                run += 1
                if run == SHOUT_MIN_FRAMES:
                    ts = offset_sec + (i - SHOUT_MIN_FRAMES + 1) * hop / sr
                    out.shout_moments.append(round(ts, 1))
            else:
                run = 0
    return out


def _to_dict(prefix: str, a: SpeakerAcoustics) -> dict:
    return {
        f"{prefix}_pitch_hz": a.pitch_mean,
        f"{prefix}_tonlama_sapmasi": a.pitch_std,
        f"{prefix}_monoton": a.monotone,
        f"{prefix}_ses_seviyesi": a.loudness_mean,
        f"{prefix}_bagirma_sayisi": len(a.shout_moments),
        f"{prefix}_bagirma_anlari": a.shout_moments[:10],
    }


def analyze(audio_path: str, segments: list[dict]) -> dict:
    """Cagrinin akustik metriklerini dondur. Hata olursa BOS dondurur (pipeline dusmez).

    segments: [{speaker, start, end, text}] — mono dosyada konusmaci ayrimi icin.
    """
    path = Path(audio_path)
    if not audio_path or not path.is_file():
        return {}
    try:
        info = audio.probe(path)
        if info.channels >= 2:
            return _analyze_stereo(path)
        return _analyze_mono(path, segments)
    except Exception as exc:  # akustik analiz asla puanlamayi dusurmez
        logger.warning("Akustik analiz atlandi (%s): %s", path.name, exc)
        return {}


def _analyze_stereo(path: Path) -> dict:
    import tempfile

    with tempfile.TemporaryDirectory(prefix="kg_ac_") as tmp:
        left, right = audio.split_stereo(path, tmp)
        cust, sr_c = _read_wav_mono(left)
        agent, sr_a = _read_wav_mono(right)
        out = {}
        out.update(_to_dict("musteri", analyze_channel(cust, sr_c)))
        out.update(_to_dict("temsilci", analyze_channel(agent, sr_a)))
        return out


def _analyze_mono(path: Path, segments: list[dict]) -> dict:
    import tempfile

    if not segments:
        return {}
    with tempfile.TemporaryDirectory(prefix="kg_ac_") as tmp:
        mono = audio.to_mono16k(path, tmp)
        x, sr = _read_wav_mono(mono)

    out = {}
    for speaker, prefix in (("musteri", "musteri"), ("temsilci", "temsilci")):
        pieces, shouts = [], []
        for seg in segments:
            if seg.get("speaker") != speaker:
                continue
            a, b = int(seg["start"] * sr), int(seg["end"] * sr)
            chunk = x[max(0, a):min(len(x), b)]
            if len(chunk) > sr // 10:
                pieces.append(chunk)
                part = analyze_channel(chunk, sr, offset_sec=seg["start"])
                shouts.extend(part.shout_moments)
        if not pieces:
            continue
        merged = analyze_channel(np.concatenate(pieces), sr)
        merged.shout_moments = sorted(shouts)[:10]
        out.update(_to_dict(prefix, merged))
    return out


def acoustic_risky_moments(metrics: dict) -> list[dict]:
    """Akustik bulgulari 'riskli an' formatina cevir (dashboard'da timestamp'li)."""
    risky: list[dict] = []
    for ts in (metrics.get("temsilci_bagirma_anlari") or [])[:5]:
        risky.append({
            "zaman": ts, "onem": "yuksek",
            "aciklama": "Temsilcinin ses tonu belirgin sekilde yukseldi (bagirma tespiti).",
        })
    for ts in (metrics.get("musteri_bagirma_anlari") or [])[:5]:
        risky.append({
            "zaman": ts, "onem": "orta",
            "aciklama": "Musteri sesini yukseltti — gerginlik/ofke isareti.",
        })
    return risky
