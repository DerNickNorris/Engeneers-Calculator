"""Gemeinsame Grundlagen der Getrieberechner: Evolventengeometrie, Betriebsfaktor, Werkstoffe, Normtabellen."""

from __future__ import annotations

import math
from dataclasses import dataclass

from ingrechner.core.model import NumberField


def inv(a: float) -> float:
    """Evolventenfunktion inv α = tan α − α (α in rad)."""
    return math.tan(a) - a


def inv_umkehr(y: float) -> float:
    """α zu inv α = y (Newton-Verfahren)."""
    a = (3 * y) ** (1 / 3) if y > 0 else 0.0
    for _ in range(50):
        f = inv(a) - y
        d = math.tan(a) ** 2
        if d == 0:
            break
        a_neu = a - f / d
        if abs(a_neu - a) < 1e-14:
            return a_neu
        a = a_neu
    return a


@dataclass
class Radpaar:
    """Geometrie eines Stirnradpaars (Außenverzahnung) nach DIN 3960 / ISO 21771. Längen in mm, Winkel in rad."""

    mn: float
    z1: int
    z2: int
    beta: float
    alpha_n: float
    x1: float
    x2: float
    b: float
    ha: float = 1.0      # Kopfhöhenfaktor h_aP*
    hf: float = 1.25     # Fußhöhenfaktor h_fP*

    def __post_init__(self) -> None:
        mn, z1, z2 = self.mn, self.z1, self.z2
        self.mt = mn / math.cos(self.beta)
        self.alpha_t = math.atan(math.tan(self.alpha_n) / math.cos(self.beta))
        self.beta_b = math.atan(math.tan(self.beta) * math.cos(self.alpha_t))
        self.d1, self.d2 = z1 * self.mt, z2 * self.mt
        self.db1, self.db2 = self.d1 * math.cos(self.alpha_t), self.d2 * math.cos(self.alpha_t)
        self.u = z2 / z1
        sx = self.x1 + self.x2
        self.alpha_wt = inv_umkehr(2 * sx * math.tan(self.alpha_n) / (z1 + z2) + inv(self.alpha_t))
        self.ad = (z1 + z2) * self.mt / 2                       # Null-Achsabstand
        self.a = self.ad * math.cos(self.alpha_t) / math.cos(self.alpha_wt)
        self.dw1 = 2 * self.a / (1 + self.u)
        self.dw2 = 2 * self.a * self.u / (1 + self.u)
        self.k = (self.a - self.ad) / mn - sx                    # Kopfhöhenänderungsfaktor (≤ 0 = Kopfkürzung)
        self.da1 = self.d1 + 2 * mn * (self.ha + self.x1 + self.k)
        self.da2 = self.d2 + 2 * mn * (self.ha + self.x2 + self.k)
        self.df1 = self.d1 - 2 * mn * (self.hf - self.x1)
        self.df2 = self.d2 - 2 * mn * (self.hf - self.x2)
        ga = math.sqrt(self.da1**2 - self.db1**2) / 2 + math.sqrt(self.da2**2 - self.db2**2) / 2 \
            - self.a * math.sin(self.alpha_wt)
        self.eps_a = ga / (math.pi * self.mt * math.cos(self.alpha_t))
        self.eps_b = self.b * math.sin(self.beta) / (math.pi * mn)
        self.eps_g = self.eps_a + self.eps_b
        self.zn1 = z1 / (math.cos(self.beta_b) ** 2 * math.cos(self.beta))
        self.zn2 = z2 / (math.cos(self.beta_b) ** 2 * math.cos(self.beta))

    # ------------------------------------------------------------ Prüfmaße
    def zahnweite(self, z: int, x: float) -> tuple[int, float]:
        """Messzähnezahl k und Zahnweite W_k in mm."""
        zw = z * inv(self.alpha_t) / inv(self.alpha_n)           # Ersatzzähnezahl für die Zahnweite
        k = max(2, round(zw * self.alpha_n / math.pi + 0.5 + 2 * x * math.tan(self.alpha_n) / math.pi))
        wk = self.mn * math.cos(self.alpha_n) * ((k - 0.5) * math.pi + z * inv(self.alpha_t)) \
            + 2 * x * self.mn * math.sin(self.alpha_n)
        return k, wk

    def kopfdicke(self, z: int, x: float, da: float, d: float) -> float:
        """Zahndicke am Kopfkreis im Normalschnitt (mm)."""
        db = d * math.cos(self.alpha_t)
        a_at = math.acos(db / da)
        s_at = da * ((math.pi + 4 * x * math.tan(self.alpha_n)) / (2 * z) + inv(self.alpha_t) - inv(a_at))
        beta_a = math.atan(math.tan(self.beta) * da / d)
        return s_at * math.cos(beta_a)

    def x_min(self, z: int) -> float:
        """Grenze gegen Unterschnitt (ohne Kopfrundung des Werkzeugs)."""
        return self.ha - z * math.sin(self.alpha_t) ** 2 / (2 * math.cos(self.beta))


