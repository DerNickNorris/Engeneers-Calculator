"""Heizkörperleistung bei abweichenden Temperaturen (DIN EN 442) und erforderliche Normleistung."""

from __future__ import annotations

import math

import numpy as np

from ingrechner.core.model import Calculator, NumberField
from ingrechner.core.stoffwerte import stoffwerte
from ingrechner.core.svg import ACCENT, INK, Svg
from ingrechner.core.units import Q_, fmt_num

NORM = (75.0, 65.0, 20.0)


def dt_log(tv: float, tr: float, ti: float) -> float:
    """Logarithmische Übertemperatur ΔT_ln = (θ_V − θ_R) / ln((θ_V − θ_i)/(θ_R − θ_i))."""
    a, b = tv - ti, tr - ti
    if abs(a - b) < 1e-9:
        return a
    return (tv - tr) / math.log(a / b)


DT_NORM = dt_log(*NORM)   # 49,83 K


class Heizkoerper(Calculator):
    id = "hz.heizkoerper"
    title = "Heizkörperleistung"
    category = "Heizung / Wärme"
    description = (
        "Umrechnung der Norm-Wärmeleistung (75/65/20 °C) auf andere Vorlauf-, Rücklauf- und Raumtemperaturen "
        "über die logarithmische Übertemperatur und den Heizkörperexponenten; erforderliche Normleistung "
        "für einen Raumwärmebedarf (z. B. bei Umstellung auf Wärmepumpe)."
    )
    norm = "DIN EN 442-2 (Normwärmeleistung bei 75/65/20 °C, Exponent n)"
    keywords = ("heizkörper", "radiator", "heizkörperleistung", "normleistung", "en 442", "exponent",
                "übertemperatur", "wärmepumpe", "vorlauftemperatur")

    fields = [
        NumberField("phiN", "Normwärmeleistung (75/65/20)", "Φ_N", "W", 1500, min=0, decimals=0,
                    tooltip="Herstellerangabe nach DIN EN 442; ältere Kataloge 90/70/20 vorher umrechnen"),
        NumberField("n", "Heizkörperexponent", "n", "", 1.3, min=1.0, max=2.0, min_inclusive=True, decimals=2,
                    tooltip="Plattenheizkörper ≈ 1,25–1,33; Gliederheizkörper ≈ 1,3; Konvektoren ≈ 1,4–1,5; "
                            "Fußbodenheizung ≈ 1,1"),
        NumberField("tv", "Vorlauftemperatur", "θ_V", "degC", 55, min=0, max=120, decimals=1),
        NumberField("tr", "Rücklauftemperatur", "θ_R", "degC", 45, min=0, max=120, decimals=1),
        NumberField("ti", "Raumtemperatur", "θ_i", "degC", 20, min=0, max=40, min_inclusive=True, decimals=1),
        NumberField("Qb", "Raumwärmebedarf (optional)", "Q̇_H", "W", 0, min=0, min_inclusive=True, decimals=0,
                    tooltip="Heizlast des Raumes nach DIN EN 12831 – für die erforderliche Normleistung; 0 = ohne"),
    ]

    def compute(self, inp) -> None:
        tv, tr, ti = (inp[k].to("degC").magnitude for k in ("tv", "tr", "ti"))
        if tv <= tr:
            raise ValueError("Die Vorlauftemperatur muss über der Rücklauftemperatur liegen.")
        if tr <= ti:
            raise ValueError("Die Rücklauftemperatur muss über der Raumtemperatur liegen.")
        n = inp["n"]
        phiN = inp["phiN"].to("W").magnitude
        dtl = dt_log(tv, tr, ti)
        f = (dtl / DT_NORM) ** n
        phi = phiN * f
        self.step("Norm-Übertemperatur", "ΔT_ln,N = (75 − 65) / ln((75 − 20)/(65 − 20))", "", f"{fmt_num(DT_NORM, 2)} K")
        self.step("Logarithmische Übertemperatur", "ΔT_ln = (θ_V − θ_R) / ln((θ_V − θ_i)/(θ_R − θ_i))",
                  f"ΔT_ln = ({fmt_num(tv, 1)} − {fmt_num(tr, 1)}) / ln(({fmt_num(tv, 1)} − {fmt_num(ti, 1)}) / "
                  f"({fmt_num(tr, 1)} − {fmt_num(ti, 1)}))", f"{fmt_num(dtl, 2)} K")
        self.step("Umrechnungsfaktor", "f = (ΔT_ln / ΔT_ln,N)^n",
                  f"f = ({fmt_num(dtl, 2)} / {fmt_num(DT_NORM, 2)})^{fmt_num(n, 2)}", fmt_num(f, 4))
        self.step("Wärmeleistung", "Φ = Φ_N · f", f"Φ = {fmt_num(phiN, 0)} W · {fmt_num(f, 4)}", f"{fmt_num(phi, 0)} W")

        sw = stoffwerte("wasser", (tv + tr) / 2)
        V = phi / (sw.rho * sw.cp * 1000 * (tv - tr)) * 3600 * 1000   # l/h
        self.step("Heizwasserstrom", "V̇ = Φ / (ρ · c_p · (θ_V − θ_R))",
                  f"V̇ = {fmt_num(phi, 0)} W / ({fmt_num(sw.rho, 1)} · {fmt_num(sw.cp * 1000, 0)} · "
                  f"{fmt_num(tv - tr, 1)})", f"{fmt_num(V, 1)} l/h")

        self.result("phi", "Wärmeleistung", "Φ", Q_(phi, "W"), "W", 0, highlight=True)
        self.result("f", "Leistungsfaktor", "Φ/Φ_N", Q_(f * 100, "percent"), "percent", 1, highlight=True)
        self.result("dtl", "Log. Übertemperatur", "ΔT_ln", Q_(dtl, "K"), "K", 2)
        self.result("V", "Heizwasserstrom", "V̇", Q_(V, "liter/hour"), "liter/hour", 1)
        Qb = inp["Qb"].to("W").magnitude
        if Qb > 0:
            phiN_erf = Qb / f
            self.step("Erforderliche Normleistung", "Φ_N,erf = Q̇_H / f",
                      f"Φ_N,erf = {fmt_num(Qb, 0)} W / {fmt_num(f, 4)}", f"{fmt_num(phiN_erf, 0)} W")
            self.result("phiN_erf", "Erforderliche Normleistung", "Φ_N,erf", Q_(phiN_erf, "W"), "W", 0, highlight=True)
            self.result("deckung", "Deckung des Wärmebedarfs", "Φ/Q̇_H", Q_(phi / Qb * 100, "percent"), "percent", 0)
            if phi < Qb:
                self.warn(f"Der Heizkörper deckt nur {fmt_num(phi / Qb * 100, 0)} % des Wärmebedarfs – Normleistung "
                          f"mindestens {fmt_num(phiN_erf, 0)} W oder höhere Vorlauftemperatur.")
            else:
                self.info(f"Wärmebedarf gedeckt ({fmt_num(phi / Qb * 100, 0)} %).")
        if (tr - ti) / (tv - ti) < 0.3:
            self.info("Sehr große Spreizung im Verhältnis zur Übertemperatur – Heizkörper wird ungleichmäßig warm.")
        self.info("Gilt für frei aufgestellte Heizkörper; Verkleidungen, Nischen und Anschlussart mindern die "
                  "Leistung (Herstellerfaktoren).")

    def plot(self, fig, raw, result) -> bool:
        if not result.ok:
            return False
        spreiz = float(raw["tv"]) - float(raw["tr"])
        ti, n, phiN = float(raw["ti"]), float(raw["n"]), float(raw["phiN"])
        tvs = np.linspace(ti + spreiz + 3, 90, 100)
        phis = [phiN * (dt_log(t, t - spreiz, ti) / DT_NORM) ** n for t in tvs]
        ax = fig.subplots()
        ax.plot(tvs, phis, color="#c0392b", lw=2, label=f"Spreizung {fmt_num(spreiz, 0)} K")
        ax.plot([float(raw["tv"])], [result.value("phi")], "o", color="#2b3a4a")
        if float(raw.get("Qb", 0) or 0) > 0:
            ax.axhline(float(raw["Qb"]), color="#1f6fb2", ls="--", lw=1.2, label="Wärmebedarf")
        ax.set_xlabel("Vorlauftemperatur θ_V  [°C]")
        ax.set_ylabel("Wärmeleistung Φ  [W]")
        ax.set_title("Heizkörperleistung über der Vorlauftemperatur")
        ax.grid(True, alpha=0.3)
        ax.legend(loc="upper left")
        return True

    def sketch_svg(self, raw) -> str:
        s = Svg()
        s.rect(80, 60, 200, 110, fill="#eef3f8")
        for x in range(92, 280, 16):
            s.line(x, 66, x, 164, "#9aa7b4", 1.2)
        s.arrow(30, 70, 78, 70, "#c0392b").text(30, 62, "θ_V", 12, "#c0392b", "start", True)
        s.arrow(282, 160, 330, 160, "#1f6fb2").text(330, 152, "θ_R", 12, "#1f6fb2", "end", True)
        for x in (120, 180, 240):
            s.arrow(x, 56, x, 26, ACCENT, 1.4, 6)
        s.text(180, 200, "Raum θ_i", 12, INK, italic=True)
        return s.render()
