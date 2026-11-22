"""Ventilator: Leistungsaufnahme, spezifische Ventilatorleistung (SFP) und Jahresenergie."""

from __future__ import annotations

import numpy as np

from ingrechner.core.feuchte import hoehe_druck
from ingrechner.core.model import Calculator, NumberField
from ingrechner.core.svg import ACCENT, INK, MUTED, Svg
from ingrechner.core.units import Q_, fmt_num

# SFP-Klassen DIN EN 16798-3 (W/(m³/s), Obergrenzen)
SFP_KLASSEN = [("SFP 0", 300), ("SFP 1", 500), ("SFP 2", 750), ("SFP 3", 1250), ("SFP 4", 2000), ("SFP 5", 3000),
               ("SFP 6", 4500), ("SFP 7", float("inf"))]


def sfp_klasse(sfp: float) -> str:
    return next(k for k, g in SFP_KLASSEN if sfp <= g)


class Ventilator(Calculator):
    id = "lu.ventilator"
    title = "Ventilator – Leistung & SFP"
    category = "Lüftung / RLT"
    description = (
        "Elektrische Leistungsaufnahme eines Ventilators aus Volumenstrom, Gesamtdruckerhöhung und "
        "Systemwirkungsgrad, spezifische Ventilatorleistung SFP mit Klasse nach DIN EN 16798-3, Dichtekorrektur "
        "für Temperatur und Aufstellhöhe sowie Jahresenergie und -kosten."
    )
    norm = "P_el = V̇ · Δp / η_ges;  SFP = P_el / V̇ (DIN EN 16798-3);  Δp ~ ρ bei gleicher Drehzahl"
    keywords = ("ventilator", "lüfter", "sfp", "spezifische ventilatorleistung", "leistungsaufnahme", "ec-motor",
                "16798-3", "energie", "lüftung", "rlt", "ventilatorpressung", "stromkosten")

    fields = [
        NumberField("V", "Volumenstrom", "V̇", "m**3/hour", 4000, min=0, decimals=0),
        NumberField("dp_ext", "Externe Pressung (Kanalnetz)", "Δp_ext", "Pa", 300, min=0, min_inclusive=True,
                    decimals=0),
        NumberField("dp_int", "Interne Druckverluste (Gerät)", "Δp_int", "Pa", 350, min=0, min_inclusive=True,
                    decimals=0, tooltip="Filter, WRG, Register, Gehäuse – Herstellerangabe"),
        NumberField("eta", "Systemwirkungsgrad", "η_ges", "percent", 55, min=5, max=90, decimals=1,
                    tooltip="Ventilator · Motor · Antrieb/FU; EC-Radialventilatoren freilaufend 50–65 %"),
        NumberField("theta", "Lufttemperatur am Ventilator", "θ", "degC", 20, min=-30, max=120, decimals=1),
        NumberField("hoehe", "Aufstellhöhe über NN", "h_NN", "m", 100, min=-400, max=4000, min_inclusive=True,
                    decimals=0),
        NumberField("t", "Betriebsstunden pro Jahr", "t", "hour", 3000, min=0, max=8760, decimals=0),
        NumberField("teil", "Mittlere Auslastung (Volumenstrom)", "V̇_m/V̇", "percent", 100, min=10, max=100,
                    decimals=0, tooltip="Bei bedarfsgeregelten Anlagen (CO₂, Präsenz): Leistung ~ V̇³ "
                                        "(Affinitätsgesetz, vereinfacht)"),
        NumberField("preis", "Strompreis", "k_E", "EUR/(kW*h)", 0.30, min=0, decimals=3),
    ]

    def compute(self, inp) -> None:
        V = inp["V"].to("m**3/s").magnitude
        dp = inp["dp_ext"].to("Pa").magnitude + inp["dp_int"].to("Pa").magnitude
        eta = inp["eta"].to("percent").magnitude / 100
        theta = inp["theta"].to("degC").magnitude
        p = hoehe_druck(inp["hoehe"].to("m").magnitude)
        rho = p / (287.06 * (theta + 273.15))
        P_luft = V * dp
        P = P_luft / eta
        sfp = P / V if V else 0.0
        self.step("Gesamtdruckerhöhung", "Δp = Δp_ext + Δp_int",
                  f"Δp = {fmt_num(inp['dp_ext'].to('Pa').magnitude, 0)} + {fmt_num(inp['dp_int'].to('Pa').magnitude, 0)} Pa",
                  f"{fmt_num(dp, 0)} Pa")
        self.step("Luftleistung", "P_L = V̇ · Δp", f"P_L = {fmt_num(V, 4)} m³/s · {fmt_num(dp, 0)} Pa",
                  f"{fmt_num(P_luft, 0)} W")
        self.step("Elektrische Leistung", "P_el = P_L / η_ges", f"P_el = {fmt_num(P_luft, 0)} W / {fmt_num(eta, 3)}",
                  f"{fmt_num(P, 0)} W")
        self.step("Spezifische Ventilatorleistung", "SFP = P_el / V̇", f"SFP = {fmt_num(P, 0)} W / {fmt_num(V, 4)} m³/s",
                  f"{fmt_num(sfp, 0)} W/(m³/s) → {sfp_klasse(sfp)}")
        x = inp["teil"].to("percent").magnitude / 100
        t = inp["t"].to("hour").magnitude
        E = P * x**3 * t / 1000
        preis = inp["preis"].to("EUR/(kW*h)").magnitude
        self.step("Jahresenergie", "E = P_el · (V̇_m/V̇)³ · t", f"E = {fmt_num(P, 0)} W · {fmt_num(x, 2)}³ · {fmt_num(t, 0)} h",
                  f"{fmt_num(E, 0)} kWh/a")

        self.result("P", "Elektrische Leistungsaufnahme", "P_el", Q_(P, "W"), "kW", 2, highlight=True)
        self.result("sfp", "Spezifische Ventilatorleistung", "SFP", Q_(sfp, "W/(m**3/s)"), "W/(m**3/s)", 0,
                    highlight=True)
        self.result("PL", "Luftleistung", "P_L", Q_(P_luft, "W"), "kW", 2)
        self.result("dp", "Gesamtdruckerhöhung", "Δp", Q_(dp, "Pa"), "Pa", 0)
        self.result("rho", "Luftdichte am Ventilator", "ρ", Q_(rho, "kg/m**3"), "kg/m**3", 3)
        self.result("E", "Jahresenergie", "E", Q_(E, "kW*h/year"), "kW*h/year", 0)
        self.result("K", "Energiekosten", "K", Q_(E * preis, "EUR/year"), "EUR/year", 0, highlight=True)
        self.info(f"SFP-Klasse nach DIN EN 16798-3: {sfp_klasse(sfp)} (Grenzen SFP 1 ≤ 500, SFP 2 ≤ 750, "
                  "SFP 3 ≤ 1250, SFP 4 ≤ 2000 W/(m³/s)).")
        if sfp > 1250:
            self.warn("SFP über Klasse 3 – Druckverluste (Filter, Kanalnetz) und Ventilatorwirkungsgrad prüfen; "
                      "GEG/EnEV-Anforderungen für Neuanlagen beachten.")
        if abs(rho / 1.2 - 1) > 0.05:
            self.info(f"Luftdichte {fmt_num(rho, 3)} kg/m³ weicht von 1,2 kg/m³ (Kennlinien-Normdichte) ab: bei gleicher "
                      f"Drehzahl ändern sich Druck und Leistung im Verhältnis {fmt_num(rho / 1.2, 3)}.")

    def plot(self, fig, raw, result) -> bool:
        if not result.ok:
            return False
        V = float(raw["V"])
        xs = np.linspace(0.2, 1.0, 50)
        ax = fig.subplots()
        P = result.value("P") * 1000
        ax.plot(xs * 100, P * xs**3, color="#1f6fb2", lw=2, label="P_el ~ V̇³ (Anlagenkennlinie ~ V̇²)")
        ax.plot([float(raw["teil"])], [P * (float(raw["teil"]) / 100) ** 3], "o", color="#c0392b",
                label="mittlere Auslastung")
        ax.set_xlabel(f"Volumenstrom  [% von {fmt_num(V, 0)} m³/h]")
        ax.set_ylabel("Leistungsaufnahme  [W]")
        ax.set_title("Leistung bei Teillast (bedarfsgeregelt)")
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=8)
        return True

    def sketch_svg(self, raw) -> str:
        s = Svg()
        s.circle(180, 110, 50, fill="#eef3f8")
        for ang in range(0, 360, 45):
            import math
            a = math.radians(ang)
            s.line(180, 110, 180 + 40 * math.cos(a), 110 + 40 * math.sin(a), ACCENT, 3)
        s.circle(180, 110, 8, fill="#2b3a4a")
        s.arrow(40, 110, 125, 110, ACCENT).arrow(235, 110, 330, 110, ACCENT)
        s.text(60, 100, "V̇", 13, INK, italic=True).text(300, 100, "Δp", 13, INK, italic=True)
        s.text(180, 200, "SFP = Leistungsaufnahme / Volumenstrom", 11, MUTED)
        return s.render()
