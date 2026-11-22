"""Automatische Abschaltung im TN-System mit Leitungsschutzschalter (DIN VDE 0100-410)."""

from __future__ import annotations

import numpy as np

from ingrechner.core.model import Calculator, ChoiceField, NumberField
from ingrechner.core.svg import ACCENT, INK, Svg
from ingrechner.core.units import Q_, fmt_num, fmt_q

from .spannungsfall import LEITER

# Auslösecharakteristik LS-Schalter (DIN EN 60898-1): sicheres Auslösen des
# elektromagnetischen Auslösers (< 0,1 s) beim k-fachen Bemessungsstrom
CHARAKTERISTIK = {"B": 5, "C": 10, "D": 20}
C_MIN = 0.95   # Spannungsfaktor für den kleinsten Kurzschlussstrom (DIN EN 60909-0)


class Abschaltbedingung(Calculator):
    id = "et.abschaltbedingung"
    title = "Abschaltbedingung LS-Schalter"
    category = "Elektrotechnik"
    description = (
        "Schleifenimpedanz und kleinster einpoliger Kurzschlussstrom am Leitungsende im TN-System; "
        "Prüfung, ob der Leitungsschutzschalter in der geforderten Zeit abschaltet, und maximale Leitungslänge."
    )
    norm = "DIN VDE 0100-410 (Abschaltzeiten Tab. 41.1), LS-Schalter DIN EN 60898-1, c_min nach DIN EN 60909-0"
    keywords = ("abschaltbedingung", "schleifenimpedanz", "kurzschlussstrom", "ls-schalter", "sicherungsautomat",
                "leitungslänge", "fehlerschutz", "tn-system", "vde 0100-410")

    fields = [
        NumberField("U0", "Spannung gegen Erde", "U₀", "V", 230, min=0, decimals=0),
        NumberField("Zv", "Schleifenimpedanz am Verteiler", "Z_S,v", "ohm", 0.3, min=0, min_inclusive=True,
                    decimals=3, tooltip="Gemessen oder vom Netzbetreiber; typisch 0,1–0,5 Ω an der Unterverteilung"),
        NumberField("L", "Einfache Leitungslänge", "L", "m", 30, min=0, decimals=1),
        NumberField("S", "Querschnitt Außenleiter = Schutzleiter", "S", "mm**2", 1.5, min=0, decimals=2),
        ChoiceField("leiter", "Leiterwerkstoff", [("cu", "Kupfer"), ("al", "Aluminium")], "cu"),
        NumberField("theta", "Leitertemperatur im Fehlerfall", "θ", "degC", 80, min=-40, max=250,
                    min_inclusive=True, decimals=0,
                    tooltip="Konservativ: mittlere Temperatur während des Kurzschlusses, häufig 80 °C angesetzt"),
        ChoiceField("char", "Auslösecharakteristik", [("B", "B (5 × I_n)"), ("C", "C (10 × I_n)"),
                                                      ("D", "D (20 × I_n)")], "B"),
        NumberField("In", "Bemessungsstrom", "I_n", "A", 16, min=0, decimals=1),
        ChoiceField("zeit", "Geforderte Abschaltzeit", [
            ("0.4", "0,4 s – Endstromkreis (Steckdosen ≤ 63 A, fest angeschlossen ≤ 32 A), 230 V"),
            ("5", "5 s – Verteilerstromkreis")], "0.4"),
    ]

    @staticmethod
    def _rho(leiter: str, theta: float) -> float:
        rho20, alpha, _ = LEITER[leiter]
        return rho20 * (1 + alpha * (theta - 20))

    def compute(self, inp) -> None:
        U0, Zv, L, S, In = inp["U0"], inp["Zv"], inp["L"], inp["S"], inp["In"]
        theta = inp["theta"].to("degC").magnitude
        rho = Q_(self._rho(inp["leiter"], theta), "ohm*mm**2/m")
        k = CHARAKTERISTIK[inp["char"]]
        R_L = (2 * rho * L / S).to("ohm")
        Zs = Zv + R_L
        Ik = (C_MIN * U0 / Zs).to("A")
        Ia = k * In
        reserve = (Ik / Ia).to("").magnitude
        L_max = ((C_MIN * U0 / Ia - Zv) * S / (2 * rho)).to("m")

        self.step("Spezifischer Widerstand", "ρ_θ = ρ₂₀ · (1 + α · (θ − 20 °C))", f"θ = {fmt_num(theta, 0)} °C",
                  fmt_q(rho, "ohm*mm**2/m", 5))
        self.step("Widerstand Hin- und Rückleiter", "R_L = 2 · ρ_θ · L / S",
                  f"R_L = 2 · {fmt_q(rho, 'ohm*mm**2/m', 5)} · {fmt_q(L, 'm', 1)} / {fmt_q(S, 'mm**2', 2)}",
                  fmt_q(R_L, "ohm", 4))
        self.step("Schleifenimpedanz am Leitungsende", "Z_S = Z_S,v + R_L",
                  f"Z_S = {fmt_q(Zv, 'ohm', 3)} + {fmt_q(R_L, 'ohm', 4)}", fmt_q(Zs, "ohm", 4))
        self.step("Kleinster Kurzschlussstrom", "I_k,min = c_min · U₀ / Z_S",
                  f"I_k,min = {fmt_num(C_MIN, 2)} · {fmt_q(U0, 'V', 0)} / {fmt_q(Zs, 'ohm', 4)}", fmt_q(Ik, "A", 1))
        self.step("Auslösestrom LS-Schalter", f"I_a = {k} · I_n  (Charakteristik {inp['char']})",
                  f"I_a = {k} · {fmt_q(In, 'A', 1)}", fmt_q(Ia, "A", 1))
        self.step("Bedingung", "I_k,min ≥ I_a", f"{fmt_q(Ik, 'A', 1)} ≥ {fmt_q(Ia, 'A', 1)}",
                  "erfüllt" if reserve >= 1 else "NICHT erfüllt")
        self.step("Maximale Leitungslänge", "L_max = (c_min · U₀ / I_a − Z_S,v) · S / (2 · ρ_θ)",
                  f"L_max = ({fmt_num(C_MIN, 2)} · {fmt_q(U0, 'V', 0)} / {fmt_q(Ia, 'A', 1)} − {fmt_q(Zv, 'ohm', 3)}) · "
                  f"{fmt_q(S, 'mm**2', 2)} / (2 · {fmt_q(rho, 'ohm*mm**2/m', 5)})",
                  fmt_q(L_max, "m", 1) if L_max.magnitude > 0 else "keine")

        self.result("Ik", "Kleinster Kurzschlussstrom", "I_k,min", Ik, "A", 1, highlight=True)
        self.result("Ia", "Auslösestrom", "I_a", Ia, "A", 1)
        self.result("Zs", "Schleifenimpedanz", "Z_S", Zs, "ohm", 4, highlight=True)
        self.result("Lmax", "Maximale Leitungslänge", "L_max", Q_(max(0.0, L_max.magnitude), "m"), "m", 1,
                    highlight=True)
        self.result("reserve", "Reserve I_k / I_a", "I_k/I_a", Q_(reserve, ""), "", 2)

        if reserve >= 1:
            self.info(f"Abschaltbedingung erfüllt: Der Schalter löst magnetisch aus (< 0,1 s) und hält "
                      f"damit {inp['zeit'].replace('.', ',')} s ein.")
        else:
            self.warn(f"Abschaltbedingung NICHT erfüllt: I_k,min = {fmt_q(Ik, 'A', 0)} < I_a = {fmt_q(Ia, 'A', 0)}. "
                      "Querschnitt vergrößern, Leitung kürzen, andere Charakteristik oder RCD einsetzen.")
        if L_max.magnitude <= 0:
            self.warn("Bereits die Schleifenimpedanz am Verteiler ist zu hoch für diesen Schalter.")
        self.info("Vereinfachung: Leitungsreaktanz vernachlässigt (bei S ≤ 16 mm² unerheblich); Schmelzsicherungen "
                  "gG erfordern Kennlinien. Die Messung der Schleifenimpedanz nach DIN VDE 0100-600 bleibt Pflicht.")

    def plot(self, fig, raw, result) -> bool:
        if not result.ok:
            return False
        U0, Zv, S = float(raw["U0"]), float(raw["Zv"]), float(raw["S"])
        rho = self._rho(raw["leiter"], float(raw["theta"]))
        Ia = CHARAKTERISTIK[raw["char"]] * float(raw["In"])
        Lmax = max(result.value("Lmax"), float(raw["L"]), 10)
        x = np.linspace(0, 1.6 * Lmax, 200)
        ax = fig.subplots()
        ax.plot(x, C_MIN * U0 / (Zv + 2 * rho * x / S), color="#1f6fb2", lw=2, label="I_k,min(L)")
        ax.axhline(Ia, color="#c0392b", ls="--", lw=1.4, label=f"I_a = {Ia:g} A".replace(".", ","))
        ax.plot([float(raw["L"])], [result.value("Ik")], "o", color="#2b3a4a", label="Auslegung")
        ax.set_xlabel("Einfache Leitungslänge L  [m]")
        ax.set_ylabel("Kurzschlussstrom  [A]")
        ax.set_title("Kurzschlussstrom über der Leitungslänge")
        ax.grid(True, alpha=0.3)
        ax.legend(loc="upper right")
        return True

    def sketch_svg(self, raw) -> str:
        s = Svg()
        s.rect(20, 70, 60, 70, fill="#ffffff").text(50, 100, "UV", 13, INK).text(50, 120, "Z_S,v", 11, INK)
        s.rect(92, 92, 30, 26, fill="#dce6f1").text(107, 110, raw.get("char", "B"), 12, INK, bold=True)
        s.line(80, 105, 92, 105, INK, 2).line(122, 105, 300, 105, INK, 2)
        s.line(80, 130, 300, 130, "#2e7d4f", 2).text(200, 146, "PE", 11, "#2e7d4f")
        s.rect(300, 90, 40, 50, fill="#ffffff")
        s.line(300, 90, 340, 140, "#c0392b", 2).line(340, 90, 300, 140, "#c0392b", 2)
        s.text(320, 160, "Fehler", 11, "#c0392b")
        s.arrow(150, 92, 260, 92).text(205, 84, "I_k", 12, ACCENT, italic=True)
        s.dim_h(122, 300, 190, "L")
        return s.render()
