"""Wälzlager-Lebensdauer nach ISO 281 (nominelle und modifizierte), optional Lagerkräfte aus Zahnkräften."""

from __future__ import annotations

import math

import numpy as np

from ingrechner.core.model import Calculator, ChoiceField, NumberField
from ingrechner.core.svg import ACCENT, INK, MUTED, Svg
from ingrechner.core.units import Q_, fmt_num

DIREKT = {"kraefte": ["direkt"]}
ZAHN = {"kraefte": ["zahnrad"]}
XY_FREI = {"xy": ["vorgabe"]}
RILLE = {"xy": ["rillenkugel"]}

# Rillenkugellager, normale Lagerluft (ISO 281 Tab. 3): f₀·F_a/C₀ -> (e, Y)
RILLENKUGEL = [(0.172, 0.19, 2.30), (0.345, 0.22, 1.99), (0.689, 0.26, 1.71), (1.03, 0.28, 1.55), (1.38, 0.30, 1.45),
               (2.07, 0.34, 1.31), (3.45, 0.38, 1.15), (5.17, 0.42, 1.04), (6.89, 0.44, 1.00)]
# Zuverlässigkeitsbeiwert a₁ (ISO 281:2007)
A1 = {"90": 1.0, "95": 0.64, "96": 0.55, "97": 0.47, "98": 0.37, "99": 0.25}


def rillenkugel_ey(f0fa_c0: float) -> tuple[float, float]:
    xs = [r[0] for r in RILLENKUGEL]
    q = min(max(f0fa_c0, xs[0]), xs[-1])
    for (x0, e0, y0), (x1, e1, y1) in zip(RILLENKUGEL, RILLENKUGEL[1:]):
        if x0 <= q <= x1:
            t = (q - x0) / (x1 - x0)
            return e0 + t * (e1 - e0), y0 + t * (y1 - y0)
    return RILLENKUGEL[-1][1:]