def radpaar_felder() -> list:
    return [
        NumberField("mn", "Normalmodul", "m_n", "mm", 3, min=0, decimals=3),
        NumberField("z1", "Zähnezahl Ritzel", "z₁", "", 19, min=6, max=500, min_inclusive=True, decimals=0),
        NumberField("z2", "Zähnezahl Rad", "z₂", "", 71, min=6, max=2000, min_inclusive=True, decimals=0),
        NumberField("beta", "Schrägungswinkel", "β", "degree", 15, min=0, max=45, min_inclusive=True, decimals=2,
                    tooltip="0° = Geradverzahnung; Industriegetriebe meist 8–20°"),
        NumberField("alpha", "Normaleingriffswinkel", "α_n", "degree", 20, min=10, max=30, decimals=1),
        NumberField("x1", "Profilverschiebung Ritzel", "x₁", "", 0.3, min=-1, max=1.5, min_inclusive=True,
                    decimals=3),
        NumberField("x2", "Profilverschiebung Rad", "x₂", "", -0.1, min=-1.5, max=1.5, min_inclusive=True,
                    decimals=3),
        NumberField("b", "Zahnbreite (tragend)", "b", "mm", 40, min=0, decimals=1),
    ]


def radpaar(inp) -> Radpaar:
    return Radpaar(inp["mn"].to("mm").magnitude, int(round(inp["z1"])), int(round(inp["z2"])),
                   inp["beta"].to("radian").magnitude, inp["alpha"].to("radian").magnitude,
                   float(inp["x1"]), float(inp["x2"]), inp["b"].to("mm").magnitude)


# ------------------------------------------------------------- Betriebsfaktor
# Richtwerte nach gängiger Herstellersystematik (Laststoßgrad × tägliche Laufzeit) …
F_B_GRUND = {
    "I": (1.0, 1.15, 1.25),       # gleichförmig
    "II": (1.25, 1.4, 1.5),       # mäßige Stöße
    "III": (1.5, 1.7, 1.8),       # starke Stöße
}
LASTSTOSS = [("I", "I – gleichförmig (Förderband, Lüfter, Pumpe)"),
             ("II", "II – mäßige Stöße (Rührwerk, Hubwerk, Mischer)"),
             ("III", "III – starke Stöße (Brecher, Presse, Schwingförderer)")]


def betriebsfaktor(klasse: str, stunden: float, schaltungen: float) -> tuple[float, float, float]:
    """(f_B, Grundwert, Zuschlag Schalthäufigkeit)."""
    i = 0 if stunden <= 8 else 1 if stunden <= 16 else 2
    grund = F_B_GRUND[klasse][i]
    zu = 0.0 if schaltungen <= 10 else 0.1 if schaltungen <= 60 else 0.2 if schaltungen <= 200 else 0.3
    return grund + zu, grund, zu


# Zuschlagfaktor f_Z für Querkräfte von Übertragungselementen am Wellenende
F_Z = {"keins": ("kein Übertragungselement", 0.0), "zahnrad": ("Zahnrad (z ≥ 17)", 1.15),
       "kette": ("Kettenrad (z ≥ 13)", 1.4), "keilriemen": ("Keilriemenscheibe", 1.75),
       "flachriemen": ("Flachriemenscheibe", 2.5)}


# ------------------------------------------------------- Verzahnungswerkstoffe
@dataclass(frozen=True)
class ZahnWerkstoff:
    name: str
    sigma_hlim: float    # N/mm²
    sigma_flim: float    # N/mm²
    E: float             # N/mm²
    nu: float = 0.3
    gehaertet: bool = False


