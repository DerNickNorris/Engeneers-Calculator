"""Wärmeleistung, Volumenstrom oder Spreizung eines Heiz-/Kühlkreises; Wärmemenge über eine Dauer."""

from __future__ import annotations

import numpy as np

from ingrechner.core.model import Calculator, ChoiceField, NumberField
from ingrechner.core.stoffwerte import MEDIEN_AUSWAHL, stoffwerte
from ingrechner.core.svg import ACCENT, INK, Svg
from ingrechner.core.units import Q_, fmt_num, fmt_q

MIT_Q = {"modus": ["volumenstrom", "spreizung"]}
MIT_V = {"modus": ["leistung", "spreizung"]}
MIT_DT = {"modus": ["leistung", "volumenstrom"]}


class Waermemenge(Calculator):
    id = "hz.waermemenge"
    title = "Wärmemenge & Wärmeleistung"
    category = "Heizung / Wärme"
    description = (
        "Q̇ = ṁ · c_p · Δθ: Wärmeleistung, Volumenstrom oder Temperaturspreizung eines Heiz- oder "
        "Kühlkreises mit temperaturabhängigen Stoffwerten; optional Wärmemenge über eine Betriebsdauer."
    )
    norm = "Kalorische Grundgleichung; Stoffwerte nach VDI-Wärmeatlas"
    keywords = ("wärmemenge", "wärmeleistung", "spreizung", "volumenstrom", "massenstrom", "heizleistung",
                "kälteleistung", "kwh", "energie", "heizung")

    fields = [
        ChoiceField("modus", "Gesucht", [("leistung", "Wärmeleistung Q̇"), ("volumenstrom", "Volumenstrom V̇"),
                                         ("spreizung", "Temperaturspreizung Δθ")], "volumenstrom"),
        ChoiceField("medium", "Medium", MEDIEN_AUSWAHL, "wasser"),
        NumberField("tvl", "Vorlauf-/Eintrittstemperatur", "θ_VL", "degC", 70, min=-20, max=200,
                    min_inclusive=True, decimals=1),
        NumberField("Q", "Wärmeleistung", "Q̇", "kW", 20, min=0, decimals=3, visible_if=MIT_Q),
        NumberField("V", "Volumenstrom", "V̇", "m**3/hour", 0.86, min=0, decimals=4, visible_if=MIT_V),
        NumberField("dt", "Temperaturspreizung", "Δθ", "K", 20, min=0, decimals=2, visible_if=MIT_DT,
                    tooltip="Heizkörper 70/50 → 20 K, Fußbodenheizung 5–10 K, Kaltwasser 6/12 → 6 K"),
        NumberField("t", "Betriebsdauer (optional)", "t", "hour", 0, min=0, min_inclusive=True, decimals=1,
                    tooltip="Für die Wärmemenge Q = Q̇ · t; 0 = keine Wärmemenge berechnen"),
    ]

    def compute(self, inp) -> None:
        med, modus = inp["medium"], inp["modus"]
        tvl = inp["tvl"].to("degC").magnitude

        if modus == "spreizung":
            Q, V = inp["Q"], inp["V"]
            dt = 0.0
            for _ in range(5):   # Stoffwerte bei Mitteltemperatur (iterativ)
                sw = stoffwerte(med, tvl - dt / 2)
                dt = (Q / (V * Q_(sw.rho, "kg/m**3") * Q_(sw.cp, "kJ/(kg*K)"))).to("K").magnitude
            self.step("Temperaturspreizung", "Δθ = Q̇ / (V̇ · ρ · c_p)",
                      f"Δθ = {fmt_q(Q, 'kW', 3)} / ({fmt_q(V, 'm**3/hour', 4)} · {fmt_num(sw.rho, 1)} kg/m³ · "
                      f"{fmt_num(sw.cp, 3)} kJ/(kg·K))", f"{fmt_num(dt, 2)} K")
        else:
            dt = inp["dt"].to("K").magnitude
            sw = stoffwerte(med, tvl - dt / 2)
        self.step("Stoffwerte bei Mitteltemperatur", "θ_m = θ_VL − Δθ/2",
                  f"θ_m = {fmt_num(tvl, 1)} °C − {fmt_num(dt, 2)} K / 2 = {fmt_num(sw.theta, 1)} °C",
                  f"ρ = {fmt_num(sw.rho, 1)} kg/m³, c_p = {fmt_num(sw.cp, 3)} kJ/(kg·K)")
        rho, cp, DT = Q_(sw.rho, "kg/m**3"), Q_(sw.cp, "kJ/(kg*K)"), Q_(dt, "K")

        if modus == "leistung":
            V = inp["V"]
            Q = (V * rho * cp * DT).to("kW")
            self.step("Wärmeleistung", "Q̇ = V̇ · ρ · c_p · Δθ",
                      f"Q̇ = {fmt_q(V, 'm**3/s', 6)} · {fmt_num(sw.rho, 1)} kg/m³ · {fmt_num(sw.cp, 3)} kJ/(kg·K) · "
                      f"{fmt_num(dt, 2)} K", fmt_q(Q, "kW", 3))
        elif modus == "volumenstrom":
            Q = inp["Q"]
            V = (Q / (rho * cp * DT)).to("m**3/hour")
            self.step("Volumenstrom", "V̇ = Q̇ / (ρ · c_p · Δθ)",
                      f"V̇ = {fmt_q(Q, 'kW', 3)} / ({fmt_num(sw.rho, 1)} kg/m³ · {fmt_num(sw.cp, 3)} kJ/(kg·K) · "
                      f"{fmt_num(dt, 2)} K)", fmt_q(V, "m**3/hour", 4))
        m = (V * rho).to("kg/hour")
        self.step("Massenstrom", "ṁ = V̇ · ρ", f"ṁ = {fmt_q(V, 'm**3/hour', 4)} · {fmt_num(sw.rho, 1)} kg/m³",
                  fmt_q(m, "kg/hour", 1))
        trl = tvl - dt

        self.result("Q", "Wärmeleistung", "Q̇", Q, "kW", 3, highlight=modus == "leistung")
        self.result("V", "Volumenstrom", "V̇", V, "m**3/hour", 4, highlight=modus == "volumenstrom")
        self.result("Vl", "Volumenstrom", "V̇", V, "liter/hour", 1)
        self.result("m", "Massenstrom", "ṁ", m, "kg/hour", 1)
        self.result("dt", "Temperaturspreizung", "Δθ", DT, "K", 2, highlight=modus == "spreizung")
        self.result("trl", "Rücklauf-/Austrittstemperatur", "θ_RL", Q_(trl, "degC"), "degC", 1)
        t = inp["t"].to("hour").magnitude
        if t > 0:
            E = (Q * inp["t"]).to("kW*h")
            self.step("Wärmemenge", "Q = Q̇ · t", f"Q = {fmt_q(Q, 'kW', 3)} · {fmt_num(t, 1)} h", fmt_q(E, "kW*h", 2))
            self.result("E", "Wärmemenge", "Q", E, "kW*h", 2, highlight=True)

        if med == "wasser" and trl < 0:
            self.warn("Austrittstemperatur unter 0 °C – Frostgefahr bei reinem Wasser (Frostschutzmittel?).")
        if med == "luft":
            self.info("Luft: nur sensible Wärme (trockene Luft, 1 bar) – Kondensation/Feuchte nicht berücksichtigt.")
        if med == "wasser" and dt < 3:
            self.info("Kleine Spreizung (< 3 K) erfordert große Volumenströme – Pumpenleistung und "
                      "Rohrdimension prüfen.")

    def plot(self, fig, raw, result) -> bool:
        if not result.ok:
            return False
        ax = fig.subplots()
        dts = np.linspace(2, 40, 120)
        q, v, dt = result.value("Q"), result.value("V"), result.value("dt")
        if raw["modus"] == "leistung":
            ax.plot(dts, q / dt * dts, color="#1f6fb2", lw=2)
            ax.plot([dt], [q], "o", color="#c0392b")
            ax.set_ylabel("Wärmeleistung Q̇  [kW]")
            ax.set_title(f"Leistung bei V̇ = {fmt_num(v, 3)} m³/h")
        else:
            ax.plot(dts, v * dt / dts, color="#1f6fb2", lw=2)
            ax.plot([dt], [v], "o", color="#c0392b")
            ax.set_ylabel("Volumenstrom V̇  [m³/h]")
            ax.set_title(f"Volumenstrom bei Q̇ = {fmt_num(q, 2)} kW")
        ax.set_xlabel("Temperaturspreizung Δθ  [K]")
        ax.grid(True, alpha=0.3)
        return True

    def sketch_svg(self, raw) -> str:
        s = Svg()
        s.rect(30, 70, 70, 80, fill="#ffffff").text(65, 108, "Erzeuger", 11, INK)
        s.rect(260, 70, 70, 80, fill="#ffffff").text(295, 108, "Verbraucher", 11, INK)
        s.line(100, 85, 260, 85, "#c0392b", 4).line(100, 135, 260, 135, "#1f6fb2", 4)
        s.arrow(150, 70, 210, 70, "#c0392b").text(180, 62, "θ_VL", 12, "#c0392b", italic=True)
        s.arrow(210, 150, 150, 150, "#1f6fb2").text(180, 168, "θ_RL", 12, "#1f6fb2", italic=True)
        s.text(180, 114, "Q̇ = ṁ · c_p · Δθ", 12, ACCENT, italic=True)
        return s.render()
