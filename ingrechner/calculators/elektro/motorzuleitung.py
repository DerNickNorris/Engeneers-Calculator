"""Motorzuleitung & Schutz: Querschnitt nach Strombelastbarkeit und Spannungsfall, Motorschutz, Vorsicherung."""

from __future__ import annotations

import math

from ingrechner.core.model import Calculator, ChoiceField, NumberField
from ingrechner.core.svg import ACCENT, INK, MUTED, Svg
from ingrechner.core.units import Q_, fmt_num

QUERSCHNITTE = [1.5, 2.5, 4, 6, 10, 16, 25, 35, 50, 70, 95, 120, 150, 185, 240]
# Strombelastbarkeit Cu, PVC 70 °C, 3 belastete Adern, 30 °C Umgebung (DIN VDE 0298-4 / IEC 60364-5-52), in A
I_Z = {
    "A1": [13.5, 18, 24, 31, 42, 56, 73, 89, 108, 136, 164, 188],
    "A2": [13, 17.5, 23, 29, 39, 52, 68, 83, 99, 125, 150, 172],
    "B1": [15.5, 21, 28, 36, 50, 68, 89, 110, 134, 171, 207, 239],
    "B2": [15, 20, 27, 34, 46, 62, 80, 99, 118, 149, 179, 206],
    "C": [17.5, 24, 32, 41, 57, 76, 96, 119, 144, 184, 223, 259, 299, 341, 403],
    "E": [18.5, 25, 34, 43, 60, 80, 101, 126, 153, 196, 238, 276, 319, 364, 430],
}
VERLEGEART = {"A1": "A1 – Aderleitungen im Rohr in wärmegedämmter Wand", "A2": "A2 – Kabel im Rohr in wärmegedämmter Wand",
              "B1": "B1 – Aderleitungen im Rohr auf der Wand", "B2": "B2 – Kabel im Rohr auf der Wand",
              "C": "C – Kabel direkt auf der Wand", "E": "E – Kabel frei in Luft (Kabelpritsche)"}
F_TEMP = [(10, 1.22), (15, 1.17), (20, 1.12), (25, 1.06), (30, 1.0), (35, 0.94), (40, 0.87), (45, 0.79), (50, 0.71),
          (55, 0.61), (60, 0.50)]
F_HAEUF = {1: 1.0, 2: 0.80, 3: 0.70, 4: 0.65, 5: 0.60, 6: 0.57, 7: 0.54, 8: 0.52, 9: 0.50, 12: 0.45, 16: 0.41,
           20: 0.38}
SICHERUNGEN = [2, 4, 6, 10, 13, 16, 20, 25, 32, 35, 40, 50, 63, 80, 100, 125, 160, 200, 250, 315, 400, 500, 630]
# Zulässiges Verhältnis I_A/I_n einer gG-Sicherung abhängig von der Anlaufzeit (Richtwerte aus Zeit-Strom-Kennlinien)
GG_ANLAUF = [(2, 5.0), (5, 4.0), (10, 3.3), (20, 2.8)]
KAPPA_CU = 56.0 / (1 + 0.00393 * 50)    # 70 °C
DIR = {"vorgabe": ["leistung"]}
STROM = {"vorgabe": ["strom"]}


def interp(tab, x):
    xs = [a for a, _ in tab]
    x = min(max(x, xs[0]), xs[-1])
    for (x0, y0), (x1, y1) in zip(tab, tab[1:]):
        if x0 <= x <= x1:
            return y0 + (x - x0) / (x1 - x0) * (y1 - y0)
    return tab[-1][1]


def haeufung(n: int) -> float:
    keys = sorted(F_HAEUF)
    k = max(x for x in keys if x <= max(n, 1))
    return F_HAEUF[k]


def spannungsfall(I: float, L: float, S: float, U: float, cosphi: float) -> float:
    R = L / (KAPPA_CU * S)
    X = 0.08e-3 * L
    return math.sqrt(3) * I * (R * cosphi + X * math.sqrt(max(1 - cosphi**2, 0))) / U * 100