# Richtwerte (Werkstoffqualität etwa MQ nach ISO 6336-5); E = 206 000 N/mm² für Stahl → Z_E = 189,8 (DIN 3990)
ZAHN_WERKSTOFFE = {
    "16mncr5": ZahnWerkstoff("16MnCr5 einsatzgehärtet", 1470, 430, 206000, gehaertet=True),
    "18crnimo": ZahnWerkstoff("18CrNiMo7-6 einsatzgehärtet", 1500, 500, 206000, gehaertet=True),
    "42crmo4_n": ZahnWerkstoff("42CrMo4 vergütet + nitriert", 1100, 370, 206000, gehaertet=True),
    "34crnimo6": ZahnWerkstoff("34CrNiMo6 vergütet", 800, 320, 206000),
    "42crmo4": ZahnWerkstoff("42CrMo4 vergütet", 730, 300, 206000),
    "c45": ZahnWerkstoff("C45 vergütet", 590, 230, 206000),
    "gjs700": ZahnWerkstoff("EN-GJS-700-2", 620, 240, 175000, 0.28),
}


# Kopf-Formfaktor Y_Fa und Spannungskorrekturfaktor Y_Sa für x = 0 (Bezugsprofil 20°/1,0/1,25/0,25),
# Tabellenwerte DIN 3990-3 über der Ersatzzähnezahl z_n
_YF_TAB = [(17, 2.97, 1.52), (20, 2.80, 1.55), (25, 2.62, 1.59), (30, 2.52, 1.625), (40, 2.40, 1.67),
           (50, 2.32, 1.70), (60, 2.28, 1.73), (80, 2.22, 1.77), (100, 2.18, 1.79), (200, 2.12, 1.86),
           (1000, 2.06, 1.97)]


def y_fs(zn: float, x: float) -> float:
    """Kopffaktor Y_FS = Y_Fa · Y_Sa (Näherung: Tabellenwerte für x = 0, Profilverschiebung linear korrigiert)."""
    zs = [r[0] for r in _YF_TAB]
    zn_c = min(max(zn, zs[0]), zs[-1])
    i = next(i for i, z in enumerate(zs) if z >= zn_c)
    if i == 0:
        yfa, ysa = _YF_TAB[0][1:]
    else:
        (za, fa, sa), (zb, fb, sb) = _YF_TAB[i - 1], _YF_TAB[i]
        t = (zn_c - za) / (zb - za)
        yfa, ysa = fa + t * (fb - fa), sa + t * (sb - sa)
    return yfa * ysa - x * (0.2 + 12 / zn_c)


# ------------------------------------------------------------- Passfedern
# DIN 6885-1: Wellendurchmesser über … bis (mm) -> (b, h, t1, t2)
PASSFEDERN = [
    (6, 8, 2, 2, 1.2, 1.0), (8, 10, 3, 3, 1.8, 1.4), (10, 12, 4, 4, 2.5, 1.8), (12, 17, 5, 5, 3.0, 2.3),
    (17, 22, 6, 6, 3.5, 2.8), (22, 30, 8, 7, 4.0, 3.3), (30, 38, 10, 8, 5.0, 3.3), (38, 44, 12, 8, 5.0, 3.3),
    (44, 50, 14, 9, 5.5, 3.8), (50, 58, 16, 10, 6.0, 4.3), (58, 65, 18, 11, 7.0, 4.4), (65, 75, 20, 12, 7.5, 4.9),
    (75, 85, 22, 14, 9.0, 5.4), (85, 95, 25, 14, 9.0, 5.4), (95, 110, 28, 16, 10.0, 6.4),
    (110, 130, 32, 18, 11.0, 7.4), (130, 150, 36, 20, 12.0, 8.4), (150, 170, 40, 22, 13.0, 9.4),
    (170, 200, 45, 25, 15.0, 10.4), (200, 230, 50, 28, 17.0, 11.4),
]
PASSFEDER_LAENGEN = [6, 8, 10, 12, 14, 16, 18, 20, 22, 25, 28, 32, 36, 40, 45, 50, 56, 63, 70, 80, 90, 100, 110, 125,
                     140, 160, 180, 200, 220, 250, 280, 320, 360, 400]


def passfeder(d: float) -> tuple[float, float, float, float] | None:
    for lo, hi, b, h, t1, t2 in PASSFEDERN:
        if lo < d <= hi:
            return b, h, t1, t2
    return None
