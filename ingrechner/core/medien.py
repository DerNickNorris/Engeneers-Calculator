"""Mediendatenbank: Stoffwerte von Flüssigkeiten und Gasen über Temperatur (und Druck).

Die Werte sind **Richtwerte für überschlägige Berechnungen** (Quellen: VDI-Wärmeatlas, Hersteller-
datenblätter von Wärmeträgern und Ölen, DVGW G 260, Literaturwerte für Abwasser und Schlämme).
Für Nachweise sind die Stoffdaten des konkreten Mediums zu verwenden.

Modelle
-------
* ``Tabelle``      – Stützstellen ρ, μ, c_p über θ (Glykol-Gemische); ln μ wird linear interpoliert.
* ``WasserBasis``  – Wasser mit Zuschlägen (Abwasser, Klärschlamm als äquivalente Viskosität).
* ``Walther``      – Mineral-/Pflanzenöle: Viskosität nach Ubbelohde-Walther (DIN 51563) aus zwei
  Stützwerten, Dichte linear über den Ausdehnungskoeffizienten.
* ``Gas``          – Gemisch idealer Gase mit Realgasfaktor aus dem 2. Virialkoeffizienten
  (Pitzer/Tsonopoulos, Kay-Regel), Viskosität nach Sutherland und Herning-Zipperer.
* ``Fett``         – Schmierfette: nur Kennwerte, keine Strömungsrechnung (nicht-newtonsch).
"""

from __future__ import annotations

import math
from bisect import bisect_left
from dataclasses import dataclass, field

from .stoffwerte import dampfdruck, stoffwerte

R = 8.314462618          # J/(mol·K)
P_NORM = 101325.0        # Pa
T_NORM = 273.15          # K


@dataclass
class Zustand:
    """Stoffwerte bei θ (°C) und p (Pa, absolut)."""

    theta: float
    p: float
    rho: float           # kg/m³
    mu: float            # Pa·s
    cp: float            # kJ/(kg·K)
    pv: float            # Pa (Dampfdruck; 0 = vernachlässigbar)
    Z: float = 1.0       # Realgasfaktor (Gase)

    @property
    def nu(self) -> float:
        """Kinematische Viskosität in m²/s."""
        return self.mu / self.rho


@dataclass
class Medium:
    id: str
    name: str
    gruppe: str
    art: str                       # "fluessig", "gas", "pastoes"
    t_min: float
    t_max: float
    hinweis: str = ""
    newtonsch: bool = True
    kennwerte: dict[str, str] = field(default_factory=dict)   # Zusatzangaben für die Ansicht

    @property
    def fliessfaehig(self) -> bool:
        return self.art != "pastoes"

    def pruefe(self, theta: float) -> None:
        if not self.t_min - 1e-9 <= theta <= self.t_max + 1e-9:
            raise ValueError(f"{self.name}: Stoffwerte nur für {_f(self.t_min)} … {_f(self.t_max)} °C hinterlegt "
                             f"(eingegeben {_f(theta)} °C).")

    def zustand(self, theta: float, p: float = P_NORM) -> Zustand:  # pragma: no cover - abstrakt
        raise NotImplementedError


def _f(x: float) -> str:
    return f"{x:g}".replace(".", ",").replace("-", "−")


def _interp(xs: list[float], ys: list[float], x: float) -> float:
    i = min(max(bisect_left(xs, x), 1), len(xs) - 1)
    x0, x1 = xs[i - 1], xs[i]
    return ys[i - 1] + (x - x0) / (x1 - x0) * (ys[i] - ys[i - 1])


# --------------------------------------------------------------------- Wasser
@dataclass
class Wasser(Medium):
    def zustand(self, theta: float, p: float = P_NORM) -> Zustand:
        self.pruefe(theta)
        sw = stoffwerte("wasser", theta)
        return Zustand(theta, p, sw.rho, sw.nu * 1e-6 * sw.rho, sw.cp, dampfdruck(theta) * 1000)


