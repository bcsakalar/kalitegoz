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


# Turkce dogal konusma ~2.5 kelime/sn. Bu esigin altina duesen bir segment,
# icine sessizlik katmis demektir (bkz. docs/v2/01-KOK-NEDEN.md §D).
MIN_WORDS_PER_SEC = 0.7
# Kelime zaman damgasi gelmeyen segmentleri kirparken kullanilan tahmini hiz.
ASSUMED_WORDS_PER_SEC = 2.5


def _clip_to_speech(seg, text: str) -> tuple[float, float]:
    """Segmentin GERCEK konusma sinirlarini bul.

    Whisper, arkasinda sessizlik olan bir segmentin `end` zamanini 30 sn'lik
    pencere sinirina dogru uzatir. Stereo cagrida her kanalda karsi taraf
    konusurken uzun sessizlik oldugu icin bu sisme devasa oluyordu: olculen
    ornek "Tamam, not aldim." = 3 kelime / 20.6 sn = 0.15 kelime/sn (gercegin
    ~17 kati). Sisen `end`, metrics.py'de sahte soz kesme uretiyor ve bu sahte
    sayi prompt'a "KESIN degerler" diye giriyordu (B3).

    Birincil cozum: kelime zaman damgalarindan ilk/son kelimeyi al.
    Yedek: kelime zamani yoksa kelime sayisina gore makul bir sureye kirp.
    """
    words = getattr(seg, "words", None)
    if words:
        timed = [w for w in words if w.start is not None and w.end is not None]
        if timed:
            return float(timed[0].start), float(timed[-1].end)

    start, end = float(seg.start), float(seg.end)
    n_words = len(text.split())
    dur = end - start
    if dur > 0 and n_words / dur < MIN_WORDS_PER_SEC:
        end = start + max(1.0, n_words / ASSUMED_WORDS_PER_SEC)
    return start, end


def transcribe(path: str | Path) -> list[dict]:
    """Dosyayi coz ve [{start, end, text}] listesi dondur.

    8kHz telefon sesi icin: whisper girisi zaten 16k'ya resample edilmis mono
    dosyalardir (audio.py), VAD filtresi telefon hattindaki bos/gurultulu
    bolumleri ayiklar.

    Zaman damgalari `_clip_to_speech` ile gercek konusma sinirlarina cekilir —
    aksi halde soz kesme/sessizlik/konusma orani metrikleri anlamsiz olur.
    """
    model = get_model()
    segments, _info = model.transcribe(
        str(path),
        language=settings.stt_language,
        beam_size=5,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 400},
        condition_on_previous_text=False,
        # Segment bitisini gercek konusma bitisine cekebilmek icin sart.
        word_timestamps=True,
    )
    out = []
    for seg in segments:
        text = seg.text.strip()
        if not text:
            continue
        start, end = _clip_to_speech(seg, text)
        if end <= start:
            end = start + 1.0
        out.append({"start": round(start, 2), "end": round(end, 2), "text": text})
    return out
