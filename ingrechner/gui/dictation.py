"""Diktat: Mikrofonaufnahme (Qt Multimedia) + Offline-Erkennung (faster-whisper) im Hintergrund."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from pathlib import Path

import numpy as np
from PySide6.QtCore import QObject, QThread, QTimer, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (QFileDialog, QLineEdit, QMenu, QMessageBox, QPlainTextEdit, QTextEdit,
                               QToolButton, QWidget)

from ingrechner.core import speech
from ingrechner.core.audio import pcm_to_float, resample

from .theme import C

SILENCE_PEAK = 0.002   # Spitzenpegel darunter = praktisch Stille (Mikrofon gesperrt/stumm)
NO_SIGNAL_HELP = (
    "Das Mikrofon hat nur Stille geliefert. Häufige Ursachen unter Windows:\n\n"
    "1. Datenschutz: Einstellungen › Datenschutz und Sicherheit › Mikrofon › "
    "„Mikrofonzugriff“ und „Desktop-Apps den Zugriff auf das Mikrofon erlauben“ einschalten.\n"
    "2. Falsches Gerät: Einstellungen › System › Sound › Eingabe – das richtige Mikrofon als "
    "Standard wählen und den Pegel beim Sprechen prüfen.\n"
    "3. Mikrofon stummgeschaltet (Taste am Headset/Laptop) oder Lautstärke auf 0.\n\n"
    "Danach die App neu starten und erneut diktieren.")
AUDIO_FILTER = "Audiodateien (*.wav *.mp3 *.m4a *.ogg *.flac *.aac *.wma *.opus);;Alle Dateien (*)"


def qt_samples_to_float(data: bytes, sample_format, channels: int) -> np.ndarray:
    """Qt-Rohdaten (abhängig vom Gerät) in float32 Mono umwandeln."""
    from PySide6.QtMultimedia import QAudioFormat

    if sample_format == QAudioFormat.Float:
        arr = np.frombuffer(data[: len(data) - len(data) % 4], dtype="<f4").astype(np.float32)
        if channels > 1:
            arr = arr[: arr.size - arr.size % channels].reshape(-1, channels).mean(axis=1)
        return arr
    width = {QAudioFormat.Int16: 2, QAudioFormat.Int32: 4, QAudioFormat.UInt8: 1}.get(sample_format)
    if width is None:
        raise speech.SpeechError("Das Mikrofon liefert ein nicht unterstütztes Audioformat.")
    frame = width * channels
    return pcm_to_float(data[: len(data) - len(data) % frame], width, channels)


class AudioRecorder(QObject):
    """Nimmt vom Standard-Mikrofon auf; ``stop()`` liefert 16-kHz-Mono-float32."""

    level = Signal(float)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._src = None
        self._io = None
        self._buf = bytearray()
        self._fmt = None
        self.started_at = 0.0

    @property
    def active(self) -> bool:
        return self._src is not None

    def start(self) -> None:
        from PySide6.QtMultimedia import QAudioFormat, QAudioSource, QMediaDevices

        device = QMediaDevices.defaultAudioInput()
        if device.isNull():
            raise speech.SpeechError("Kein Mikrofon gefunden. Bitte ein Mikrofon anschließen und in "
                                     "Windows als Standard-Aufnahmegerät auswählen.")
        fmt = QAudioFormat()
        fmt.setSampleRate(speech.SAMPLE_RATE)
        fmt.setChannelCount(1)
        fmt.setSampleFormat(QAudioFormat.Int16)
        if not device.isFormatSupported(fmt):
            fmt = device.preferredFormat()
        self._fmt = fmt
        self._buf = bytearray()
        self._src = QAudioSource(device, fmt, self)
        self._io = self._src.start()
        if self._io is None:
            self._src = None
            raise speech.SpeechError("Das Mikrofon konnte nicht geöffnet werden (Datenschutz-Einstellungen "
                                     "von Windows prüfen: Mikrofonzugriff für Desktop-Apps erlauben).")
        self._io.readyRead.connect(self._read)
        self.started_at = time.monotonic()

    def _read(self) -> None:
        if self._io is None:
            return
        chunk = bytes(self._io.readAll().data())
        if not chunk:
            return
        self._buf += chunk
        try:
            samples = qt_samples_to_float(chunk, self._fmt.sampleFormat(), self._fmt.channelCount())
            if samples.size:
                self.level.emit(float(min(1.0, np.sqrt(np.mean(samples ** 2)) * 4)))
        except speech.SpeechError:
            pass

    def stop(self) -> np.ndarray:
        if self._src is None:
            return np.zeros(0, np.float32)
        self._read()
        self._src.stop()
        self._src.deleteLater()
        self._src, self._io = None, None
        samples = qt_samples_to_float(bytes(self._buf), self._fmt.sampleFormat(), self._fmt.channelCount())
        self._buf = bytearray()
        return resample(samples, self._fmt.sampleRate())


class _Job(QThread):
    done = Signal(str)
    failed = Signal(str)

    def __init__(self, service: SpeechService, audio, parent=None) -> None:
        super().__init__(parent)
        self.service, self.audio = service, audio

    def run(self) -> None:
        try:
            engine = self.service.engine()
            text = engine.transcribe(self.audio, glossary=self.service.ctx.speech_glossary)
        except Exception as exc:  # noqa: BLE001 - Fehler sichtbar machen statt abstürzen
            self.failed.emit(str(exc))
            return
        self.done.emit(text)


class SpeechService(QObject):
    """Ein Modell für die ganze App; lädt beim ersten Diktat (im Hintergrund)."""

    busy_changed = Signal(bool)

    def __init__(self, ctx) -> None:
        super().__init__()
        self.ctx = ctx
        self._engine = None
        self._engine_path = None
        self._lock = threading.Lock()
        self.recorder = AudioRecorder(self)
        self.active_button: DictateButton | None = None
        self._jobs: set[_Job] = set()

    def status(self) -> tuple[bool, str]:
        if not speech.available():
            return False, "Spracherkennung nicht installiert (Paket faster-whisper fehlt)."
        path = self.ctx.speech_model_path
        if not path or not speech.is_model_ready(path):
            return False, "Kein Sprachmodell eingerichtet – unter Extras › Einstellungen › Diktat herunterladen."
        return True, f"Bereit: {path.name}"

    def engine(self) -> speech.SpeechEngine:
        path = self.ctx.speech_model_path
        with self._lock:
            if self._engine is None or self._engine_path != path:
                if path is None:
                    raise speech.SpeechError("Kein Sprachmodell eingerichtet.")
                self._engine = speech.SpeechEngine(path)
                self._engine_path = path
            return self._engine

    def transcribe_async(self, audio, on_done: Callable[[str], None], on_fail: Callable[[str], None]) -> _Job:
        job = _Job(self, audio)
        self._jobs.add(job)

        def cleanup():
            self._jobs.discard(job)
            job.deleteLater()

        job.done.connect(on_done)
        job.failed.connect(on_fail)
        job.finished.connect(cleanup)
        job.start()
        return job

    def wait_idle(self, timeout_ms: int = 60000) -> None:
        for job in list(self._jobs):
            job.wait(timeout_ms)


def insert_text(target: QWidget, text: str) -> None:
    """Text an der Cursorposition einfügen, mit sinnvollem Leerzeichen davor."""
    if not text:
        return
    if isinstance(target, (QPlainTextEdit, QTextEdit)):
        cur = target.textCursor()
        before = target.toPlainText()[: cur.position()]
        sep = "" if not before or before[-1] in " \n" else " "
        cur.insertText(sep + text)
        target.setTextCursor(cur)
    elif isinstance(target, QLineEdit):
        pos = target.cursorPosition()
        before = target.text()[:pos]
        sep = "" if not before or before.endswith(" ") else " "
        target.insert(sep + text)


class DictateButton(QToolButton):
    """🎤 Klick = Aufnahme starten/stoppen. Pfeil-Menü: Audiodatei transkribieren.

    ``target``: Textfeld, in das eingefügt wird; alternativ ``on_text``-Callback.
    """

    def __init__(self, ctx, target: QWidget | None = None, on_text: Callable[[str], None] | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        self.target = target
        self.on_text = on_text
        self.state = "idle"
        self.setPopupMode(QToolButton.MenuButtonPopup)
        menu = QMenu(self)
        act = QAction("Audiodatei transkribieren …", self)
        act.triggered.connect(self.transcribe_file)
        menu.addAction(act)
        self.setMenu(menu)
        self.clicked.connect(self.toggle)
        self._timer = QTimer(self)
        self._timer.setInterval(250)
        self._timer.timeout.connect(self._tick)
        self._level = 0.0
        self._idle_look()

    # -------------------------------------------------------------- Look
    def _idle_look(self) -> None:
        self.state = "idle"
        self.setEnabled(True)
        self.setText("🎤 Diktat")
        self.setToolTip("Diktat starten (offline). Erneut klicken zum Beenden.\n"
                        "Pfeil: vorhandene Audiodatei transkribieren.")
        self.setStyleSheet("")

    def _tick(self) -> None:
        secs = int(time.monotonic() - self.ctx.speech.recorder.started_at)
        bars = "▮" * max(1, int(self._level * 5)) + "▯" * (5 - max(1, int(self._level * 5)))
        self.setText(f"■ Stopp {secs // 60}:{secs % 60:02d} {bars}")

    def _set_level(self, v: float) -> None:
        self._level = v

    # ------------------------------------------------------------ Aktionen
    def _ensure_ready(self) -> bool:
        ok, msg = self.ctx.speech.status()
        if ok:
            return True
        win = self.window()
        r = QMessageBox.question(self, "Diktat nicht eingerichtet", f"{msg}\n\nEinstellungen jetzt öffnen?")
        if r == QMessageBox.Yes and hasattr(win, "edit_settings"):
            win.edit_settings(tab="diktat")
        return self.ctx.speech.status()[0]

    def toggle(self) -> None:
        if self.state == "recording":
            self.stop()
        elif self.state == "idle":
            self.start()

    def start(self) -> None:
        if not self._ensure_ready():
            return
        svc = self.ctx.speech
        if svc.active_button is not None and svc.active_button is not self:
            svc.active_button.stop()  # nur eine Aufnahme gleichzeitig
        try:
            svc.recorder.start()
        except speech.SpeechError as exc:
            QMessageBox.warning(self, "Diktat", str(exc))
            return
        except Exception as exc:  # noqa: BLE001 - z. B. fehlende Multimedia-Bibliotheken
            from .errors import format_error, write_log

            import sys

            path = write_log(format_error(*sys.exc_info()))
            QMessageBox.critical(self, "Diktat", "Die Mikrofonaufnahme konnte nicht gestartet werden:\n"
                                 f"{type(exc).__name__}: {exc}" + (f"\n\nDetails: {path}" if path else ""))
            return
        svc.active_button = self
        svc.recorder.level.connect(self._set_level)
        self._level_connected = True
        self.state = "recording"
        self.setStyleSheet(f"QToolButton {{ color: white; background: {C['error']}; border-radius: 5px; "
                           f"padding: 4px 8px; font-weight: 600; }}")
        self._tick()
        self._timer.start()

    def stop(self) -> None:
        if self.state != "recording":
            return
        svc = self.ctx.speech
        self._timer.stop()
        if getattr(self, "_level_connected", False):
            svc.recorder.level.disconnect(self._set_level)
            self._level_connected = False
        audio = svc.recorder.stop()
        svc.active_button = None
        if audio.size and float(np.abs(audio).max()) < SILENCE_PEAK:
            self._idle_look()
            QMessageBox.warning(self, "Diktat – kein Signal", NO_SIGNAL_HELP)
            return
        self._run(audio)

    def transcribe_file(self) -> None:
        if self.state != "idle" or not self._ensure_ready():
            return
        start = str(self.ctx.settings.value("lastAudioDir", ""))
        path, _ = QFileDialog.getOpenFileName(self, "Audiodatei transkribieren", start, AUDIO_FILTER)
        if path:
            self.ctx.settings.setValue("lastAudioDir", str(Path(path).parent))
            self._run(path)

    def _run(self, audio) -> None:
        self.state = "busy"
        self.setEnabled(False)
        self.setText("⏳ Erkenne Sprache …")
        self.setStyleSheet("")
        win = self.window()
        if hasattr(win, "statusBar"):
            win.statusBar().showMessage("Spracherkennung läuft (offline) …")
        self.ctx.speech.transcribe_async(audio, self._done, self._failed)

    def _done(self, text: str) -> None:
        self._idle_look()
        win = self.window()
        if not text.strip():
            if hasattr(win, "statusBar"):
                win.statusBar().showMessage("Keine Sprache erkannt.", 5000)
            return
        if self.on_text:
            self.on_text(text)
        elif self.target is not None:
            insert_text(self.target, text)
            self.target.setFocus()
        if hasattr(win, "statusBar"):
            win.statusBar().showMessage(f"Diktat eingefügt ({len(text.split())} Wörter).", 5000)

    def _failed(self, message: str) -> None:
        self._idle_look()
        QMessageBox.warning(self, "Spracherkennung", f"Die Spracherkennung ist fehlgeschlagen:\n{message}")
