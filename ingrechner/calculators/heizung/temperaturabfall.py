"""Temperaturabfall des Heizwassers entlang einer gedämmten Rohrleitung."""

from __future__ import annotations

import math

import numpy as np

from ingrechner.core.model import Calculator, ChoiceField, NumberField
from ingrechner.core.rohrdaten import EMISSION
from ingrechner.core.stoffwerte import stoffwerte
from ingrechner.core.svg import ACCENT, INK, Svg
from ingrechner.core.units import Q_, fmt_num, fmt_q
from ingrechner.core.waermeverlust import rohrverlust, temperaturverlauf

from ._rohr import aufloesen, emission_feld, rohr_felder


class Temperaturabfall(Calculator):
    id = "hz.temperaturabfall"
    title = "Temperaturabfall in der Leitung"
    category = "Heizung / Wärme"
    description = (
        "Austrittstemperatur, Temperaturabfall und Wärmeverlust einer durchströmten Rohrleitung in Luft "
        "(exponentieller Abfall bei konstantem Wärmedurchlasswiderstand je Meter)."
    )
    norm = "Energiebilanz ṁ·c_p·dθ = −(θ − θ_a)/R' · dx; Wärmeübergang nach DIN EN ISO 12241"
    keywords = ("temperaturabfall", "abkühlung", "auskühlung", "vorlauftemperatur", "leitung", "fernleitung",
                "wärmeverlust", "rohrleitung", "zirkulation")
    material_map = {"lam_rohr": "lam"}
    material_select = ("werkstoff", "frei")

    fields = [
        NumberField("tein", "Eintrittstemperatur", "θ_ein", "degC", 70, min=0, max=150, min_inclusive=True,
                    decimals=1),
        NumberField("V", "Volumenstrom (Wasser)", "V̇", "m**3/hour", 1.0, min=0, decimals=4),
        NumberField("L", "Leitungslänge", "L", "m", 200, min=0, decimals=1),
        *rohr_felder(),
        NumberField("ta", "Umgebungstemperatur", "θ_a", "degC", 10, min=-50, max=100, min_inclusive=True,
                    decimals=1),
        ChoiceField("ort", "Verlegung", [("innen", "im Gebäude (ruhende Luft)"),
                                         ("aussen", "im Freien (Wind)")], "innen"),
        NumberField("wind", "Windgeschwindigkeit", "v", "m/s", 5, min=0, min_inclusive=True, decimals=1,
                    visible_if={"ort": ["aussen"]}),
        emission_feld(),
    ]

    def _r(self, inp, g, tm):
        eps = EMISSION[inp["oberflaeche"]][0] if g["daemm"] > 0 else 0.80
        return rohrverlust(tm, inp["ta"].to("degC").magnitude, g["da"], g["s"], g["lam_r"], g["daemm"],
                           g["lam_d"], eps, inp["ort"], inp["wind"].to("m/s").magnitude if inp["ort"] == "aussen" else 0)

    def compute(self, inp) -> None:
        g = aufloesen(inp)
        tein, ta = inp["tein"].to("degC").magnitude, inp["ta"].to("degC").magnitude
        L = inp["L"].to("m").magnitude
        sw = stoffwerte("wasser", tein)
        m = inp["V"].to("m**3/s").magnitude * sw.rho          # kg/s
        cp = sw.cp * 1000
        taus = tein
        for _ in range(6):   # R' bei mittlerer Temperatur der Strecke
            r = self._r(inp, g, (tein + taus) / 2)
            taus = temperaturverlauf(tein, ta, m, cp, r.R_ges, L)
        dT = tein - taus
        Q = m * cp * dT
        di = g["da"] - 2 * g["s"]
        v = inp["V"].to("m**3/s").magnitude / (math.pi * di**2 / 4)

        self.step("Massenstrom", "ṁ = V̇ · ρ(θ_ein)",
                  f"ṁ = {fmt_q(inp['V'], 'm**3/s', 6)} · {fmt_num(sw.rho, 1)} kg/m³", f"{fmt_num(m, 4)} kg/s")
        self.step("Wärmedurchlasswiderstand je Meter (bei θ_mittel)", "R' = R_R + R_D + R_a",
                  f"{g['rohr']}, {g['werkstoff']}, {fmt_num(g['daemm'] * 1000, 0)} mm {g['daemmstoff']}; "
                  f"θ_mittel = {fmt_num((tein + taus) / 2, 1)} °C", f"{fmt_num(r.R_ges, 4)} m·K/W")
        self.step("Austrittstemperatur", "θ_aus = θ_a + (θ_ein − θ_a) · exp(−L / (ṁ · c_p · R'))",
                  f"θ_aus = {fmt_num(ta, 1)} + ({fmt_num(tein, 1)} − {fmt_num(ta, 1)}) · exp(−{fmt_num(L, 1)} / "
                  f"({fmt_num(m, 4)} · {fmt_num(cp, 0)} · {fmt_num(r.R_ges, 4)}))", f"{fmt_num(taus, 2)} °C")
        self.step("Wärmeverlust der Strecke", "Q̇ = ṁ · c_p · (θ_ein − θ_aus)",
                  f"Q̇ = {fmt_num(m, 4)} kg/s · {fmt_num(cp, 0)} J/(kg·K) · {fmt_num(dT, 3)} K", f"{fmt_num(Q, 1)} W")

        self.result("taus", "Austrittstemperatur", "θ_aus", Q_(taus, "degC"), "degC", 2, highlight=True)
        self.result("dT", "Temperaturabfall", "Δθ", Q_(dT, "K"), "K", 3, highlight=True)
        self.result("Q", "Wärmeverlust der Leitung", "Q̇_V", Q_(Q, "W"), "W", 1, highlight=True)
        self.result("q", "Mittlerer Verlust je Meter", "q", Q_(Q / L, "W/m"), "W/m", 2)
        self.result("v", "Strömungsgeschwindigkeit", "v", Q_(v, "m/s"), "m/s", 3)
        self.result("t", "Verweilzeit", "t", Q_(L / v / 60 if v else 0, "minute"), "minute", 1)
        self.result("R", "Wärmedurchlasswiderstand je Meter", "R'", Q_(r.R_ges, "m*K/W"), "m*K/W", 4)

        if v < 0.1:
            self.warn(f"Sehr kleine Fließgeschwindigkeit ({fmt_num(v, 3)} m/s): große Abkühlung, bei Stillstand "
                      "kühlt die Leitung vollständig aus.")
        if dT > 0.2 * (tein - ta):
            self.info("Großer Temperaturabfall – Dämmung verstärken oder Volumenstrom erhöhen.")
        self.info("Stationärer Betrieb; Auskühlung bei Stillstand und Aufheizvorgänge sind nicht erfasst.")

    def plot(self, fig, raw, result) -> bool:
        if not result.ok:
            return False
        L = float(raw["L"])
        tein, ta = float(raw["tein"]), float(raw["ta"])
        taus = result.value("taus")
        k = -math.log((taus - ta) / (tein - ta)) / L if tein != ta and taus != ta else 0
        x = np.linspace(0, L, 200)
        ax = fig.subplots()
        ax.plot(x, ta + (tein - ta) * np.exp(-k * x), color="#c0392b", lw=2, label="Medium")
        drop = abs(tein - taus)
        if drop < 0.3 * abs(tein - ta):          # kleiner Abfall: auf den Mediumverlauf zoomen
            pad = max(0.5, 0.3 * drop)
            ax.set_ylim(min(tein, taus) - pad, max(tein, taus) + pad)
        else:
            ax.axhline(ta, color="#1f6fb2", lw=1.2, ls="--", label="Umgebung")
        ax.set_xlabel("Leitungslänge x  [m]")
        ax.set_ylabel("Temperatur  [°C]")
        ax.set_title("Temperaturverlauf entlang der Leitung")
        ax.grid(True, alpha=0.3)
        ax.legend(loc="best")
        return True

    def sketch_svg(self, raw) -> str:
        s = Svg()
        s.rect(40, 92, 280, 36, fill="#eef3f8")
        s.rect(40, 102, 280, 16, fill="#dce6f1")
        s.arrow(80, 110, 280, 110, "#c0392b")
        s.text(40, 82, "θ_ein", 13, "#c0392b", "start", True).text(320, 82, "θ_aus", 13, "#1f6fb2", "end", True)
        for x in (90, 180, 270):
            s.arrow(x, 128, x, 156, ACCENT, 1.4, 6)
        s.text(180, 176, "Wärmeverlust q an die Umgebung", 11, INK)
        s.dim_h(40, 320, 204, "L")
        return s.render()
