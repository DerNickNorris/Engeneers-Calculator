"""Wechsel-/Drehstromleistung und Blindleistungskompensation."""

from __future__ import annotations

import math

import numpy as np

from ingrechner.core.model import Calculator, ChoiceField, NumberField
from ingrechner.core.svg import ACCENT, INK, MUTED, Svg
from ingrechner.core.units import Q_, fmt_num, fmt_q

DREH = {"netz": ["3ac"]}


class Kompensation(Calculator):
    id = "et.kompensation"
    title = "Leistung & Blindstromkompensation"
    category = "Elektrotechnik"
    description = (
        "Schein-, Wirk- und Blindleistung sowie Strom eines Verbrauchers; erforderliche "
        "Kompensationsleistung und Kondensatorkapazität für einen Ziel-Leistungsfaktor."
    )
    norm = "Grundlagen Wechselstromtechnik; Kompensation vgl. DIN EN 60831"
    keywords = ("blindleistung", "kompensation", "cos phi", "leistungsfaktor", "kondensator", "drehstrom",
                "scheinleistung", "wirkleistung", "kvar")

    fields = [
        ChoiceField("netz", "Netz", [("3ac", "Drehstrom 3~"), ("1ac", "Wechselstrom 1~")], "3ac"),
        NumberField("U", "Nennspannung", "U", "V", 400, min=0, decimals=0,
                    tooltip="Drehstrom: Außenleiterspannung; Wechselstrom: Leiter–Neutralleiter"),
        NumberField("f", "Netzfrequenz", "f", "Hz", 50, min=0, decimals=1),
        NumberField("P", "Wirkleistung", "P", "kW", 100, min=0, decimals=2),
        NumberField("cos1", "Leistungsfaktor vorher", "cos φ₁", "", 0.7, min=0, max=1, decimals=3),
        NumberField("cos2", "Ziel-Leistungsfaktor", "cos φ₂", "", 0.95, min=0, max=1, decimals=3,
                    tooltip="Netzbetreiber verlangen meist cos φ ≥ 0,9 (Blindarbeit sonst kostenpflichtig)"),
        ChoiceField("schaltung", "Kondensatorschaltung", [("dreieck", "Dreieck"), ("stern", "Stern")],
                    "dreieck", visible_if=DREH),
    ]

    def compute(self, inp) -> None:
        P, U, f = inp["P"], inp["U"], inp["f"]
        c1, c2 = inp["cos1"], inp["cos2"]
        dreh = inp["netz"] == "3ac"
        if c2 < c1:
            raise ValueError("Der Ziel-Leistungsfaktor muss größer als der vorhandene sein.")
        k = math.sqrt(3) if dreh else 1.0
        tan1 = math.tan(math.acos(c1))
        tan2 = math.tan(math.acos(c2))
        S1 = P / c1
        Q1 = P * tan1
        I1 = (S1 / (k * U)).to("A")
        S2 = P / c2
        I2 = (S2 / (k * U)).to("A")
        Qc = (P * (tan1 - tan2)).to("kW")
        omega = 2 * math.pi * f

        self.step("Scheinleistung vorher", "S₁ = P / cos φ₁", f"S₁ = {fmt_q(P, 'kW', 2)} / {fmt_num(c1, 3)}",
                  f"{fmt_num(S1.to('kW').magnitude, 2)} kVA")
        self.step("Blindleistung vorher", "Q₁ = P · tan φ₁", f"Q₁ = {fmt_q(P, 'kW', 2)} · {fmt_num(tan1, 4)}",
                  f"{fmt_num(Q1.to('kW').magnitude, 2)} kvar")
        self.step("Strom vorher", "I₁ = S₁ / (√3 · U)" if dreh else "I₁ = S₁ / U",
                  f"I₁ = {fmt_num(S1.to('kW').magnitude * 1000, 0)} VA / ({'√3 · ' if dreh else ''}{fmt_q(U, 'V', 0)})",
                  fmt_q(I1, "A", 1))
        self.step("Kompensationsleistung", "Q_C = P · (tan φ₁ − tan φ₂)",
                  f"Q_C = {fmt_q(P, 'kW', 2)} · ({fmt_num(tan1, 4)} − {fmt_num(tan2, 4)})",
                  f"{fmt_num(Qc.magnitude, 2)} kvar")

        if dreh and inp["schaltung"] == "dreieck":
            n, formula, sub = 3, "C = Q_C / (3 · ω · U²)  je Kondensator (Dreieck)", "3 · "
        elif dreh:
            n, formula, sub = 1, "C = Q_C / (ω · U²)  je Kondensator (Stern, U_C = U/√3)", ""
        else:
            n, formula, sub = 1, "C = Q_C / (ω · U²)", ""
        C = (Qc / (n * Q_(omega, "1/s") * U**2)).to("microfarad")
        self.step("Kondensatorkapazität", formula,
                  f"C = {fmt_num(Qc.to('W').magnitude, 0)} var / ({sub}2π · {fmt_q(f, 'Hz', 1)} · "
                  f"({fmt_q(U, 'V', 0)})²)", fmt_q(C, "microfarad", 2))
        self.step("Strom nachher", "I₂ = P / (cos φ₂ · √3 · U)" if dreh else "I₂ = P / (cos φ₂ · U)",
                  f"I₂ = {fmt_q(P, 'kW', 2)} / ({fmt_num(c2, 3)} · {'√3 · ' if dreh else ''}{fmt_q(U, 'V', 0)})",
                  fmt_q(I2, "A", 1))

        red = (1 - (I2 / I1).to("").magnitude) * 100
        loss_red = (1 - ((I2 / I1).to("").magnitude) ** 2) * 100
        as_unit = lambda q, u: Q_(q.to("W").magnitude / 1000, u)  # noqa: E731 - W -> kVA/kvar
        self.result("Qc", "Kompensationsleistung", "Q_C", as_unit(Qc, "kvar"), "kvar", 2, highlight=True)
        self.result("C", "Kapazität je Kondensator", "C", C, "microfarad", 2, highlight=True)
        self.result("S1", "Scheinleistung vorher", "S₁", as_unit(S1, "kVA"), "kVA", 2)
        self.result("Q1", "Blindleistung vorher", "Q₁", as_unit(Q1, "kvar"), "kvar", 2)
        self.result("S2", "Scheinleistung nachher", "S₂", as_unit(S2, "kVA"), "kVA", 2)
        self.result("I1", "Strom vorher", "I₁", I1, "A", 1)
        self.result("I2", "Strom nachher", "I₂", I2, "A", 1, highlight=True)
        self.result("red", "Stromreduzierung", "ΔI", Q_(red, "percent"), "percent", 1)

        self.info(f"Leitungsverluste sinken um ca. {fmt_num(loss_red, 0)} % (∝ I²).")
        if c2 > 0.98:
            self.warn("Ziel-cos φ > 0,98: Gefahr der Überkompensation bei Teillast – Regelanlage vorsehen.")
        if Qc.magnitude > 0 and dreh:
            self.info("Bei Oberschwingungen (Umrichter, LED-Treiber) verdrosselte Kompensation vorsehen, um "
                      "Resonanzen zu vermeiden.")

    def plot(self, fig, raw, result) -> bool:
        if not result.ok:
            return False
        P, c1 = float(raw["P"]), float(raw["cos1"])
        tan1 = math.tan(math.acos(c1))
        cs = np.linspace(c1, 1.0, 100)
        ax = fig.subplots()
        ax.plot(cs, P * (tan1 - np.tan(np.arccos(cs))), color="#1f6fb2", lw=2)
        ax.plot([float(raw["cos2"])], [result.value("Qc")], "o", color="#c0392b")
        ax.set_xlabel("Ziel-Leistungsfaktor cos φ₂")
        ax.set_ylabel("Kompensationsleistung Q_C  [kvar]")
        ax.set_title("Erforderliche Kompensation")
        ax.grid(True, alpha=0.3)
        return True

    def sketch_svg(self, raw) -> str:
        s = Svg()
        ox, oy = 60, 180
        P = 200
        c1 = float(raw.get("cos1", 0.7) or 0.7)
        c2 = float(raw.get("cos2", 0.95) or 0.95)
        try:
            q1 = min(130, P * math.tan(math.acos(c1)))
            q2 = P * math.tan(math.acos(c2))
        except ValueError:
            q1, q2 = 130, 40
        s.arrow(ox, oy, ox + P, oy, INK).text(ox + P / 2, oy + 18, "P", 13, INK, italic=True)
        s.arrow(ox + P, oy, ox + P, oy - q1, ACCENT).text(ox + P + 8, oy - q1 / 2, "Q₁", 13, ACCENT, "start", True)
        s.arrow(ox, oy, ox + P, oy - q1, MUTED).text(ox + P / 2 - 26, oy - q1 / 2 - 6, "S₁", 13, MUTED, italic=True)
        s.arrow(ox, oy, ox + P, oy - q2, "#2e7d4f").text(ox + P / 2 + 16, oy - q2 / 2 + 16, "S₂", 13, "#2e7d4f",
                                                        italic=True)
        s.line(ox + P + 30, oy - q1, ox + P + 30, oy - q2, "#c0392b", 3)
        s.text(ox + P + 36, oy - (q1 + q2) / 2, "Q_C", 13, "#c0392b", "start", True)
        return s.render()
