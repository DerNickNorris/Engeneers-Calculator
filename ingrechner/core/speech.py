"""Offline-Spracherkennung mit faster-whisper.

* Läuft komplett lokal (CPU, int8) – es werden keine Audiodaten verschickt.
* Das Modell wird einmalig heruntergeladen (Einstellungen) oder von der IT als
  Ordner bereitgestellt (für Rechner ohne Internet).
* ``faster-whisper`` ist optional: Fehlt es, bleibt die App voll nutzbar, nur die
  Diktat-Schaltflächen sind deaktiviert.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .audio import SAMPLE_RATE, load_audio


@dataclass(frozen=True)
class ModelInfo:
    key: str        # Name für faster_whisper.download_model
    label: str
    size: str
    hint: str


MODELS = [
    ModelInfo("base", "Base", "≈ 150 MB", "sehr schnell, für kurze Diktate auf schwachen PCs"),
    ModelInfo("small", "Small", "≈ 480 MB", "guter Kompromiss – Empfehlung für Büro-PCs"),
    ModelInfo("medium", "Medium", "≈ 1,5 GB", "genauer, deutlich langsamer"),
    ModelInfo("large-v3-turbo", "Large v3 Turbo", "≈ 1,6 GB", "beste Erkennung, für leistungsstarke PCs"),
]
DEFAULT_MODEL = "small"
MODEL_FILES = ("model.bin", "config.json", "tokenizer.json")


class SpeechError(RuntimeError):
    pass


def available() -> bool:
    try:
        import faster_whisper  # noqa: F401
    except ImportError:
        return False
    return True


def model_dir(base: str | Path, key: str) -> Path:
    return Path(base) / f"faster-whisper-{key}"


def is_model_ready(path: str | Path) -> bool:
    p = Path(path)
    return p.is_dir() and all((p / f).exists() for f in MODEL_FILES)


def download(key: str, base: str | Path) -> Path:
    """Lädt das Modell einmalig herunter (benötigt Internet)."""
    if not available():
        raise SpeechError("Die Spracherkennung (faster-whisper) ist nicht installiert.")
    from faster_whisper import download_model

    target = model_dir(base, key)
    target.mkdir(parents=True, exist_ok=True)
    try:
        download_model(key, output_dir=str(target))
    except Exception as exc:  # Netzwerkfehler, Proxy, Speicherplatz …
        raise SpeechError(f"Download fehlgeschlagen: {exc}") from exc
    if not is_model_ready(target):
        raise SpeechError("Download unvollständig – bitte erneut versuchen.")
    return target


def build_prompt(glossary: str) -> str | None:
    """Fachbegriffe als Kontext: verbessert die Schreibweise von Fachwörtern."""
    terms = [t.strip() for t in glossary.replace("\n", ",").split(",") if t.strip()]
    if not terms:
        return None
    return "Besprechungsprotokoll. Fachbegriffe: " + ", ".join(terms[:80]) + "."


class SpeechEngine:
    """Hält ein geladenes Modell (Laden dauert einige Sekunden) und transkribiert."""

    _lock = threading.Lock()

    def __init__(self, path: str | Path, threads: int = 0) -> None:
        if not available():
            raise SpeechError("Die Spracherkennung (faster-whisper) ist nicht installiert.")
        if not is_model_ready(path):
            raise SpeechError("Kein Sprachmodell vorhanden – bitte unter Extras › Einstellungen "
                              "herunterladen oder einen Modellordner wählen.")
        from faster_whisper import WhisperModel

        self.path = Path(path)
        self.model = WhisperModel(str(self.path), device="cpu", compute_type="int8", cpu_threads=threads)

    def transcribe(self, audio: np.ndarray | str | Path, glossary: str = "", language: str = "de",
                   progress: Callable[[float], None] | None = None,
                   cancelled: Callable[[], bool] | None = None) -> str:
        """Gibt den erkannten Text zurück. ``audio``: float32-Array (16 kHz) oder Dateipfad."""
        if not isinstance(audio, np.ndarray):
            audio = load_audio(audio)
        audio = np.asarray(audio, dtype=np.float32)
        duration = audio.size / SAMPLE_RATE
        if duration < 0.3:
            return ""
        with self._lock:  # ein Modell, eine Transkription gleichzeitig
            segments, _info = self.model.transcribe(
                audio, language=language, beam_size=5, vad_filter=True,
                initial_prompt=build_prompt(glossary), condition_on_previous_text=False)
            parts = []
            for seg in segments:
                parts.append(seg.text.strip())
                if progress and duration:
                    progress(min(1.0, seg.end / duration))
                if cancelled and cancelled():
                    break
        return tidy(" ".join(p for p in parts if p))


def tidy(text: str) -> str:
    """Leerzeichen bereinigen, ersten Buchstaben groß schreiben."""
    text = " ".join(text.split())
    for p in (" ,", " .", " ?", " !", " :"):
        text = text.replace(p, p.strip())
    return text[:1].upper() + text[1:] if text else text
