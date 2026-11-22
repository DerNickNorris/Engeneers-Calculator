"""Update-Hinweis: prüft im Hintergrund die GitHub-Releases und zeigt neue Versionen an."""

from __future__ import annotations

import threading

from PySide6.QtCore import QObject, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QLabel, QMessageBox, QWidget

from ingrechner import __version__
from ingrechner.core import updates

from .theme import C


class UpdateChecker(QObject):
    finished = Signal(object, str)   # (ReleaseInfo | None, Fehlertext)

    def __init__(self, parent: QObject | None = None, fetch=updates.fetch_latest) -> None:
        super().__init__(parent)
        self._fetch = fetch
        self.running = False

    def check(self) -> None:
        if self.running:
            return
        self.running = True

        def work():
            try:
                info, err = self._fetch(), ""
            except Exception as exc:  # noqa: BLE001 - offline, Proxy, Rate-Limit …
                info, err = None, str(exc)
            self.running = False
            self.finished.emit(info, err)

        threading.Thread(target=work, daemon=True).start()


def open_download(info: updates.ReleaseInfo) -> None:
    QDesktopServices.openUrl(QUrl(info.installer_url or info.url))


def show_update_dialog(parent: QWidget, info: updates.ReleaseInfo) -> None:
    notes = info.notes.strip()
    if len(notes) > 1200:
        notes = notes[:1200] + " …"
    box = QMessageBox(parent)
    box.setWindowTitle("Neue Version verfügbar")
    box.setIcon(QMessageBox.Information)
    box.setText(f"<b>Version {info.version}</b> ist verfügbar (installiert: {__version__}).")
    box.setInformativeText("Das Setup aktualisiert die vorhandene Installation; Einstellungen, Projekte "
                           "und Team-Dateien bleiben erhalten.")
    if notes:
        box.setDetailedText(notes)
    dl = box.addButton("Herunterladen", QMessageBox.AcceptRole)
    box.addButton("Später", QMessageBox.RejectRole)
    box.exec()
    if box.clickedButton() is dl:
        open_download(info)


class UpdateBadge(QLabel):
    """Klickbarer Hinweis in der Statusleiste."""

    def __init__(self, info: updates.ReleaseInfo, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.info = info
        self.setText(f"<a href='#' style='color:{C['accent']}; text-decoration:none'>"
                     f"⬆ Version {info.version} verfügbar</a>")
        self.setTextFormat(Qt.RichText)
        self.setToolTip("Klicken für Details und Download")
        self.linkActivated.connect(lambda _: show_update_dialog(self.window(), self.info))
