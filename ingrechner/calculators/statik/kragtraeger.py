"""Kragträger (einseitig eingespannt) unter Endlast und Gleichstreckenlast."""

from __future__ import annotations

import numpy as np

from ingrechner.core.model import Calculator, NumberField
from ingrechner.core.svg import ACCENT, INK, Svg
from ingrechner.core.units import Q_, fmt_num, fmt_q


class Kragtraeger(Calculator):
    id = "st.kragtraeger"
    title = "Kragträger"
    category = "Bau / Statik"
    description = (
        "Einspannmoment, Querkraft, Biegespannung, Durchbiegung und Endverdrehung eines Kragträgers "
        "unter Einzellast am freien Ende und Gleichstreckenlast (Superposition)."
    )
    norm = "Technische Mechanik (Bernoulli-Balken, linear-elastisch); Schneider Bautabellen"
    keywords = ("kragträger", "kragarm", "auskragung", "einspannung", "balkon", "konsole", "durchbiegung")
    material_map = {"E": "E", "fy": "Re"}

    fields = [
        NumberField("L", "Kraglänge", "L", "mm", 1500, min=0, decimals=0),
        NumberField("F", "Einzellast am Ende", "F", "kN", 5, min=0, min_inclusive=True, decimals=3),
        NumberField("q", "Gleichstreckenlast", "q", "kN/m", 2, min=0, min_inclusive=True, decimals=3),
        NumberField("I", "Flächenträgheitsmoment", "I_y", "cm**4", 1943, min=0, decimals=1,
                    tooltip="z. B. IPE 200: I_y = 1943 cm⁴"),
        NumberField("W", "Widerstandsmoment", "W_y", "cm**3", 194, min=0, decimals=1,
                    tooltip="z. B. IPE 200: W_y = 194 cm³"),
        NumberField("E", "Elastizitätsmodul", "E", "N/mm**2", 210000, min=0, decimals=0),
        NumberField("fy", "Streckgrenze", "f_y", "N/mm**2", 235, min=0, decimals=0),
        NumberField("gM", "Teilsicherheitsbeiwert Widerstand", "γ_M0", "", 1.0, min=1, min_inclusive=True,
                    decimals=2),
        NumberField("wl", "Durchbiegungsgrenze L/…", "L/w", "", 150, min=0, decimals=0,
                    tooltip="Kragarme üblich L/150 (Kraglänge); Einfeldträger L/300"),
    ]

    def compute(self, inp) -> None:
        L, F, q, I, W, E = inp["L"], inp["F"], inp["q"], inp["I"], inp["W"], inp["E"]
        if F.magnitude == 0 and q.magnitude == 0:
            raise ValueError("Bitte eine Einzellast oder eine Streckenlast angeben.")
        V = (F + q * L).to("kN")
        M = (F * L + q * L**2 / 2).to("kN*m")
        w = (F * L**3 / (3 * E * I) + q * L**4 / (8 * E * I)).to("mm")
        phi = (F * L**2 / (2 * E * I) + q * L**3 / (6 * E * I)).to("")
        sigma = (M / W).to("N/mm**2")
        f_d = inp["fy"] / inp["gM"]
        eta = (sigma / f_d).to("").magnitude
        w_zul = L / inp["wl"]

        self.step("Querkraft an der Einspannung", "V = F + q · L",
                  f"V = {fmt_q(F, 'kN')} + {fmt_q(q, 'kN/m')} · {fmt_q(L, 'm')}", fmt_q(V, "kN"))
        self.step("Einspannmoment", "M = F · L + q · L² / 2",
                  f"M = {fmt_q(F, 'kN')} · {fmt_q(L, 'm')} + {fmt_q(q, 'kN/m')} · ({fmt_q(L, 'm')})² / 2",
                  fmt_q(M, "kN*m"))
        self.step("Biegespannung", "σ = M / W_y", f"σ = {fmt_q(M, 'N*mm', 0)} / {fmt_q(W, 'mm**3', 0)}",
                  fmt_q(sigma, "N/mm**2", 2))
        self.step("Durchbiegung am Ende", "w = F·L³ / (3·E·I) + q·L⁴ / (8·E·I)",
                  f"E·I = {fmt_q(E * I, 'kN*m**2', 1)}", fmt_q(w, "mm", 2))
        self.step("Endverdrehung", "φ = F·L² / (2·E·I) + q·L³ / (6·E·I)", f"E·I = {fmt_q(E * I, 'kN*m**2', 1)}",
                  f"{fmt_num(phi.magnitude * 1000, 3)} mrad")
        self.step("Zulässige Durchbiegung", "w_zul = L / (L/w)",
                  f"w_zul = {fmt_q(L, 'mm', 0)} / {fmt_num(inp['wl'], 0)}", fmt_q(w_zul, "mm", 2))

        self.result("M", "Einspannmoment", "M_E", M, "kN*m", 3, highlight=True)
        self.result("V", "Querkraft / Auflagerkraft", "V", V, "kN", 3)
        self.result("sigma", "Biegespannung", "σ", sigma, "N/mm**2", 2, highlight=True)
        self.result("eta", "Ausnutzung Spannung", "η_σ", Q_(eta * 100, "percent"), "percent", 1, highlight=True)
        self.result("w", "Durchbiegung am Ende", "w", w, "mm", 2, highlight=True)
        self.result("w_zul", "Zulässige Durchbiegung", "w_zul", w_zul, "mm", 2)
        self.result("phi", "Endverdrehung", "φ", Q_(phi.magnitude * 1000, "mrad"), "mrad", 3)

        if eta > 1:
            self.warn(f"Spannungsnachweis NICHT erfüllt ({fmt_num(eta * 100, 1)} %).")
        else:
            self.info(f"Spannungsnachweis erfüllt ({fmt_num(eta * 100, 1)} %).")
        if w > w_zul:
            self.warn(f"Durchbiegung {fmt_q(w, 'mm', 1)} > w_zul = {fmt_q(w_zul, 'mm', 1)}.")
        self.info("Eigengewicht ist in q einzurechnen; Biegedrillknicken und Einspannung (Anschluss) "
                  "sind gesondert nachzuweisen.")

    def plot(self, fig, raw, result) -> bool:
        if not result.ok:
            return False
        L = float(raw["L"])
        F, q = float(raw["F"]) * 1e3, float(raw["q"])
        EI = float(raw["E"]) * float(raw["I"]) * 1e4
        x = np.linspace(0, L, 201)              # x ab Einspannung
        M = -(F * (L - x) + q * (L - x) ** 2 / 2)
        w = F * x**2 * (3 * L - x) / (6 * EI) + q * x**2 * (6 * L**2 - 4 * L * x + x**2) / (24 * EI)
        ax1, ax2 = fig.subplots(2, 1, sharex=True)
        ax1.fill_between(x / 1000, 0, M / 1e6, color="#1f6fb2", alpha=0.18)
        ax1.plot(x / 1000, M / 1e6, color="#1f6fb2", lw=2)
        ax1.set_ylabel("M  [kN·m]")
        ax1.set_title("Momentenverlauf (Einspannung links)")
        ax2.plot(x / 1000, -w, color="#2b3a4a", lw=2)
        ax2.set_ylabel("w  [mm]")
        ax2.set_xlabel("x  [m]")
        ax2.set_title("Biegelinie")
        for ax in (ax1, ax2):
            ax.grid(True, alpha=0.3)
        return True

    def sketch_svg(self, raw) -> str:
        s = Svg()
        x0, x1, y = 60, 300, 120
        s.rect(x0 - 18, 60, 18, 120, fill="#dce6f1")
        for k in range(64, 180, 10):
            s.line(x0 - 18, k + 8, x0 - 8, k, INK, 0.8)
        s.rect(x0, y - 5, x1 - x0, 10)
        try:
            has_q = float(raw.get("q", 0)) > 0
            has_f = float(raw.get("F", 0)) > 0
        except (TypeError, ValueError):
            has_q = has_f = True
        if has_q:
            s.line(x0, 82, x1, 82, ACCENT, 1.4)
            for i in range(7):
                xi = x0 + i * (x1 - x0) / 6
                s.arrow(xi, 82, xi, y - 7)
            s.text((x0 + x1) / 2, 74, "q", 14, ACCENT, italic=True)
        if has_f:
            s.arrow(x1, 40, x1, y - 7).text(x1 + 10, 52, "F", 14, ACCENT, "start", True)
        s.dim_h(x0, x1, 170, "L")
        return s.render()
