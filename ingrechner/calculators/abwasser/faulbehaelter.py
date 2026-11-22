"""Faulbehälter: Wärmebedarf für Schlammaufheizung und Behälterverluste, Deckung durch Klärgas."""

from __future__ import annotations

import math

import numpy as np

from ingrechner.core import medien
from ingrechner.core.model import Calculator, ChoiceField, NumberField
from ingrechner.core.svg import ACCENT, INK, MUTED, Svg
from ingrechner.core.units import Q_, fmt_num

HI_CH4 = 9.97          # Heizwert Methan kWh/m³ (Normzustand)
GAS = {"gas": ["ja"]}


class Faulbehaelter(Calculator):
    id = "aw.faulbehaelter"
    title = "Faulbehälter – Wärmebedarf"
    category = "Abwasser / Klärwerk"
    description = (
        "Wärmebedarf eines beheizten Faulbehälters: Aufheizen des Rohschlamms auf Faultemperatur und "
        "Transmissionsverluste über Wand, Decke und Boden; Faulzeit, Jahreswärmemenge und optional die Deckung "
        "durch das Klärgas (BHKW-Abwärme oder Kessel)."
    )
    norm = "Q̇ = V̇_S·ρ·c_p·(θ_F − θ_RS) + Σ U·A·Δθ; Heizwert CH₄ 9,97 kWh/m³; vgl. DWA-M 368, DWA-A 216"
    keywords = ("faulbehälter", "faulturm", "faulung", "mesophil", "thermophil", "klärschlamm", "schlammheizung",
                "wärmebedarf", "klärgas", "bhkw", "faulzeit", "rohschlamm", "klärwerk")

    fields = [
        NumberField("QS", "Rohschlammmenge", "V̇_S", "m**3/day", 40, min=0, decimals=1),
        ChoiceField("schlamm", "Rohschlamm", [(m.id, m.name) for m in medien.MEDIEN if m.id.startswith("klaerschlamm")],
                    "klaerschlamm_5"),
        NumberField("tRS", "Rohschlammtemperatur", "θ_RS", "degC", 12, min=5, max=40, min_inclusive=True, decimals=1),
        NumberField("tF", "Faultemperatur", "θ_F", "degC", 37, min=10, max=60, decimals=1,
                    tooltip="mesophil 35–38 °C, thermophil 50–55 °C"),
        NumberField("D", "Innendurchmesser Behälter", "D", "m", 14, min=0, decimals=2),
        NumberField("H", "Zylindrische Höhe", "H", "m", 13, min=0, decimals=2,
                    tooltip="Konus/Kegel vereinfacht vernachlässigt (Volumen und Fläche etwas größer)"),
        NumberField("Uw", "U-Wert Wand", "U_W", "W/(m**2*K)", 0.40, min=0, decimals=3),
        NumberField("Ud", "U-Wert Decke", "U_D", "W/(m**2*K)", 0.40, min=0, decimals=3),
        NumberField("Ub", "U-Wert Boden (gegen Erdreich)", "U_B", "W/(m**2*K)", 0.60, min=0, decimals=3),
        NumberField("ta", "Norm-Außentemperatur", "θ_a", "degC", -12, min=-30, max=20, min_inclusive=True,
                    decimals=1),
        NumberField("tam", "Mittlere Jahres-Außentemperatur", "θ_a,m", "degC", 9, min=-10, max=25, decimals=1),
        NumberField("tE", "Erdreichtemperatur", "θ_E", "degC", 10, min=0, max=25, min_inclusive=True, decimals=1),
        NumberField("zus", "Zuschlag Leitungen / Wärmetauscher", "z", "percent", 10, min=0, min_inclusive=True,
                    max=50, decimals=0),
        ChoiceField("gas", "Deckung durch Klärgas", [("nein", "nicht prüfen"), ("ja", "prüfen")], "ja"),
        NumberField("Vg", "Klärgasanfall", "V̇_G", "m**3/day", 900, min=0, decimals=0, visible_if=GAS,
                    tooltip="Normvolumen; Richtwert 20–25 l je Einwohner und Tag"),
        NumberField("ch4", "Methangehalt", "y_CH₄", "percent", 63, min=30, max=80, decimals=1, visible_if=GAS),
        NumberField("eta", "Nutzbarer Wärmeanteil", "η_th", "percent", 45, min=1, max=100, decimals=0, visible_if=GAS,
                    tooltip="BHKW thermisch ca. 40–50 %, Heizkessel ca. 85–90 %"),
    ]

    def _bedarf(self, inp, ta: float) -> tuple[float, float, float, dict]:
        QS = inp["QS"].to("m**3/s").magnitude
        tRS, tF = inp["tRS"].to("degC").magnitude, inp["tF"].to("degC").magnitude
        z = medien.medium(inp["schlamm"]).zustand((tRS + tF) / 2)
        Q_auf = QS * z.rho * z.cp * 1000 * (tF - tRS)
        D, H = inp["D"].to("m").magnitude, inp["H"].to("m").magnitude
        A_w, A_d = math.pi * D * H, math.pi * D**2 / 4
        tE = inp["tE"].to("degC").magnitude
        verl = {"Wand": inp["Uw"].to("W/(m**2*K)").magnitude * A_w * (tF - ta),
                "Decke": inp["Ud"].to("W/(m**2*K)").magnitude * A_d * (tF - ta),
                "Boden": inp["Ub"].to("W/(m**2*K)").magnitude * A_d * (tF - tE)}
        f = 1 + inp["zus"].to("percent").magnitude / 100
        return Q_auf, sum(verl.values()), f, {"z": z, "A_w": A_w, "A_d": A_d, "verl": verl}

    def compute(self, inp) -> None:
        tRS, tF = inp["tRS"].to("degC").magnitude, inp["tF"].to("degC").magnitude
        if tF <= tRS:
            raise ValueError("Die Faultemperatur muss über der Rohschlammtemperatur liegen.")
        ta = inp["ta"].to("degC").magnitude
        Q_auf, Q_tr, f, d = self._bedarf(inp, ta)
        z = d["z"]
        QS = inp["QS"].to("m**3/day").magnitude
        self.step("Stoffwerte Schlamm", "ρ, c_p bei mittlerer Temperatur", medien.medium(inp["schlamm"]).name,
                  f"ρ = {fmt_num(z.rho, 1)} kg/m³, c_p = {fmt_num(z.cp, 3)} kJ/(kg·K)")
        self.step("Schlammaufheizung", "Q̇_A = V̇_S · ρ · c_p · (θ_F − θ_RS)",
                  f"Q̇_A = {fmt_num(QS, 1)} m³/d · {fmt_num(z.rho, 1)} · {fmt_num(z.cp, 3)} · "
                  f"{fmt_num(tF - tRS, 1)} K / 86 400", f"{fmt_num(Q_auf / 1000, 1)} kW")
        v = d["verl"]
        self.step("Transmissionsverluste", "Q̇_T = U_W·A_W·(θ_F − θ_a) + U_D·A_D·(θ_F − θ_a) + U_B·A_B·(θ_F − θ_E)",
                  f"A_W = {fmt_num(d['A_w'], 1)} m², A_D = A_B = {fmt_num(d['A_d'], 1)} m²; "
                  + ", ".join(f"{k} {fmt_num(w / 1000, 2)} kW" for k, w in v.items()),
                  f"{fmt_num(Q_tr / 1000, 2)} kW")
        Q = (Q_auf + Q_tr) * f
        self.step("Wärmebedarf (Auslegung)", "Q̇ = (Q̇_A + Q̇_T) · (1 + z)",
                  f"Q̇ = ({fmt_num(Q_auf / 1000, 1)} + {fmt_num(Q_tr / 1000, 2)}) kW · {fmt_num(f, 2)}",
                  f"{fmt_num(Q / 1000, 1)} kW")
        Qa_m, Qt_m, _, _ = self._bedarf(inp, inp["tam"].to("degC").magnitude)
        E = (Qa_m + Qt_m) * f / 1000 * 8760 / 1000
        self.step("Jahreswärmebedarf", "E = Q̇(θ_a,m) · 8760 h", f"θ_a,m = {fmt_num(inp['tam'].to('degC').magnitude, 1)} °C",
                  f"{fmt_num(E, 0)} MWh/a")
        Vb = math.pi * inp["D"].to("m").magnitude ** 2 / 4 * inp["H"].to("m").magnitude
        tF_d = Vb / QS if QS else float("inf")
        self.step("Faulzeit", "t_F = V / V̇_S", f"V = {fmt_num(Vb, 0)} m³", f"{fmt_num(tF_d, 1)} d")

        self.result("Q", "Wärmebedarf (Auslegung)", "Q̇", Q_(Q, "W"), "kW", 1, highlight=True)
        self.result("Qa", "davon Schlammaufheizung", "Q̇_A", Q_(Q_auf, "W"), "kW", 1)
        self.result("Qt", "davon Transmission", "Q̇_T", Q_(Q_tr, "W"), "kW", 1)
        self.result("E", "Jahreswärmebedarf", "E", Q_(E, "MW*h/year"), "MW*h/year", 0, highlight=True)
        self.result("V", "Behältervolumen (Zylinder)", "V", Q_(Vb, "m**3"), "m**3", 0)
        self.result("tF", "Faulzeit", "t_F", Q_(tF_d, "day"), "day", 1, highlight=True)

        if inp["gas"] == "ja":
            Vg = inp["Vg"].to("m**3/day").magnitude
            ch4 = inp["ch4"].to("percent").magnitude / 100
            eta = inp["eta"].to("percent").magnitude / 100
            Hi = HI_CH4 * ch4
            Q_gas = Vg * Hi * eta / 24 * 1000          # W
            self.step("Wärmeangebot aus Klärgas", "Q̇_G = V̇_G · H_i · η_th;  H_i = y_CH₄ · 9,97 kWh/m³",
                      f"Q̇_G = {fmt_num(Vg, 0)} m³/d · {fmt_num(Hi, 2)} kWh/m³ · {fmt_num(eta, 2)} / 24 h",
                      f"{fmt_num(Q_gas / 1000, 1)} kW")
            self.result("Qg", "Wärmeangebot Klärgas", "Q̇_G", Q_(Q_gas, "W"), "kW", 1)
            self.result("dg", "Deckungsgrad (Auslegung)", "Q̇_G/Q̇", Q_(Q_gas / Q * 100, "percent"), "percent", 0,
                        highlight=True)
            if Q_gas < Q:
                self.warn(f"Das Klärgas deckt bei Norm-Außentemperatur nur {fmt_num(Q_gas / Q * 100, 0)} % des "
                          "Wärmebedarfs – Zusatzheizung bzw. Erdgas/Heizöl als Reserve vorsehen.")
            else:
                self.info(f"Wärmebedarf durch Klärgas gedeckt ({fmt_num(Q_gas / Q * 100, 0)} %).")
        if tF < 30:
            self.info("Faultemperatur unter dem mesophilen Bereich (35–38 °C) – geringere Abbauleistung.")
        if tF_d < 20 and tF < 45:
            self.warn(f"Faulzeit {fmt_num(tF_d, 1)} d < 20 d – für mesophile Faulung zu kurz (Stabilisierung).")
        self.info("Vereinfachte Geometrie (Zylinder ohne Konus); Wärmeverluste der Schlammleitungen und "
                  "Wärmetauscher über den Zuschlag.")

    def plot(self, fig, raw, result) -> bool:
        if not result.ok:
            return False
        inp = {}
        for f in self.fields:
            v = (self.defaults() | raw)[f.key]
            inp[f.key] = Q_(float(v), f.unit) if isinstance(f, NumberField) and f.unit else v
        tas = np.linspace(-20, 25, 60)
        vals = [self._bedarf(inp, t) for t in tas]
        qa = np.array([v[0] for v in vals]) * vals[0][2] / 1000
        qt = np.array([v[1] for v in vals]) * vals[0][2] / 1000
        ax = fig.subplots()
        ax.stackplot(tas, qa, qt, colors=["#1f6fb2", "#e59866"], labels=["Schlammaufheizung", "Transmission"],
                     alpha=0.85)
        if raw.get("gas", "ja") == "ja":
            ax.axhline(result.value("Qg"), color="#27ae60", lw=2, ls="--", label="Wärmeangebot Klärgas")
        ax.axvline(float(raw["ta"]), color="#2b3a4a", lw=0.8, ls=":")
        ax.set_xlabel("Außentemperatur θ_a  [°C]")
        ax.set_ylabel("Wärmebedarf  [kW]")
        ax.set_title("Wärmebedarf des Faulbehälters")
        ax.grid(True, alpha=0.3)
        ax.legend(loc="lower left", fontsize=8)
        return True

    def sketch_svg(self, raw) -> str:
        s = Svg()
        s.rect(120, 40, 120, 140, fill="#e8dccb")
        s.polygon([(120, 180), (240, 180), (180, 210)], fill="#e8dccb")
        s.polygon([(120, 40), (240, 40), (180, 18)], fill="#d5c4ac")
        s.text(180, 115, "θ_F", 14, INK, italic=True)
        s.arrow(40, 150, 118, 150, "#8e6e43").text(40, 142, "Rohschlamm", 10, INK, "start")
        s.arrow(182, 16, 182, 2, "#27ae60", 2, 6).text(200, 12, "Klärgas", 10, "#27ae60", "start")
        for y in (70, 110):
            s.arrow(242, y, 290, y, "#c0392b", 1.6, 6)
        s.text(296, 94, "Verluste", 11, "#c0392b", "start")
        s.line(60, 205, 300, 205, MUTED, 1, "4 3").text(300, 200, "Erdreich", 9, MUTED, "end")
        s.arrow(40, 60, 118, 60, ACCENT).text(40, 52, "Heizung Q̇", 10, INK, "start")
        return s.render()
