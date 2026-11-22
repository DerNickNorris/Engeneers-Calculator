"""Werkzeuge (Phase 2): eigenständige Ansichten neben den Rechenmodulen."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtWidgets import QWidget


@dataclass(frozen=True)
class ToolSpec:
    id: str
    title: str
    description: str
    keywords: tuple[str, ...]
    factory: Callable[..., QWidget]   # factory(context) -> QWidget
    category: str = "Werkzeuge"


def tools() -> list[ToolSpec]:
    from ..protocols.protocol_view import ProtocolView
    from ..protocols.template_editor import TemplateEditorView
    from .materials_view import MaterialsView
    from .medien_view import MedienView
    from .plotter import PlotterView
    from .sci_calc import SciCalcView
    from .unit_converter import UnitConverterView

    return [
        ToolSpec("tool.units", "Einheitenumrechner", "Umrechnen zwischen Einheiten in 24 Kategorien",
                 ("einheit", "umrechnen", "umrechner", "konvertieren", "psi", "bar", "zoll"), UnitConverterView),
        ToolSpec("tool.sci", "Wissenschaftlicher Rechner", "Taschenrechner mit Funktionen, Variablen und Verlauf",
                 ("taschenrechner", "rechner", "sin", "wurzel", "formel"), SciCalcView),
        ToolSpec("tool.materials", "Materialdatenbank", "Werkstoffkennwerte, vom Team erweiterbar",
                 ("material", "werkstoff", "stahl", "aluminium", "e-modul", "dichte", "streckgrenze"), MaterialsView),
        ToolSpec("tool.medien", "Mediendatenbank", "Stoffwerte von Flüssigkeiten und Gasen über der Temperatur",
                 ("medium", "medien", "fluid", "stoffwerte", "viskosität", "dichte", "glykol", "sole", "öl",
                  "klärschlamm", "abwasser", "erdgas", "klärgas", "biogas", "co2", "stickstoff", "fett"), MedienView),
        ToolSpec("tool.plotter", "Funktionsplotter", "Funktionen und Messwerte darstellen",
                 ("plot", "diagramm", "funktion", "graph", "kennlinie", "messwerte"), PlotterView),
        ToolSpec("proto.editor", "Besprechungsprotokoll", "Protokolle nach Vorlage erstellen, mit Diktat",
                 ("protokoll", "besprechung", "baubesprechung", "diktat", "sprache", "jour fixe", "notiz"),
                 ProtocolView, "Protokolle"),
        ToolSpec("proto.templates", "Vorlagen-Editor", "Protokollvorlagen für das Team gestalten",
                 ("vorlage", "protokoll", "template", "baustein"), TemplateEditorView, "Protokolle"),
    ]
