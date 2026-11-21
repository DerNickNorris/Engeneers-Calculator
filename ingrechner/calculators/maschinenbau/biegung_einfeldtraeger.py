"""Biegung am Einfeldträger (Balken auf zwei Stützen)."""

from __future__ import annotations

import numpy as np

from ingrechner.core.model import Calculator, ChoiceField, NumberField
from ingrechner.core.svg import ACCENT, INK, Svg
from ingrechner.core.units import Q_, fmt_num, fmt_q

EINZEL = {"lastfall": ["einzellast"]}
STRECKE = {"lastfall": ["streckenlast"]}
RECHTECK = {"querschnitt": ["rechteck"]}
WERTE = {"querschnitt": ["werte"]}


class BiegungEinfeldtraeger(Calculator):
    id = "mb.biegung_einfeldtraeger"
    title = "Biegung Einfeldträger"
    category = "Maschinenbau"
    description = (
        "Biegemoment, Biegespannung und Durchbiegung eines statisch bestimmt gelagerten "
        "Einfeldträgers unter Einzellast in Feldmitte oder Gleichstreckenlast."
    )
    norm = "Technische Mechanik (Bernoulli-Balken, linear-elastisch); vgl. Roloff/Matek, Dubbel"
    keywords = ("balken", "träger", "biegung", "durchbiegung", "biegespannung", "moment")
    material_map = {"E": "E", "Re": "Re"}

    fields = [
        ChoiceField("lastfall", "Lastfall", [
            ("einzellast", "Einzellast F in Feldmitte"),
            ("streckenlast", "Gleichstreckenlast q"),
        ], "einzellast"),
        NumberField("L", "Stützweite", "L", "mm", 2000, min=0, decimals=1),
        NumberField("F", "Einzellast", "F", "kN", 10, min=0, decimals=3, visible_if=EINZEL),
        NumberField("q", "Streckenlast", "q", "kN/m", 5, min=0, decimals=3, visible_if=STRECKE),
        ChoiceField("querschnitt", "Querschnitt", [
            ("rechteck", "Rechteck-Vollquerschnitt b × h"),
            ("werte", "Querschnittswerte direkt (z. B. Profil)"),
        ], "rechteck"),
        NumberField("b", "Breite", "b", "mm", 50, min=0, decimals=1, visible_if=RECHTECK),
        NumberField("h", "Höhe", "h", "mm", 100, min=0, decimals=1, visible_if=RECHTECK),
        NumberField("Iy", "Flächenträgheitsmoment", "I_y", "cm**4", 1943, min=0, decimals=1,
                    visible_if=WERTE, tooltip="z. B. IPE 200: I_y = 1943 cm⁴"),
        NumberField("Wy", "Widerstandsmoment", "W_y", "cm**3", 194, min=0, decimals=1,
                    visible_if=WERTE, tooltip="z. B. IPE 200: W_y = 194 cm³"),
        NumberField("E", "Elastizitätsmodul", "E", "N/mm**2", 210000, min=0, decimals=0,
                    tooltip="Stahl ≈ 210 000 N/mm², Aluminium ≈ 70 000 N/mm²"),
        NumberField("Re", "Streckgrenze", "R_e", "N/mm**2", 235, min=0, decimals=0,
                    tooltip="z. B. S235: 235 N/mm², S355: 355 N/mm²"),
        NumberField("S", "Sicherheitsbeiwert", "S", "", 1.5, min=1, min_inclusive=True, decimals=2),
        NumberField("wl", "Durchbiegungsgrenze L/…", "L/w", "", 300, min=0, decimals=0,
                    tooltip="Zulässige Durchbiegung w_zul = L / Wert (üblich 200 … 500)"),
    ]

    def compute(self, inp) -> None:
        L = inp["L"]
        E = inp["E"]

        # Querschnittswerte
        if inp["querschnitt"] == "rechteck":
            b, h = inp["b"], inp["h"]
            I = b * h**3 / 12
            W = b * h**2 / 6
            self.step("Flächenträgheitsmoment", "I_y = b · h³ / 12",
                      f"I_y = {fmt_q(b, 'mm', 1)} · ({fmt_q(h, 'mm', 1)})³ / 12",
                      fmt_q(I, "cm**4", 2))
            self.step("Widerstandsmoment", "W_y = b · h² / 6",
                      f"W_y = {fmt_q(b, 'mm', 1)} · ({fmt_q(h, 'mm', 1)})² / 6",
                      fmt_q(W, "cm**3", 2))
        else:
            I, W = inp["Iy"], inp["Wy"]
        self.result("Iy", "Flächenträgheitsmoment", "I_y", I, "cm**4", 2)
        self.result("Wy", "Widerstandsmoment", "W_y", W, "cm**3", 2)

        # Schnittgrößen
        if inp["lastfall"] == "einzellast":
            F = inp["F"]
            A = F / 2
            M = F * L / 4
            w = F * L**3 / (48 * E * I)
            self.step("Auflagerkräfte", "A = B = F / 2", f"A = {fmt_q(F, 'kN')} / 2", fmt_q(A, "kN"))
            self.step("Max. Biegemoment (Feldmitte)", "M_max = F · L / 4",
                      f"M_max = {fmt_q(F, 'kN')} · {fmt_q(L, 'm')} / 4", fmt_q(M, "kN*m"))
            self.step("Max. Durchbiegung", "w_max = F · L³ / (48 · E · I_y)",
                      f"w_max = {fmt_q(F, 'N', 0)} · ({fmt_q(L, 'mm', 0)})³ / "
                      f"(48 · {fmt_q(E, 'N/mm**2', 0)} · {fmt_q(I, 'mm**4', 0)})",
                      fmt_q(w, "mm"))
        else:
            q = inp["q"]
            A = q * L / 2
            M = q * L**2 / 8
            w = 5 * q * L**4 / (384 * E * I)
            self.step("Auflagerkräfte", "A = B = q · L / 2",
                      f"A = {fmt_q(q, 'kN/m')} · {fmt_q(L, 'm')} / 2", fmt_q(A, "kN"))
            self.step("Max. Biegemoment (Feldmitte)", "M_max = q · L² / 8",
                      f"M_max = {fmt_q(q, 'kN/m')} · ({fmt_q(L, 'm')})² / 8", fmt_q(M, "kN*m"))
            self.step("Max. Durchbiegung", "w_max = 5 · q · L⁴ / (384 · E · I_y)",
                      f"w_max = 5 · {fmt_q(q, 'N/mm')} · ({fmt_q(L, 'mm', 0)})⁴ / "
                      f"(384 · {fmt_q(E, 'N/mm**2', 0)} · {fmt_q(I, 'mm**4', 0)})",
                      fmt_q(w, "mm"))

        self.result("A", "Auflagerkraft A = B", "A", A, "kN")
        self.result("M", "Max. Biegemoment", "M_max", M, "kN*m", highlight=True)

        # Spannungsnachweis
        sigma = M / W
        sigma_zul = inp["Re"] / inp["S"]
        eta_s = (sigma / sigma_zul).to("").magnitude
        self.step("Biegespannung", "σ_b = M_max / W_y",
                  f"σ_b = {fmt_q(M, 'N*mm', 0)} / {fmt_q(W, 'mm**3', 0)}", fmt_q(sigma, "N/mm**2", 2))
        self.step("Zulässige Spannung", "σ_zul = R_e / S",
                  f"σ_zul = {fmt_q(inp['Re'], 'N/mm**2', 0)} / {fmt_num(inp['S'], 2)}",
                  fmt_q(sigma_zul, "N/mm**2", 2))
        self.step("Ausnutzung Spannung", "η_σ = σ_b / σ_zul",
                  f"η_σ = {fmt_q(sigma, 'N/mm**2', 2)} / {fmt_q(sigma_zul, 'N/mm**2', 2)}",
                  f"{fmt_num(eta_s * 100, 1)} %")
        self.result("sigma", "Biegespannung", "σ_b", sigma, "N/mm**2", 2, highlight=True)
        self.result("eta_s", "Ausnutzung Spannung", "η_σ", Q_(eta_s * 100, "percent"), "percent", 1, highlight=True)

        # Durchbiegungsnachweis
        w_zul = L / inp["wl"]
        eta_w = (w / w_zul).to("").magnitude
        self.step("Zulässige Durchbiegung", "w_zul = L / (L/w)",
                  f"w_zul = {fmt_q(L, 'mm', 1)} / {fmt_num(inp['wl'], 0)}", fmt_q(w_zul, "mm"))
        self.result("w", "Max. Durchbiegung", "w_max", w, "mm", 3, highlight=True)
        self.result("eta_w", "Ausnutzung Durchbiegung", "η_w", Q_(eta_w * 100, "percent"), "percent", 1)

        # Rechteck: Schubspannung
        if inp["querschnitt"] == "rechteck":
            tau = 1.5 * A / (inp["b"] * inp["h"])
            self.step("Max. Schubspannung (Rechteck)", "τ_max = 1,5 · A / (b · h)",
                      f"τ_max = 1,5 · {fmt_q(A, 'N', 0)} / ({fmt_q(inp['b'], 'mm', 1)} · "
                      f"{fmt_q(inp['h'], 'mm', 1)})", fmt_q(tau, "N/mm**2", 2))
            self.result("tau", "Max. Schubspannung", "τ_max", tau, "N/mm**2", 2)
            if (L / inp["h"]).to("").magnitude < 5:
                self.warn("Kurzer Balken (L/h < 5): Schubverformung ist nicht vernachlässigbar, "
                          "die Bernoulli-Theorie liefert hier zu kleine Durchbiegungen.")

        # Bewertung
        if eta_s > 1:
            self.warn(f"Spannungsnachweis NICHT erfüllt: Ausnutzung {fmt_num(eta_s * 100, 1)} % > 100 %.")
        else:
            self.info(f"Spannungsnachweis erfüllt ({fmt_num(eta_s * 100, 1)} %).")
        if eta_w > 1:
            self.warn(f"Durchbiegung zu groß: {fmt_q(w, 'mm', 2)} > w_zul = {fmt_q(w_zul, 'mm', 2)}.")
        else:
            self.info(f"Durchbiegung zulässig ({fmt_num(eta_w * 100, 1)} % von w_zul).")
        if (sigma > inp["Re"]):
            self.warn("Biegespannung über der Streckgrenze – die linear-elastische Rechnung ist ungültig.")
        self.info("Eigengewicht des Trägers ist nicht berücksichtigt; Stabilität (Kippen) wird nicht geprüft.")

    # -------------------------------------------------------------- Diagramm
    def plot(self, fig, raw, result) -> bool:
        if not result.ok:
            return False
        L = float(raw["L"])  # mm
        EI = float(raw["E"]) * result.value("Iy") * 1e4  # N·mm²
        x = np.linspace(0, L, 201)
        if raw["lastfall"] == "einzellast":
            F = float(raw["F"]) * 1e3  # N
            xs = np.minimum(x, L - x)
            M = F * xs / 2
            w = F * xs * (3 * L**2 - 4 * xs**2) / (48 * EI)
        else:
            q = float(raw["q"])  # N/mm
            M = q * x * (L - x) / 2
            w = q * x * (L**3 - 2 * L * x**2 + x**3) / (24 * EI)

        ax1, ax2 = fig.subplots(2, 1, sharex=True)
        xm = x / 1000
        ax1.fill_between(xm, 0, M / 1e6, color="#1f6fb2", alpha=0.18)
        ax1.plot(xm, M / 1e6, color="#1f6fb2", lw=2)
        ax1.set_ylabel("M  [kN·m]")
        ax1.invert_yaxis()
        ax1.set_title("Biegemomentenverlauf")
        ax2.plot(xm, -w, color="#2b3a4a", lw=2)
        ax2.axhline(0, color="#9aa7b4", lw=0.8)
        ax2.set_ylabel("w  [mm]")
        ax2.set_xlabel("x  [m]")
        ax2.set_title("Biegelinie")
        for ax in (ax1, ax2):
            ax.grid(True, alpha=0.3)
        return True

    # ---------------------------------------------------------------- Skizze
    def sketch_svg(self, raw) -> str:
        s = Svg()
        x0, x1, y = 50, 310, 120
        s.rect(x0, y - 5, x1 - x0, 10)
        s.support_pin(x0, y + 5)
        s.support_roller(x1, y + 5)
        s.text(x0, y + 48, "A", 13, INK).text(x1, y + 48, "B", 13, INK)
        if raw.get("lastfall") == "streckenlast":
            s.line(x0, 70, x1, 70, ACCENT, 1.6)
            for i in range(9):
                xi = x0 + i * (x1 - x0) / 8
                s.arrow(xi, 70, xi, y - 7)
            s.text((x0 + x1) / 2, 62, "q", 15, ACCENT, italic=True)
        else:
            xm = (x0 + x1) / 2
            s.arrow(xm, 50, xm, y - 7)
            s.text(xm + 12, 62, "F", 15, ACCENT, "start", italic=True)
        s.dim_h(x0, x1, 195, "L")
        return s.render()
