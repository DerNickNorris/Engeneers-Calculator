"""Feuchte Luft (h,x-Beziehungen nach Mollier) für die Lüftungsrechner.

Sättigungsdampfdruck nach DIN 4108-3 (Magnus-Formel über Wasser bzw. Eis, gültig etwa −50 … 60 °C),
oberhalb 60 °C aus der Wasserdampftafel. Wassergehalt x in kg Wasser je kg trockene Luft.
"""

from __future__ import annotations

import math

from .stoffwerte import dampfdruck

P_NORM = 101325.0
R_L = 287.06          # J/(kg·K) trockene Luft
CP_L = 1.006          # kJ/(kg·K) trockene Luft
CP_D = 1.86           # kJ/(kg·K) Wasserdampf
R0 = 2501.0           # kJ/kg Verdampfungsenthalpie bei 0 °C


def p_saett(theta: float) -> float:
    """Sättigungsdampfdruck in Pa (über Eis unter 0 °C)."""
    if theta < 0:
        return 610.5 * math.exp(21.875 * theta / (265.5 + theta))
    if theta <= 60:
        return 610.5 * math.exp(17.269 * theta / (237.3 + theta))
    return dampfdruck(min(theta, 150.0)) * 1000


def taupunkt(pd: float) -> float:
    """Taupunkt- bzw. Reiftemperatur in °C zum Dampfpartialdruck pd (Pa)."""
    if pd <= 0:
        return -math.inf
    if pd >= 610.5:
        a = math.log(pd / 610.5)
        return 237.3 * a / (17.269 - a)
    a = math.log(pd / 610.5)
    return 265.5 * a / (21.875 - a)


def hoehe_druck(h: float) -> float:
    """Luftdruck in Pa in der Höhe h (m über NN), barometrische Höhenformel (Normatmosphäre)."""
    return P_NORM * (1 - 2.25577e-5 * h) ** 5.25588


def x_aus_phi(theta: float, phi: float, p: float = P_NORM) -> float:
    pd = phi * p_saett(theta)
    if pd >= p:
        raise ValueError("Der Dampfdruck erreicht den Gesamtdruck.")
    return 0.622 * pd / (p - pd)


def x_saett(theta: float, p: float = P_NORM) -> float:
    return x_aus_phi(theta, 1.0, p)


def pd_aus_x(x: float, p: float = P_NORM) -> float:
    return x * p / (0.622 + x)


def phi_aus_x(theta: float, x: float, p: float = P_NORM) -> float:
    return pd_aus_x(x, p) / p_saett(theta)


def enthalpie(theta: float, x: float) -> float:
    """Spezifische Enthalpie in kJ/kg trockene Luft (ungesättigt)."""
    return CP_L * theta + x * (R0 + CP_D * theta)


def theta_aus_h(h: float, x: float) -> float:
    return (h - R0 * x) / (CP_L + CP_D * x)


def dichte(theta: float, x: float, p: float = P_NORM) -> float:
    """Dichte der feuchten Luft in kg/m³."""
    return p / (R_L * (theta + 273.15)) * (1 + x) / (1 + 1.608 * x)


class Zustand:
    """Zustand feuchter Luft aus θ und φ (oder x)."""

    def __init__(self, theta: float, phi: float | None = None, x: float | None = None, p: float = P_NORM) -> None:
        self.theta, self.p = theta, p
        self.x = x if x is not None else x_aus_phi(theta, phi if phi is not None else 0.5, p)
        self.phi = phi_aus_x(theta, self.x, p)
        if self.phi > 1.0 + 1e-6:
            raise ValueError(f"Übersättigte Luft bei {theta:g} °C (φ > 100 %) – Nebel/Kondensat.")
        self.h = enthalpie(theta, self.x)
        self.rho = dichte(theta, self.x, p)
        self.pd = pd_aus_x(self.x, p)
        self.tau = taupunkt(self.pd)
