"""Temperaturabhängige Stoffwerte von Wasser und Luft (Tabellen mit linearer Interpolation).

Wasser: 0 … 150 °C, flüssig bei Sättigungsdruck bzw. 1 bar.
Luft:  −20 … 200 °C bei 1 bar.
Werte nach VDI-Wärmeatlas (gerundet); Abweichungen < 1 % gegenüber der Quelle.
"""

from __future__ import annotations

import math
from bisect import bisect_left
from dataclasses import dataclass


@dataclass(frozen=True)
class Stoffwerte:
    name: str
    theta: float      # °C
    rho: float        # kg/m³
    cp: float         # kJ/(kg·K)
    lam: float        # W/(m·K)
    nu: float         # mm²/s (kinematische Viskosität)

    @property
    def pr(self) -> float:
        """Prandtl-Zahl Pr = ν·ρ·c_p / λ."""
        return self.nu * 1e-6 * self.rho * self.cp * 1e3 / self.lam

    @property
    def rho_cp(self) -> float:
        """Volumetrische Wärmekapazität in kJ/(m³·K)."""
        return self.rho * self.cp


#        θ      ρ       c_p     λ       ν
WASSER = [
    (0, 999.8, 4.217, 0.561, 1.792),
    (10, 999.7, 4.192, 0.580, 1.306),
    (20, 998.2, 4.182, 0.598, 1.004),
    (30, 995.7, 4.178, 0.615, 0.801),
    (40, 992.2, 4.179, 0.631, 0.658),
    (50, 988.0, 4.181, 0.644, 0.553),
    (60, 983.2, 4.185, 0.654, 0.474),
    (70, 977.8, 4.190, 0.663, 0.413),
    (80, 971.8, 4.197, 0.670, 0.365),
    (90, 965.3, 4.205, 0.675, 0.326),
    (100, 958.4, 4.216, 0.679, 0.295),
    (110, 951.0, 4.229, 0.682, 0.272),
    (120, 943.1, 4.245, 0.683, 0.252),
    (130, 934.8, 4.263, 0.684, 0.233),
    (140, 926.1, 4.285, 0.684, 0.217),
    (150, 917.0, 4.310, 0.682, 0.203),
]

LUFT = [
    (-20, 1.377, 1.006, 0.0226, 11.6),
    (0, 1.275, 1.006, 0.0242, 13.5),
    (20, 1.188, 1.007, 0.0257, 15.3),
    (40, 1.112, 1.007, 0.0272, 17.2),
    (60, 1.045, 1.009, 0.0286, 19.1),
    (80, 0.986, 1.010, 0.0300, 21.1),
    (100, 0.933, 1.012, 0.0314, 23.1),
    (150, 0.823, 1.017, 0.0348, 28.5),
    (200, 0.736, 1.026, 0.0381, 34.4),
]

TABELLEN = {"wasser": ("Wasser", WASSER), "luft": ("Luft (1 bar)", LUFT)}


def _interp(table, theta: float, name: str) -> Stoffwerte:
    temps = [row[0] for row in table]
    if not temps[0] <= theta <= temps[-1]:
        raise ValueError(f"Stoffwerte {name}: Temperatur {theta:g} °C außerhalb des Tabellenbereichs "
                         f"{temps[0]} … {temps[-1]} °C.".replace(".", ",", 1))
    i = bisect_left(temps, theta)
    if temps[i] == theta:
        row = table[i]
        return Stoffwerte(name, theta, *row[1:])
    lo, hi = table[i - 1], table[i]
    f = (theta - lo[0]) / (hi[0] - lo[0])
    vals = [a + f * (b - a) for a, b in zip(lo[1:], hi[1:])]
    return Stoffwerte(name, theta, *vals)


def stoffwerte(medium: str, theta: float) -> Stoffwerte:
    """Stoffwerte für ``medium`` ("wasser" oder "luft") bei ``theta`` in °C."""
    name, table = TABELLEN[medium]
    return _interp(table, theta, name)


MEDIEN_AUSWAHL = [("wasser", "Wasser"), ("luft", "Luft")]


# Sättigungsdampfdruck von Wasser in kPa (IAPWS-IF97, gerundet)
DAMPFDRUCK_WASSER = [
    (0, 0.6113), (10, 1.2282), (20, 2.3393), (30, 4.2470), (40, 7.3849), (50, 12.352), (60, 19.946),
    (70, 31.201), (80, 47.414), (90, 70.182), (100, 101.42), (110, 143.38), (120, 198.67), (130, 270.28),
    (140, 361.54), (150, 476.16),
]


def dampfdruck(theta: float) -> float:
    """Sättigungsdampfdruck von Wasser in kPa bei ``theta`` in °C (0 … 150 °C).

    Interpoliert linear in ln(p) über 1/T – damit ist die Abweichung zur IAPWS-Formulierung < 0,1 %.
    """
    temps = [t for t, _ in DAMPFDRUCK_WASSER]
    if not temps[0] <= theta <= temps[-1]:
        raise ValueError(f"Dampfdruck Wasser: Temperatur {theta:g} °C außerhalb 0 … 150 °C.")
    i = max(1, bisect_left(temps, theta))
    (t0, p0), (t1, p1) = DAMPFDRUCK_WASSER[i - 1], DAMPFDRUCK_WASSER[i]
    x0, x1, x = 1 / (t0 + 273.15), 1 / (t1 + 273.15), 1 / (theta + 273.15)
    return math.exp(math.log(p0) + (x - x0) / (x1 - x0) * (math.log(p1) - math.log(p0)))