@dataclass
class WasserBasis(Medium):
    """Wasser mit Dichtezuschlag und Viskositätsfaktor (bzw. äquivalenter Viskosität bei 20 °C)."""

    d_rho: float = 0.0
    f_nu: float = 1.0
    nu20: float | None = None      # äquivalente kin. Viskosität bei 20 °C in mm²/s (Schlamm)

    def zustand(self, theta: float, p: float = P_NORM) -> Zustand:
        self.pruefe(theta)
        sw = stoffwerte("wasser", theta)
        rho = sw.rho + self.d_rho
        if self.nu20 is not None:   # Temperaturgang wie Wasser
            nu = self.nu20 * sw.nu / stoffwerte("wasser", 20).nu
        else:
            nu = sw.nu * self.f_nu
        return Zustand(theta, p, rho, nu * 1e-6 * rho, sw.cp, dampfdruck(theta) * 1000)


# -------------------------------------------------------------------- Tabelle
@dataclass
class Tabelle(Medium):
    """Stützstellen (θ °C, ρ kg/m³, μ mPa·s, c_p kJ/(kg·K)); Dampfdruck wie Wasser (konservativ)."""

    punkte: list[tuple[float, float, float, float]] = field(default_factory=list)
    pv_wasser: bool = True

    def zustand(self, theta: float, p: float = P_NORM) -> Zustand:
        self.pruefe(theta)
        ts = [q[0] for q in self.punkte]
        rho = _interp(ts, [q[1] for q in self.punkte], theta)
        mu = math.exp(_interp(ts, [math.log(q[2]) for q in self.punkte], theta)) / 1000
        cp = _interp(ts, [q[3] for q in self.punkte], theta)
        pv = dampfdruck(min(max(theta, 0.0), 150.0)) * 1000 if self.pv_wasser else 0.0
        return Zustand(theta, p, rho, mu, cp, pv)


# -------------------------------------------------------------------- Walther
@dataclass
class Walther(Medium):
    """Öl: ν(θ) aus zwei Stützwerten nach Ubbelohde-Walther, ρ(θ) = ρ₁₅·(1 − α·(θ − 15))."""

    rho15: float = 880.0
    t1: float = 40.0
    nu1: float = 46.0
    t2: float = 100.0
    nu2: float = 6.8
    alpha: float = 0.00065
    cp20: float = 1.88
    dcp: float = 0.0037

    def _ab(self) -> tuple[float, float]:
        y1 = math.log10(math.log10(self.nu1 + 0.7))
        y2 = math.log10(math.log10(self.nu2 + 0.7))
        x1, x2 = math.log10(self.t1 + 273.15), math.log10(self.t2 + 273.15)
        b = (y1 - y2) / (x2 - x1)
        return y1 + b * x1, b

    def nu_mm2(self, theta: float) -> float:
        a, b = self._ab()
        return 10 ** (10 ** (a - b * math.log10(theta + 273.15))) - 0.7

    def zustand(self, theta: float, p: float = P_NORM) -> Zustand:
        self.pruefe(theta)
        rho = self.rho15 * (1 - self.alpha * (theta - 15))
        nu = self.nu_mm2(theta) * 1e-6
        return Zustand(theta, p, rho, nu * rho, self.cp20 + self.dcp * (theta - 20), 0.0)


# ------------------------------------------------------------------------ Gas
@dataclass(frozen=True)
class Komponente:
    name: str
    M: float        # g/mol
    Tc: float       # K
    Pc: float       # bar
    omega: float
    mu0: float      # Pa·s bei T0
    T0: float
    S: float        # Sutherland-Konstante K
    cp25: float     # kJ/(kg·K) ideal bei 25 °C
    dcp: float      # kJ/(kg·K²)

    def mu(self, T: float) -> float:
        return self.mu0 * (T / self.T0) ** 1.5 * (self.T0 + self.S) / (T + self.S)


