"""Wärmeverlust gedämmter und ungedämmter Rohrleitungen in Luft (DIN EN ISO 12241 / VDI 2055).

Längenbezogener Wärmestrom q = (θ_m − θ_a) / R' mit
    R' = ln(d_a/d_i)/(2π·λ_Rohr) + ln(D/d_a)/(2π·λ_D) + 1/(π·D·h_a)
h_a = h_Konvektion + h_Strahlung hängt von der Oberflächentemperatur ab und wird iteriert.
Der innere Wärmeübergang wird vernachlässigt (liegt auf der sicheren Seite für den Verlust).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

SIGMA = 5.670e-8  # W/(m²·K⁴)


def h_konvektion(D: float, dT: float, ort: str, wind: float = 0.0) -> float:
    """Konvektiver Wärmeübergang außen [W/(m²·K)] am waagerechten Rohr, D in m.

    innen (freie Konvektion, DIN EN ISO 12241 Gl. 26/27):
        laminar   D³·ΔT ≤ 10 m³K:  h = 1,25 · (ΔT/D)^0,25
        turbulent D³·ΔT > 10 m³K:  h = 1,21 · ΔT^(1/3)
    außen (erzwungene Konvektion durch Wind, Gl. 32/33):
        v·D ≤ 8,55·10⁻³ m²/s:  h = 8,1·10⁻³/D + 3,14·√(v/D)
        v·D > 8,55·10⁻³ m²/s:  h = 8,9 · v^0,9 / D^0,1
    """
    dT = abs(dT)
    if ort == "aussen" and wind > 0:
        if wind * D <= 8.55e-3:
            return 8.1e-3 / D + 3.14 * math.sqrt(wind / D)
        return 8.9 * wind**0.9 / D**0.1
    if dT < 1e-6:
        return 0.0
    if D**3 * dT <= 10:
        return 1.25 * (dT / D) ** 0.25
    return 1.21 * dT ** (1 / 3)


def h_strahlung(eps: float, ts: float, ta: float) -> float:
    """Strahlungsanteil h_r = ε·σ·(T_s⁴ − T_a⁴)/(T_s − T_a) [W/(m²·K)], Temperaturen in °C."""
    Ts, Ta = ts + 273.15, ta + 273.15
    if abs(Ts - Ta) < 1e-9:
        return 4 * eps * SIGMA * Ts**3
    return eps * SIGMA * (Ts**4 - Ta**4) / (Ts - Ta)


@dataclass
class RohrVerlust:
    q: float           # W/m
    ts: float          # Oberflächentemperatur °C
    D: float           # Außendurchmesser (mit Dämmung) m
    h_conv: float
    h_rad: float
    R_rohr: float      # m·K/W
    R_daemm: float
    R_aussen: float

    @property
    def h_a(self) -> float:
        return self.h_conv + self.h_rad

    @property
    def R_ges(self) -> float:
        return self.R_rohr + self.R_daemm + self.R_aussen


def rohrverlust(theta_m: float, theta_a: float, d_a: float, s: float, lam_rohr: float,
                daemm: float, lam_daemm: float, eps: float, ort: str = "innen",
                wind: float = 0.0) -> RohrVerlust:
    """Wärmeverlust je Meter Rohr. Längen in m, Temperaturen in °C."""
    d_i = d_a - 2 * s
    if d_i <= 0:
        raise ValueError("Die Wanddicke ist zu groß für den Rohrdurchmesser.")
    D = d_a + 2 * daemm
    R_rohr = math.log(d_a / d_i) / (2 * math.pi * lam_rohr)
    R_daemm = math.log(D / d_a) / (2 * math.pi * lam_daemm) if daemm > 0 else 0.0
    dT = theta_m - theta_a
    ts = theta_a + 0.3 * dT if daemm > 0 else theta_m - 0.02 * dT     # Startwert
    for _ in range(200):
        hc = h_konvektion(D, ts - theta_a, ort, wind)
        hr = h_strahlung(eps, ts, theta_a)
        h = max(hc + hr, 1e-6)
        R_a = 1 / (math.pi * D * h)
        q = dT / (R_rohr + R_daemm + R_a)
        ts_new = theta_a + q * R_a
        if abs(ts_new - ts) < 1e-7:
            ts = ts_new
            break
        ts = 0.5 * ts + 0.5 * ts_new        # gedämpfte Iteration
    hc = h_konvektion(D, ts - theta_a, ort, wind)
    hr = h_strahlung(eps, ts, theta_a)
    R_a = 1 / (math.pi * D * (hc + hr))
    q = dT / (R_rohr + R_daemm + R_a)
    return RohrVerlust(q, theta_a + q * R_a, D, hc, hr, R_rohr, R_daemm, R_a)


def temperaturverlauf(theta_ein: float, theta_a: float, m_dot: float, cp: float, R_ges: float,
                      L: float) -> float:
    """Austrittstemperatur nach der Länge L (exponentieller Abfall).

    θ(x) = θ_a + (θ_ein − θ_a) · exp(−x / (ṁ · c_p · R'))   (ṁ in kg/s, c_p in J/(kg·K), R' in m·K/W)
    """
    return theta_a + (theta_ein - theta_a) * math.exp(-L / (m_dot * cp * R_ges))
