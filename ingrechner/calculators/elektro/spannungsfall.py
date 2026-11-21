"""Spannungsfall auf Leitungen (in Anlehnung an DIN VDE 0100-520 Anhang G)."""

from __future__ import annotations

import math

import numpy as np

from ingrechner.core.model import Calculator, ChoiceField, NumberField
from ingrechner.core.svg import ACCENT, INK, Svg
from ingrechner.core.units import Q_, fmt_num, fmt_q

AC = {"netz": ["1ac", "3ac"]}

# Spezifischer Widerstand bei 20 °C [Ω·mm²/m] und Temperaturbeiwert α20 [1/K]
LEITER = {
    "cu": (0.017241, 0.00393, "Kupfer"),
    "al": (0.028264, 0.00403, "Aluminium"),
}
NORMQUERSCHNITTE = [1.5, 2.5, 4, 6, 10, 16, 25, 35, 50, 70, 95, 120, 150, 185, 240, 300]


class Spannungsfall(Calculator):
    id = "et.spannungsfall"
    title = "Spannungsfall Leitung"
    category = "Elektrotechnik"
    description = (
        "Spannungsfall, Leitungswiderstand und Verlustleistung für Gleich-, Wechsel- und "
        "Drehstrom. Bei Überschreitung des Grenzwerts wird der erforderliche Querschnitt vorgeschlagen."
    )
    norm = "In Anlehnung an DIN VDE 0100-520 (VDE 0100-520) Anhang G"
    keywords = ("spannungsfall", "leitung", "kabel", "querschnitt", "vde", "drehstrom", "wechselstrom")

    fields = [
        ChoiceField("netz", "Stromart", [
            ("1ac", "Wechselstrom 1~ (L + N)"),
            ("3ac", "Drehstrom 3~ (symmetrisch)"),
            ("dc", "Gleichstrom (+ / −)"),
        ], "1ac"),
        NumberField("Un", "Nennspannung", "U_n", "V", 230, min=0, decimals=0,
                    tooltip="Wechselstrom: Leiter–Neutralleiter (230 V); Drehstrom: Außenleiterspannung (400 V)"),
        NumberField("I", "Betriebsstrom", "I_b", "A", 16, min=0, decimals=2),
        NumberField("L", "Einfache Leitungslänge", "L", "m", 20, min=0, decimals=1),
        NumberField("S", "Leiterquerschnitt", "S", "mm**2", 1.5, min=0, decimals=2),
        ChoiceField("leiter", "Leiterwerkstoff", [("cu", "Kupfer"), ("al", "Aluminium")], "cu"),
        NumberField("theta", "Leitertemperatur", "θ", "degC", 70, min=-40, max=250, min_inclusive=True,
                    decimals=0, tooltip="Konservativ: zulässige Betriebstemperatur, z. B. PVC 70 °C, VPE 90 °C"),
        NumberField("cosphi", "Leistungsfaktor", "cos φ", "", 1.0, min=0, max=1, decimals=2, visible_if=AC),
        NumberField("lam", "Reaktanzbelag", "λ", "milliohm/m", 0.08, min=0, min_inclusive=True,
                    decimals=3, visible_if=AC, tooltip="DIN VDE 0100-520 Anhang G: 0,08 mΩ/m, wenn unbekannt"),
        NumberField("grenze", "Grenzwert Spannungsfall", "Δu_zul", "percent", 3, min=0, max=100, decimals=1,
                    tooltip="Empfehlung VDE 0100-520 Anh. G: 3 % Beleuchtung, 5 % andere Verbraucher; "
                            "DIN 18015-1: 3 % ab Zähler"),
    ]

    @staticmethod
    def _params(inp):
        netz = inp["netz"]
        b = 1 if netz == "3ac" else 2
        U0 = inp["Un"] / math.sqrt(3) if netz == "3ac" else inp["Un"]
        cos = inp["cosphi"] if netz != "dc" else 1.0
        sin = math.sqrt(max(0.0, 1 - cos**2))
        lam = inp["lam"] if netz != "dc" else Q_(0, "milliohm/m")
        return netz, b, U0, cos, sin, lam

    def compute(self, inp) -> None:
        netz, b, U0, cos, sin, lam = self._params(inp)
        rho20, alpha, name = LEITER[inp["leiter"]]
        theta = inp["theta"].to("degC").magnitude
        rho = Q_(rho20 * (1 + alpha * (theta - 20)), "ohm*mm**2/m")
        L, S, I = inp["L"], inp["S"], inp["I"]

        self.step("Spezifischer Widerstand bei Betriebstemperatur", "ρ_θ = ρ_20 · (1 + α · (θ − 20 °C))",
                  f"ρ_θ = {fmt_num(rho20, 6)} Ω·mm²/m · (1 + {fmt_num(alpha, 5)} 1/K · "
                  f"({fmt_num(theta, 0)} − 20) K)", fmt_q(rho, "ohm*mm**2/m", 6))
        if netz == "3ac":
            self.step("Strangspannung", "U_0 = U_n / √3", f"U_0 = {fmt_q(inp['Un'], 'V', 0)} / √3",
                      fmt_q(U0, "V", 1))

        R = (rho * L / S).to("ohm")
        dU = (b * (rho * L / S * cos + lam * L * sin) * I).to("V")
        du = (dU / U0).to("percent")
        b_txt = "1 (Drehstrom)" if b == 1 else "2 (Hin- und Rückleiter)"
        if netz == "dc":
            self.step("Spannungsfall", "ΔU = b · ρ_θ · L / S · I_b",
                      f"ΔU = 2 · {fmt_q(rho, 'ohm*mm**2/m', 5)} · {fmt_q(L, 'm', 1)} / "
                      f"{fmt_q(S, 'mm**2', 2)} · {fmt_q(I, 'A', 2)}", fmt_q(dU, "V", 2))
        else:
            self.step("Spannungsfall", "ΔU = b · (ρ_θ · L / S · cos φ + λ · L · sin φ) · I_b",
                      f"ΔU = {b} · ({fmt_q(rho, 'ohm*mm**2/m', 5)} · {fmt_q(L, 'm', 1)} / "
                      f"{fmt_q(S, 'mm**2', 2)} · {fmt_num(cos, 2)} + {fmt_q(lam, 'milliohm/m', 3)} · "
                      f"{fmt_q(L, 'm', 1)} · {fmt_num(sin, 3)}) · {fmt_q(I, 'A', 2)}", fmt_q(dU, "V", 2))
        self.step("Relativer Spannungsfall", "Δu = ΔU / U_0 · 100 %",
                  f"Δu = {fmt_q(dU, 'V', 2)} / {fmt_q(U0, 'V', 1)} · 100 %", fmt_q(du, "percent", 2))
        self.info(f"Faktor b = {b_txt}.")

        if netz == "3ac":
            P = (math.sqrt(3) * inp["Un"] * I * cos).to("kW")
            Pv = (3 * I**2 * R).to("W")
        else:
            P = (inp["Un"] * I * cos).to("kW")
            Pv = (2 * I**2 * R).to("W")
        self.step("Verlustleistung", "P_v = n · I_b² · R_L",
                  f"P_v = {3 if netz == '3ac' else 2} · ({fmt_q(I, 'A', 2)})² · {fmt_q(R, 'ohm', 4)}",
                  fmt_q(Pv, "W", 1))

        self.result("du", "Relativer Spannungsfall", "Δu", du, "percent", 2, highlight=True)
        self.result("dU", "Spannungsfall", "ΔU", dU, "V", 2, highlight=True)
        self.result("R", "Widerstand je Leiter", "R_L", R, "ohm", 4)
        self.result("P", "Übertragene Wirkleistung", "P", P, "kW", 2)
        self.result("Pv", "Verlustleistung Leitung", "P_v", Pv, "W", 1)
        self.result("rel_Pv", "Verlustanteil", "P_v/P", (Pv / P).to("percent"), "percent", 2)

        grenze = inp["grenze"]
        if du > grenze:
            self.warn(f"Spannungsfall {fmt_q(du, 'percent', 2)} überschreitet den Grenzwert "
                      f"{fmt_q(grenze, 'percent', 1)}.")
            nenner = grenze.to("").magnitude * U0 / (b * I) - lam * L * sin
            if nenner.magnitude > 0:
                S_min = (rho * L * cos / nenner).to("mm**2")
                vorschlag = next((s for s in NORMQUERSCHNITTE if s >= S_min.magnitude), None)
                self.step("Mindestquerschnitt", "S_min = ρ_θ · L · cos φ / (Δu_zul · U_0 / (b · I_b) − λ · L · sin φ)",
                          f"S_min = {fmt_q(rho, 'ohm*mm**2/m', 5)} · {fmt_q(L, 'm', 1)} · {fmt_num(cos, 2)} / "
                          f"({fmt_num(grenze.to('').magnitude, 4)} · {fmt_q(U0, 'V', 1)} / ({b} · "
                          f"{fmt_q(I, 'A', 2)}) − {fmt_q(lam, 'milliohm/m', 3)} · {fmt_q(L, 'm', 1)} · "
                          f"{fmt_num(sin, 3)})", fmt_q(S_min, "mm**2", 2))
                if vorschlag:
                    self.warn(f"Erforderlich: S ≥ {fmt_q(S_min, 'mm**2', 2)} → Vorschlag {name} "
                              f"{fmt_num(vorschlag, 1)} mm².")
                else:
                    self.warn("Erforderlicher Querschnitt größer als 300 mm² – Parallelleitungen prüfen.")
            else:
                self.warn("Grenzwert ist allein durch den induktiven Anteil nicht einzuhalten.")
        else:
            self.info(f"Grenzwert {fmt_q(grenze, 'percent', 1)} eingehalten.")

        if netz == "3ac" and inp["Un"].magnitude < 300:
            self.warn("Drehstrom gewählt, aber U_n < 300 V: Bei Drehstrom ist die Außenleiterspannung "
                      "(meist 400 V) einzugeben.")
        if netz != "3ac" and inp["Un"].magnitude > 300 and netz == "1ac":
            self.warn("Wechselstrom mit U_n > 300 V – ist eventuell Drehstrom gemeint?")
        if netz != "dc" and S.magnitude > 50:
            self.info("Bei großen Querschnitten dominiert der induktive Anteil – Reaktanzbelag "
                      "möglichst aus Herstellerangaben übernehmen.")
        self.info("Nicht geprüft: Strombelastbarkeit (DIN VDE 0298-4), Abschaltbedingungen und Kurzschluss.")

    # -------------------------------------------------------------- Diagramm
    def plot(self, fig, raw, result) -> bool:
        if not result.ok:
            return False
        L = float(raw["L"])
        du = result.value("du")
        x = np.linspace(0, max(2 * L, 1), 200)
        ax = fig.subplots()
        ax.plot(x, du * x / L, color="#1f6fb2", lw=2, label="Δu(L)")
        ax.axhline(float(raw["grenze"]), color="#c0392b", lw=1.4, ls="--", label="Grenzwert")
        ax.plot([L], [du], "o", color="#2b3a4a", label="Auslegungspunkt")
        ax.set_xlabel("Einfache Leitungslänge L  [m]")
        ax.set_ylabel("Spannungsfall Δu  [%]")
        ax.set_title("Spannungsfall über der Leitungslänge")
        ax.grid(True, alpha=0.3)
        ax.legend(loc="upper left")
        return True

    # ---------------------------------------------------------------- Skizze
    def sketch_svg(self, raw) -> str:
        s = Svg()
        netz = raw.get("netz", "1ac")
        s.rect(22, 70, 64, 80, fill="#ffffff")
        s.text(54, 106, "~" if netz != "dc" else "=", 22, INK).text(54, 132, "U_n", 12, INK)
        s.rect(274, 70, 64, 80, fill="#ffffff")
        s.text(306, 115, "Last", 13, INK)
        n = 3 if netz == "3ac" else 2
        for i in range(n):
            y = 84 + i * (52 / max(1, n - 1))
            s.line(86, y, 274, y, INK, 2)
        s.arrow(140, 60, 210, 60, ACCENT).text(175, 52, "I_b", 13, ACCENT, italic=True)
        s.text(180, 170, "S", 13, INK, italic=True)
        s.dim_h(86, 274, 198, "L (einfache Länge)")
        return s.render()