KOMP = {
    "CH4": Komponente("Methan", 16.043, 190.6, 46.0, 0.011, 11.07e-6, 293.15, 198, 2.226, 0.0035),
    "C2H6": Komponente("Ethan", 30.07, 305.3, 48.7, 0.099, 9.2e-6, 293.15, 252, 1.75, 0.0045),
    "CO2": Komponente("Kohlendioxid", 44.01, 304.1, 73.8, 0.225, 14.7e-6, 293.15, 240, 0.846, 0.0009),
    "N2": Komponente("Stickstoff", 28.013, 126.2, 33.9, 0.039, 17.6e-6, 293.15, 111, 1.040, 0.00008),
    "O2": Komponente("Sauerstoff", 31.999, 154.6, 50.4, 0.022, 20.3e-6, 293.15, 127, 0.918, 0.00015),
    "Ar": Komponente("Argon", 39.948, 150.9, 49.0, 0.0, 22.3e-6, 293.15, 144, 0.520, 0.0),
}


@dataclass
class Gas(Medium):
    zusammensetzung: dict[str, float] = field(default_factory=dict)   # Molanteile

    def _mix(self):
        y = {k: v / sum(self.zusammensetzung.values()) for k, v in self.zusammensetzung.items()}
        M = sum(y[k] * KOMP[k].M for k in y)
        Tc = sum(y[k] * KOMP[k].Tc for k in y)
        Pc = sum(y[k] * KOMP[k].Pc for k in y) * 1e5
        om = sum(y[k] * KOMP[k].omega for k in y)
        return y, M, Tc, Pc, om

    @property
    def M(self) -> float:
        return self._mix()[1]

    def Z(self, theta: float, p: float) -> float:
        _, _, Tc, Pc, om = self._mix()
        Tr, Pr = (theta + 273.15) / Tc, p / Pc
        B0 = 0.083 - 0.422 / Tr**1.6
        B1 = 0.139 - 0.172 / Tr**4.2
        return 1 + (B0 + om * B1) * Pr / Tr

    def normdichte(self) -> float:
        """Dichte im Normzustand (0 °C, 1,01325 bar) in kg/m³."""
        return self.zustand(0.0, P_NORM).rho

    def zustand(self, theta: float, p: float = P_NORM) -> Zustand:
        self.pruefe(theta)
        if p <= 0:
            raise ValueError("Der Absolutdruck muss größer als null sein.")
        y, M, *_ = self._mix()
        T = theta + 273.15
        Z = self.Z(theta, p)
        rho = p * M / 1000 / (Z * R * T)
        num = sum(y[k] * KOMP[k].mu(T) * math.sqrt(KOMP[k].M) for k in y)
        den = sum(y[k] * math.sqrt(KOMP[k].M) for k in y)
        cp = sum(y[k] * KOMP[k].M * (KOMP[k].cp25 + KOMP[k].dcp * (theta - 25)) for k in y) / M
        return Zustand(theta, p, rho, num / den, cp, 0.0, Z)


# ----------------------------------------------------------------------- Fett
@dataclass
class Fett(Medium):
    def zustand(self, theta: float, p: float = P_NORM) -> Zustand:
        raise ValueError(f"{self.name}: Schmierfette sind nicht-newtonsch (Fließgrenze) – keine "
                         "Strömungsrechnung mit einer Viskosität möglich. Förderung mit Schmierstoff- bzw. "
                         "Verdrängerpumpen nach Herstellerangabe.")


# ================================================================== Datenbank
W_ABW = "Wasser / Abwasser"
W_WT = "Wärmeträger / Sole"
W_OEL = "Öle / Brennstoffe"
W_LM = "Lebensmittel"
W_GAS = "Gase"
W_FETT = "Schmierfette"

_SCHLAMM_HINWEIS = ("Klärschlamm ist nicht-newtonsch (Bingham-Fluid mit Fließgrenze). Die äquivalente Viskosität "
                    "liefert überschlägige Druckverluste im turbulenten Bereich; bei langen Leitungen, kleinen "
                    "Geschwindigkeiten oder höherem TS Fließkurve des Schlamms bzw. Erfahrungswerte verwenden.")


def _oel(id_, name, vg, nu100, rho15, hinweis="", **kw):
    return Walther(id_, name, W_OEL, "fluessig", -10, 120, hinweis or
                   f"Mineralöl ISO VG {vg} (ν₄₀ = {vg} mm²/s, ν₁₀₀ ≈ {_f(nu100)} mm²/s, VI ≈ 100). "
                   "Viskosität nach Ubbelohde-Walther; Herstellerdatenblatt beachten.",
                   rho15=rho15, t1=40, nu1=vg, t2=100, nu2=nu100, **kw)


