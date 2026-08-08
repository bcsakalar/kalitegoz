"""Konusmaci ayrimi + transkripsiyon.

Strateji:
1. Stereo kayit  -> kanal ayrimi (sol=musteri, sag=temsilci). pyannote'a HIC girilmez.
2. Mono + HF_TOKEN -> pyannote diarization + whisper segmentlerini hizalama.
   Ilk konusan konusmaci temsilci kabul edilir (cagri merkezinde acilisi temsilci yapar).
3. Mono, token yok -> tek konusmaci, speaker='bilinmeyen'.
"""

import logging
import tempfile
from pathlib import Path

from ..config import settings
from . import audio, stt

logger = logging.getLogger(__name__)

MUSTERI = "musteri"
TEMSILCI = "temsilci"
BILINMEYEN = "bilinmeyen"


def diarize_and_transcribe(path: str | Path) -> list[dict]:
    """[{speaker, start, end, text}] listesi dondurur (zamana gore sirali)."""
    info = audio.probe(path)
    with tempfile.TemporaryDirectory(prefix="kalitegoz_") as tmp:
        if info.channels >= 2:
            return _stereo(path, tmp)
        return _mono(path, tmp)


def _stereo(path: str | Path, tmp: str) -> list[dict]:
    left, right = audio.split_stereo(path, tmp)
    segments = []
    for wav, speaker in ((left, MUSTERI), (right, TEMSILCI)):
        for seg in stt.transcribe(wav):
            seg["speaker"] = speaker
            segments.append(seg)
    segments.sort(key=lambda s: (s["start"], s["end"]))
    return segments


def _mono(path: str | Path, tmp: str) -> list[dict]:
    mono = audio.to_mono16k(path, tmp)
    segments = stt.transcribe(mono)

    turns = _pyannote_turns(mono) if settings.hf_token else None
    if not turns:
        if settings.hf_token:
            logger.warning("pyannote calistirilamadi, tek konusmaci varsayiliyor")
        for seg in segments:
            seg["speaker"] = BILINMEYEN
        return segments

    # Ilk konusan pyannote etiketi -> temsilci, digerleri -> musteri
    first_label = turns[0][2]
    for seg in segments:
        seg["speaker"] = _dominant_speaker(seg, turns, first_label)
    return segments


def _pyannote_turns(wav_path: Path) -> list[tuple[float, float, str]] | None:
    try:
        from pyannote.audio import Pipeline  # opsiyonel bagimlilik
    except ImportError:
        logger.warning(
            "pyannote.audio kurulu degil (requirements-diarization.txt); "
            "mono kayit tek konusmaci olarak islenecek"
        )
        return None
    try:
        pipeline = Pipeline.from_pretrained(
            settings.pyannote_model, use_auth_token=settings.hf_token
        )
        diarization = pipeline(str(wav_path))
        turns = [
            (turn.start, turn.end, label)
            for turn, _, label in diarization.itertracks(yield_label=True)
        ]
        turns.sort(key=lambda t: t[0])
        return turns or None
    except Exception as exc:
        logger.warning("pyannote hatasi: %s", exc)
        return None


def _dominant_speaker(seg: dict, turns: list[tuple[float, float, str]], first_label: str) -> str:
    """Whisper segmentiyle en cok ortusen pyannote konusmacisini bul."""
    overlaps: dict[str, float] = {}
    for start, end, label in turns:
        ov = min(seg["end"], end) - max(seg["start"], start)
        if ov > 0:
            overlaps[label] = overlaps.get(label, 0.0) + ov
    if not overlaps:
        return BILINMEYEN
    best = max(overlaps, key=overlaps.get)
    return TEMSILCI if best == first_label else MUSTERI
