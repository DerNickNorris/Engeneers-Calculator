"""Pumpensumpf: Nutzvolumen aus zulässigen Schaltspielen, Schaltpegel und Laufzeiten."""

from __future__ import annotations

import math

import numpy as np

from ingrechner.calculators.pumpen._pumpe import pumpe_svg
from ingrechner.core.model import Calculator, ChoiceField, NumberField
from ingrechner.core.svg import ACCENT, INK, MUTED, Svg
from ingrechner.core.units import Q_, fmt_num

RUND = {"form": ["rund"]}
RECHTECK = {"form": ["rechteck"]}


class Pumpensumpf(Calculator):
    id = "aw.pumpensumpf"
    title = "Pumpensumpf – Nutzvolumen"
    category = "Abwasser / Klärwerk"
    description = (
        "Erforderliches Nutzvolumen eines Pumpensumpfs aus Förderstrom und zulässigen Schaltspielen je Pumpe "
        "(ungünstigster Zufluss = halber Förderstrom), Wechselbetrieb mehrerer Pumpen, Pegelhub, Ein- und "
        "Ausschaltpegel, Lauf- und Stillstandszeiten sowie Aufenthaltszeit."
    )
    norm = "V_N = Q_P · T_min / 4 mit T_min = 3600 / (z · n); vgl. DWA-A 134, Herstellerangaben der Pumpen"
    keywords = ("pumpensumpf", "pumpwerk", "schaltspiele", "schalthäufigkeit", "nutzvolumen", "pegel",
                "einschaltpegel", "abwasser", "hebeanlage", "pumpenschacht", "wechselbetrieb", "tauchmotorpumpe")

    fields = [
        NumberField("QP", "Förderstrom einer Pumpe", "Q_P", "liter/second", 20, min=0, decimals=2,
                    tooltip="Förderstrom im Betriebspunkt (z. B. aus „Pumpenkennlinie & Betriebspunkt“)"),
        NumberField("z", "Zulässige Schaltspiele je Pumpe", "z", "1/hour", 10, min=0, decimals=1,
                    tooltip="Herstellerangabe; Tauchmotorpumpen kleiner Leistung ca. 10–15 /h, größere Motoren "
                            "6–10 /h"),
        NumberField("n", "Pumpen im Wechselbetrieb", "n", "", 2, min=1, max=6, min_inclusive=True, decimals=0,
                    tooltip="Pumpen, die sich beim Anlauf abwechseln (Reservepumpe mitgezählt, wenn sie im "
                            "Wechsel läuft) – jede Pumpe schaltet dann nur jedes n-te Mal"),
        NumberField("Qzu", "Spitzenzufluss", "Q_zu,max", "liter/second", 15, min=0, min_inclusive=True, decimals=2),
        NumberField("Qd", "Mittlerer Tageszufluss (optional)", "Q_d", "m**3/day", 0, min=0, min_inclusive=True,
                    decimals=1, tooltip="Für die mittlere Aufenthaltszeit im Sumpf; 0 = ohne"),
        ChoiceField("form", "Grundriss", [("rund", "rund"), ("rechteck", "rechteckig")], "rund"),
        NumberField("D", "Innendurchmesser", "D", "m", 2.0, min=0, decimals=2, visible_if=RUND),
        NumberField("a", "Länge", "a", "m", 2.5, min=0, decimals=2, visible_if=RECHTECK),
        NumberField("b", "Breite", "b", "m", 2.0, min=0, decimals=2, visible_if=RECHTECK),
        NumberField("hmin", "Ausschaltpegel über Sohle", "h_aus", "m", 0.6, min=0, min_inclusive=True, decimals=2,
                    tooltip="Mindestüberdeckung der Pumpe/des Motors nach Herstellerangabe"),
        NumberField("Vtot", "Totvolumen-Zuschlag (Einbauten)", "ΔV", "percent", 0, min=0, min_inclusive=True, max=50,
                    decimals=0, tooltip="Verdrängung durch Pumpen, Rohre, Schwimmer – vergrößert den Pegelhub"),
    ]

    def compute(self, inp) -> None:
        QP = inp["QP"].to("m**3/s").magnitude
        z = inp["z"].to("1/hour").magnitude
        n = int(round(inp["n"]))
        if z <= 0:
            raise ValueError("Die zulässigen Schaltspiele müssen größer als null sein.")
        Tmin = 3600 / (z * n)
        V = QP * Tmin / 4
        self.step("Kürzeste Spielzeit", "T_min = 3600 s / (z · n)",
                  f"T_min = 3600 / ({fmt_num(z, 1)} · {n})", f"{fmt_num(Tmin / 60, 2)} min")
        self.step("Nutzvolumen", "V_N = Q_P · T_min / 4  (ungünstigster Zufluss Q_zu = Q_P / 2)",
                  f"V_N = {fmt_num(QP * 1000, 2)} l/s · {fmt_num(Tmin, 0)} s / 4", f"{fmt_num(V, 2)} m³")
        if inp["form"] == "rund":
            D = inp["D"].to("m").magnitude
            A = math.pi * D**2 / 4
            geo = f"A = π · {fmt_num(D, 2)}² / 4"
        else:
            a, b = inp["a"].to("m").magnitude, inp["b"].to("m").magnitude
            A = a * b
            geo = f"A = {fmt_num(a, 2)} · {fmt_num(b, 2)}"
        f_tot = 1 + inp["Vtot"].to("percent").magnitude / 100
        dh = V / A * f_tot
        hmin = inp["hmin"].to("m").magnitude
        self.step("Grundfläche", "A", geo, f"{fmt_num(A, 3)} m²")
        self.step("Pegelhub", "Δh = V_N / A · (1 + ΔV)", f"Δh = {fmt_num(V, 2)} / {fmt_num(A, 3)} · {fmt_num(f_tot, 2)}",
                  f"{fmt_num(dh, 3)} m")
        Qzu = inp["Qzu"].to("m**3/s").magnitude
        self.result("V", "Erforderliches Nutzvolumen", "V_N", Q_(V, "m**3"), "m**3", 2, highlight=True)
        self.result("dh", "Pegelhub (Ein − Aus)", "Δh", Q_(dh, "m"), "m", 2, highlight=True)
        self.result("hein", "Einschaltpegel über Sohle", "h_ein", Q_(hmin + dh, "m"), "m", 2, highlight=True)
        self.result("A", "Grundfläche", "A", Q_(A, "m**2"), "m**2", 2)
        self.result("Tmin", "Kürzeste Spielzeit je Pumpe", "T_min", Q_(Tmin * n, "s"), "minute", 1)
        self.result("tl", "Laufzeit bei Q_zu = Q_P/2", "t_L", Q_(2 * V / QP, "s"), "minute", 1)
        if Qzu > 0:
            if Qzu >= QP:
                self.warn(f"Der Spitzenzufluss ({fmt_num(Qzu * 1000, 1)} l/s) erreicht den Förderstrom einer Pumpe – "
                          "die Pumpe läuft dauernd bzw. der Sumpf staut ein. Zweite Pumpe parallel oder größere "
                          "Pumpe vorsehen.")
            else:
                t_lauf = V / (QP - Qzu)
                t_still = V / Qzu
                self.result("tlz", "Laufzeit bei Spitzenzufluss", "t_L,max", Q_(t_lauf, "s"), "minute", 1)
                self.result("tsz", "Stillstandszeit bei Spitzenzufluss", "t_S", Q_(t_still, "s"), "minute", 1)
                self.step("Spiel bei Spitzenzufluss", "t_L = V_N / (Q_P − Q_zu);  t_S = V_N / Q_zu",
                          f"Q_zu = {fmt_num(Qzu * 1000, 2)} l/s",
                          f"t_L = {fmt_num(t_lauf / 60, 1)} min, t_S = {fmt_num(t_still / 60, 1)} min")
        Qd = inp["Qd"].to("m**3/s").magnitude
        if Qd > 0:
            V_mittel = V / 2 + A * hmin
            t_auf = V_mittel / Qd
            self.result("tauf", "Mittlere Aufenthaltszeit im Sumpf", "t_A", Q_(t_auf, "s"), "hour", 2)
            if t_auf > 2 * 3600:
                self.warn("Aufenthaltszeit über 2 h – Faulprozesse, Geruch und H₂S-Bildung möglich.")
        if 2 * V / QP < 60:
            self.info("Sehr kurze Pumpenlaufzeiten (< 1 min) – Mindestlaufzeit des Herstellers beachten.")
        if dh < 0.2:
            self.info("Kleiner Pegelhub – Schaltgenauigkeit der Niveausonde/Schwimmer prüfen.")
        self.info("Alarmpegel und Rückstauebene oberhalb des Einschaltpegels der Grundlastpumpe vorsehen; "
                  "Einschaltpegel der Spitzenlastpumpe entsprechend höher.")

    def plot(self, fig, raw, result) -> bool:
        if not result.ok:
            return False
        QP = float(raw["QP"]) / 1000
        V = result.value("V")
        x = np.linspace(0.02, 0.98, 200)
        T = V / (QP - x * QP) + V / (x * QP)
        ax = fig.subplots()
        ax.plot(x * 100, 3600 / T, color="#1f6fb2", lw=2, label="Schaltspiele (Anlage)")
        ax.axhline(float(raw["z"]) * float(raw["n"]), color="#c0392b", ls="--", label="zulässig z · n")
        ax.set_xlabel("Zufluss Q_zu / Q_P  [%]")
        ax.set_ylabel("Pumpenstarts je Stunde")
        ax.set_title("Schalthäufigkeit über dem Zufluss")
        ax.grid(True, alpha=0.3)
        ax.legend(loc="lower center")
        return True

    def sketch_svg(self, raw) -> str:
        s = Svg()
        s.line(80, 30, 80, 200, INK, 3).line(280, 30, 280, 200, INK, 3).line(80, 200, 280, 200, INK, 3)
        s.rect(82, 90, 196, 108, fill="#cfe0f1", stroke="#cfe0f1", width=0)
        s.line(82, 90, 278, 90, ACCENT, 1.5)
        s.line(82, 140, 278, 140, MUTED, 1, "5 4")
        pumpe_svg(s, 150, 180, 14)
        s.line(164, 180, 230, 180, ACCENT, 3).line(230, 180, 230, 20, ACCENT, 3)
        s.arrow(20, 60, 78, 60, ACCENT).text(20, 52, "Q_zu", 12, INK, "start", True)
        s.text(286, 86, "Ein", 10, INK, "start").text(286, 154, "Aus", 10, INK, "start")
        s.dim_v(318, 90, 140, "")
        s.text(334, 120, "Δh", 12, INK, "start", True)
        s.text(240, 30, "Q_P", 12, INK, "start", True)
        return s.render()
