"""Gemeinsame Bausteine der Lüftungsrechner: Luftzustand aus der Mediendatenbank, Kanalmaße."""

from __future__ import annotations

import math

from ingrechner.core import medien
from ingrechner.core.feuchte import hoehe_druck
from ingrechner.core.model import ChoiceField, NumberField

# Runde Luftleitungen DIN EN 1506 (Nenndurchmesser in mm)
RUND = [63, 80, 100, 125, 150, 160, 200, 250, 280, 300, 315, 355, 400, 450, 500, 560, 600, 630, 710, 800, 900,
        1000, 1120, 1250, 1400, 1600]
# Rechteckkanäle: übliche Seitenlängen in mm (Raster 50/100 mm)
RECHTECK = [100, 150, 200, 250, 300, 350, 400, 450, 500, 600, 700, 800, 900, 1000, 1200, 1400, 1600, 1800, 2000]

# Absolute Rauheit von Luftleitungen in mm
RAUHEIT = {"blech": ("Stahlblech verzinkt (k = 0,15 mm)", 0.15), "wickelfalz": ("Wickelfalzrohr (k = 0,09 mm)", 0.09),
           "kunststoff": ("Kunststoff (k = 0,01 mm)", 0.01), "flex": ("Flexrohr Aluminium (k = 3 mm)", 3.0),
           "gemauert": ("Gemauert / Beton (k = 3 mm)", 3.0)}


def luft_felder(theta: float = 20.0) -> list:
    """Medium (Gase der Mediendatenbank), Temperatur und Aufstellhöhe für den Luftdruck."""
    return [
        ChoiceField("gas", "Medium", medien.auswahl("gas"), "luft",
                    tooltip="Gase aus der Mediendatenbank – für Lüftung „Luft (trocken)“; Feuchte beeinflusst die "
                            "Dichte nur um ≈ 1 %"),
        NumberField("theta", "Lufttemperatur", "θ", "degC", theta, min=-50, max=400, min_inclusive=True, decimals=1),
        NumberField("hoehe", "Aufstellhöhe über NN", "h_NN", "m", 100, min=-400, max=4000, min_inclusive=True,
                    decimals=0, tooltip="Bestimmt den Luftdruck (barometrische Höhenformel)"),
    ]


def luft(inp):
    """Zustand (ρ, ν, c_p …) des gewählten Gases bei θ und dem Luftdruck der Aufstellhöhe."""
    p = hoehe_druck(inp["hoehe"].to("m").magnitude)
    m = medien.medium(inp["gas"])
    return m, m.zustand(inp["theta"].to("degC").magnitude, p)


def rauheit_feld(default: str = "blech") -> ChoiceField:
    return ChoiceField("rauheit", "Kanalwerkstoff", [(k, v[0]) for k, v in RAUHEIT.items()], default)


def d_hydraulisch(a: float, b: float) -> float:
    return 2 * a * b / (a + b)


def d_gleichwertig(a: float, b: float) -> float:
    """Gleichwertiger Durchmesser (gleicher Druckverlust bei gleichem Volumenstrom, Huebscher)."""
    return 1.30 * (a * b) ** 0.625 / (a + b) ** 0.25


def flaeche(form: str, d: float = 0.0, a: float = 0.0, b: float = 0.0) -> float:
    return math.pi * d**2 / 4 if form == "rund" else a * b
