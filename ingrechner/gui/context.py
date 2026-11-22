"""Gemeinsamer App-Zustand: Einstellungen und Materialdatenbank."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, QStandardPaths

from ingrechner.core.materials import MaterialLibrary


def default_material_path() -> Path:
    base = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
    return Path(base) / "materialien.json"


class AppContext:
    def __init__(self, settings: QSettings | None = None) -> None:
        self.settings = settings or QSettings("Ingenieurs-Rechner", "Ingenieurs-Rechner")
        self._materials: MaterialLibrary | None = None

    # ----------------------------------------------------- Materialdatei
    @property
    def material_path(self) -> Path:
        value = self.settings.value("materials/path", "")
        return Path(value) if value else default_material_path()

    @material_path.setter
    def material_path(self, path: str | Path) -> None:
        self.settings.setValue("materials/path", str(path))
        self._materials = None  # beim nächsten Zugriff neu laden

    @property
    def materials(self) -> MaterialLibrary:
        if self._materials is None:
            self._materials = MaterialLibrary(self.material_path)
        return self._materials

    # -------------------------------------------------- Bearbeiter-Name
    @property
    def default_author(self) -> str:
        return str(self.settings.value("user/name", ""))

    @default_author.setter
    def default_author(self, name: str) -> None:
        self.settings.setValue("user/name", name)
