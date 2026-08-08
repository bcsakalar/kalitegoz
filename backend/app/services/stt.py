"""faster-whisper tabanli STT. Model tembel yuklenir ve process icinde tek kopyadir."""

import logging
import threading
from pathlib import Path

from ..config import settings

logger = logging.getLogger(__name__)

_model = None
_lock = threading.Lock()


def get_model():
    global _model
    if _model is not None:
        return _model
    with _lock:
        if _model is not None:
            return _model
        from faster_whisper import WhisperModel

        device = settings.whisper_device
        candidates = ["cuda", "cpu"] if device == "auto" else [device]
        last_err: Exception | None = None
        for dev in candidates:
            compute = settings.whisper_compute_type if dev == "cuda" else "int8"
            try:
                logger.info("Whisper yukleniyor: %s / %s / %s", settings.whisper_model, dev, compute)
                _model = WhisperModel(settings.whisper_model, device=dev, compute_type=compute)
                return _model
            except Exception as exc:  # CUDA yoksa CPU'ya dus
                logger.warning("Whisper %s ile yuklenemedi: %s", dev, exc)
                last_err = exc
        raise RuntimeError(f"Whisper modeli yuklenemedi: {last_err}")


def transcribe(path: str | Path) -> list[dict]:
    """Dosyayi coz ve [{start, end, text}] listesi dondur.

    8kHz telefon sesi icin: whisper girisi zaten 16k'ya resample edilmis mono
    dosyalardir (audio.py), VAD filtresi telefon hattindaki bos/gurultulu
    bolumleri ayiklar.
    """
    model = get_model()
    segments, _info = model.transcribe(
        str(path),
        language=settings.stt_language,
        beam_size=5,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 400},
        condition_on_previous_text=False,
    )
    out = []
    for seg in segments:
        text = seg.text.strip()
        if not text:
            continue
        out.append({"start": round(seg.start, 2), "end": round(seg.end, 2), "text": text})
    return out
