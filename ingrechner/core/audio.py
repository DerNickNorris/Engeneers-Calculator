"""Audio einlesen und auf 16 kHz Mono (float32) bringen – Eingangsformat für Whisper."""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

SAMPLE_RATE = 16_000


def resample(samples: np.ndarray, src_rate: int, dst_rate: int = SAMPLE_RATE) -> np.ndarray:
    """Lineare Interpolation – für Sprache ausreichend genau."""
    samples = np.asarray(samples, dtype=np.float32)
    if src_rate == dst_rate or samples.size == 0:
        return samples
    n_out = int(round(samples.size * dst_rate / src_rate))
    x_old = np.linspace(0.0, 1.0, num=samples.size, endpoint=False)
    x_new = np.linspace(0.0, 1.0, num=n_out, endpoint=False)
    return np.interp(x_new, x_old, samples).astype(np.float32)


def pcm_to_float(data: bytes, sample_width: int, channels: int) -> np.ndarray:
    """PCM-Rohdaten (8/16/32 bit) -> float32 Mono im Bereich −1 … 1."""
    if sample_width == 2:
        arr = np.frombuffer(data, dtype="<i2").astype(np.float32) / 32768.0
    elif sample_width == 4:
        arr = np.frombuffer(data, dtype="<i4").astype(np.float32) / 2147483648.0
    elif sample_width == 1:
        arr = (np.frombuffer(data, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
    else:
        raise ValueError(f"Nicht unterstützte Sample-Breite: {sample_width} Byte")
    if channels > 1:
        arr = arr[: arr.size - arr.size % channels].reshape(-1, channels).mean(axis=1)
    return arr


def load_audio(path: str | Path) -> np.ndarray:
    """Liest WAV direkt, andere Formate (mp3, m4a, ogg …) über PyAV."""
    path = Path(path)
    if path.suffix.lower() == ".wav":
        try:
            with wave.open(str(path), "rb") as wf:
                data = wf.readframes(wf.getnframes())
                arr = pcm_to_float(data, wf.getsampwidth(), wf.getnchannels())
                return resample(arr, wf.getframerate())
        except wave.Error:
            pass  # z. B. Float-WAV -> PyAV versuchen
    try:
        import av
    except ImportError as exc:
        raise RuntimeError("Für dieses Audioformat wird das Paket „av“ benötigt.") from exc
    chunks: list[np.ndarray] = []
    with av.open(str(path)) as container:
        stream = next((s for s in container.streams if s.type == "audio"), None)
        if stream is None:
            raise ValueError("Die Datei enthält keine Tonspur.")
        resampler = av.AudioResampler(format="flt", layout="mono", rate=SAMPLE_RATE)
        for frame in container.decode(stream):
            for out in resampler.resample(frame):
                chunks.append(out.to_ndarray().reshape(-1))
        for out in resampler.resample(None):
            chunks.append(out.to_ndarray().reshape(-1))
    return np.concatenate(chunks).astype(np.float32) if chunks else np.zeros(0, np.float32)


def save_wav(path: str | Path, samples: np.ndarray, rate: int = SAMPLE_RATE) -> None:
    pcm = (np.clip(samples, -1.0, 1.0) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(pcm.tobytes())
