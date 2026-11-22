"""Auslegung eines Wärmetauschers (Wärmeübertragers) über die mittlere logarithmische Temperaturdifferenz."""

from __future__ import annotations

import math

import numpy as np

from ingrechner.core.model import Calculator, ChoiceField, NumberField
from ingrechner.core.medien import waerme_auswahl
from ingrechner.core.medien import waermestoff as stoffwerte
from ingrechner.core.svg import INK, MUTED, Svg
from ingrechner.core.units import Q_, fmt_num, fmt_q

K_RICHTWERTE = (
    "Richtwerte k [W/(m²·K)] (VDI-Wärmeatlas, Herstellerangaben haben Vorrang):\n"
    "Plattenwärmeübertrager Wasser/Wasser 2500–7000\n"
    "Rohrbündel Wasser/Wasser 800–1700\n"
    "Doppelrohr Wasser/Wasser 800–1500\n"
    "Rohrbündel Dampf/Wasser 1500–4000\n"
    "Lamellenrohr Luft/Wasser (luftseitig) 15–50\n"
    "Glattrohr Luft/Wasser 10–40"
)


def lmtd(dta: float, dtb: float) -> float:
    """Mittlere logarithmische Temperaturdifferenz."""
    if abs(dta - dtb) < 1e-9:
        return dta
    return (dta - dtb) / math.log(dta / dtb)


