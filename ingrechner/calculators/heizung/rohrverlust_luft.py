"""Wärmeverlust einer gedämmten oder ungedämmten Rohrleitung in Luft (DIN EN ISO 12241 / VDI 2055)."""

from __future__ import annotations

import numpy as np

from ingrechner.core.model import Calculator, ChoiceField, NumberField
from ingrechner.core.rohrdaten import EMISSION
from ingrechner.core.units import Q_, fmt_num
from ingrechner.core.waermeverlust import rohrverlust

from ._rohr import aufloesen, emission_feld, querschnitt_svg, rohr_felder


class RohrverlustLuft(Calculator):
    id = "hz.rohrverlust_luft"
    title = "Wärmeverlust Rohrleitung (Luft)"
    category = "Heizung / Wärme"
    description = (
        "Wärmeverlust je Meter und gesamt, Oberflächentemperatur und Vergleich mit dem ungedämmten Rohr "
        "für Rohrleitungen in Gebäuden (freie Konvektion) oder im Freien (Wind) – mit Strahlungsanteil."
    )
    norm = "DIN EN ISO 12241 (Wärmeübergang außen, Abschnitt 4), VDI 2055 Blatt 1"
    keywords = ("wärmeverlust", "rohrleitung", "dämmung", "isolierung", "rohrdämmung", "verlust", "w/m",
                "oberflächentemperatur", "vdi 2055", "iso 12241", "heizungsrohr")
    material_map = {"lam_rohr": "lam"}
    material_select = ("werkstoff", "frei")

    fields = [
        *rohr_felder(),
        NumberField("tm", "Mediumtemperatur", "θ_m", "degC", 70, min=-50, max=400, min_inclusive=True, decimals=1),
        NumberField("ta", "Umgebungstemperatur", "θ_a", "degC", 20, min=-50, max=100, min_inclusive=True,
                    decimals=1),
        ChoiceField("ort", "Verlegung", [("innen", "im Gebäude (ruhende Luft)"),
                                         ("aussen", "im Freien (Wind)")], "innen"),
        NumberField("wind", "Windgeschwindigkeit", "v", "m/s", 5, min=0, min_inclusive=True, decimals=1,
                    visible_if={"ort": ["aussen"]}),
        emission_feld(),
        NumberField("L", "Rohrlänge", "L", "m", 10, min=0, decimals=1),
    ]

    def _calc(self, inp, g, daemm=None):
        eps = EMISSION[inp["oberflaeche"]][0] if (daemm if daemm is not None else g["daemm"]) > 0 else \
            (0.80 if not g["kunststoff"] else 0.93)
        return rohrverlust(inp["tm"].to("degC").magnitude, inp["ta"].to("degC").magnitude, g["da"], g["s"],
                           g["lam_r"], g["daemm"] if daemm is None else daemm, g["lam_d"], eps, inp["ort"],
                           inp["wind"].to("m/s").magnitude if inp["ort"] == "aussen" else 0.0)

    def compute(self, inp) -> None:
        g = aufloesen(inp)
        tm, ta = inp["tm"].to("degC").magnitude, inp["ta"].to("degC").magnitude
        if abs(tm - ta) < 0.01:
            raise ValueError("Medium- und Umgebungstemperatur sind gleich – kein Wärmestrom.")
        L = inp["L"].to("m").magnitude
        r = self._calc(inp, g)
        r0 = self._calc(inp, g, daemm=0.0)
        di = g["da"] - 2 * g["s"]

        self.step("Geometrie", "D = d_a + 2·s_D", f"{g['rohr']}: d_a = {fmt_num(g['da'] * 1000, 1)} mm, "
                  f"d_i = {fmt_num(di * 1000, 1)} mm, s_D = {fmt_num(g['daemm'] * 1000, 1)} mm",
                  f"D = {fmt_num(r.D * 1000, 1)} mm")
        self.step("Wärmeleitwiderstand Rohrwand", "R_R = ln(d_a/d_i) / (2π · λ_R)",
                  f"{g['werkstoff']}: λ_R = {fmt_num(g['lam_r'], 3)} W/(m·K)", f"{fmt_num(r.R_rohr, 5)} m·K/W")
        if g["daemm"] > 0:
            self.step("Wärmeleitwiderstand Dämmung", "R_D = ln(D/d_a) / (2π · λ_D)",
                      f"{g['daemmstoff']}: λ_D = {fmt_num(g['lam_d'], 4)} W/(m·K)", f"{fmt_num(r.R_daemm, 4)} m·K/W")
        konv = ("freie Konvektion, waagerechtes Rohr" if inp["ort"] == "innen"
                else f"Wind v = {fmt_num(inp['wind'].to('m/s').magnitude, 1)} m/s")
        self.step("Wärmeübergang außen (iteriert über θ_s)", "h_a = h_k + h_r;  h_r = ε·σ·(T_s⁴ − T_a⁴)/(T_s − T_a)",
                  f"{konv}: h_k = {fmt_num(r.h_conv, 2)}, h_r = {fmt_num(r.h_rad, 2)} W/(m²·K)",
                  f"h_a = {fmt_num(r.h_a, 2)} W/(m²·K)")
        self.step("Wärmeübergangswiderstand außen", "R_a = 1 / (π · D · h_a)", "", f"{fmt_num(r.R_aussen, 4)} m·K/W")
        self.step("Längenbezogener Wärmeverlust", "q = (θ_m − θ_a) / (R_R + R_D + R_a)",
                  f"q = {fmt_num(tm - ta, 1)} K / {fmt_num(r.R_ges, 4)} m·K/W", f"{fmt_num(r.q, 2)} W/m")
        self.step("Oberflächentemperatur", "θ_s = θ_a + q · R_a",
                  f"θ_s = {fmt_num(ta, 1)} °C + {fmt_num(r.q, 2)} W/m · {fmt_num(r.R_aussen, 4)} m·K/W",
                  f"{fmt_num(r.ts, 1)} °C")

        self.result("q", "Wärmeverlust je Meter", "q", Q_(r.q, "W/m"), "W/m", 2, highlight=True)
        self.result("Qges", "Wärmeverlust gesamt", "Q̇", Q_(r.q * L, "W"), "W", 1, highlight=True)
        self.result("ts", "Oberflächentemperatur", "θ_s", Q_(r.ts, "degC"), "degC", 1, highlight=True)
        self.result("q0", "Verlust ungedämmt (Vergleich)", "q₀", Q_(r0.q, "W/m"), "W/m", 1)
        if g["daemm"] > 0 and r0.q:
            self.result("red", "Verlustminderung durch Dämmung", "η_D", Q_((1 - r.q / r0.q) * 100, "percent"),
                        "percent", 1)
        self.result("ha", "Wärmeübergangskoeffizient außen", "h_a", Q_(r.h_a, "W/(m**2*K)"), "W/(m**2*K)", 2)
        self.result("R", "Wärmedurchlasswiderstand je Meter", "R'", Q_(r.R_ges, "m*K/W"), "m*K/W", 4)

        if tm > ta and r.ts > 60:
            self.warn(f"Oberflächentemperatur {fmt_num(r.ts, 0)} °C > 60 °C – Verbrennungsgefahr, Berührungsschutz "
                      "vorsehen bzw. Dämmung verstärken.")
        if tm < ta:
            self.info("Medium kälter als die Umgebung: Wärmegewinn (negatives q). Bei Kaltwasser auf Tauwasser an "
                      "der Oberfläche achten (θ_s gegen Taupunkt prüfen).")
        if g["daemm"] > 0 and inp["oberflaeche"] in ("blech_alu", "blech_alu_ox", "verzinkt") and r.ts - ta > 5:
            self.info("Blanke Blechmäntel strahlen wenig ab – die Oberfläche wird dadurch wärmer.")
        if g["kunststoff"]:
            self.info(f"Kunststoffrohr ({g['werkstoff']}): zulässige Betriebstemperatur und Druck nach "
                      "Herstellerangabe prüfen.")
        self.info("Annahmen: waagerechtes Rohr, innerer Wärmeübergang vernachlässigt (auf der sicheren Seite), "
                  "λ der Dämmung konstant; Halterungen und Armaturen erhöhen den Verlust (VDI 2055: Zuschläge).")

    def plot(self, fig, raw, result) -> bool:
        if not result.ok:
            return False
        inp = self._quantities(raw)
        g = aufloesen(inp)
        xs = np.linspace(0, max(0.12, g["daemm"] * 2), 60)
        qs = [self._calc(inp, g, daemm=x).q for x in xs]
        ax = fig.subplots()
        ax.plot(xs * 1000, qs, color="#1f6fb2", lw=2)
        ax.plot([g["daemm"] * 1000], [result.value("q")], "o", color="#c0392b")
        ax.set_xlabel("Dämmdicke  [mm]")
        ax.set_ylabel("Wärmeverlust q  [W/m]")
        ax.set_title("Wärmeverlust über der Dämmdicke")
        ax.set_ylim(bottom=0)
        ax.grid(True, alpha=0.3)
        return True

    def _quantities(self, raw):
        out = {}
        for f in self.fields:
            v = raw.get(f.key, f.default)
            out[f.key] = v if isinstance(f, ChoiceField) else (Q_(float(v), f.unit) if f.unit else float(v))
        return out

    def sketch_svg(self, raw) -> str:
        try:
            d = float(raw.get("daemm", 50))
        except (TypeError, ValueError):
            d = 50
        return querschnitt_svg(d, "Querschnitt – Rohr mit Dämmung")