MEDIEN: list[Medium] = [
    Wasser("wasser", "Wasser", W_ABW, "fluessig", 0, 150, "Reines Wasser, Stoffwerte nach VDI-Wärmeatlas."),
    WasserBasis("abwasser_zulauf", "Abwasser kommunal (Zulauf)", W_ABW, "fluessig", 0, 80,
                "Rohabwasser mit geringem Feststoffanteil: ρ ≈ Wasser + 2 kg/m³, ν ≈ 1,1 · Wasser. "
                "Feststoffe/Zöpfe erfordern Freistromrad bzw. freien Kugeldurchgang.", d_rho=2.0, f_nu=1.1),
    WasserBasis("klaerwasser", "Klärwasser / Abwasser gereinigt (Ablauf)", W_ABW, "fluessig", 0, 80,
                "Gereinigtes Abwasser – Stoffwerte praktisch wie Wasser.", d_rho=0.5, f_nu=1.02),
    *[WasserBasis(f"klaerschlamm_{ts}", f"Klärschlamm TS {ts} %", W_ABW, "fluessig", 5, 80,
                  _SCHLAMM_HINWEIS, newtonsch=False, d_rho=d, nu20=n,
                  kennwerte={"Trockensubstanz": f"{ts} %", "Äquivalente Viskosität 20 °C": f"{_f(n)} mm²/s"})
      for ts, d, n in ((2, 5.0, 6.0), (4, 10.0, 25.0), (5, 12.0, 45.0), (6, 15.0, 80.0))],

    Tabelle("eg30", "Ethylenglykol 30 % (Masse)", W_WT, "fluessig", -10, 100,
            "Wasser-Ethylenglykol, Frostschutz bis ca. −15 °C (z. B. Antifrogen N). Richtwerte ±5 %.",
            kennwerte={"Gefrierpunkt": "≈ −15 °C"},
            punkte=[(-10, 1048, 5.2, 3.64), (0, 1045, 3.6, 3.68), (20, 1038, 2.0, 3.73), (40, 1030, 1.3, 3.78),
                    (60, 1020, 0.9, 3.84), (80, 1009, 0.67, 3.89), (100, 996, 0.52, 3.94)]),
    Tabelle("eg40", "Ethylenglykol 40 % (Masse)", W_WT, "fluessig", -20, 100,
            "Wasser-Ethylenglykol, Frostschutz bis ca. −24 °C. Richtwerte ±5 %.",
            kennwerte={"Gefrierpunkt": "≈ −24 °C"},
            punkte=[(-20, 1071, 11.0, 3.40), (-10, 1067, 7.1, 3.43), (0, 1062, 4.8, 3.47), (20, 1053, 2.6, 3.53),
                    (40, 1043, 1.6, 3.60), (60, 1032, 1.1, 3.67), (80, 1020, 0.8, 3.73), (100, 1006, 0.62, 3.79)]),
    Tabelle("pg30", "Propylenglykol 30 % (Masse)", W_WT, "fluessig", -10, 100,
            "Wasser-Propylenglykol (lebensmittelverträglich, z. B. Antifrogen L), Frostschutz bis ca. −12 °C. "
            "Richtwerte ±5 %.", kennwerte={"Gefrierpunkt": "≈ −12 °C"},
            punkte=[(-10, 1036, 8.0, 3.80), (0, 1032, 5.3, 3.83), (20, 1025, 2.7, 3.87), (40, 1016, 1.6, 3.92),
                    (60, 1004, 1.0, 3.97), (80, 991, 0.72, 4.01), (100, 976, 0.55, 4.05)]),
    Tabelle("pg40", "Propylenglykol 40 % (Masse)", W_WT, "fluessig", -20, 100,
            "Wasser-Propylenglykol, Frostschutz bis ca. −21 °C. Richtwerte ±5 %.",
            kennwerte={"Gefrierpunkt": "≈ −21 °C"},
            punkte=[(-20, 1050, 25.0, 3.58), (-10, 1047, 13.0, 3.62), (0, 1043, 8.2, 3.66), (20, 1034, 3.9, 3.71),
                    (40, 1023, 2.2, 3.77), (60, 1011, 1.4, 3.84), (80, 997, 0.95, 3.90), (100, 982, 0.7, 3.96)]),

    Walther("heizoel", "Heizöl EL / Diesel", W_OEL, "fluessig", -5, 80,
            "Heizöl EL nach DIN 51603-1 bzw. Diesel nach EN 590 (ν₂₀ ≈ 4 mm²/s). Dampfdruck vernachlässigt.",
            rho15=840, t1=20, nu1=4.0, t2=40, nu2=2.7, alpha=0.00083, cp20=1.90, dcp=0.0036),
    _oel("vg32", "Schmieröl ISO VG 32", 32, 5.4, 870),
    _oel("vg46", "Schmieröl ISO VG 46", 46, 6.8, 875),
    _oel("hlp46", "Hydrauliköl HLP 46", 46, 6.8, 875,
         "Hydrauliköl HLP 46 nach DIN 51524-2 (ν₄₀ = 46 mm²/s, VI ≈ 100)."),
    _oel("vg68", "Schmieröl ISO VG 68", 68, 8.7, 880),
    _oel("vg100", "Schmieröl ISO VG 100", 100, 11.1, 885),
    _oel("vg150", "Schmieröl ISO VG 150", 150, 14.5, 890),
    _oel("vg220", "Schmieröl ISO VG 220", 220, 18.5, 895),
    _oel("vg320", "Schmieröl ISO VG 320", 320, 24.0, 900),
    _oel("vg460", "Schmieröl ISO VG 460", 460, 30.0, 905),

    Walther("speiseoel", "Speiseöl (Raps-/Sonnenblumenöl)", W_LM, "fluessig", 0, 120,
            "Pflanzliches Speiseöl, flüssig ab ca. 0 °C (ν₄₀ ≈ 35 mm²/s). Richtwerte.",
            rho15=920, t1=40, nu1=35, t2=100, nu2=8.0, alpha=0.00068, cp20=1.95, dcp=0.0030),
    Walther("speisefett", "Speisefett geschmolzen (Frittierfett, Talg, Schmalz)", W_LM, "fluessig", 45, 120,
            "Tierische und gehärtete Fette sind erst oberhalb ca. 40–45 °C flüssig – Leitungen begleitbeheizen, "
            "Erstarren beim Abkühlen beachten. Richtwerte (ν₆₀ ≈ 25 mm²/s).",
            kennwerte={"Schmelzbereich": "≈ 30–45 °C"},
            rho15=920, t1=60, nu1=25, t2=100, nu2=9.0, alpha=0.00072, cp20=2.0, dcp=0.0030),

    Gas("luft", "Luft (trocken)", W_GAS, "gas", -50, 400, "Trockene Luft (N₂ 78 %, O₂ 21 %, Ar 1 %).",
        zusammensetzung={"N2": 0.7808, "O2": 0.2095, "Ar": 0.0097}),
    Gas("stickstoff", "Stickstoff N₂", W_GAS, "gas", -50, 400, "Reiner Stickstoff.", zusammensetzung={"N2": 1.0}),
    Gas("co2", "Kohlendioxid CO₂ (gasförmig)", W_GAS, "gas", -20, 400,
        "Gasförmiges CO₂. Achtung: kritischer Punkt 31 °C / 73,8 bar – bei hohen Drücken und niedrigen "
        "Temperaturen flüssig bzw. überkritisch; das Gasmodell gilt nur deutlich darunter (≲ 30 bar).",
        zusammensetzung={"CO2": 1.0}),
    Gas("erdgas_h", "Erdgas H", W_GAS, "gas", -20, 200,
        "Modellzusammensetzung CH₄ 93 %, C₂H₆ 4 %, N₂ 2 %, CO₂ 1 % (Normdichte ≈ 0,77 kg/m³, DVGW G 260 "
        "Gruppe H). Für Abrechnung/Netzberechnung tatsächliche Gasbeschaffenheit verwenden.",
        zusammensetzung={"CH4": 0.93, "C2H6": 0.04, "N2": 0.02, "CO2": 0.01}),
    Gas("erdgas_l", "Erdgas L", W_GAS, "gas", -20, 200,
        "Modellzusammensetzung CH₄ 83 %, C₂H₆ 4 %, N₂ 12 %, CO₂ 1 % (Normdichte ≈ 0,82 kg/m³, Gruppe L).",
        zusammensetzung={"CH4": 0.83, "C2H6": 0.04, "N2": 0.12, "CO2": 0.01}),
    Gas("klaergas_60", "Klärgas / Biogas 60 % CH₄", W_GAS, "gas", -10, 100,
        "Trockenes Klärgas CH₄ 60 %, CO₂ 38 %, N₂ 2 %. Rohgas ist wasserdampfgesättigt (Kondensat, "
        "Entwässerungspunkte) und enthält H₂S.",
        zusammensetzung={"CH4": 0.60, "CO2": 0.38, "N2": 0.02}),
    Gas("klaergas_65", "Klärgas / Biogas 65 % CH₄", W_GAS, "gas", -10, 100,
        "Trockenes Klärgas CH₄ 65 %, CO₂ 33 %, N₂ 2 %.", zusammensetzung={"CH4": 0.65, "CO2": 0.33, "N2": 0.02}),

    *[Fett(f"fett_nlgi{k}", f"Schmierfett NLGI {k}", W_FETT, "pastoes", -20, 120,
           "Schmierfett – nicht-newtonsch mit Fließgrenze. Keine Strömungsrechnung; Kennwerte als Richtwerte. "
           "Förderung über Zentralschmierpumpen bzw. Fassförderpumpen nach Herstellerangabe.", newtonsch=False,
           kennwerte={"Walkpenetration (DIN ISO 2137)": pen, "Konsistenz": kons, "Dichte": "≈ 0,90–0,95 kg/l",
                      "Typische Grundölviskosität": "ISO VG 100–460", "Einsatz": einsatz})
      for k, pen, kons, einsatz in (
          ("000", "445–475", "fließfähig", "Zentralschmieranlagen, Getriebe"),
          ("00", "400–430", "halbflüssig", "Zentralschmieranlagen, Getriebe"),
          ("0", "355–385", "sehr weich", "Zentralschmieranlagen"),
          ("1", "310–340", "weich", "Wälzlager, Zentralschmierung"),
          ("2", "265–295", "mittel", "Wälz- und Gleitlager (Standard)"))],
]

