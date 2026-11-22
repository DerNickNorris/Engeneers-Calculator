"""Gemeinsame Bausteine der Pumpenrechner: Medium, Rohrreibung, Kennlinien-Fit, Schnittpunkte, Motoren."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from ingrechner.calculators.fluid.druckverlust_rohr import rohrreibungszahl
from ingrechner.core.model import ChoiceField, Column, NumberField, TableField
from ingrechner.core import medien
from ingrechner.core.svg import INK, Svg

G = 9.80665

# ---------------------------------------------------------------- Medium
BENUTZER = {"medium": ["benutzer"]}
DB = {"medium": medien.ids("fluessig")}
WASSER = DB   # Kompatibilität


def medium_felder(theta: float = 60.0, mit_pv: bool = False) -> list:
    felder = [
        ChoiceField("medium", "Fördermedium", [*medien.auswahl("fluessig"),
                                               ("benutzer", "Benutzerdefiniert (eigene Stoffwerte)")],
                    "wasser", tooltip="Stoffwerte aus der Mediendatenbank (Extras › Mediendatenbank) – "
                                      "Richtwerte für überschlägige Berechnungen."),
        NumberField("theta", "Medientemperatur", "θ", "degC", theta, min=-50, max=200, min_inclusive=True,
                    decimals=1, visible_if=DB),
        NumberField("rho", "Dichte", "ρ", "kg/m**3", 1000, min=0, decimals=1, visible_if=BENUTZER),
        NumberField("nu", "Kinematische Viskosität", "ν", "mm**2/s", 1.3, min=0, decimals=3, visible_if=BENUTZER,
                    tooltip="Wasser 20 °C ≈ 1,0; Ethylenglykol 30 % bei 0 °C ≈ 3,5; kommunales Abwasser ≈ 1,1"),
    ]
    if mit_pv:
        felder.append(NumberField("pv", "Dampfdruck des Mediums", "p_v", "kPa", 2.34, min=0, min_inclusive=True,
                                  decimals=3, visible_if=BENUTZER, tooltip="Absoluter Sättigungsdampfdruck bei "
                                                                           "Fördertemperatur"))
    return felder


@dataclass
class Medium:
    name: str
    rho: float      # kg/m³
    nu: float       # m²/s
    pv: float       # Pa (absolut)
    cp: float = 4.186           # kJ/(kg·K)
    newtonsch: bool = True
    hinweis: str = ""
    id: str = "benutzer"


def medium(inp) -> Medium:
    if inp["medium"] == "benutzer":
        pv = inp["pv"].to("Pa").magnitude if "pv" in inp else 0.0
        return Medium("benutzerdefiniert", inp["rho"].to("kg/m**3").magnitude, inp["nu"].to("m**2/s").magnitude, pv)
    m = medien.medium(inp["medium"])
    t = inp["theta"].to("degC").magnitude
    z = m.zustand(t)
    return Medium(f"{m.name}, {t:g} °C".replace(".", ","), z.rho, z.nu, z.pv, z.cp, m.newtonsch, m.hinweis, m.id)


def medium_hinweise(calc, med: Medium) -> None:
    if not med.newtonsch:
        calc.warn("Nicht-newtonsches Medium: Berechnung mit äquivalenter Viskosität – nur überschlägig. "
                  + med.hinweis)
    viskositaet_pruefen(calc, med.nu)


def viskositaet_pruefen(calc, nu: float) -> None:
    nu_mm = nu * 1e6
    if nu_mm > 20:
        calc.warn(f"Viskosität {nu_mm:.0f} mm²/s > 20 mm²/s: Förderhöhe, Förderstrom und Wirkungsgrad der "
                  "Kreiselpumpe sinken gegenüber der Wasserkennlinie – Umrechnung nach ISO/TR 17766 (bzw. "
                  "Hydraulic Institute) erforderlich.")
    elif nu_mm > 5:
        calc.info("Erhöhte Viskosität: Die Wasserkennlinie der Pumpe gilt nur noch näherungsweise "
                  "(Korrektur nach ISO/TR 17766 ab ca. 20 mm²/s).")


# ------------------------------------------------------------- Rauheit
RAUHEIT = {
    "stahl": ("Stahl neu (k = 0,045 mm)", 0.045),
    "stahl_alt": ("Stahl gebraucht / leicht verkrustet (k = 0,15 mm)", 0.15),
    "kupfer": ("Kupfer, Edelstahl (k = 0,0015 mm)", 0.0015),
    "kunststoff": ("Kunststoff PE/PP/PVC (k = 0,007 mm)", 0.007),
    "guss": ("Gusseisen (k = 0,25 mm)", 0.25),
    "beton": ("Beton, Steinzeug – Abwasser (k = 1,0 mm)", 1.0),
}


def rauheit_felder(default: str = "stahl", vis: dict | None = None) -> list:
    v = dict(vis or {})
    return [
        ChoiceField("rauheit", "Rohrrauheit", [*[(k, t[0]) for k, t in RAUHEIT.items()],
                                               ("frei", "Eigener Wert")], default, visible_if=v or None),
        NumberField("k", "Absolute Rauheit", "k", "mm", 0.045, min=0, min_inclusive=True, decimals=4,
                    visible_if={**v, "rauheit": ["frei"]}),
    ]


def rauheit(inp) -> float:
    """Absolute Rauheit in m."""
    if inp["rauheit"] == "frei":
        return inp["k"].to("m").magnitude
    return RAUHEIT[inp["rauheit"]][1] / 1000


@dataclass
class RohrDp:
    v: float        # m/s
    re: float
    lam: float
    r: float        # Pa/m
    dp_r: float     # Pa
    dp_z: float     # Pa


def rohr_dp(V: float, di: float, L: float, k: float, zeta: float, rho: float, nu: float) -> RohrDp:
    """Druckverlust einer Rohrleitung (Darcy-Weisbach / Colebrook) – V in m³/s, Längen in m."""
    A = math.pi * di**2 / 4
    v = V / A
    if v <= 0:
        return RohrDp(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    re = v * di / nu
    lam = rohrreibungszahl(re, k / di)
    q = rho * v**2 / 2
    r = lam / di * q
    return RohrDp(v, re, lam, r, r * L, zeta * q)


# ------------------------------------------------------------ Kennlinie
def kennlinie_feld(default=None) -> TableField:
    return TableField(
        "kennlinie", "Pumpenkennlinie (Punkte aus dem Datenblatt, Nenndrehzahl)",
        [Column("Q", "V̇", "m**3/hour", decimals=2, min=0), Column("H", "H", "m", decimals=2, min=0),
         Column("eta", "η", "percent", optional=True, decimals=1, min=0)],
        default or [[0, 6.0, 0], [1, 5.8, 30], [2, 5.2, 42], [3, 4.3, 45], [4, 3.0, 40], [5, 1.4, 28]],
        min_rows=3, max_rows=15,
        tooltip="Mindestens drei Punkte V̇/H von der Herstellerkennlinie ablesen; η (Pumpen- oder Gesamt-"
                "wirkungsgrad) optional. Werte können aus Excel eingefügt werden.")


def pchip(x: np.ndarray, y: np.ndarray):
    """Formtreue kubische Hermite-Interpolation (Fritsch-Carlson) – keine Überschwinger zwischen den Punkten.

    Außerhalb der Stützstellen wird linear mit der Randsteigung fortgesetzt.
    """
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    h = np.diff(x)
    delta = np.diff(y) / h
    m = np.zeros_like(y)
    for k in range(1, len(x) - 1):
        if delta[k - 1] * delta[k] > 0:
            w1, w2 = 2 * h[k] + h[k - 1], h[k] + 2 * h[k - 1]
            m[k] = (w1 + w2) / (w1 / delta[k - 1] + w2 / delta[k])
    def rand(h0, h1, d0, d1):
        d = ((2 * h0 + h1) * d0 - h0 * d1) / (h0 + h1)
        if np.sign(d) != np.sign(d0):
            return 0.0
        if np.sign(d0) != np.sign(d1) and abs(d) > abs(3 * d0):
            return 3 * d0
        return d
    if len(x) == 2:
        m[:] = delta[0]
    else:
        m[0] = rand(h[0], h[1], delta[0], delta[1])
        m[-1] = rand(h[-1], h[-2], delta[-1], delta[-2])

    def f(xq):
        xq = np.asarray(xq, dtype=float)
        out = np.empty_like(xq)
        lo, hi = xq < x[0], xq > x[-1]
        out[lo] = y[0] + m[0] * (xq[lo] - x[0])
        out[hi] = y[-1] + m[-1] * (xq[hi] - x[-1])
        mid = ~(lo | hi)
        i = np.clip(np.searchsorted(x, xq[mid], side="right") - 1, 0, len(x) - 2)
        t = (xq[mid] - x[i]) / h[i]
        h00, h10 = 2 * t**3 - 3 * t**2 + 1, t**3 - 2 * t**2 + t
        h01, h11 = -2 * t**3 + 3 * t**2, t**3 - t**2
        out[mid] = h00 * y[i] + h10 * h[i] * m[i] + h01 * y[i + 1] + h11 * h[i] * m[i + 1]
        return out
    return f


class Kennlinie:
    """Kennlinie aus Datenblattpunkten: H(V̇) als Ausgleichsparabel, η(V̇) formtreu interpoliert (PCHIP).

    Drehzahländerung nach den Affinitätsgesetzen: V̇ ~ n, H ~ n², η ≈ konstant auf der Parabel.
    """

    def __init__(self, rows) -> None:
        pts = sorted((r[0], r[1], r[2] if len(r) > 2 else None) for r in rows)
        q = np.array([p[0] for p in pts], dtype=float)
        h = np.array([p[1] for p in pts], dtype=float)
        if len(set(q)) < 3:
            raise ValueError("Für die Kennlinie werden mindestens drei verschiedene Förderströme benötigt.")
        self.q, self.h = q, h
        self.q_max = float(q.max())
        self.ch = np.polyfit(q, h, 2)
        fit = np.polyval(self.ch, q)
        self.abw = float(np.max(np.abs(fit - h)) / max(h.max(), 1e-9))
        eta = [(p[0], p[2]) for p in pts if p[2] is not None]
        self.q_eta = np.array([e[0] for e in eta], dtype=float)
        self.eta_pts = np.array([e[1] for e in eta], dtype=float) / 100
        self.ce = None
        if len(eta) >= 3:
            if len(set(self.q_eta)) != len(self.q_eta):
                raise ValueError("Doppelte Förderströme bei den Wirkungsgradpunkten.")
            self.ce = pchip(self.q_eta, self.eta_pts)
        # Labile Kennlinie: Maximum der Förderhöhe nicht bei V̇ = V̇_min
        hs = np.polyval(self.ch, np.linspace(q.min(), q.max(), 60))
        self.instabil = bool(hs.max() - hs[0] > 0.01 * h.max())

    @property
    def hat_eta(self) -> bool:
        return self.ce is not None

    def H(self, Q, n: float = 1.0):
        """Förderhöhe in m bei V̇ in m³/h und relativer Drehzahl n."""
        return n**2 * np.polyval(self.ch, np.asarray(Q, dtype=float) / n)

    def eta(self, Q, n: float = 1.0):
        if self.ce is None:
            return None
        Q = np.asarray(Q, dtype=float)
        val = np.clip(self.ce(np.atleast_1d(Q / n)), 0.0, 1.0)
        return val if Q.ndim else val[0]

    def bep(self) -> tuple[float, float] | None:
        """Bestpunkt (V̇_opt in m³/h, η_max) bei Nenndrehzahl."""
        if self.ce is None:
            return None
        qs = np.linspace(self.q_eta.min(), self.q_eta.max(), 400)
        e = self.ce(qs)
        i = int(np.argmax(e))
        return float(qs[i]), float(e[i])

    def koeff_text(self) -> str:
        a2, a1, a0 = self.ch
        def term(c: float) -> str:
            return f"{'−' if c < 0 else '+'} {abs(c):.4g}".replace(".", ",")
        return f"H(V̇) = {a0:.4g}".replace(".", ",") + f" {term(a1)}·V̇ {term(a2)}·V̇²"


def nullstelle(f, a: float, b: float, n: int = 80) -> float | None:
    """Bisektion für f(x) = 0 in [a, b]; None, wenn kein Vorzeichenwechsel vorliegt."""
    fa, fb = f(a), f(b)
    if fa == 0:
        return a
    if fa * fb > 0:
        return None
    for _ in range(n):
        m = (a + b) / 2
        fm = f(m)
        if fa * fm <= 0:
            b = m
        else:
            a, fa = m, fm
    return (a + b) / 2


# ---------------------------------------------------------------- Motoren
IEC_GROESSEN = [0.12, 0.18, 0.25, 0.37, 0.55, 0.75, 1.1, 1.5, 2.2, 3, 4, 5.5, 7.5, 11, 15, 18.5, 22, 30, 37, 45,
                55, 75, 90, 110, 132, 160, 200, 250, 315]

# Mindestwirkungsgrade 4-polig, 50 Hz nach IEC 60034-30-1 in %
IE3 = [64.8, 69.9, 73.5, 77.3, 80.8, 82.5, 84.1, 85.3, 86.7, 87.7, 88.6, 89.6, 90.4, 91.4, 92.1, 92.6, 93.0,
       93.6, 93.9, 94.2, 94.6, 95.0, 95.2, 95.4, 95.6, 95.8, 96.0, 96.0, 96.0]
IE4 = [69.8, 74.7, 77.9, 81.1, 83.9, 85.7, 87.2, 88.2, 89.5, 90.4, 91.1, 91.9, 92.6, 93.3, 93.9, 94.2, 94.5,
       94.9, 95.2, 95.4, 95.7, 96.0, 96.1, 96.3, 96.4, 96.6, 96.7, 96.7, 96.7]


def motor_zuschlag(p2_kw: float) -> float:
    """Übliche Leistungsreserve für Kreiselpumpenantriebe (Herstellerpraxis)."""
    if p2_kw <= 7.5:
        return 0.20
    if p2_kw <= 40:
        return 0.15
    return 0.10


def motor_groesse(p_kw: float) -> tuple[int, float] | None:
    for i, p in enumerate(IEC_GROESSEN):
        if p >= p_kw - 1e-9:
            return i, p
    return None


# ------------------------------------------------------------------ Skizze
def pumpe_svg(s: Svg, cx: float, cy: float, r: float = 22, fill: str = "#ffffff") -> Svg:
    """Pumpensymbol nach DIN EN ISO 10628 (Kreis mit Dreieck in Förderrichtung nach rechts)."""
    s.circle(cx, cy, r, fill=fill)
    s.polygon([(cx - r * 0.55, cy - r * 0.8), (cx - r * 0.55, cy + r * 0.8), (cx + r, cy)], fill="#dce6f1",
              stroke=INK, width=1.4)
    return s