class Waelzlager(Calculator):
    id = "mb.waelzlager"
    title = "Wälzlager – Lebensdauer"
    category = "Maschinenbau"
    description = (
        "Nominelle Lebensdauer L₁₀ bzw. L₁₀h und modifizierte Lebensdauer L_nm eines Wälzlagers nach ISO 281: "
        "äquivalente Last mit X/Y-Faktoren (Rillenkugellager automatisch), Zuverlässigkeit, statische Kennzahl "
        "und erforderliche Tragzahl. Lagerkräfte wahlweise direkt oder aus den Zahnkräften eines Zahnrads "
        "zwischen zwei Lagern."
    )
    norm = "L₁₀ = (C/P)^p · 10⁶ U, p = 3 (Kugel) bzw. 10/3 (Rolle); L_nm = a₁·a_ISO·L₁₀; P = X·F_r + Y·F_a (ISO 281)"
    keywords = ("wälzlager", "kugellager", "rollenlager", "lebensdauer", "l10", "l10h", "tragzahl", "iso 281",
                "lager", "äquivalente last", "rillenkugellager", "lagerkraft", "getriebe")

    fields = [
        ChoiceField("art", "Lagerart", [("kugel", "Kugellager (p = 3)"), ("rolle", "Rollenlager (p = 10/3)")], "kugel"),
        ChoiceField("kraefte", "Lagerkräfte", [("direkt", "direkt vorgeben"),
                                               ("zahnrad", "aus Zahnkräften (Rad zwischen zwei Lagern)")], "direkt"),
        NumberField("Fr", "Radialkraft", "F_r", "N", 3000, min=0, min_inclusive=True, decimals=0, visible_if=DIREKT),
        NumberField("Fa", "Axialkraft", "F_a", "N", 800, min=0, min_inclusive=True, decimals=0, visible_if=DIREKT),
        NumberField("Ft", "Umfangskraft am Zahnrad", "F_t", "N", 4000, min=0, min_inclusive=True, decimals=0,
                    visible_if=ZAHN),
        NumberField("Fr_z", "Radialkraft am Zahnrad", "F_r,Z", "N", 1600, min=0, min_inclusive=True, decimals=0,
                    visible_if=ZAHN),
        NumberField("Fa_z", "Axialkraft am Zahnrad", "F_a,Z", "N", 1100, min=0, min_inclusive=True, decimals=0,
                    visible_if=ZAHN),
        NumberField("dw", "Wälzkreisdurchmesser", "d_w", "mm", 60, min=0, decimals=1, visible_if=ZAHN),
        NumberField("la", "Abstand Lager A – Zahnrad", "l_A", "mm", 50, min=0, decimals=1, visible_if=ZAHN),
        NumberField("lb", "Abstand Zahnrad – Lager B", "l_B", "mm", 90, min=0, decimals=1, visible_if=ZAHN),
        ChoiceField("lager", "Nachzuweisendes Lager", [("A", "Lager A (nimmt die Axialkraft auf – Festlager)"),
                                                       ("B", "Lager B (Loslager)")], "A", visible_if=ZAHN),
        ChoiceField("xy", "X/Y-Faktoren", [("rillenkugel", "Rillenkugellager (automatisch, ISO 281)"),
                                           ("vorgabe", "aus Katalog vorgeben"), ("radial", "nur Radiallast (X = 1)")],
                    "rillenkugel"),
        NumberField("f0", "Berechnungsfaktor f₀", "f₀", "", 14, min=5, max=20, decimals=1, visible_if=RILLE,
                    tooltip="Katalogwert des Rillenkugellagers (meist 12–16)"),
        NumberField("e", "Grenzwert e", "e", "", 0.3, min=0, decimals=3, visible_if=XY_FREI),
        NumberField("X", "Radialfaktor X (F_a/F_r > e)", "X", "", 0.56, min=0, decimals=3, visible_if=XY_FREI),
        NumberField("Y", "Axialfaktor Y (F_a/F_r > e)", "Y", "", 1.5, min=0, min_inclusive=True, decimals=3,
                    visible_if=XY_FREI),
        NumberField("C", "Dynamische Tragzahl", "C", "kN", 35.1, min=0, decimals=2),
        NumberField("C0", "Statische Tragzahl", "C₀", "kN", 19.0, min=0, decimals=2),
        NumberField("n", "Drehzahl", "n", "1/minute", 1450, min=0, decimals=1),
        ChoiceField("zuv", "Zuverlässigkeit", [(k, f"{k} %") for k in A1], "90"),
        NumberField("aiso", "Lebensdauerbeiwert (ISO 281)", "a_ISO", "", 1.0, min=0.1, max=50, decimals=2,
                    tooltip="Schmierung und Verunreinigung nach ISO 281 bzw. Herstellerverfahren; 1 = nominell"),
        NumberField("Lsoll", "Geforderte Lebensdauer", "L_h,soll", "hour", 20000, min=0, decimals=0,
                    tooltip="Getriebe 8 h/d: 10 000–25 000 h; Dauerbetrieb 24 h/d: 40 000–60 000 h"),
    ]

    def _kraefte(self, inp) -> tuple[float, float]:
        if inp["kraefte"] == "direkt":
            return inp["Fr"].to("N").magnitude, inp["Fa"].to("N").magnitude
        Ft, Frz, Faz = (inp[k].to("N").magnitude for k in ("Ft", "Fr_z", "Fa_z"))
        la, lb = inp["la"].to("mm").magnitude, inp["lb"].to("mm").magnitude
        rz = inp["dw"].to("mm").magnitude / 2
        L = la + lb
        if L <= 0:
            raise ValueError("Der Lagerabstand muss größer als null sein.")
        # Tangentialebene: nur F_t;  Radialebene: F_r und Kippmoment F_a·r
        At, Bt = Ft * lb / L, Ft * la / L
        Ar, Br = (Frz * lb + Faz * rz) / L, (Frz * la - Faz * rz) / L
        A, B = math.hypot(At, Ar), math.hypot(Bt, Br)
        self.step("Lagerkräfte", "Tangentialebene: A_t = F_t·l_B/l, B_t = F_t·l_A/l;  Radialebene mit F_a·d_w/2",
                  f"l = {fmt_num(L, 1)} mm: A_t = {fmt_num(At, 0)}, A_r = {fmt_num(Ar, 0)}, B_t = {fmt_num(Bt, 0)}, "
                  f"B_r = {fmt_num(Br, 0)} N", f"F_A = {fmt_num(A, 0)} N, F_B = {fmt_num(B, 0)} N")
        return (A, Faz) if inp["lager"] == "A" else (B, 0.0)

    def compute(self, inp) -> None:
        Fr, Fa = self._kraefte(inp)
        C = inp["C"].to("N").magnitude
        C0 = inp["C0"].to("N").magnitude
        n = inp["n"].to("1/minute").magnitude
        p = 3.0 if inp["art"] == "kugel" else 10 / 3
        xy = inp["xy"]
        if xy == "radial" or Fa == 0:
            X, Y, e = 1.0, 0.0, float("inf")
        elif xy == "rillenkugel":
            e, Yv = rillenkugel_ey(float(inp["f0"]) * Fa / C0)
            X, Y = (1.0, 0.0) if Fr > 0 and Fa / Fr <= e else (0.56, Yv)
            self.step("X/Y-Faktoren (Rillenkugellager)", "e, Y aus f₀·F_a/C₀ (ISO 281); X = 0,56 für F_a/F_r > e",
                      f"f₀·F_a/C₀ = {fmt_num(float(inp['f0']) * Fa / C0, 3)}, F_a/F_r = "
                      f"{fmt_num(Fa / Fr if Fr else float('inf'), 3)}", f"e = {fmt_num(e, 3)}, X = {fmt_num(X, 2)}, "
                      f"Y = {fmt_num(Y, 2)}")
        else:
            e = float(inp["e"])
            X, Y = (1.0, 0.0) if Fr > 0 and Fa / Fr <= e else (float(inp["X"]), float(inp["Y"]))
        P = max(X * Fr + Y * Fa, Fr)
        self.step("Äquivalente dynamische Last", "P = X·F_r + Y·F_a (≥ F_r)",
                  f"P = {fmt_num(X, 2)}·{fmt_num(Fr, 0)} + {fmt_num(Y, 2)}·{fmt_num(Fa, 0)}", f"{fmt_num(P, 0)} N")
        if P <= 0:
            raise ValueError("Das Lager ist unbelastet (P = 0).")
        L10 = (C / P) ** p
        L10h = L10 * 1e6 / (60 * n) if n > 0 else float("inf")
        a1 = A1[inp["zuv"]]
        aiso = float(inp["aiso"])
        Lnmh = a1 * aiso * L10h
        self.step("Nominelle Lebensdauer", "L₁₀ = (C/P)^p;  L₁₀h = L₁₀·10⁶/(60·n)",
                  f"L₁₀ = ({fmt_num(C / 1000, 2)} kN / {fmt_num(P / 1000, 3)} kN)^{fmt_num(p, 3)}",
                  f"{fmt_num(L10, 1)} · 10⁶ U = {fmt_num(L10h, 0)} h")
        self.step("Modifizierte Lebensdauer", "L_nmh = a₁ · a_ISO · L₁₀h",
                  f"a₁ = {fmt_num(a1, 2)} ({inp['zuv']} %), a_ISO = {fmt_num(aiso, 2)}", f"{fmt_num(Lnmh, 0)} h")
        P0 = max(0.6 * Fr + 0.5 * Fa, Fr) if inp["art"] == "kugel" else Fr + (0 if Fa == 0 else 0)
        S0 = C0 / P0 if P0 else float("inf")
        Lsoll = inp["Lsoll"].to("hour").magnitude
        C_erf = P * (Lsoll * 60 * n / 1e6 / (a1 * aiso)) ** (1 / p) if n > 0 else 0
        self.result("Lh", "Nominelle Lebensdauer", "L₁₀h", Q_(L10h, "hour"), "hour", 0, highlight=True)
        self.result("Lnmh", "Modifizierte Lebensdauer", "L_nmh", Q_(Lnmh, "hour"), "hour", 0, highlight=True)
        self.result("L10", "Nominelle Lebensdauer (Umdrehungen)", "L₁₀", Q_(L10, ""), "", 1)
        self.result("P", "Äquivalente dynamische Last", "P", Q_(P, "N"), "N", 0)
        self.result("Fr", "Radiallast am Lager", "F_r", Q_(Fr, "N"), "N", 0)
        self.result("Fa", "Axiallast am Lager", "F_a", Q_(Fa, "N"), "N", 0)
        self.result("CP", "Tragzahlverhältnis", "C/P", Q_(C / P, ""), "", 2)
        self.result("S0", "Statische Kennzahl", "S₀", Q_(S0, ""), "", 2)
        self.result("Cerf", "Erforderliche dynamische Tragzahl", "C_erf", Q_(C_erf, "N"), "kN", 2, highlight=True)
        if Lnmh < Lsoll:
            self.warn(f"Lebensdauer {fmt_num(Lnmh, 0)} h < gefordert {fmt_num(Lsoll, 0)} h – Lager mit "
                      f"C ≥ {fmt_num(C_erf / 1000, 1)} kN wählen.")
        else:
            self.info(f"Geforderte Lebensdauer {fmt_num(Lsoll, 0)} h erreicht.")
        if S0 < 1:
            self.warn(f"Statische Kennzahl S₀ = {fmt_num(S0, 2)} < 1 – bleibende Verformungen; S₀ ≥ 1–2 (Stöße ≥ 2) "
                      "anstreben.")
        if P > 0.5 * C:
            self.warn("P > 0,5·C – sehr hohe Belastung, außerhalb des Gültigkeitsbereichs der Lebensdauerformel.")
        elif P < 0.01 * C:
            self.info("Sehr geringe Belastung (P < 0,01·C) – Mindestbelastung gegen Schlupf beachten.")

    def plot(self, fig, raw, result) -> bool:
        if not result.ok:
            return False
        p = 3.0 if raw.get("art", "kugel") == "kugel" else 10 / 3
        C = float(raw["C"]) * 1000
        n = float(raw["n"])
        P0 = result.value("P")
        Ps = np.linspace(P0 * 0.3, P0 * 2.5, 100)
        ax = fig.subplots()
        ax.plot(Ps / 1000, (C / Ps) ** p * 1e6 / (60 * n), color="#1f6fb2", lw=2)
        ax.plot([P0 / 1000], [result.value("Lh")], "o", color="#c0392b")
        ax.axhline(float(raw["Lsoll"]), color="#2b3a4a", ls="--", lw=1, label="gefordert")
        ax.set_yscale("log")
        ax.set_xlabel("Äquivalente Last P  [kN]")
        ax.set_ylabel("L₁₀h  [h]")
        ax.set_title("Lebensdauer über der Belastung")
        ax.grid(True, alpha=0.3, which="both")
        ax.legend()
        return True

    def sketch_svg(self, raw) -> str:
        s = Svg()
        s.line(30, 110, 330, 110, INK, 10)
        for x, t in ((80, "A"), (290, "B")):
            s.rect(x - 15, 120, 30, 26, fill="#dce6f1").circle(x, 133, 7, fill="#9aa7b4")
            s.text(x, 166, t, 13, INK, bold=True)
        s.rect(150, 70, 40, 80, fill="#f5d7d3")
        s.arrow(170, 40, 170, 68, "#c0392b").text(176, 46, "Zahnkräfte", 11, INK, "start")
        s.arrow(120, 60, 148, 60, ACCENT).text(100, 54, "F_a", 11, INK, "end", True)
        s.dim_h(80, 170, 200, "l_A").dim_h(170, 290, 200, "l_B")
        return s.render()
