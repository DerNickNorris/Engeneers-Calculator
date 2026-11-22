"""Übersetzung und Stufenaufteilung mit Zähnezahlvorschlag, Drehzahlen und Momenten je Welle."""

from __future__ import annotations

import math

from ingrechner.core.model import Calculator, ChoiceField, NumberField
from ingrechner.core.svg import INK, MUTED, Svg
from ingrechner.core.units import Q_, fmt_num

STUFEN_FREI = {"stufen_art": ["vorgabe"]}


def zaehne_vorschlag(i_soll: float, z_min: int, z_max: int, z1_max: int = 40,
                     tol: float = 0.005) -> tuple[int, int, float]:
    """Zähnezahlpaar: kleinstes Ritzel mit Abweichung ≤ tol, teilerfremd bevorzugt („Jagdzahnung“);
    gibt es keins, das Paar mit der kleinsten Abweichung."""
    kand = []
    for z1 in range(z_min, z1_max + 1):
        z2 = round(i_soll * z1)
        if z_min <= z2 <= z_max:
            kand.append((abs(z2 / z1 - i_soll) / i_soll, z1, z2))
    if not kand:
        raise ValueError(f"Für i = {fmt_num(i_soll, 3)} gibt es keine Zähnezahlen zwischen {z_min} und {z_max}.")
    gut = [k for k in kand if k[0] <= tol]
    if gut:
        err, z1, z2 = min(gut, key=lambda k: (math.gcd(k[1], k[2]) != 1, k[1]))
    else:
        err, z1, z2 = min(kand)
    return z1, z2, z2 / z1


