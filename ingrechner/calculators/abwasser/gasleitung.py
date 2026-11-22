"""Klärgas-/Biogasleitung: Druckverlust im Niederdruck, Geschwindigkeit und Kondensatanfall."""

from __future__ import annotations

import math

import numpy as np

from ingrechner.calculators.pumpen._pumpe import rauheit, rauheit_felder, rohr_dp
from ingrechner.core import medien
from ingrechner.core.model import Calculator, ChoiceField, NumberField
from ingrechner.core.stoffwerte import dampfdruck
from ingrechner.core.svg import ACCENT, INK, MUTED, Svg
from ingrechner.core.units import Q_, fmt_num

from ._aw import rohr_felder, rohr_geometrie

M_W = 18.015          # g/mol Wasser
V_MN = 22.414         # l/mol ideales Gas im Normzustand


def wasserbeladung(theta: float, p_abs: float) -> float:
    """Wasserdampf je Norm-m³ trockenes Gas in kg bei Sättigung (θ in °C, p in Pa)."""
    pv = dampfdruck(theta) * 1000
    if pv >= p_abs:
        raise ValueError("Der Sättigungsdampfdruck erreicht den Gasdruck.")
    return pv / (p_abs - pv) * M_W / V_MN


class Gasleitung(Calculator):
    id = "aw.gasleitung"
    title = "Klärgasleitung"
    category = "Abwasser / Klärwerk"
    description = (
        "Klärgas-, Biogas- oder Erdgasleitung im Niederdruck: Betriebsvolumenstrom aus Normvolumenstrom, "
        "Gasgeschwindigkeit, Druckverlust (Darcy-Weisbach mit Realgasdichte) gegen den zulässigen Druckverlust "
        "sowie Kondensatanfall beim Abkühlen des wassergesättigten Gases."
    )
    norm = "V̇_B = V̇_N · (p_N/p) · (T/T_N) · Z; Δp nach Darcy-Weisbach; Kondensat aus Sättigungsbeladung"
    keywords = ("klärgas", "biogas", "faulgas", "gasleitung", "kondensat", "kondensatabscheider", "niederdruck",
                "gasdruck", "mbar", "bhkw", "erdgas", "faulbehälter", "gasgeschwindigkeit")

    fields = [
        NumberField("Vn", "Gasvolumenstrom (Normzustand)", "V̇_N", "m**3/hour", 60, min=0, decimals=2,
                    tooltip="Normzustand 0 °C, 1013,25 mbar, trocken"),
        ChoiceField("gas", "Gas", medien.auswahl("gas"), "klaergas_65"),
        NumberField("pue", "Betriebsüberdruck", "p_ü", "mbar", 30, min=0, min_inclusive=True, decimals=1,
                    tooltip="Klärgas-Niederdrucknetz typisch 20–50 mbar"),
        NumberField("pamb", "Luftdruck", "p_amb", "mbar", 1013.25, min=500, decimals=1),
        NumberField("tg", "Gastemperatur in der Leitung", "θ_G", "degC", 15, min=-10, max=80, decimals=1),
        *rohr_felder("pe11:110"),
        NumberField("L", "Leitungslänge", "L", "m", 120, min=0, decimals=1),
        *rauheit_felder("kunststoff"),
        NumberField("zeta", "Summe Einzelwiderstände", "Σζ", "", 6, min=0, min_inclusive=True, decimals=2,
                    tooltip="Bögen, Absperrklappen, Kiesfilter/Flammensperre, Kondensatabscheider"),
        NumberField("dpz", "Zulässiger Druckverlust", "Δp_zul", "mbar", 5, min=0, decimals=1),
        NumberField("tsat", "Sättigungstemperatur am Eintritt", "θ_ein", "degC", 35, min=0, max=80, decimals=1,
                    tooltip="Gas verlässt den Faulbehälter wassergesättigt bei etwa Faultemperatur"),
    ]

    def compute(self, inp) -> None:
        g = medien.medium(inp["gas"])
        pue = inp["pue"].to("Pa").magnitude
        p = inp["pamb"].to("Pa").magnitude + pue
        tg = inp["tg"].to("degC").magnitude
        z = g.zustand(tg, p)
        zn = g.zustand(0.0, medien.P_NORM)
        Vn = inp["Vn"].to("m**3/s").magnitude
        m = Vn * zn.rho
        Vb = m / z.rho
        self.step("Gasdichte", "ρ = p · M / (Z · R · T)", f"{g.name}: p = {fmt_num(p / 100, 1)} mbar abs, "
                  f"θ = {fmt_num(tg, 1)} °C, Z = {fmt_num(z.Z, 4)}",
                  f"ρ = {fmt_num(z.rho, 4)} kg/m³ (Norm: {fmt_num(zn.rho, 4)} kg/m³)")
        self.step("Betriebsvolumenstrom", "V̇_B = V̇_N · ρ_N / ρ", f"V̇_B = {fmt_num(Vn * 3600, 2)} m³/h · "
                  f"{fmt_num(zn.rho, 4)} / {fmt_num(z.rho, 4)}", f"{fmt_num(Vb * 3600, 2)} m³/h")
        name, di, _, _ = rohr_geometrie(inp)
        r = rohr_dp(Vb, di, inp["L"].to("m").magnitude, rauheit(inp), float(inp["zeta"]), z.rho, z.nu)
        dp = r.dp_r + r.dp_z
        self.step("Strömung", "v = V̇_B / A;  Re = v · d_i / ν", f"{name}: d_i = {fmt_num(di * 1000, 1)} mm",
                  f"v = {fmt_num(r.v, 2)} m/s, Re = {fmt_num(r.re, 0)}, λ = {fmt_num(r.lam, 4)}")
        self.step("Druckverlust", "Δp = (λ · L/d_i + Σζ) · ρ · v²/2",
                  f"Δp = ({fmt_num(r.lam, 4)} · {fmt_num(inp['L'].to('m').magnitude, 1)}/{fmt_num(di, 4)} + "
                  f"{fmt_num(float(inp['zeta']), 2)}) · {fmt_num(z.rho, 4)} · {fmt_num(r.v, 2)}²/2",
                  f"{fmt_num(dp / 100, 2)} mbar")
        tsat = inp["tsat"].to("degC").magnitude
        x1 = wasserbeladung(tsat, p)
        x2 = wasserbeladung(min(tg, tsat), p)
        kond = Vn * 3600 * (x1 - x2)          # kg/h
        self.step("Kondensatanfall", "ṁ_K = V̇_N · (x(θ_ein) − x(θ_G));  x = p_s/(p − p_s) · M_W/V_m,N",
                  f"x(θ_ein) = {fmt_num(x1 * 1000, 1)} g/m³, x(θ_G) = {fmt_num(x2 * 1000, 1)} g/m³",
                  f"{fmt_num(kond * 24, 1)} l/d")

        dpz = inp["dpz"].to("Pa").magnitude
        self.result("dp", "Druckverlust", "Δp", Q_(dp, "Pa"), "mbar", 2, highlight=True)
        self.result("v", "Gasgeschwindigkeit", "v", Q_(r.v, "m/s"), "m/s", 2, highlight=True)
        self.result("Vb", "Betriebsvolumenstrom", "V̇_B", Q_(Vb, "m**3/s"), "m**3/hour", 2)
        self.result("rho", "Gasdichte (Betrieb)", "ρ", Q_(z.rho, "kg/m**3"), "kg/m**3", 4)
        self.result("kond", "Kondensatanfall", "ṁ_K", Q_(kond * 24, "liter/day"), "liter/day", 1, highlight=True)
        self.result("P", "Brennstoffleistung (Heizwert)", "P_B",
                    Q_(Vn * 3600 * self._hi(inp["gas"]), "kW"), "kW", 0)
        self.result("di", "Innendurchmesser", "d_i", Q_(di * 1000, "mm"), "mm", 1)

        if dp > dpz:
            self.warn(f"Druckverlust {fmt_num(dp / 100, 2)} mbar über dem zulässigen Wert {fmt_num(dpz / 100, 1)} mbar "
                      "– größere Nennweite wählen.")
        if dp > 0.1 * pue and pue > 0:
            self.warn("Der Druckverlust übersteigt 10 % des Betriebsüberdrucks – Versorgungsdruck am Verbraucher "
                      "(BHKW, Kessel, Fackel) prüfen.")
        if r.v > 6:
            self.warn(f"Gasgeschwindigkeit {fmt_num(r.v, 1)} m/s – für feuchtes Klärgas sind ≤ 5–6 m/s üblich "
                      "(Kondensatmitriss, Geräusche).")
        if kond > 0:
            self.info(f"Kondensat {fmt_num(kond * 24, 1)} l/d: Leitung mit Gefälle (≥ 0,5–1 %) zu frostfreien "
                      "Kondensatabscheidern an Tiefpunkten verlegen.")
        self.info("Inkompressible Rechnung mit Dichte am Leitungsanfang – für Niederdruck zulässig. Klärgas enthält "
                  "H₂S: Werkstoffe und Explosionsschutz (DGUV, DWA-M 363) beachten.")

    @staticmethod
    def _hi(mid: str) -> float:
        """Heizwert kWh/m³ (Norm) aus dem Brennbaranteil der Modellzusammensetzung."""
        g = medien.medium(mid)
        y = g.zusammensetzung
        tot = sum(y.values())
        return (y.get("CH4", 0) * 9.97 + y.get("C2H6", 0) * 17.4) / tot

    def plot(self, fig, raw, result) -> bool:
        if not result.ok:
            return False
        Vn = float(raw["Vn"])
        vs = np.linspace(Vn * 0.1, Vn * 2, 80)
        dp0 = result.value("dp")
        ax = fig.subplots()
        ax.plot(vs, dp0 * (vs / Vn) ** 1.85, color="#1f6fb2", lw=2, label="Druckverlust (≈ V̇^1,85)")
        ax.axhline(float(raw["dpz"]), color="#c0392b", ls="--", label="zulässig")
        ax.plot([Vn], [dp0], "o", color="#2b3a4a")
        ax.set_xlabel("Normvolumenstrom V̇_N  [m³/h]")
        ax.set_ylabel("Δp  [mbar]")
        ax.set_title("Druckverlust über dem Gasvolumenstrom")
        ax.grid(True, alpha=0.3)
        ax.legend(loc="upper left", fontsize=8)
        return True

    def sketch_svg(self, raw) -> str:
        s = Svg()
        s.rect(20, 60, 70, 110, fill="#e8dccb").text(55, 120, "FB", 12, INK, bold=True)
        s.line(90, 80, 300, 110, "#27ae60", 4)
        s.rect(300, 95, 50, 40, fill="#eef3f8").text(325, 120, "BHKW", 9, INK, bold=True)
        s.line(200, 95, 200, 150, MUTED, 2).rect(190, 150, 20, 24, fill="#cfe0f1")
        s.text(200, 192, "Kondensat", 10, MUTED)
        s.arrow(120, 70, 180, 78, ACCENT).text(150, 60, "V̇_N", 12, INK, italic=True)
        s.text(250, 80, "Gefälle ≥ 0,5 %", 10, MUTED)
        return s.render()
