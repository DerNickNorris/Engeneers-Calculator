"""Gemeinsame Grundlagen der Asynchronmotor-Rechner: Normreihen, Wirkungsgradklassen, Kennlinien."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from ingrechner.calculators.pumpen._pumpe import IE3, IE4, IEC_GROESSEN, motor_groesse

# Mindestwirkungsgrade 4-polig, 50 Hz nach IEC 60034-30-1 (IE2) in %
IE2 = [59.1, 64.7, 68.5, 72.7, 77.1, 79.6, 81.4, 82.8, 84.3, 85.5, 86.6, 87.7, 88.7, 89.8, 90.6, 91.2, 91.6, 92.3,
       92.7, 93.1, 93.5, 94.0, 94.2, 94.5, 94.7, 94.9, 95.1, 95.1, 95.1]
IE_TAB = {"IE2": IE2, "IE3": IE3, "IE4": IE4}

# Typische Katalogwerte 4-poliger IE3-Normmotoren (Richtwerte):
# P_N kW -> (cos φ, I_A/I_N, M_A/M_N, M_K/M_N, J_M kg·m²)
_TYP = [(0.12, 0.66, 3.5, 2.0, 2.0, 0.0004), (0.55, 0.74, 4.5, 2.2, 2.3, 0.0015), (1.1, 0.78, 5.5, 2.3, 2.6, 0.0035),
        (2.2, 0.80, 6.5, 2.3, 2.8, 0.0070), (4.0, 0.82, 7.0, 2.3, 2.9, 0.013), (7.5, 0.83, 7.2, 2.3, 3.0, 0.035),
        (15, 0.84, 7.3, 2.3, 2.9, 0.09), (30, 0.86, 7.3, 2.3, 2.8, 0.24), (55, 0.86, 7.0, 2.4, 2.7, 0.55),
        (110, 0.87, 7.0, 2.3, 2.6, 1.4), (200, 0.88, 7.0, 2.2, 2.5, 3.6), (315, 0.88, 7.2, 2.2, 2.5, 6.5)]


@dataclass
class Typwerte:
    cosphi: float
    ia: float
    ma: float
    mk: float
    J: float
    eta: float     # IE3-Mindestwirkungsgrad (4-polig) in %


def typwerte(pn_kw: float) -> Typwerte:
    """Richtwerte eines 4-poligen IE3-Normmotors (logarithmisch interpoliert über P_N)."""
    xs = [math.log(r[0]) for r in _TYP]
    x = min(max(math.log(pn_kw), xs[0]), xs[-1])
    vals = [float(np.interp(x, xs, [r[k] for r in _TYP])) for k in range(1, 5)]
    J = math.exp(float(np.interp(x, xs, [math.log(r[5]) for r in _TYP])))
    sel = motor_groesse(pn_kw)
    eta = IE3[sel[0]] if sel else IE3[-1]
    return Typwerte(*vals, J, eta)


def mindestklasse(pn_kw: float, pole: int) -> str:
    """Mindest-Effizienzklasse nach EU-Ökodesign-Verordnung 2019/1781 (Stand ab 01.07.2023, Netzbetrieb)."""
    if pn_kw < 0.12:
        return "keine Anforderung (< 0,12 kW)"
    if pn_kw < 0.75:
        return "IE2"
    if 75 <= pn_kw <= 200 and pole in (2, 4, 6):
        return "IE4"
    if pn_kw <= 1000:
        return "IE3"
    return "keine Anforderung (> 1000 kW)"


def leistungsklasse(pn_kw: float, klasse: str) -> float:
    """Mindestwirkungsgrad (4-polig, 50 Hz) der Klasse bei P_N in % (P_N wird auf die IEC-Reihe gerundet)."""
    sel = motor_groesse(pn_kw)
    idx = sel[0] if sel else len(IEC_GROESSEN) - 1
    return IE_TAB[klasse][idx]


# ------------------------------------------------------------- Kennlinien
class Kennlinie:
    """Drehmoment über dem Schlupf nach Kloss, an das Anlaufmoment angepasst.

    M(s) = 2·M_K / (s/s_K + s_K/s) · c(s);  c(s) = 1 + (M_A/M_Kloss(1) − 1)·((s − s_K)/(1 − s_K))² für s > s_K,
    sonst c = 1 – Betriebsbereich und Kippmoment bleiben unverändert, M(1) = M_A.
    """

    def __init__(self, MN: float, sN: float, mk: float, ma: float) -> None:
        self.MN, self.sN = MN, sN
        self.MK = mk * MN
        self.MA = ma * MN
        self.sK = sN * (mk + math.sqrt(mk**2 - 1)) if mk > 1 else sN
        self.c1 = self.MA / self._kloss(1.0) - 1

    def _kloss(self, s):
        s = np.maximum(np.asarray(s, dtype=float), 1e-9)
        return 2 * self.MK / (s / self.sK + self.sK / s)

    def M(self, s):
        s = np.asarray(s, dtype=float)
        t = np.clip((s - self.sK) / max(1 - self.sK, 1e-9), 0.0, 1.0)
        return self._kloss(s) * (1 + self.c1 * t**2)


def strom(I_N: float, cosphi: float, last: float) -> float:
    """Ständerstrom bei relativer Last (Näherung: Magnetisierungsstrom + lastproportionaler Wirkanteil)."""
    I0 = I_N * math.sqrt(max(1 - cosphi**2, 0.0)) * 0.85
    return math.sqrt(I0**2 + (I_N**2 - I0**2) * last**2)


def teillast(eta_N: float, last: float, a: float = 0.4) -> float:
    """Wirkungsgrad bei relativer Last (lastunabhängige Verluste Anteil a der Nennverluste; a = 0,4 ergibt das
    Wirkungsgradmaximum bei ≈ 80 % Last wie bei typischen Normmotoren)."""
    if last <= 0:
        return 0.0
    pv = (1 / eta_N - 1)
    return last / (last + pv * (a + (1 - a) * last**2))


def synchron(f: float, pole: int) -> float:
    return 120 * f / pole


def polzahl(f: float, nN: float) -> int:
    """Polzahl aus der Nenndrehzahl (nächste Synchrondrehzahl oberhalb)."""
    p = max(1, math.floor(60 * f / nN))
    return 2 * p
