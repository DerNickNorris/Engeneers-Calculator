"""Unerwartete Fehler sichtbar machen.

Die Windows-.exe hat kein Konsolenfenster: Ohne diesen Handler würden Fehler in
Qt-Ereignissen (z. B. beim Klick auf „Diktat“) unbemerkt verschwinden. Jetzt
erscheint ein Dialog, und die Details landen in einer Protokolldatei.
"""

from __future__ import annotations

import sys
import traceback
from datetime import datetime
from pathlib import Path

from ingrechner import __version__

LOG_NAME = "fehlerprotokoll.log"
_MAX_LOG_BYTES = 512_000


def log_path() -> Path:
    from .context import app_data_dir

    return app_data_dir() / LOG_NAME


def write_log(text: str, path: Path | None = None) -> Path | None:
    path = path or log_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.stat().st_size > _MAX_LOG_BYTES:
            path.replace(path.with_suffix(".alt.log"))
        with path.open("a", encoding="utf-8") as fh:
            fh.write(text)
        return path
    except OSError:
        return None


def format_error(exc_type, exc, tb) -> str:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    details = "".join(traceback.format_exception(exc_type, exc, tb))
    return f"=== {stamp} · Version {__version__} · {sys.platform}\n{details}\n"


def handle_exception(exc_type, exc, tb, show_dialog: bool = True, path: Path | None = None) -> str:
    """Schreibt den Fehler ins Protokoll und zeigt (optional) einen Dialog. Gibt den Text zurück."""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc, tb)
        return ""
    text = format_error(exc_type, exc, tb)
    written = write_log(text, path)
    try:
        sys.__stderr__.write(text)  # in der Entwicklung weiterhin in der Konsole
    except (AttributeError, OSError):
        pass
    if show_dialog:
        try:
            from PySide6.QtWidgets import QApplication, QMessageBox

            if QApplication.instance() is not None:
                box = QMessageBox(QApplication.activeWindow())
                box.setIcon(QMessageBox.Critical)
                box.setWindowTitle("Unerwarteter Fehler")
                box.setText(f"Es ist ein unerwarteter Fehler aufgetreten:\n{exc_type.__name__}: {exc}")
                box.setInformativeText(
                    "Die Arbeit kann in der Regel fortgesetzt werden. Bitte die Details "
                    + (f"aus der Datei\n{written}\n" if written else "")
                    + "an den Entwickler weitergeben.")
                box.setDetailedText(text)
                box.exec()
        except Exception:  # noqa: BLE001 - im Fehlerhandler niemals selbst abstürzen
            pass
    return text


def install() -> None:
    sys.excepthook = handle_exception
