"""Feuchte Luft (h,x): Zustand, Mischung, Erwärmen und Kühlen mit Entfeuchtung."""

from __future__ import annotations

import numpy as np

from ingrechner.core import feuchte
from ingrechner.core.feuchte import Zustand
from ingrechner.core.model import Calculator, ChoiceField, NumberField
from ingrechner.core.svg import ACCENT, INK, MUTED, Svg
from ingrechner.core.units import Q_, fmt_num

MISCH = {"modus": ["mischung"]}
ERW = {"modus": ["erwaermen"]}
KUEHL = {"modus": ["kuehlen"]}
MIT_V = {"modus": ["mischung", "erwaermen", "kuehlen"]}


class FeuchteLuft(Calculator):
    id = "lu.feuchte"
    title = "Feuchte Luft (h,x)"
    category = "Lüftung / RLT"
    description = (
        "Zustandsgrößen feuchter Luft nach Mollier (Wassergehalt, Enthalpie, Taupunkt, Dichte) und die "
        "Luftbehandlung: Mischung zweier Luftströme, Erwärmen und Kühlen mit Entfeuchtung (Kühlerleistung, "
        "Kondensatmenge) – mit Luftdruck aus der Aufstellhöhe."
    )
    norm = "x = 0,622·p_D/(p − p_D); h = 1,006·θ + x·(2501 + 1,86·θ); p_s nach DIN 4108-3 (Magnus)"
    keywords = ("feuchte luft", "mollier", "hx", "h,x", "taupunkt", "relative feuchte", "wassergehalt", "enthalpie",
                "mischluft", "kühler", "entfeuchtung", "kondensat", "erhitzer", "lüftung", "rlt", "psychrometrie")

    fields = [
        ChoiceField("modus", "Aufgabe", [("zustand", "Zustand berechnen"), ("mischung", "Mischung zweier Ströme"),
                                         ("erwaermen", "Erwärmen (Lufterhitzer)"),
                                         ("kuehlen", "Kühlen / Entfeuchten (Luftkühler)")], "kuehlen"),
        NumberField("t1", "Temperatur Zustand 1", "θ₁", "degC", 32, min=-40, max=100, decimals=1),
        NumberField("phi1", "Relative Feuchte Zustand 1", "φ₁", "percent", 40, min=0, max=100, decimals=1),
        NumberField("V1", "Volumenstrom Zustand 1", "V̇₁", "m**3/hour", 4000, min=0, decimals=0, visible_if=MIT_V),
        NumberField("t2", "Temperatur Zustand 2", "θ₂", "degC", 24, min=-40, max=100, decimals=1, visible_if=MISCH),
        NumberField("phi2", "Relative Feuchte Zustand 2", "φ₂", "percent", 50, min=0, max=100, decimals=1,
                    visible_if=MISCH),
        NumberField("V2", "Volumenstrom Zustand 2", "V̇₂", "m**3/hour", 2000, min=0, min_inclusive=True, decimals=0,
                    visible_if=MISCH),
        NumberField("th", "Austrittstemperatur Erhitzer", "θ_aus", "degC", 40, min=-40, max=100, decimals=1,
                    visible_if=ERW),
        NumberField("tz", "Austrittstemperatur Kühler", "θ_aus", "degC", 16, min=-40, max=100, decimals=1,
                    visible_if=KUEHL),
        NumberField("tk", "Kühlflächentemperatur (mittlere)", "θ_K", "degC", 10, min=-10, max=40, decimals=1,
                    visible_if=KUEHL, tooltip="Kaltwasser 6/12 °C → θ_K ≈ 9–11 °C; liegt sie unter dem Taupunkt, "
                                              "wird entfeuchtet"),
        NumberField("hoehe", "Aufstellhöhe über NN", "h_NN", "m", 100, min=-400, max=4000, min_inclusive=True,
                    decimals=0),
    ]

    def _zeile(self, name: str, z: Zustand) -> str:
        return (f"{name}: θ = {fmt_num(z.theta, 1)} °C, φ = {fmt_num(z.phi * 100, 1)} %, x = {fmt_num(z.x * 1000, 2)} g/kg, "
                f"h = {fmt_num(z.h, 2)} kJ/kg")

    def compute(self, inp) -> None:
        p = feuchte.hoehe_druck(inp["hoehe"].to("m").magnitude)
        t1 = inp["t1"].to("degC").magnitude
        z1 = Zustand(t1, inp["phi1"].to("percent").magnitude / 100, p=p)
        self.step("Zustand 1", "p_s(θ) (Magnus); x = 0,622·φ·p_s/(p − φ·p_s); h = 1,006θ + x(2501 + 1,86θ)",
                  f"p = {fmt_num(p / 100, 1)} hPa, p_s = {fmt_num(feuchte.p_saett(t1), 1)} Pa", self._zeile("1", z1))
        modus = inp["modus"]
        self.result("x1", "Wassergehalt", "x₁", Q_(z1.x * 1000, "g/kg"), "g/kg", 2, highlight=modus == "zustand")
        self.result("h1", "Enthalpie", "h₁", Q_(z1.h, "kJ/kg"), "kJ/kg", 2, highlight=modus == "zustand")
        self.result("tau1", "Taupunkt", "θ_τ,1", Q_(z1.tau, "degC"), "degC", 1, highlight=modus == "zustand")
        self.result("rho1", "Dichte feuchte Luft", "ρ₁", Q_(z1.rho, "kg/m**3"), "kg/m**3", 3)
        if modus == "zustand":
            self.result("pd", "Dampfpartialdruck", "p_D", Q_(z1.pd, "Pa"), "Pa", 0)
            self.result("xs", "Sättigungswassergehalt", "x_s", Q_(feuchte.x_saett(t1, p) * 1000, "g/kg"), "g/kg", 2)
            return
        m1 = inp["V1"].to("m**3/s").magnitude * z1.rho / (1 + z1.x)     # kg trockene Luft / s
        if modus == "mischung":
            z2 = Zustand(inp["t2"].to("degC").magnitude, inp["phi2"].to("percent").magnitude / 100, p=p)
            m2 = inp["V2"].to("m**3/s").magnitude * z2.rho / (1 + z2.x)
            if m1 + m2 <= 0:
                raise ValueError("Mindestens ein Volumenstrom muss größer als null sein.")
            x = (m1 * z1.x + m2 * z2.x) / (m1 + m2)
            h = (m1 * z1.h + m2 * z2.h) / (m1 + m2)
            t = feuchte.theta_aus_h(h, x)
            if x > feuchte.x_saett(t, p):
                self.warn("Die Mischung liegt im Nebelgebiet (übersättigt) – Kondensat/Nebel möglich.")
                zm = None
            else:
                zm = Zustand(t, x=x, p=p)
            self.step("Zustand 2", "", "", self._zeile("2", z2))
            self.step("Mischung", "x_M = Σṁ·x / Σṁ;  h_M = Σṁ·h / Σṁ",
                      f"ṁ₁ = {fmt_num(m1 * 3600, 0)} kg/h, ṁ₂ = {fmt_num(m2 * 3600, 0)} kg/h",
                      f"θ_M = {fmt_num(t, 2)} °C, x_M = {fmt_num(x * 1000, 2)} g/kg, h_M = {fmt_num(h, 2)} kJ/kg")
            self.result("tm", "Mischtemperatur", "θ_M", Q_(t, "degC"), "degC", 2, highlight=True)
            self.result("xm", "Wassergehalt Mischung", "x_M", Q_(x * 1000, "g/kg"), "g/kg", 2, highlight=True)
            if zm is not None:
                self.result("phim", "Relative Feuchte Mischung", "φ_M", Q_(zm.phi * 100, "percent"), "percent", 1,
                            highlight=True)
            self.result("hm", "Enthalpie Mischung", "h_M", Q_(h, "kJ/kg"), "kJ/kg", 2)
            return

        tz = inp["th" if modus == "erwaermen" else "tz"].to("degC").magnitude
        if modus == "erwaermen":
            if tz < t1:
                raise ValueError("Beim Erwärmen muss die Austrittstemperatur über der Eintrittstemperatur liegen.")
            z2 = Zustand(tz, x=z1.x, p=p)
            Q = m1 * (z2.h - z1.h)
            kond = 0.0
            self.step("Erwärmen (x = konst.)", "Q̇ = ṁ_L · (h₂ − h₁)", self._zeile("2", z2), f"{fmt_num(Q, 2)} kW")
        else:
            if tz > t1:
                raise ValueError("Beim Kühlen muss die Austrittstemperatur unter der Eintrittstemperatur liegen.")
            tk = inp["tk"].to("degC").magnitude
            if tk < z1.tau and tz > tk:
                # Gerade zum Kühlflächenpunkt (θ_K, x_s(θ_K)) im h,x-Diagramm
                xk = feuchte.x_saett(tk, p)
                x2 = xk + (z1.x - xk) * (tz - tk) / (t1 - tk)
                x2 = min(x2, feuchte.x_saett(tz, p))
                self.step("Kühlen mit Entfeuchtung", "Zustandsänderung auf der Geraden zum Kühlflächenpunkt (θ_K, x_s)",
                          f"θ_K = {fmt_num(tk, 1)} °C < θ_τ = {fmt_num(z1.tau, 1)} °C, x_s(θ_K) = {fmt_num(xk * 1000, 2)} g/kg",
                          f"x₂ = {fmt_num(x2 * 1000, 2)} g/kg")
            elif tz < z1.tau:
                x2 = feuchte.x_saett(tz, p)
                self.step("Kühlen unter den Taupunkt", "x₂ = x_s(θ_aus)", "", f"x₂ = {fmt_num(x2 * 1000, 2)} g/kg")
            else:
                x2 = z1.x
                self.step("Trockenes Kühlen", "x = konst. (θ_K ≥ θ_τ)", f"θ_τ = {fmt_num(z1.tau, 1)} °C", "")
            z2 = Zustand(tz, x=x2, p=p)
            kond = m1 * (z1.x - z2.x)
            h_w = 4.19 * tk if tk > 0 else 0.0
            Q = m1 * (z1.h - z2.h) - kond * h_w
            self.step("Kühlerleistung", "Q̇ = ṁ_L · (h₁ − h₂) − ṁ_W · h_W", self._zeile("2", z2), f"{fmt_num(Q, 2)} kW")
        self.result("Q", "Leistung Erhitzer/Kühler", "Q̇", Q_(Q, "kW"), "kW", 2, highlight=True)
        self.result("phi2", "Relative Feuchte Austritt", "φ₂", Q_(z2.phi * 100, "percent"), "percent", 1,
                    highlight=True)
        self.result("x2", "Wassergehalt Austritt", "x₂", Q_(z2.x * 1000, "g/kg"), "g/kg", 2)
        self.result("h2", "Enthalpie Austritt", "h₂", Q_(z2.h, "kJ/kg"), "kJ/kg", 2)
        if modus == "kuehlen":
            self.result("kond", "Kondensat", "ṁ_W", Q_(kond * 3600, "kg/hour"), "kg/hour", 1, highlight=True)
            self.result("Qs", "davon sensibel", "Q̇_s", Q_(m1 * (feuchte.CP_L + feuchte.CP_D * z1.x) * (t1 - tz), "kW"),
                        "kW", 2)
            if z2.phi > 0.95:
                self.info("Austrittsluft nahezu gesättigt – Nachheizung bzw. Tropfenabscheider vorsehen.")
        if modus == "erwaermen" and z2.phi < 0.25:
            self.info(f"Relative Feuchte nach dem Erwärmen {fmt_num(z2.phi * 100, 0)} % – Befeuchtung prüfen.")

    def plot(self, fig, raw, result) -> bool:
        """Vereinfachtes h,x-Diagramm (θ über x mit Linien gleicher relativer Feuchte)."""
        if not result.ok:
            return False
        p = feuchte.hoehe_druck(float(raw["hoehe"]))
        ts = np.linspace(-10, 45, 120)
        ax = fig.subplots()
        for phi in (0.2, 0.4, 0.6, 0.8, 1.0):
            xs = [feuchte.x_aus_phi(t, phi, p) * 1000 for t in ts]
            ax.plot(xs, ts, color="#1f6fb2" if phi == 1 else "#9aa7b4", lw=1.6 if phi == 1 else 0.8)
            ax.annotate(f"{phi * 100:.0f} %", (xs[-25], ts[-25]), fontsize=7, color="#6b7b8c")
        t1, x1 = float(raw["t1"]), result.value("x1")
        ax.plot([x1], [t1], "o", color="#c0392b")
        ax.annotate("1", (x1, t1), xytext=(4, 4), textcoords="offset points")
        if raw.get("modus") in ("erwaermen", "kuehlen"):
            t2 = float(raw["th"] if raw.get("modus") == "erwaermen" else raw["tz"])
            ax.plot([x1, result.value("x2")], [t1, t2], "-o", color="#c0392b")
        if raw.get("modus") == "mischung":
            x2 = feuchte.x_aus_phi(float(raw["t2"]), float(raw["phi2"]) / 100, p) * 1000
            ax.plot([x1, x2], [t1, float(raw["t2"])], "--o", color="#6b7b8c")
            ax.plot([result.value("xm")], [result.value("tm")], "o", color="#27ae60")
        ax.set_xlim(0, 25)
        ax.set_ylim(-10, 45)
        ax.set_xlabel("Wassergehalt x  [g/kg]")
        ax.set_ylabel("Temperatur θ  [°C]")
        ax.set_title("h,x-Diagramm (vereinfacht)")
        ax.grid(True, alpha=0.3)
        return True

    def sketch_svg(self, raw) -> str:
        s = Svg()
        m = raw.get("modus", "kuehlen")
        s.rect(130, 70, 100, 80, fill="#eef3f8")
        label = {"zustand": "Luft", "mischung": "Mischkammer", "erwaermen": "Erhitzer", "kuehlen": "Kühler"}[m]
        s.text(180, 114, label, 12, INK, bold=True)
        s.arrow(30, 110, 128, 110, ACCENT).text(30, 100, "1: θ₁, φ₁", 10, INK, "start")
        s.arrow(232, 110, 330, 110, ACCENT).text(330, 100, "θ_aus", 10, INK, "end")
        if m == "mischung":
            s.arrow(180, 20, 180, 68, ACCENT).text(186, 30, "2: θ₂, φ₂", 10, INK, "start")
        if m == "kuehlen":
            s.arrow(180, 152, 180, 196, MUTED).text(186, 190, "Kondensat", 10, MUTED, "start")
        return s.render()
