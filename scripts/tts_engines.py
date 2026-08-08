"""KaliteGoz demo TTS motorlari — GERCEK kadin/erkek sesli seslendirme.

Neden iki motor?
----------------
Piper'in resmi VOICES.md dokumani uc Turkce ses listeler (dfki, fahrettin,
fettah) ama HuggingFace rhasspy/piper-voices deposunda GERCEKTE yalnizca
`dfki` yuklu — digerlerine istek 404 doner (dogrulandi: 2026-07).

Ve kritik olan: dfki bir ERKEK sesidir. Olculen medyan F0 ~108 Hz (iki bagimsiz
yontemle dogrulandi: otokorelasyon 104 Hz, spektral harmonik araligi 108 Hz) —
Ahmet'ten (137 Hz) bile kalin. Eski kod bunu KADIN sanip kadin konusmaci icin
1.06 ile carpiyordu; sonuc ~114 Hz, yani HALA ERKEK. Bu yuzden demoda "iki
konusmaci da erkek" duyuluyordu.

Tek erkek modelden inandirici bir kadin sesi cikarilamaz: 108 -> ~190 Hz icin
~1.75 faktor gerekir, bu da formantlari bozar VE (resample tempo'yu da
kaydirdigi icin) konusmayi %75 hizlandirir. Yani Piper yolunda GERCEK cinsiyet
ayrimi MUMKUN DEGILDIR — bu bilinen ve kabul edilen bir sinirdir.

Cozum: edge-tts (Microsoft Edge'in online TTS servisi) — API anahtari
gerektirmez, model indirmez ve Turkce icin GERCEKTEN iki ayri konusmaci
sunar:
    tr-TR-EmelNeural   -> Female  (olculen medyan F0 ~199 Hz)
    tr-TR-AhmetNeural  -> Male    (olculen medyan F0 ~137 Hz)

Piper motoru yine de korunur: edge-tts internet ister; internetsiz ortamda
(CI, air-gapped kurulum) demo yine URETILEBILSIN diye `piper` motoru offline
fallback olarak durur — ama yukarida acikladigimiz gibi cinsiyetleri DOGRU
veremez, yalnizca iki konusmaciyi hafifce ayirir. Varsayilan `auto`: edge
dene, olmazsa piper (ve yuksek sesle uyar).

Kullanim:
    from tts_engines import make_engine
    eng = make_engine("auto", voices_dir)
    audio, sr = eng.tts("Merhaba", gender="kadin", speaker="ayse.yilmaz")
"""

from __future__ import annotations

import hashlib
import io
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
import wave
from pathlib import Path

import numpy as np

__all__ = ["make_engine", "EdgeEngine", "PiperEngine", "TTSError"]


class TTSError(RuntimeError):
    pass


# =====================================================================
# Konusmaci varyantlari
# =====================================================================
# Tek bir kadin sesi (Emel) 7 farkli kadin temsilci icin kullanilirsa tum
# temsilciler ayni insana benzer; diarization/temsilci ayrimi demolarinda
# bu inandiriciligi bozar. Cozum: her konusmaciya adindan TURETILEN kucuk
# ve DETERMINISTIK bir prosodi ofseti (hiz + ton) ver. Ofsetler bilerek
# dar tutuldu — buyuk kaydirmalar tam da kacindigimiz formant bozulmasini
# geri getirirdi.
_RATE_STEPS = (-6, -3, 0, 3, 6, 9)        # yuzde
_PITCH_STEPS = (-16, -8, 0, 8, 16)        # Hz
# Ayni cagrida ayni cinsiyetten iki kisi icin ISTENEN en kucuk ton farki.
# 16 Hz secildi cunku edge-tts'in `pitch` parametresi MUTLAK degil, prosodi
# ipucudur: olculen sonuc istenenin ~0.75 katidir (8 Hz istendiginde gercekte
# ~6 Hz olculdu — ayirt etmek icin zayif). 16 Hz istendiginde ~12 Hz gerceklesir
# ve erkek ses 121-153 Hz araliginda kalarak erkek kalir.
MIN_PITCH_GAP = 16                         # Hz


def speaker_variant(speaker: str, avoid_pitch: int | None = None) -> tuple[int, int]:
    """Konusmaci adindan (rate%, pitchHz) ofseti — ayni ad hep ayni ses.

    avoid_pitch verilirse sonucun tonu ondan en az MIN_PITCH_GAP kadar uzak
    olmasi GARANTI edilir. Bu, ayni cagrida ayni cinsiyetten iki kisi (orn.
    erkek temsilci + erkek musteri) konustugunda gerekir: ikisi ayni tonu
    alirsa kanal ayrimi demosu "tek kisi konusuyor" gibi gorunur.

    Cakisma notu: hash tabanli secim, konusmaci sayisi grid'e (6x5=30) yaklastikca
    FARKLI konusmacilara ayni varyanti verebilir (guvercin yuvasi). Bu, ayni
    cagrida bulunmayan iki temsilci icin zararsizdir — yan yana duyulmazlar.
    Ayni cagri icindeki ayrim ise avoid_pitch ile kesin olarak saglanir.
    """
    if not speaker:
        return 0, 0
    h = hashlib.sha256(speaker.encode("utf-8")).digest()
    rate = _RATE_STEPS[h[0] % len(_RATE_STEPS)]
    idx = h[1] % len(_PITCH_STEPS)
    pitch = _PITCH_STEPS[idx]
    if avoid_pitch is not None and abs(pitch - avoid_pitch) < MIN_PITCH_GAP:
        # Deterministik olarak grid'de ilerleyip yeterince uzak ilk tonu sec.
        for k in range(1, len(_PITCH_STEPS)):
            cand = _PITCH_STEPS[(idx + k) % len(_PITCH_STEPS)]
            if abs(cand - avoid_pitch) >= MIN_PITCH_GAP:
                pitch = cand
                break
    return rate, pitch


