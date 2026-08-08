"""ffmpeg/ffprobe tabanli ses yardimcilari.

Agir ses kutuphanesi bagimliligi yerine ffmpeg subprocess kullanilir;
faster-whisper dosya yolunu dogrudan kabul eder.
"""

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np

AUDIO_EXTS = {".wav", ".mp3", ".m4a", ".ogg", ".flac"}


class AudioError(RuntimeError):
    pass


@dataclass
class AudioInfo:
    channels: int
    duration_sec: float
    sample_rate: int


def _run(cmd: list[str]) -> str:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise AudioError(f"{cmd[0]} hatasi: {proc.stderr[-800:]}")
    return proc.stdout


def read_mono_f32(path: str | Path) -> tuple[np.ndarray, int]:
    """Herhangi bir ses dosyasini mono float32 [-1,1] + ornekleme hizina cozer.

    Neden ffmpeg (Python `wave` degil): ffmpeg'in channelsplit'i kanala bir
    layout maskesi atadigi icin ciktisini WAVE_FORMAT_EXTENSIBLE (format 65534)
    olarak yazar; Python'un `wave` modulu bu alt-formati "unknown format: 65534"
    ile reddeder ve akustik analiz sessizce atlanirdi. ffmpeg her alt-formati
    okur, bu yuzden burada tek dogru arac odur.
    """
    proc = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path),
         "-ac", "1", "-f", "f32le", "-acodec", "pcm_f32le", "pipe:1"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        raise AudioError(f"ffmpeg cozemedi ({path}): {proc.stderr.decode(errors='replace')[-400:]}")
    data = np.frombuffer(proc.stdout, dtype=np.float32)
    sr = probe(path).sample_rate
    return data, sr


def probe(path: str | Path) -> AudioInfo:
    out = _run(
        [
            "ffprobe",
            "-v", "error",
            "-select_streams", "a:0",
            "-show_entries", "stream=channels,sample_rate,duration",
            "-show_entries", "format=duration",
            "-of", "json",
            str(path),
        ]
    )
    data = json.loads(out)
    streams = data.get("streams") or []
    if not streams:
        raise AudioError(f"Ses akisi bulunamadi: {path}")
    stream = streams[0]
    duration = stream.get("duration") or data.get("format", {}).get("duration") or 0
    return AudioInfo(
        channels=int(stream.get("channels", 1)),
        duration_sec=float(duration),
        sample_rate=int(stream.get("sample_rate", 8000)),
    )


def split_stereo(path: str | Path, workdir: str | Path) -> tuple[Path, Path]:
    """Stereo dosyayi 16k mono sol/sag kanallara ayirir (sol=musteri, sag=temsilci)."""
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    left = workdir / "left.wav"
    right = workdir / "right.wav"
    _run(
        [
            "ffmpeg", "-y", "-i", str(path),
            "-filter_complex", "[0:a]channelsplit=channel_layout=stereo[l][r]",
            "-map", "[l]", "-ar", "16000", "-c:a", "pcm_s16le", str(left),
            "-map", "[r]", "-ar", "16000", "-c:a", "pcm_s16le", str(right),
        ]
    )
    return left, right


def to_mono16k(path: str | Path, workdir: str | Path) -> Path:
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    out = workdir / "mono16k.wav"
    _run(
        [
            "ffmpeg", "-y", "-i", str(path),
            "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(out),
        ]
    )
    return out