_BY_ID = {m.id: m for m in MEDIEN}
GRUPPEN = list(dict.fromkeys(m.gruppe for m in MEDIEN))


def medium(mid: str) -> Medium:
    try:
        return _BY_ID[mid]
    except KeyError:
        raise ValueError(f"Unbekanntes Medium „{mid}“.") from None


def auswahl(*arten: str) -> list[tuple[str, str]]:
    """Optionen für ein Auswahlfeld, gefiltert nach Art ("fluessig", "gas")."""
    return [(m.id, m.name) for m in MEDIEN if not arten or m.art in arten]


def ids(*arten: str) -> list[str]:
    return [m.id for m in MEDIEN if m.art in arten]


# ------------------------------------------------- Helfer für Wärmerechner
@dataclass
class Waermestoff:
    name: str
    theta: float
    rho: float      # kg/m³
    cp: float       # kJ/(kg·K)


def waerme_auswahl() -> list[tuple[str, str]]:
    """Flüssigkeiten und Gase (bei 1 atm) für Wärmemengen- und Wärmetauscherrechner."""
    return [(m.id, m.name) for m in MEDIEN if m.art in ("fluessig", "gas")]


def waermestoff(mid: str, theta: float) -> Waermestoff:
    """ρ und c_p bei θ; Luft weiterhin aus der VDI-Tabelle (1 bar), sonst aus der Mediendatenbank."""
    if mid == "luft":
        sw = stoffwerte("luft", theta)
        return Waermestoff("Luft (1 bar)", theta, sw.rho, sw.cp)
    m = medium(mid)
    z = m.zustand(theta)
    return Waermestoff(m.name, theta, z.rho, z.cp)