def _fmt_signed(value: int, unit: str) -> str:
    return f"{value:+d}{unit}"


# =====================================================================
# edge-tts motoru (varsayilan)
# =====================================================================

EDGE_VOICES = {
    "kadin": "tr-TR-EmelNeural",
    "erkek": "tr-TR-AhmetNeural",
}


class EdgeEngine:
    """Microsoft Edge online TTS. Gercek iki konusmaci, anahtar gerektirmez.

    Uretilen ses mp3 gelir; ffmpeg ile wav'e cozulur. Ayni metin+ses+prosodi
    kombinasyonu disk cache'lenir, boylece demo tekrar uretimi anlik olur.
    """

    name = "edge"

    def __init__(self, cache_dir: Path | None = None):
        try:
            import edge_tts  # noqa: F401
        except ImportError as exc:  # pragma: no cover - kurulum hatasi
            raise TTSError(
                "edge-tts kurulu degil. Kurulum: pip install -r scripts/requirements.txt"
            ) from exc
        if not shutil.which("ffmpeg"):
            raise TTSError(
                "edge-tts motoru mp3 cozmek icin ffmpeg ister; PATH'te bulunamadi. "
                "ffmpeg kurun veya --tts-engine piper kullanin."
            )
        self.cache_dir = cache_dir
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    # -- yardimcilar --------------------------------------------------
    def _cache_path(self, key: str) -> Path | None:
        if not self.cache_dir:
            return None
        return self.cache_dir / f"{key}.wav"

    @staticmethod
    def _decode_mp3(raw: bytes) -> tuple[np.ndarray, int]:
        """mp3 baytlarini ffmpeg ile 22050 Hz mono float32'ye cozer."""
        proc = subprocess.run(
            ["ffmpeg", "-loglevel", "error", "-i", "pipe:0",
             "-ar", "22050", "-ac", "1", "-f", "wav", "pipe:1"],
            input=raw, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        if proc.returncode != 0 or not proc.stdout:
            raise TTSError(f"ffmpeg mp3 cozemedi: {proc.stderr.decode(errors='replace')[:300]}")
        with wave.open(io.BytesIO(proc.stdout), "rb") as r:
            sr = r.getframerate()
            data = np.frombuffer(r.readframes(r.getnframes()), dtype=np.int16)
        return data.astype(np.float32) / 32768.0, sr

    def _synthesize(self, text: str, voice: str, rate: int, pitch: int) -> bytes:
        import asyncio

        import edge_tts

        async def run() -> bytes:
            comm = edge_tts.Communicate(
                text, voice,
                rate=_fmt_signed(rate, "%"),
                pitch=_fmt_signed(pitch, "Hz"),
            )
            buf = bytearray()
            async for chunk in comm.stream():
                if chunk["type"] == "audio":
                    buf.extend(chunk["data"])
            return bytes(buf)

        try:
            return asyncio.run(run())
        except Exception as exc:  # aglayla ilgili her sey
            raise TTSError(f"edge-tts sentez hatasi: {exc}") from exc

    # -- ortak arayuz -------------------------------------------------
    def tts(self, text: str, gender: str, speaker: str = "",
            avoid_pitch: int | None = None) -> tuple[np.ndarray, int]:
        voice = EDGE_VOICES[gender]
        rate, pitch = speaker_variant(speaker, avoid_pitch)
        key = hashlib.sha256(
            f"{voice}|{rate}|{pitch}|{text}".encode("utf-8")
        ).hexdigest()[:32]

        cached = self._cache_path(key)
        if cached and cached.is_file():
            with wave.open(str(cached), "rb") as r:
                sr = r.getframerate()
                data = np.frombuffer(r.readframes(r.getnframes()), dtype=np.int16)
            return data.astype(np.float32) / 32768.0, sr

        audio, sr = self._decode_mp3(self._synthesize(text, voice, rate, pitch))
        if cached:
            with wave.open(str(cached), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(sr)
                w.writeframes((np.clip(audio, -1, 1) * 32767).astype(np.int16).tobytes())
        return audio, sr


# =====================================================================
# Piper motoru (offline fallback)
# =====================================================================

HF_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main"
PIPER_MODEL = ("tr_TR-dfki-medium", "tr/tr_TR/dfki/medium")

# dfki ERKEK bir sestir (~108 Hz). Buradaki faktorler cinsiyet URETMEZ —
# uretemezler; yalnizca iki konusmaciyi ayirt edilebilir kilar.
#
# Neden daha buyuk bir kadin faktoru yok: `_pitch_shift` resample tabanlidir,
# yani tonu yukseltirken TEMPOYU da ayni oranda hizlandirir. Kadin araligina
# cikmak icin gereken ~1.75, konusmayi %75 hizlandirip anlasilmaz yapardi.
# Tempoyu koruyan bir kaydirma (phase vocoder / WSOLA) formantlari yine
# bozardi ve bu fallback icin orantisiz karmasiklik olurdu.
#
# Ozet: cevrimdisi demoda her iki konusmaci da erkek tinlar. Dogru cinsiyet
# icin edge-tts (varsayilan) kullanin.
PIPER_PITCH = {"kadin": 1.15, "erkek": 0.95}


def download_piper_voice(voices_dir: Path) -> Path:
    voices_dir.mkdir(parents=True, exist_ok=True)
    name, hf_dir = PIPER_MODEL
    onnx = voices_dir / f"{name}.onnx"
    cfg = voices_dir / f"{name}.onnx.json"
    for target, url in (
        (onnx, f"{HF_BASE}/{hf_dir}/{name}.onnx"),
        (cfg, f"{HF_BASE}/{hf_dir}/{name}.onnx.json"),
    ):
        if not target.exists():
            print(f"  indiriliyor: {url}")
            try:
                urllib.request.urlretrieve(url, target)
            except urllib.error.HTTPError as exc:
                target.unlink(missing_ok=True)
                raise TTSError(f"Piper ses modeli indirilemedi ({url}): {exc}") from exc
    return onnx


def _pitch_shift(x: np.ndarray, factor: float) -> np.ndarray:
    if abs(factor - 1.0) < 1e-3:
        return x
    n_out = int(round(len(x) / factor))
    return np.interp(
        np.linspace(0, len(x) - 1, n_out), np.arange(len(x)), x
    ).astype(np.float32)


class PiperEngine:
    """Cevrimdisi fallback: tek TR model (dfki) + pitch profili."""

    name = "piper"

    def __init__(self, voices_dir: Path):
        try:
            from piper import PiperVoice
        except ImportError as exc:
            raise TTSError(
                "piper-tts kurulu degil. Kurulum: pip install -r scripts/requirements.txt"
            ) from exc
        self.voice = PiperVoice.load(str(download_piper_voice(voices_dir)))

    def tts(self, text: str, gender: str, speaker: str = "",
            avoid_pitch: int | None = None) -> tuple[np.ndarray, int]:
        buf = io.BytesIO()
        wav = wave.open(buf, "wb")
        if hasattr(self.voice, "synthesize_wav"):  # piper >= 1.3
            self.voice.synthesize_wav(text, wav)
        else:  # piper-tts 1.2.x
            self.voice.synthesize(text, wav)
        wav.close()
        buf.seek(0)
        with wave.open(buf, "rb") as r:
            sr = r.getframerate()
            data = np.frombuffer(r.readframes(r.getnframes()), dtype=np.int16)
        audio = data.astype(np.float32) / 32768.0
        rate, pitch = speaker_variant(speaker, avoid_pitch)
        # Piper'da SSML yok; ton ofsetini de ayni resample ile vermek zorundayiz.
        # Ofset bilerek kucuk tutulur (16 Hz ~ %8) — buyugu formant bozar.
        factor = PIPER_PITCH[gender] * (1 + rate / 400.0) * (1 + pitch / 200.0)
        return _pitch_shift(audio, factor), sr


# =====================================================================
# Fabrika
# =====================================================================


def make_engine(kind: str, voices_dir: Path, cache_dir: Path | None = None):
    """kind: auto | edge | piper."""
    if kind == "edge":
        return EdgeEngine(cache_dir)
    if kind == "piper":
        return PiperEngine(voices_dir)
    if kind != "auto":
        raise ValueError(f"bilinmeyen TTS motoru: {kind}")

    try:
        eng = EdgeEngine(cache_dir)
        # Gercekten ses uretebiliyor mu? (internet/servis kontrolu)
        eng.tts("test", "kadin")
        return eng
    except TTSError as exc:
        print(f"  edge-tts kullanilamiyor ({exc}); Piper'a dusuluyor.", file=sys.stderr)
        print("  UYARI: HuggingFace'te tek TR Piper modeli var (dfki) ve o bir "
              "ERKEK sesi (~108 Hz). Cevrimdisi demoda KADIN TEMSILCILER DE "
              "ERKEK TINLAR — bu bir sinirlamadir, hata degil.", file=sys.stderr)
        print("  Dogru kadin/erkek ses icin internet baglantisi ile calistirin "
              "(edge-tts varsayilandir).", file=sys.stderr)
        return PiperEngine(voices_dir)
