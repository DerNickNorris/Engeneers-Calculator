"""Gemeinsamer App-Zustand: Einstellungen und Materialdatenbank."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, QStandardPaths

from ingrechner.core.materials import MaterialLibrary
from ingrechner.core.protocols import TemplateLibrary


def app_data_dir() -> Path:
    return Path(QStandardPaths.writableLocation(QStandardPaths.AppDataLocation))


def default_material_path() -> Path:
    return app_data_dir() / "materialien.json"


def default_template_path() -> Path:
    return app_data_dir() / "protokoll-vorlagen.json"


def default_model_base() -> Path:
    return app_data_dir() / "sprachmodelle"


class AppContext:
    def __init__(self, settings: QSettings | None = None) -> None:
        self.settings = settings or QSettings("Ingenieurs-Rechner", "Ingenieurs-Rechner")
        self._materials: MaterialLibrary | None = None
        self._templates: TemplateLibrary | None = None
        self._speech = None

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

    # -------------------------------------------------------- Updates
    @property
    def update_check(self) -> bool:
        return str(self.settings.value("updates/check", "true")).lower() in ("true", "1")

    @update_check.setter
    def update_check(self, on: bool) -> None:
        self.settings.setValue("updates/check", "true" if on else "false")

    # ------------------------------------------------- Protokollvorlagen
    @property
    def template_path(self) -> Path:
        value = self.settings.value("protocols/templates", "")
        return Path(value) if value else default_template_path()

    @template_path.setter
    def template_path(self, path: str | Path) -> None:
        self.settings.setValue("protocols/templates", str(path))
        self._templates = None

    @property
    def templates(self) -> TemplateLibrary:
        if self._templates is None:
            self._templates = TemplateLibrary(self.template_path)
        return self._templates

    # ----------------------------------------------------- Spracherkennung
    @property
    def speech_model_path(self) -> Path | None:
        value = self.settings.value("speech/model_path", "")
        return Path(value) if value else None

    @speech_model_path.setter
    def speech_model_path(self, path: str | Path | None) -> None:
        self.settings.setValue("speech/model_path", str(path) if path else "")

    @property
    def speech_glossary(self) -> str:
        return str(self.settings.value("speech/glossary", ""))

    @speech_glossary.setter
    def speech_glossary(self, text: str) -> None:
        self.settings.setValue("speech/glossary", text)

    @property
    def speech(self):
        if self._speech is None:
            from .dictation import SpeechService

            self._speech = SpeechService(self)
        return self._speech
