"""Mischtemperatur von Wasserströmen und Rücklaufbeimischung für eine Ziel-Vorlauftemperatur."""

from __future__ import annotations

from ingrechner.core.model import Calculator, ChoiceField, NumberField
from ingrechner.core.stoffwerte import stoffwerte
from ingrechner.core.svg import INK, MUTED, Svg
from ingrechner.core.units import Q_, fmt_num

MISCH = {"modus": ["mischung"]}
BEIM = {"modus": ["beimischung"]}


class Mischtemperatur(Calculator):
    id = "hz.mischtemperatur"
    title = "Mischtemperatur"
    category = "Heizung / Wärme"
    description = (
        "Temperatur nach dem Zusammenführen von bis zu drei Wasserströmen (Energiebilanz mit temperatur-"
        "abhängigen Stoffwerten) oder die Aufteilung einer Rücklaufbeimischung (Mischventil), um eine "
        "Ziel-Vorlauftemperatur zu erreichen."
    )
    norm = "Energie- und Massenbilanz Σṁ·c_p·θ; Stoffwerte VDI-Wärmeatlas"
    keywords = ("mischtemperatur", "mischung", "beimischung", "mischventil", "dreiwegeventil", "rücklauf",
                "vorlauf", "hydraulik", "mischer")

    fields = [
        ChoiceField("modus", "Aufgabe", [("mischung", "Mischung mehrerer Ströme"),
                                         ("beimischung", "Rücklaufbeimischung (Mischventil)")], "mischung"),
        NumberField("V1", "Strom 1: Volumenstrom", "V̇₁", "m**3/hour", 1.0, min=0, decimals=3, visible_if=MISCH),
        NumberField("t1", "Strom 1: Temperatur", "θ₁", "degC", 70, min=0, max=150, min_inclusive=True, decimals=1,
                    visible_if=MISCH),
        NumberField("V2", "Strom 2: Volumenstrom", "V̇₂", "m**3/hour", 0.5, min=0, decimals=3, visible_if=MISCH),
        NumberField("t2", "Strom 2: Temperatur", "θ₂", "degC", 30, min=0, max=150, min_inclusive=True, decimals=1,
                    visible_if=MISCH),
        NumberField("V3", "Strom 3: Volumenstrom (0 = keiner)", "V̇₃", "m**3/hour", 0, min=0, min_inclusive=True,
                    decimals=3, visible_if=MISCH),
        NumberField("t3", "Strom 3: Temperatur", "θ₃", "degC", 50, min=0, max=150, min_inclusive=True, decimals=1,
                    visible_if=MISCH),
        NumberField("tvl", "Vorlauftemperatur Erzeuger", "θ_VL,E", "degC", 75, min=0, max=150, min_inclusive=True,
                    decimals=1, visible_if=BEIM),
        NumberField("trl", "Rücklauftemperatur Heizkreis", "θ_RL", "degC", 35, min=0, max=150, min_inclusive=True,
                    decimals=1, visible_if=BEIM),
        NumberField("tz", "Ziel-Vorlauftemperatur Heizkreis", "θ_VL,Z", "degC", 45, min=0, max=150,
                    min_inclusive=True, decimals=1, visible_if=BEIM),
        NumberField("Vh", "Volumenstrom Heizkreis", "V̇_H", "m**3/hour", 1.2, min=0, decimals=3, visible_if=BEIM),
    ]

    def compute(self, inp) -> None:
        if inp["modus"] == "mischung":
            self._mischung(inp)
        else:
            self._beimischung(inp)

    def _mischung(self, inp) -> None:
        streams = []
        for i in (1, 2, 3):
            V = inp[f"V{i}"].to("m**3/s").magnitude
            if V > 0:
                t = inp[f"t{i}"].to("degC").magnitude
                sw = stoffwerte("wasser", t)
                streams.append((i, V, t, sw.rho * V, sw.cp))
        if len(streams) < 2:
            raise ValueError("Für eine Mischung sind mindestens zwei Ströme nötig.")
        num = sum(m * cp * t for _, _, t, m, cp in streams)
        den = sum(m * cp for _, _, _, m, cp in streams)
        tm = num / den
        m_ges = sum(m for *_, m, _ in streams)
        V_ges = m_ges / stoffwerte("wasser", tm).rho
        terms = " + ".join(f"{fmt_num(m * 3600, 1)}·{fmt_num(cp, 3)}·{fmt_num(t, 1)}" for _, _, t, m, cp in streams)
        self.step("Massenströme", "ṁ_i = V̇_i · ρ(θ_i)",
                  ", ".join(f"ṁ{i} = {fmt_num(m * 3600, 1)} kg/h" for i, _, _, m, _ in streams),
                  f"Σṁ = {fmt_num(m_ges * 3600, 1)} kg/h")
        self.step("Mischtemperatur", "θ_M = Σ(ṁ_i · c_p,i · θ_i) / Σ(ṁ_i · c_p,i)", f"θ_M = ({terms}) / …",
                  f"{fmt_num(tm, 2)} °C")
        self.result("tm", "Mischtemperatur", "θ_M", Q_(tm, "degC"), "degC", 2, highlight=True)
        self.result("V", "Volumenstrom gesamt", "V̇_M", Q_(V_ges, "m**3/s"), "m**3/hour", 3, highlight=True)
        self.result("m", "Massenstrom gesamt", "ṁ_M", Q_(m_ges, "kg/s"), "kg/hour", 1)
        self.info("Adiabate Mischung ohne Wärmeverluste; Volumenströme bei der jeweiligen Stromtemperatur.")

    def _beimischung(self, inp) -> None:
        tvl, trl, tz = (inp[k].to("degC").magnitude for k in ("tvl", "trl", "tz"))
        if not trl < tz < tvl:
            raise ValueError("Die Zieltemperatur muss zwischen Rücklauf- und Erzeuger-Vorlauftemperatur liegen.")
        sw_v, sw_r, sw_z = stoffwerte("wasser", tvl), stoffwerte("wasser", trl), stoffwerte("wasser", tz)
        # Massenanteil Erzeugerwasser aus der Energiebilanz (c_p mittlerer Werte)
        x = (sw_z.cp * tz - sw_r.cp * trl) / (sw_v.cp * tvl - sw_r.cp * trl)
        x = (tz - trl) / (tvl - trl) if abs(sw_v.cp - sw_r.cp) < 1e-9 else x
        m_h = inp["Vh"].to("m**3/s").magnitude * sw_z.rho
        m_e = x * m_h
        m_b = m_h - m_e
        V_e = m_e / sw_v.rho * 3600
        V_b = m_b / sw_r.rho * 3600
        self.step("Anteil Erzeugerwasser", "x = (θ_VL,Z − θ_RL) / (θ_VL,E − θ_RL)",
                  f"x = ({fmt_num(tz, 1)} − {fmt_num(trl, 1)}) / ({fmt_num(tvl, 1)} − {fmt_num(trl, 1)})  "
                  "(mit c_p(θ) korrigiert)", f"{fmt_num(x * 100, 1)} %")
        self.step("Aufteilung der Volumenströme", "V̇_E = x · ṁ_H / ρ(θ_VL,E);  V̇_B = (1 − x) · ṁ_H / ρ(θ_RL)",
                  f"ṁ_H = {fmt_num(m_h * 3600, 1)} kg/h",
                  f"V̇_E = {fmt_num(V_e, 3)} m³/h, V̇_B = {fmt_num(V_b, 3)} m³/h")
        self.result("x", "Anteil Erzeugerwasser", "x", Q_(x * 100, "percent"), "percent", 1, highlight=True)
        self.result("Ve", "Volumenstrom vom Erzeuger", "V̇_E", Q_(V_e, "m**3/hour"), "m**3/hour", 3, highlight=True)
        self.result("Vb", "Volumenstrom Beimischung (Bypass)", "V̇_B", Q_(V_b, "m**3/hour"), "m**3/hour", 3,
                    highlight=True)
        self.result("Q", "Wärmeleistung Heizkreis", "Q̇_H", Q_(m_h * sw_z.cp * (tz - trl), "kW"), "kW", 2)
        self.info("Der Erzeuger erhält den Rücklauf mit θ_RL in Höhe von V̇_E zurück. Für Brennwertnutzung "
                  "niedrige Rücklauftemperaturen anstreben.")

    def sketch_svg(self, raw) -> str:
        s = Svg()
        if raw.get("modus", "mischung") == "beimischung":
            s.line(40, 70, 200, 70, "#c0392b", 4).line(200, 70, 320, 70, "#d68910", 4)
            s.line(40, 150, 320, 150, "#1f6fb2", 4).line(200, 150, 200, 78, "#1f6fb2", 3)
            s.polygon([(188, 58), (212, 58), (200, 78)], fill="#ffffff").polygon([(188, 82), (212, 82), (200, 62)],
                                                                                 fill="#ffffff")
            s.text(60, 60, "Erzeuger θ_VL,E", 11, "#c0392b", "start").text(320, 60, "θ_VL,Z", 11, "#d68910", "end")
            s.text(60, 170, "Rücklauf θ_RL", 11, "#1f6fb2", "start").text(206, 118, "Bypass", 11, MUTED, "start")
            s.text(180, 205, "Mischventil (Dreiwegeventil)", 11, INK)
        else:
            s.line(40, 60, 180, 110, "#c0392b", 4).line(40, 160, 180, 110, "#1f6fb2", 4)
            s.line(180, 110, 320, 110, "#d68910", 4)
            s.circle(180, 110, 8, fill="#ffffff")
            s.text(40, 50, "ṁ₁, θ₁", 12, "#c0392b", "start", True).text(40, 182, "ṁ₂, θ₂", 12, "#1f6fb2", "start", True)
            s.text(320, 100, "θ_M", 13, "#d68910", "end", True)
        return s.render()
