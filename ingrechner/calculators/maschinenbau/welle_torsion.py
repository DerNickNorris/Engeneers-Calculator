"""Welle auf Torsion: Drehmoment aus Leistung, Torsionsspannung, Verdrehwinkel, Mindestdurchmesser."""

from __future__ import annotations

import math

from ingrechner.core.model import Calculator, ChoiceField, NumberField
from ingrechner.core.svg import ACCENT, MUTED, Svg
from ingrechner.core.units import Q_, fmt_num, fmt_q

HOHL = {"querschnitt": ["hohl"]}


class WelleTorsion(Calculator):
    id = "mb.welle_torsion"
    title = "Welle auf Torsion"
    category = "Maschinenbau"
    description = (
        "Drehmoment aus Leistung und Drehzahl, Torsionsspannung und Verdrehwinkel einer Voll- oder "
        "Hohlwelle sowie der erforderliche Mindestdurchmesser (Überschlagsrechnung)."
    )
    norm = "Technische Mechanik; Überschlagsrechnung vgl. Roloff/Matek Kap. 11"
    keywords = ("welle", "torsion", "drehmoment", "verdrehung", "leistung", "drehzahl", "antrieb")
    material_map = {}

    fields = [
        NumberField("P", "Leistung", "P", "kW", 10, min=0, decimals=3),
        NumberField("n", "Drehzahl", "n", "1/min", 1450, min=0, decimals=1),
        ChoiceField("querschnitt", "Querschnitt", [("voll", "Vollwelle"), ("hohl", "Hohlwelle")], "voll"),
        NumberField("d", "Außendurchmesser", "d", "mm", 25, min=0, decimals=2),
        NumberField("di", "Innendurchmesser", "d_i", "mm", 15, min=0, min_inclusive=True, decimals=2,
                    visible_if=HOHL),
        NumberField("L", "Wellenlänge (verdrillt)", "L", "mm", 500, min=0, decimals=1),
        NumberField("tau_zul", "Zulässige Torsionsspannung", "τ_t,zul", "N/mm**2", 30, min=0, decimals=1,
                    tooltip="Überschlag bei unbekannter Biegung (Roloff/Matek): Baustahl 10–20, "
                            "Vergütungsstahl 20–40 N/mm²"),
        NumberField("G", "Schubmodul", "G", "N/mm**2", 81000, min=0, decimals=0,
                    tooltip="Stahl ≈ 81 000 N/mm², Aluminium ≈ 26 000 N/mm²"),
        NumberField("phi_zul", "Zul. Verdrehwinkel", "φ'_zul", "degree/m", 0.25, min=0, decimals=3,
                    tooltip="Üblich 0,25 °/m für Transmissionswellen (Richtwert)"),
    ]

    def compute(self, inp) -> None:
        P, n, d, L, G = inp["P"], inp["n"], inp["d"], inp["L"], inp["G"]
        omega = (2 * math.pi * n).to("1/s")
        T = (P / omega).to("N*m")
        self.step("Drehmoment", "T = P / (2π · n)", f"T = {fmt_q(P, 'W', 0)} / (2π · {fmt_q(n, '1/s', 3)})",
                  fmt_q(T, "N*m", 2))

        if inp["querschnitt"] == "hohl":
            di = inp["di"]
            if di >= d:
                raise ValueError("Der Innendurchmesser muss kleiner als der Außendurchmesser sein.")
            Ip = math.pi * (d**4 - di**4) / 32
            Wp = Ip / (d / 2)
            self.step("Polares Widerstandsmoment (Hohlwelle)", "W_p = π · (d⁴ − d_i⁴) / (16 · d)",
                      f"W_p = π · (({fmt_q(d, 'mm', 1)})⁴ − ({fmt_q(di, 'mm', 1)})⁴) / (16 · {fmt_q(d, 'mm', 1)})",
                      fmt_q(Wp, "mm**3", 0))
            k = (di / d).to("").magnitude
            d_erf = (16 * T / (math.pi * inp["tau_zul"] * (1 - k**4))) ** (1 / 3)
            d_formula = "d_erf = ∛(16 · T / (π · τ_t,zul · (1 − (d_i/d)⁴)))"
        else:
            Ip = math.pi * d**4 / 32
            Wp = math.pi * d**3 / 16
            self.step("Polares Widerstandsmoment (Vollwelle)", "W_p = π · d³ / 16",
                      f"W_p = π · ({fmt_q(d, 'mm', 1)})³ / 16", fmt_q(Wp, "mm**3", 0))
            d_erf = (16 * T / (math.pi * inp["tau_zul"])) ** (1 / 3)
            d_formula = "d_erf = ∛(16 · T / (π · τ_t,zul))"

        tau = (T / Wp).to("N/mm**2")
        eta = (tau / inp["tau_zul"]).to("").magnitude
        phi = (T * L / (G * Ip)).to("")  # rad
        phi_deg = math.degrees(phi.magnitude)
        phi_m = phi_deg / L.to("m").magnitude
        self.step("Torsionsspannung", "τ_t = T / W_p", f"τ_t = {fmt_q(T, 'N*mm', 0)} / {fmt_q(Wp, 'mm**3', 0)}",
                  fmt_q(tau, "N/mm**2", 2))
        self.step("Verdrehwinkel", "φ = T · L / (G · I_p)",
                  f"φ = {fmt_q(T, 'N*mm', 0)} · {fmt_q(L, 'mm', 0)} / ({fmt_q(G, 'N/mm**2', 0)} · "
                  f"{fmt_q(Ip, 'mm**4', 0)})", f"{fmt_num(phi.magnitude, 5)} rad = {fmt_num(phi_deg, 3)}°")
        self.step("Mindestdurchmesser", d_formula,
                  f"aus T = {fmt_q(T, 'N*m', 2)} und τ_t,zul = {fmt_q(inp['tau_zul'], 'N/mm**2', 1)}",
                  fmt_q(d_erf, "mm", 2))

        self.result("T", "Drehmoment", "T", T, "N*m", 2, highlight=True)
        self.result("tau", "Torsionsspannung", "τ_t", tau, "N/mm**2", 2, highlight=True)
        self.result("eta", "Ausnutzung", "η", Q_(eta * 100, "percent"), "percent", 1, highlight=True)
        self.result("d_erf", "Mindestdurchmesser", "d_erf", d_erf, "mm", 2)
        self.result("phi", "Verdrehwinkel gesamt", "φ", Q_(phi_deg, "degree"), "degree", 4)
        self.result("phi_m", "Verdrehwinkel je Meter", "φ'", Q_(phi_m, "degree/m"), "degree/m", 4)

        if eta > 1:
            self.warn(f"Torsionsspannung überschreitet den zulässigen Wert ({fmt_num(eta * 100, 1)} %). "
                      f"Mindestdurchmesser {fmt_q(d_erf, 'mm', 1)}.")
        else:
            self.info(f"Spannung zulässig ({fmt_num(eta * 100, 1)} %).")
        if phi_m > inp["phi_zul"].to("degree/m").magnitude:
            self.warn(f"Verdrehwinkel {fmt_num(phi_m, 3)} °/m über dem Richtwert "
                      f"{fmt_num(inp['phi_zul'].to('degree/m').magnitude, 2)} °/m.")
        self.info("Überschlag: Biegung, Kerbwirkung (Passfedernut, Absätze) und Dauerfestigkeit sind nicht "
                  "erfasst – Festigkeitsnachweis z. B. nach DIN 743 erforderlich.")

    def sketch_svg(self, raw) -> str:
        s = Svg()
        s.rect(60, 92, 240, 36)
        s.line(50, 110, 310, 110, MUTED, 1, "6,4")
        for x in (60, 300):
            s.polygon([(x - 6, 84), (x + 6, 84), (x + 6, 136), (x - 6, 136)], fill="#ffffff")
        s.arrow(40, 70, 40, 60).text(28, 54, "T", 14, ACCENT, "middle", True)
        s.line(30, 70, 50, 70, ACCENT, 2)
        s.arrow(320, 150, 320, 160).text(334, 168, "T", 14, ACCENT, "middle", True)
        s.line(310, 150, 330, 150, ACCENT, 2)
        s.dim_h(60, 300, 175, "L")
        s.dim_v(330, 92, 128, "d")
        s.text(180, 40, "P, n", 13, ACCENT, italic=True)
        return s.render()