class Motorzuleitung(Calculator):
    id = "et.motorzuleitung"
    title = "Motorzuleitung & Schutz"
    category = "Elektrotechnik"
    description = (
        "Zuleitung eines Drehstrommotors: Bemessungsstrom, Einstellwert des Motorschutzes, Leiterquerschnitt nach "
        "Strombelastbarkeit (Verlegeart, Umgebungstemperatur, Häufung) und nach Spannungsfall im Betrieb und beim "
        "Anlauf, Vorsicherung gG unter Berücksichtigung von Anlaufstrom und Anlaufzeit."
    )
    norm = "I_z·f_T·f_H ≥ I_r; Δu = √3·I·(R·cos φ + X·sin φ)/U; DIN VDE 0298-4, DIN VDE 0100-430/-520"
    keywords = ("motorzuleitung", "leitung", "querschnitt", "strombelastbarkeit", "verlegeart", "häufung",
                "motorschutz", "motorschutzschalter", "überlastrelais", "sicherung", "vorsicherung", "spannungsfall",
                "anlaufstrom", "kabel", "motor")

    fields = [
        ChoiceField("vorgabe", "Motordaten", [("leistung", "aus Leistung"), ("strom", "Bemessungsstrom vorgeben")],
                    "leistung"),
        NumberField("PN", "Bemessungsleistung", "P_N", "kW", 11, min=0, decimals=2, visible_if=DIR),
        NumberField("eta", "Wirkungsgrad", "η", "percent", 91.4, min=10, max=99.9, decimals=1, visible_if=DIR),
        NumberField("cosphi", "Leistungsfaktor", "cos φ", "", 0.84, min=0.1, max=1, decimals=2),
        NumberField("IN", "Bemessungsstrom", "I_N", "A", 21, min=0, decimals=2, visible_if=STROM),
        NumberField("UN", "Netzspannung (verkettet)", "U_N", "V", 400, min=0, decimals=0),
        ChoiceField("anlauf", "Anlauf", [("direkt", "direkt"), ("stern_dreieck", "Stern-Dreieck"),
                                         ("sanft", "Sanftanlauf / Frequenzumrichter")], "direkt"),
        NumberField("ia", "Anlaufstromverhältnis (direkt)", "I_A/I_N", "", 7.3, min=1, max=15, decimals=1),
        NumberField("tA", "Anlaufzeit", "t_A", "s", 3, min=0, decimals=1),
        NumberField("ki", "Strombegrenzung Sanftanlauf/FU", "I_max/I_N", "", 3.0, min=1, max=8, decimals=1,
                    visible_if={"anlauf": ["sanft"]}),
        NumberField("L", "Leitungslänge (einfach)", "L", "m", 80, min=0, decimals=1),
        ChoiceField("verlegeart", "Verlegeart", list(VERLEGEART.items()), "C"),
        NumberField("tu", "Umgebungstemperatur", "θ_U", "degC", 30, min=10, max=60, decimals=0),
        NumberField("n", "Anzahl gehäufter Stromkreise", "n", "", 1, min=1, max=20, min_inclusive=True, decimals=0),
        NumberField("du_b", "Zulässiger Spannungsfall Betrieb", "Δu_B", "percent", 3, min=0, decimals=1),
        NumberField("du_a", "Zulässiger Spannungsfall Anlauf", "Δu_A", "percent", 10, min=0, decimals=1),
    ]

    def compute(self, inp) -> None:
        U = inp["UN"].to("V").magnitude
        cosphi = float(inp["cosphi"])
        if inp["vorgabe"] == "leistung":
            P = inp["PN"].to("W").magnitude
            eta = inp["eta"].to("percent").magnitude / 100
            IN = P / (math.sqrt(3) * U * eta * cosphi)
            self.step("Bemessungsstrom", "I_N = P_N/(√3·U·η·cos φ)",
                      f"I_N = {fmt_num(P, 0)} W / (√3·{fmt_num(U, 0)} V·{fmt_num(eta, 3)}·{fmt_num(cosphi, 2)})",
                      f"{fmt_num(IN, 2)} A")
        else:
            IN = inp["IN"].to("A").magnitude
        anl = inp["anlauf"]
        ia = float(inp["ia"])
        IA = IN * {"direkt": ia, "stern_dreieck": ia / 3, "sanft": float(inp["ki"])}[anl]
        Ir = IN * (1 / math.sqrt(3) if anl == "stern_dreieck" else 1.0)
        self.step("Anlaufstrom", {"direkt": "I_A = (I_A/I_N)·I_N", "stern_dreieck": "I_A,Y = (I_A/I_N)·I_N/3",
                                  "sanft": "I_A = (I_max/I_N)·I_N"}[anl], "", f"I_A = {fmt_num(IA, 1)} A")
        self.step("Motorschutz-Einstellwert", "I_r = I_N" + (" / √3 (Relais im Strang)" if anl == "stern_dreieck" else ""),
                  "", f"I_r = {fmt_num(Ir, 2)} A")
        # ---------------- Querschnitt
        va = inp["verlegeart"]
        fT = interp(F_TEMP, inp["tu"].to("degC").magnitude)
        fH = haeufung(int(round(inp["n"])))
        L = inp["L"].to("m").magnitude
        du_b_max, du_a_max = inp["du_b"].to("percent").magnitude, inp["du_a"].to("percent").magnitude
        tab = I_Z[va]
        S_iz = S_du = None
        for S, iz in zip(QUERSCHNITTE, tab):
            if S_iz is None and iz * fT * fH >= IN:
                S_iz = (S, iz)
            if S_du is None and spannungsfall(IN, L, S, U, cosphi) <= du_b_max \
                    and spannungsfall(IA, L, S, U, 0.35 if anl != "sanft" else cosphi) <= du_a_max:
                S_du = S
        if S_iz is None:
            raise ValueError(f"Kein Querschnitt bis {QUERSCHNITTE[len(tab) - 1]} mm² ausreichend – parallele Leitungen "
                             "oder andere Verlegeart.")
        if S_du is None:
            S_du = QUERSCHNITTE[len(tab) - 1]
            self.warn("Auch der größte Tabellenquerschnitt hält den Spannungsfall nicht ein – kürzere Leitung oder "
                      "Parallelleitungen.")
        S = max(S_iz[0], S_du)
        iz = tab[QUERSCHNITTE.index(S)]
        Iz = iz * fT * fH
        du_b = spannungsfall(IN, L, S, U, cosphi)
        du_a = spannungsfall(IA, L, S, U, 0.35 if anl != "sanft" else cosphi)
        self.step("Strombelastbarkeit", "I_z = I_z,Tab · f_T · f_H ≥ I_N",
                  f"Verlegeart {va}, f_T = {fmt_num(fT, 2)}, f_H = {fmt_num(fH, 2)}",
                  f"mindestens {fmt_num(S_iz[0], 1)} mm² (I_z,Tab = {fmt_num(S_iz[1], 1)} A)")
        self.step("Spannungsfall", "Δu = √3·I·(R·cos φ + X·sin φ)/U;  Anlauf mit cos φ_A ≈ 0,35",
                  f"L = {fmt_num(L, 1)} m, Grenzen {fmt_num(du_b_max, 1)} % / {fmt_num(du_a_max, 1)} %",
                  f"mindestens {fmt_num(S_du, 1)} mm²")
        # ---------------- Vorsicherung gG
        tA = inp["tA"].to("s").magnitude
        k = interp(GG_ANLAUF, tA)
        In_s = next((x for x in SICHERUNGEN if x >= IN and IA / x <= k), SICHERUNGEN[-1])
        self.step("Vorsicherung gG", "I_n ≥ I_N und I_A/I_n ≤ k(t_A)",
                  f"t_A = {fmt_num(tA, 1)} s → k ≈ {fmt_num(k, 1)}", f"I_n = {In_s} A")

        self.result("IN", "Bemessungsstrom", "I_N", Q_(IN, "A"), "A", 2, highlight=True)
        self.result("Ir", "Einstellwert Motorschutz", "I_r", Q_(Ir, "A"), "A", 2, highlight=True)
        self.result("IA", "Anlaufstrom", "I_A", Q_(IA, "A"), "A", 1)
        self.result("S", "Leiterquerschnitt Cu", "S", Q_(S, "mm**2"), "mm**2", 1, highlight=True)
        self.result("Iz", "Strombelastbarkeit (korrigiert)", "I_z", Q_(Iz, "A"), "A", 1)
        self.result("du_b", "Spannungsfall Betrieb", "Δu_B", Q_(du_b, "percent"), "percent", 2)
        self.result("du_a", "Spannungsfall Anlauf", "Δu_A", Q_(du_a, "percent"), "percent", 2)
        self.result("In", "Vorsicherung gG", "I_n", Q_(In_s, "A"), "A", 0, highlight=True)
        if In_s > Iz:
            self.info(f"Sicherung {In_s} A > I_z = {fmt_num(Iz, 1)} A: zulässig, wenn der Überlastschutz durch den "
                      "Motorschutz erfolgt und die Sicherung den Kurzschlussschutz der Leitung übernimmt (DIN VDE "
                      "0100-430). Kurzschlussfestigkeit und Abschaltbedingung prüfen.")
        if anl == "stern_dreieck":
            self.info("Stern-Dreieck: zwei Motorleitungen (6 Adern) – Querschnitt je Strang für I_N/√3 ausreichend, "
                      "hier konservativ mit I_N bemessen.")
        self.info("Belastbarkeit für Cu/PVC, 3 belastete Adern, Dauerbetrieb; Abschaltbedingung mit dem Rechner "
                  "„Abschaltbedingung LS-Schalter“ bzw. Herstellerkennlinie nachweisen. Motorschutzschalter mit "
                  "integriertem Kurzschlussschutz ersetzen die Vorsicherung, wenn deren Schaltvermögen ausreicht.")

    def sketch_svg(self, raw) -> str:
        s = Svg()
        s.text(40, 40, "Netz 3~", 11, INK)
        s.rect(30, 55, 40, 30, fill="#eef3f8").text(50, 75, "F", 11, INK, bold=True)
        s.rect(30, 100, 40, 30, fill="#eef3f8").text(50, 120, "Q/K", 10, INK, bold=True)
        s.line(50, 85, 50, 100, INK, 2).line(50, 130, 50, 160, INK, 2)
        s.line(50, 160, 270, 160, ACCENT, 4).text(160, 150, "L, S", 11, INK, italic=True)
        s.circle(300, 160, 26, fill="#f5d7d3").text(300, 165, "M 3~", 10, INK, bold=True)
        s.text(90, 74, "Vorsicherung", 10, MUTED, "start").text(90, 120, "Motorschutz", 10, MUTED, "start")
        return s.render()