class Uebersetzung(Calculator):
    id = "mb.uebersetzung"
    title = "Getriebe – Übersetzung & Stufen"
    category = "Maschinenbau"
    description = (
        "Gesamtübersetzung aus An- und Abtriebsdrehzahl, Aufteilung auf 1–3 Stirnradstufen, Zähnezahlvorschlag "
        "je Stufe (kleinste Abweichung, teilerfremd = „Jagdzahnung“) sowie Drehzahl, Drehmoment und Leistung "
        "an jeder Welle mit Stufenwirkungsgraden."
    )
    norm = "i = n₁/n₂ = Π iₖ;  iₖ = z₂/z₁;  M_k+1 = M_k · iₖ · ηₖ"
    keywords = ("übersetzung", "getriebe", "stufen", "zähnezahl", "zahnrad", "jagdzahnung", "teilerfremd",
                "drehzahl", "drehmoment", "mehrstufig", "stirnradgetriebe")

    fields = [
        NumberField("n1", "Antriebsdrehzahl", "n₁", "1/minute", 1450, min=0, decimals=0),
        NumberField("n2", "Abtriebsdrehzahl (Soll)", "n₂", "1/minute", 40, min=0, decimals=2),
        NumberField("P", "Antriebsleistung", "P₁", "kW", 5.5, min=0, decimals=3),
        ChoiceField("stufen_art", "Stufenzahl", [("auto", "automatisch (iₖ ≤ 7)"), ("vorgabe", "vorgeben")], "auto"),
        NumberField("s", "Anzahl Stufen", "s", "", 2, min=1, max=3, min_inclusive=True, decimals=0,
                    visible_if=STUFEN_FREI),
        NumberField("zmin", "Mindestzähnezahl Ritzel", "z_min", "", 17, min=6, max=40, min_inclusive=True,
                    decimals=0, tooltip="Geradverzahnung ohne Profilverschiebung 17; mit x > 0 bzw. Schrägverzahnung "
                                        "ab ca. 12–14"),
        NumberField("zmax", "Höchstzähnezahl Rad", "z_max", "", 150, min=20, max=500, decimals=0),
        NumberField("eta", "Wirkungsgrad je Stufe", "η_k", "percent", 98, min=50, max=100, decimals=1),
        NumberField("tol", "Zulässige Abweichung der Übersetzung", "Δi", "percent", 2, min=0, min_inclusive=True,
                    decimals=1),
    ]

    def compute(self, inp) -> None:
        n1, n2 = inp["n1"].to("1/minute").magnitude, inp["n2"].to("1/minute").magnitude
        if n1 <= 0 or n2 <= 0:
            raise ValueError("Die Drehzahlen müssen größer als null sein.")
        i = n1 / n2
        if i < 1:
            raise ValueError("Übersetzung ins Schnelle (n₂ > n₁) – hier nur Untersetzungen.")
        s = int(round(inp["s"])) if inp["stufen_art"] == "vorgabe" else max(1, math.ceil(math.log(i) / math.log(7)))
        self.step("Gesamtübersetzung", "i = n₁ / n₂", f"i = {fmt_num(n1, 0)} / {fmt_num(n2, 2)}",
                  f"i = {fmt_num(i, 3)}, {s} Stufe(n)")
        # Aufteilung: geometrisch, erste Stufe etwas größer, letzte kleiner (Faustregel für kleinere Baugröße)
        g = i ** (1 / s)
        teile = [g] if s == 1 else [g * 1.15, *([g] * (s - 2)), g / 1.15]
        zmin, zmax = int(round(inp["zmin"])), int(round(inp["zmax"]))
        eta = inp["eta"].to("percent").magnitude / 100
        P = inp["P"].to("W").magnitude
        n, M = n1, P / (2 * math.pi * n1 / 60)
        i_ist = 1.0
        self.result("n_0", "Drehzahl Welle 1 (Antrieb)", "n₁", Q_(n, "1/minute"), "1/minute", 1)
        self.result("M_0", "Moment Welle 1 (Antrieb)", "M₁", Q_(M, "N*m"), "N*m", 2)
        for k, ik_soll in enumerate(teile, 1):
            z1, z2, ik = zaehne_vorschlag(ik_soll, zmin, zmax)
            i_ist *= ik
            n_neu, M_neu = n / ik, M * ik * eta
            self.step(f"Stufe {k}", "iₖ = z₂/z₁;  n' = n/iₖ;  M' = M·iₖ·η",
                      f"i_soll = {fmt_num(ik_soll, 3)} → z = {z1}/{z2}" + ("" if math.gcd(z1, z2) == 1 else
                                                                           f" (ggT {math.gcd(z1, z2)})"),
                      f"i = {fmt_num(ik, 4)}, n = {fmt_num(n_neu, 2)} 1/min, M = {fmt_num(M_neu, 1)} N·m")
            self.result(f"z1_{k}", f"Stufe {k}: Zähnezahl Ritzel", f"z₁,{k}", Q_(z1, ""), "", 0, highlight=True)
            self.result(f"z2_{k}", f"Stufe {k}: Zähnezahl Rad", f"z₂,{k}", Q_(z2, ""), "", 0, highlight=True)
            self.result(f"i_{k}", f"Stufe {k}: Übersetzung", f"i_{k}", Q_(ik, ""), "", 4)
            self.result(f"n_{k}", f"Drehzahl Welle {k + 1}", f"n_{k + 1}", Q_(n_neu, "1/minute"), "1/minute", 2)
            self.result(f"M_{k}", f"Moment Welle {k + 1}", f"M_{k + 1}", Q_(M_neu, "N*m"), "N*m", 1)
            n, M = n_neu, M_neu
        abw = (i_ist / i - 1) * 100
        self.result("i_ist", "Gesamtübersetzung (ist)", "i_ist", Q_(i_ist, ""), "", 4, highlight=True)
        self.result("abw", "Abweichung von der Sollübersetzung", "Δi", Q_(abw, "percent"), "percent", 2)
        self.result("n_ab", "Abtriebsdrehzahl (ist)", "n_ab", Q_(n, "1/minute"), "1/minute", 2, highlight=True)
        self.result("M_ab", "Abtriebsmoment", "M_ab", Q_(M, "N*m"), "N*m", 1, highlight=True)
        self.result("eta_ges", "Gesamtwirkungsgrad", "η_ges", Q_(eta ** s * 100, "percent"), "percent", 1)
        if abs(abw) > inp["tol"].to("percent").magnitude:
            self.warn(f"Übersetzungsabweichung {fmt_num(abw, 2)} % – Zähnezahlgrenzen erweitern oder Stufenzahl ändern.")
        if any(t > 7 for t in teile):
            self.warn("Stufenübersetzung über 7 – Stufenzahl erhöhen (Baugröße, Ritzelbelastung).")
        self.info("Katalog-Getriebe: Die tatsächlichen Übersetzungen der Baureihe dem Herstellerkatalog entnehmen; "
                  "der Zähnezahlvorschlag dient Sonder- und Eigenkonstruktionen.")

    def sketch_svg(self, raw) -> str:
        s = Svg()
        try:
            n1, n2 = float(raw.get("n1", 1450)), float(raw.get("n2", 40))
            st = int(round(float(raw.get("s", 2)))) if raw.get("stufen_art") == "vorgabe" else \
                max(1, math.ceil(math.log(max(n1 / n2, 1.0001)) / math.log(7)))
        except (TypeError, ValueError, ZeroDivisionError):
            st = 2
        x = 40
        for k in range(min(st, 3)):
            s.circle(x + 30, 80, 14, fill="#f5d7d3").circle(x + 30, 140, 44, fill="#dce6f1")
            s.text(x + 30, 84, "z₁", 10, INK, italic=True).text(x + 30, 150, "z₂", 11, INK, italic=True)
            x += 100
        s.text(180, 205, "i = Π z₂/z₁", 12, MUTED)
        return s.render()