class Waermetauscher(Calculator):
    id = "hz.waermetauscher"
    title = "Wärmetauscher-Auslegung"
    category = "Heizung / Wärme"
    description = (
        "Energiebilanz beider Seiten, mittlere logarithmische Temperaturdifferenz und erforderliche "
        "Übertragungsfläche A = Q̇ / (k · ΔT_m) für Gegen- oder Gleichstrom. Der Wärmedurchgangs-"
        "koeffizient k wird vorgegeben (Hersteller- oder Richtwert)."
    )
    norm = "VDI-Wärmeatlas, Abschnitt C (Wärmeübertrager); Stoffwerte VDI-Wärmeatlas"
    keywords = ("wärmetauscher", "wärmeübertrager", "plattenwärmetauscher", "lmtd", "logarithmische",
                "temperaturdifferenz", "fläche", "k-wert", "systemtrennung", "fernwärme")

    fields = [
        ChoiceField("strom", "Stromführung", [("gegen", "Gegenstrom"), ("gleich", "Gleichstrom")], "gegen"),
        ChoiceField("vorgabe", "Leistung aus", [("leistung", "Vorgabe Wärmeleistung"),
                                                ("primaer", "Volumenstrom der Primärseite")], "leistung"),
        NumberField("Q", "Wärmeleistung", "Q̇", "kW", 50, min=0, decimals=2, visible_if={"vorgabe": ["leistung"]}),
        ChoiceField("med1", "Primärseite (warm): Medium", waerme_auswahl(), "wasser"),
        NumberField("t1e", "Primär Eintritt", "θ_1,ein", "degC", 80, min=-20, max=200, min_inclusive=True,
                    decimals=1),
        NumberField("t1a", "Primär Austritt", "θ_1,aus", "degC", 60, min=-20, max=200, min_inclusive=True,
                    decimals=1),
        NumberField("V1", "Primär Volumenstrom", "V̇₁", "m**3/hour", 2.2, min=0, decimals=3,
                    visible_if={"vorgabe": ["primaer"]}),
        ChoiceField("med2", "Sekundärseite (kalt): Medium", waerme_auswahl(), "wasser"),
        NumberField("t2e", "Sekundär Eintritt", "θ_2,ein", "degC", 40, min=-20, max=200, min_inclusive=True,
                    decimals=1),
        ChoiceField("sek", "Sekundärseite vorgegeben über", [("austritt", "Austrittstemperatur"),
                                                             ("strom", "Volumenstrom")], "austritt"),
        NumberField("t2a", "Sekundär Austritt", "θ_2,aus", "degC", 55, min=-20, max=200, min_inclusive=True,
                    decimals=1, visible_if={"sek": ["austritt"]}),
        NumberField("V2", "Sekundär Volumenstrom", "V̇₂", "m**3/hour", 3.0, min=0, decimals=3,
                    visible_if={"sek": ["strom"]}),
        NumberField("k", "k-Wert (Wärmedurchgang)", "k", "W/(m**2*K)", 4000, min=0, decimals=0,
                    tooltip=K_RICHTWERTE),
        NumberField("z", "Flächenzuschlag", "z", "percent", 10, min=0, min_inclusive=True, max=200, decimals=0,
                    tooltip="Reserve für Verschmutzung (Fouling) und Toleranzen, üblich 10–20 %"),
    ]

    def compute(self, inp) -> None:
        t1e, t1a = inp["t1e"].to("degC").magnitude, inp["t1a"].to("degC").magnitude
        t2e = inp["t2e"].to("degC").magnitude
        if t1e <= t1a:
            raise ValueError("Primärseite: Die Eintrittstemperatur muss über der Austrittstemperatur liegen.")
        if t1e <= t2e:
            raise ValueError("Die Primärseite muss wärmer als der Sekundäreintritt sein.")

        sw1 = stoffwerte(inp["med1"], (t1e + t1a) / 2)
        C1v = Q_(sw1.rho, "kg/m**3") * Q_(sw1.cp, "kJ/(kg*K)")
        if inp["vorgabe"] == "primaer":
            V1 = inp["V1"]
            Q = (V1 * C1v * Q_(t1e - t1a, "K")).to("kW")
            self.step("Wärmeleistung (Primärseite)", "Q̇ = V̇₁ · ρ₁ · c_p1 · (θ_1,ein − θ_1,aus)",
                      f"Q̇ = {fmt_q(V1, 'm**3/s', 6)} · {fmt_num(sw1.rho, 1)} · {fmt_num(sw1.cp, 3)} · "
                      f"{fmt_num(t1e - t1a, 1)}", fmt_q(Q, "kW", 2))
        else:
            Q = inp["Q"].to("kW")
            V1 = (Q / (C1v * Q_(t1e - t1a, "K"))).to("m**3/hour")
            self.step("Volumenstrom Primärseite", "V̇₁ = Q̇ / (ρ₁ · c_p1 · (θ_1,ein − θ_1,aus))",
                      f"V̇₁ = {fmt_q(Q, 'kW', 2)} / ({fmt_num(sw1.rho, 1)} · {fmt_num(sw1.cp, 3)} · "
                      f"{fmt_num(t1e - t1a, 1)})", fmt_q(V1, "m**3/hour", 3))

        if inp["sek"] == "austritt":
            t2a = inp["t2a"].to("degC").magnitude
            if t2a <= t2e:
                raise ValueError("Sekundärseite: Die Austrittstemperatur muss über der Eintrittstemperatur liegen.")
            sw2 = stoffwerte(inp["med2"], (t2e + t2a) / 2)
            V2 = (Q / (Q_(sw2.rho, "kg/m**3") * Q_(sw2.cp, "kJ/(kg*K)") * Q_(t2a - t2e, "K"))).to("m**3/hour")
            self.step("Volumenstrom Sekundärseite", "V̇₂ = Q̇ / (ρ₂ · c_p2 · (θ_2,aus − θ_2,ein))",
                      f"V̇₂ = {fmt_q(Q, 'kW', 2)} / ({fmt_num(sw2.rho, 1)} · {fmt_num(sw2.cp, 3)} · "
                      f"{fmt_num(t2a - t2e, 1)})", fmt_q(V2, "m**3/hour", 3))
        else:
            V2 = inp["V2"]
            t2a = t2e
            for _ in range(6):
                sw2 = stoffwerte(inp["med2"], (t2e + t2a) / 2)
                t2a = t2e + (Q / (V2 * Q_(sw2.rho, "kg/m**3") * Q_(sw2.cp, "kJ/(kg*K)"))).to("K").magnitude
            self.step("Sekundär-Austrittstemperatur", "θ_2,aus = θ_2,ein + Q̇ / (V̇₂ · ρ₂ · c_p2)",
                      f"θ_2,aus = {fmt_num(t2e, 1)} °C + {fmt_q(Q, 'kW', 2)} / ({fmt_q(V2, 'm**3/s', 6)} · "
                      f"{fmt_num(sw2.rho, 1)} · {fmt_num(sw2.cp, 3)})", f"{fmt_num(t2a, 2)} °C")

        if inp["strom"] == "gegen":
            dta, dtb = t1e - t2a, t1a - t2e
            f_a, f_b = "ΔT_A = θ_1,ein − θ_2,aus", "ΔT_B = θ_1,aus − θ_2,ein"
        else:
            dta, dtb = t1e - t2e, t1a - t2a
            f_a, f_b = "ΔT_A = θ_1,ein − θ_2,ein", "ΔT_B = θ_1,aus − θ_2,aus"
        self.step("Temperaturdifferenzen an den Enden", f"{f_a};  {f_b}", "",
                  f"ΔT_A = {fmt_num(dta, 2)} K, ΔT_B = {fmt_num(dtb, 2)} K")
        if dta <= 0 or dtb <= 0:
            hint = " – mit Gegenstrom versuchen" if inp["strom"] == "gleich" else ""
            raise ValueError(f"Temperaturkreuzung: Mit diesen Temperaturen ist keine Wärmeübertragung möglich "
                             f"(ΔT_A = {fmt_num(dta, 1)} K, ΔT_B = {fmt_num(dtb, 1)} K){hint}.")
        dtm = lmtd(dta, dtb)
        self.step("Mittlere logarithmische Temperaturdifferenz", "ΔT_m = (ΔT_A − ΔT_B) / ln(ΔT_A / ΔT_B)",
                  f"ΔT_m = ({fmt_num(dta, 2)} − {fmt_num(dtb, 2)}) / ln({fmt_num(dta, 2)} / {fmt_num(dtb, 2)})",
                  f"{fmt_num(dtm, 3)} K")
        k = inp["k"]
        A = (Q / (k * Q_(dtm, "K"))).to("m**2")
        z = inp["z"].to("").magnitude
        A_z = A * (1 + z)
        self.step("Erforderliche Fläche", "A = Q̇ / (k · ΔT_m)",
                  f"A = {fmt_q(Q, 'W', 0)} / ({fmt_q(k, 'W/(m**2*K)', 0)} · {fmt_num(dtm, 3)} K)", fmt_q(A, "m**2", 3))
        self.step("Mit Zuschlag", "A_ges = A · (1 + z)", f"A_ges = {fmt_q(A, 'm**2', 3)} · (1 + {fmt_num(z, 2)})",
                  fmt_q(A_z, "m**2", 3))

        C1 = (V1 * C1v).to("W/K").magnitude
        C2 = (V2 * Q_(sw2.rho, "kg/m**3") * Q_(sw2.cp, "kJ/(kg*K)")).to("W/K").magnitude
        self.result("A", "Erforderliche Fläche", "A", A, "m**2", 3, highlight=True)
        self.result("Az", "Fläche mit Zuschlag", "A_ges", A_z, "m**2", 3, highlight=True)
        self.result("dtm", "Mittlere log. Temperaturdifferenz", "ΔT_m", Q_(dtm, "K"), "K", 3, highlight=True)
        self.result("Q", "Wärmeleistung", "Q̇", Q, "kW", 2)
        self.result("V1", "Volumenstrom primär", "V̇₁", V1, "m**3/hour", 3)
        self.result("V2", "Volumenstrom sekundär", "V̇₂", V2, "m**3/hour", 3)
        self.result("t2a", "Sekundär-Austrittstemperatur", "θ_2,aus", Q_(t2a, "degC"), "degC", 2)
        self.result("dta", "Temperaturdifferenz Ende A", "ΔT_A", Q_(dta, "K"), "K", 2)
        self.result("dtb", "Temperaturdifferenz Ende B", "ΔT_B", Q_(dtb, "K"), "K", 2)
        self.result("C1", "Wärmekapazitätsstrom primär", "Ċ₁", Q_(C1, "W/K"), "W/K", 0)
        self.result("C2", "Wärmekapazitätsstrom sekundär", "Ċ₂", Q_(C2, "W/K"), "W/K", 0)

        if min(dta, dtb) < 3:
            self.warn(f"Sehr kleine Grädigkeit ({fmt_num(min(dta, dtb), 1)} K): große Fläche und empfindlich "
                      "gegenüber Abweichungen – Auslegung mit dem Hersteller abstimmen.")
        if inp["strom"] == "gegen" and t2a > t1a:
            self.info("Temperaturübergriff (θ_2,aus > θ_1,aus) – nur im Gegenstrom möglich.")
        if (inp["med1"] == "luft") != (inp["med2"] == "luft"):
            self.info("Luft/Wasser: k ist auf die luftseitige (berippte) Fläche zu beziehen.")
        self.info("k ist eine Vorgabe – Strömungsgeschwindigkeiten, Druckverluste und Verschmutzung bestimmen "
                  "den tatsächlichen Wert. Herstellerauslegung hat Vorrang.")

    def plot(self, fig, raw, result) -> bool:
        if not result.ok:
            return False
        t1e = float(raw["t1e"])
        t2e = float(raw["t2e"])
        t2a = result.value("t2a")
        Q = result.value("Q") * 1000
        C1, C2 = result.value("C1"), result.value("C2")
        k = float(raw["k"])
        qs = np.linspace(0, Q, 400)
        th1 = t1e - qs / C1
        th2 = t2a - qs / C2 if raw["strom"] == "gegen" else t2e + qs / C2
        dA = np.diff(qs) / (k * (th1[:-1] + th1[1:] - th2[:-1] - th2[1:]) / 2)
        A = np.concatenate([[0], np.cumsum(dA)])
        x = A / A[-1] * 100
        ax = fig.subplots()
        ax.plot(x, th1, color="#c0392b", lw=2, label="Primär (warm)")
        ax.plot(x, th2, color="#1f6fb2", lw=2, label="Sekundär (kalt)")
        ax.fill_between(x, th2, th1, color="#dce6f1", alpha=0.6)
        ax.set_xlabel("Anteil der Übertragungsfläche  [%]")
        ax.set_ylabel("Temperatur  [°C]")
        ax.set_title("Temperaturverlauf " + ("Gegenstrom" if raw["strom"] == "gegen" else "Gleichstrom"))
        ax.grid(True, alpha=0.3)
        ax.legend(loc="best")
        return True

    def sketch_svg(self, raw) -> str:
        s = Svg()
        s.rect(90, 60, 180, 100, fill="#ffffff")
        for x in range(100, 270, 14):
            s.line(x, 64, x, 156, MUTED, 0.8)
        s.arrow(20, 80, 88, 80, "#c0392b").arrow(272, 80, 340, 80, "#c0392b")
        s.text(40, 72, "θ_1,ein", 11, "#c0392b").text(310, 72, "θ_1,aus", 11, "#c0392b")
        if raw.get("strom", "gegen") == "gegen":
            s.arrow(340, 140, 272, 140, "#1f6fb2").arrow(88, 140, 20, 140, "#1f6fb2")
            s.text(310, 158, "θ_2,ein", 11, "#1f6fb2").text(48, 158, "θ_2,aus", 11, "#1f6fb2")
            label = "Gegenstrom"
        else:
            s.arrow(20, 140, 88, 140, "#1f6fb2").arrow(272, 140, 340, 140, "#1f6fb2")
            s.text(40, 158, "θ_2,ein", 11, "#1f6fb2").text(310, 158, "θ_2,aus", 11, "#1f6fb2")
            label = "Gleichstrom"
        s.text(180, 115, "A, k", 14, INK, italic=True)
        s.text(180, 195, label, 12, MUTED)
        return s.render()
