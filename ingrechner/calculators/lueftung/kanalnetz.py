"""Lüftungskanalnetz – Strangberechnung mit Dimensionierung runder Leitungen und Geräteverlusten."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from ingrechner.calculators.fluid.druckverlust_rohr import rohrreibungszahl
from ingrechner.core.model import Calculator, Column, NumberField, TableField
from ingrechner.core.svg import ACCENT, INK, MUTED, Svg
from ingrechner.core.units import Q_, fmt_num

from ._lu import RAUHEIT, RUND, d_hydraulisch, luft, luft_felder, rauheit_feld


@dataclass
class TS:
    nr: int
    V: float
    name: str
    A: float
    dh: float
    L: float
    zeta: float
    dpe: float
    auto: bool
    v: float = 0.0
    R: float = 0.0
    dp: float = 0.0


class Kanalnetz(Calculator):
    id = "lu.kanalnetz"
    title = "Lüftungskanalnetz – Strang"
    category = "Lüftung / RLT"
    description = (
        "Druckverlust des ungünstigsten Strangs eines Lüftungsnetzes aus Teilstrecken (Tabelle): Volumenstrom, "
        "Durchmesser oder Rechteckmaß, Länge, Einzelwiderstände und Einbauten (Klappen, Schalldämpfer, Auslässe). "
        "Leerer Durchmesser = runde Normgröße nach v_max und R_max. Dazu die Druckverluste im Lüftungsgerät "
        "(Filter, WRG, Register) – Ergebnis ist die erforderliche Ventilatorpressung."
    )
    norm = "Darcy-Weisbach/Colebrook je Teilstrecke; Rundrohre DIN EN 1506; Δp_ges = Σ Δp_TS + Δp_Gerät"
    keywords = ("kanalnetz", "lüftungsnetz", "strang", "teilstrecke", "luftkanal", "ventilatorpressung",
                "druckverlust", "dimensionierung", "lüftung", "rlt", "zuluft", "abluft")

    fields = [
        TableField("strecken", "Teilstrecken (vom Gerät zum ungünstigsten Luftdurchlass)", [
            Column("V", "V̇", "m**3/hour", decimals=0, min=0),
            Column("d", "d/a", "mm", optional=True, decimals=0, min=0),
            Column("b", "b", "mm", optional=True, decimals=0, min=0),
            Column("L", "L", "m", decimals=1, min=0),
            Column("zeta", "Σζ", "", optional=True, decimals=2, min=0),
            Column("dpe", "Δp Einb", "Pa", optional=True, decimals=0, min=0)],
            [[4000, None, None, 12, 1.2, 25], [2500, None, None, 15, 0.8, None], [1200, None, None, 10, 0.8, None],
             [400, None, None, 6, 1.5, 30]],
            min_rows=1, max_rows=40,
            tooltip="d/a leer = automatisch rund; nur d/a = rund Ø d; d/a und b = Rechteckkanal a × b. Δp Einbauten z. B. "
                    "Volumenstromregler 50–100 Pa, Schalldämpfer 20–50 Pa, Luftdurchlass 20–40 Pa."),
        NumberField("vmax", "Max. Luftgeschwindigkeit (Dimensionierung)", "v_max", "m/s", 5, min=0, decimals=1),
        NumberField("Rmax", "Max. Druckgefälle (Dimensionierung)", "R_max", "Pa/m", 1.5, min=0, decimals=2),
        rauheit_feld(),
        NumberField("dp_g", "Druckverluste im Gerät", "Δp_Gerät", "Pa", 350, min=0, min_inclusive=True, decimals=0,
                    tooltip="Filter (Enddruckverlust), WRG, Heiz-/Kühlregister, Schalldämpfer im Gerät, "
                            "Außenluft-/Fortluftgitter"),
        NumberField("res", "Sicherheitszuschlag Kanalnetz", "z", "percent", 10, min=0, min_inclusive=True, max=50,
                    decimals=0),
        *luft_felder(20),
    ]

    def _strecken(self, rows) -> list[TS]:
        out = []
        for i, row in enumerate(rows, 1):
            V, d, b, L, zeta, dpe = (list(row) + [None] * 6)[:6]
            V = V / 3600
            if d is not None and b is not None:
                a_, b_ = d / 1000, b / 1000
                ts = TS(i, V, f"{fmt_num(d, 0)}×{fmt_num(b, 0)}", a_ * b_, d_hydraulisch(a_, b_), L, zeta or 0,
                        dpe or 0, False)
            elif d is not None:
                ts = TS(i, V, f"Ø{fmt_num(d, 0)}", math.pi * (d / 1000) ** 2 / 4, d / 1000, L, zeta or 0, dpe or 0,
                        False)
            else:
                ts = TS(i, V, "", 0.0, 0.0, L, zeta or 0, dpe or 0, True)
            out.append(ts)
        return out

    def _r(self, V, A, dh, k, z) -> tuple[float, float]:
        v = V / A
        lam = rohrreibungszahl(v * dh / z.nu, k / dh)
        return v, lam / dh * z.rho * v**2 / 2

    def _rechnen(self, inp, z) -> list[TS]:
        k = RAUHEIT[inp["rauheit"]][1] / 1000
        vmax, Rmax = inp["vmax"].to("m/s").magnitude, inp["Rmax"].to("Pa/m").magnitude
        strecken = self._strecken(inp["strecken"])
        for s in strecken:
            if s.auto:
                for dd in RUND:
                    d = dd / 1000
                    v, R = self._r(s.V, math.pi * d**2 / 4, d, k, z)
                    if v <= vmax and R <= Rmax:
                        break
                s.name, s.A, s.dh = f"Ø{dd}", math.pi * d**2 / 4, d
            s.v, s.R = self._r(s.V, s.A, s.dh, k, z)
            s.dp = s.R * s.L + s.zeta * z.rho * s.v**2 / 2 + s.dpe
        return strecken

    def compute(self, inp) -> None:
        med, z = luft(inp)
        self.step("Luftzustand", "ρ, ν", f"{med.name}, θ = {fmt_num(z.theta, 1)} °C, p = {fmt_num(z.p / 100, 0)} hPa",
                  f"ρ = {fmt_num(z.rho, 3)} kg/m³, ν = {fmt_num(z.nu * 1e6, 2)} mm²/s")
        strecken = self._rechnen(inp, z)
        for s in strecken:
            self.step(f"Teilstrecke {s.nr} – {s.name}" + (" (auto)" if s.auto else ""),
                      "Δp = R·L + Σζ·ρv²/2 + Δp_E",
                      f"V̇ = {fmt_num(s.V * 3600, 0)} m³/h, v = {fmt_num(s.v, 2)} m/s, R = {fmt_num(s.R, 2)} Pa/m, "
                      f"L = {fmt_num(s.L, 1)} m, Σζ = {fmt_num(s.zeta, 2)}" + (f", Δp_E = {fmt_num(s.dpe, 0)} Pa"
                                                                             if s.dpe else ""),
                      f"{fmt_num(s.dp, 1)} Pa")
        dp_netz = sum(s.dp for s in strecken)
        zf = 1 + inp["res"].to("percent").magnitude / 100
        dp_g = inp["dp_g"].to("Pa").magnitude
        dp = dp_netz * zf + dp_g
        self.step("Ventilatorpressung", "Δp_V = Σ Δp_TS · (1 + z) + Δp_Gerät",
                  f"Δp_V = {fmt_num(dp_netz, 1)} · {fmt_num(zf, 2)} + {fmt_num(dp_g, 0)} Pa", f"{fmt_num(dp, 0)} Pa")
        V0 = max(s.V for s in strecken)
        self.result("V", "Volumenstrom (Gerät)", "V̇", Q_(V0, "m**3/s"), "m**3/hour", 0, highlight=True)
        self.result("dp", "Erforderliche Ventilatorpressung", "Δp_V", Q_(dp, "Pa"), "Pa", 0, highlight=True)
        self.result("dpext", "davon Kanalnetz (extern, mit Zuschlag)", "Δp_ext", Q_(dp_netz * zf, "Pa"), "Pa", 0,
                    highlight=True)
        self.result("dpg", "davon Gerät (intern)", "Δp_int", Q_(dp_g, "Pa"), "Pa", 0)
        self.result("vmax", "Größte Geschwindigkeit", "v_max", Q_(max(s.v for s in strecken), "m/s"), "m/s", 2)
        self.result("L", "Leitungslänge", "ΣL", Q_(sum(s.L for s in strecken), "m"), "m", 1)
        vmax, Rmax = inp["vmax"].to("m/s").magnitude, inp["Rmax"].to("Pa/m").magnitude
        zu = [s for s in strecken if s.v > vmax * 1.02 or (not s.auto and s.R > Rmax * 1.05)]
        if zu:
            self.warn("Grenzwerte überschritten in " + ", ".join(
                f"TS {s.nr} ({s.name}: v = {fmt_num(s.v, 2)} m/s, R = {fmt_num(s.R, 2)} Pa/m)" for s in zu) + ".")
        self.info("Parallelstränge über Volumenstromregler oder Drosselklappen abgleichen; Δp des ungünstigsten "
                  "Luftdurchlasses (Herstellerangabe) als Einbau der letzten Teilstrecke berücksichtigen.")

    def plot(self, fig, raw, result) -> bool:
        if not result.ok:
            return False
        inp = {"strecken": self.field("strecken").parse(raw["strecken"])[0], "rauheit": raw["rauheit"],
               "vmax": Q_(float(raw["vmax"]), "m/s"), "Rmax": Q_(float(raw["Rmax"]), "Pa/m"),
               "gas": raw["gas"], "theta": Q_(float(raw["theta"]), "degC"), "hoehe": Q_(float(raw["hoehe"]), "m")}
        _, z = luft(inp)
        st = self._rechnen(inp, z)
        x = np.arange(1, len(st) + 1)
        ax = fig.subplots()
        ax.bar(x, [s.dp for s in st], color="#1f6fb2")
        for xi, s in zip(x, st):
            ax.annotate(s.name, (xi, s.dp), ha="center", va="bottom", fontsize=7, xytext=(0, 2),
                        textcoords="offset points")
        ax2 = ax.twinx()
        ax2.plot(x, np.cumsum([s.dp for s in st]), "o-", color="#c0392b")
        ax2.set_ylabel("Σ Δp  [Pa]", color="#c0392b")
        ax.set_xticks(x)
        ax.set_xlabel("Teilstrecke")
        ax.set_ylabel("Δp je TS  [Pa]")
        ax.set_title("Druckverlust entlang des Strangs")
        ax.grid(True, axis="y", alpha=0.3)
        return True

    def sketch_svg(self, raw) -> str:
        s = Svg()
        s.rect(14, 80, 60, 50, fill="#eef3f8").text(44, 110, "RLT", 11, INK, bold=True)
        s.line(74, 105, 340, 105, ACCENT, 8)
        for x in (140, 210, 280):
            s.line(x, 105, x, 160, ACCENT, 5).rect(x - 12, 160, 24, 8, fill="#9aa7b4")
        s.rect(332, 160, 16, 8, fill="#9aa7b4").line(340, 105, 340, 160, ACCENT, 5)
        for i, x in enumerate((107, 175, 245, 310), 1):
            s.text(x, 92, f"TS {i}", 10, INK, bold=True)
        s.text(180, 200, "Pressung = Σ Δp der Teilstrecken + Δp Gerät", 11, MUTED)
        return s.render()
