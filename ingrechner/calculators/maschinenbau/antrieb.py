"""Antriebsauslegung für Katalog-Getriebemotoren: Betriebsfaktor, Nennmoment, Motorgröße, Querkraft, Hochlauf."""

from __future__ import annotations

import math

from ingrechner.calculators.pumpen._pumpe import IEC_GROESSEN, motor_groesse
from ingrechner.core.model import Calculator, ChoiceField, NumberField
from ingrechner.core.svg import ACCENT, INK, MUTED, Svg
from ingrechner.core.units import Q_, fmt_num

from ._getriebe import F_Z, LASTSTOSS, betriebsfaktor

MOMENT = {"vorgabe": ["moment"]}
LEISTUNG = {"vorgabe": ["leistung"]}
FB_FREI = {"fb_art": ["frei"]}
FB_AUTO = {"fb_art": ["auto"]}
QUER = {"element": ["zahnrad", "kette", "keilriemen", "flachriemen"]}


class Antriebsauslegung(Calculator):
    id = "mb.antrieb"
    title = "Getriebe – Antriebsauslegung"
    category = "Maschinenbau"
    description = (
        "Auswahl eines Katalog-Getriebe(motors): Lastmoment bzw. -leistung, Übersetzung, Betriebsfaktor aus "
        "Laststoß, Laufzeit und Schalthäufigkeit, erforderliches Getriebe-Nennmoment, Motorleistung und "
        "IEC-Baugröße; Prüfung eines gewählten Getriebes (Nennmoment, zulässige Querkraft am Abtrieb) und "
        "optional die Hochlaufzeit mit reduziertem Massenträgheitsmoment."
    )
    norm = "M₂,erf = f_B · M₂; P₁ = P₂/η; F_Q = 2000·M₂/d₀ · f_Z; J_red = J/i²; Betriebsfaktoren nach Herstellersystematik"
    keywords = ("getriebe", "getriebemotor", "antrieb", "betriebsfaktor", "servicefaktor", "abtriebsmoment",
                "übersetzung", "querkraft", "radialkraft", "motor", "hochlauf", "massenträgheit", "katalog")

    fields = [
        ChoiceField("vorgabe", "Last vorgegeben als", [("moment", "Abtriebsmoment"), ("leistung", "Abtriebsleistung")],
                    "moment"),
        NumberField("M2", "Lastmoment am Abtrieb", "M₂", "N*m", 850, min=0, decimals=1, visible_if=MOMENT),
        NumberField("P2", "Leistungsbedarf am Abtrieb", "P₂", "kW", 4, min=0, decimals=3, visible_if=LEISTUNG),
        NumberField("n2", "Abtriebsdrehzahl", "n₂", "1/minute", 40, min=0, decimals=2),
        NumberField("n1", "Motordrehzahl", "n₁", "1/minute", 1450, min=0, decimals=0,
                    tooltip="4-polig 50 Hz ≈ 1450 1/min, 2-polig ≈ 2900, 6-polig ≈ 960"),
        NumberField("eta", "Getriebewirkungsgrad", "η_G", "percent", 95, min=10, max=100, decimals=1,
                    tooltip="Stirnrad ≈ 98 % je Stufe, Kegelstirnrad 2-/3-stufig ≈ 95–96 %, Schnecke 50–90 %"),
        ChoiceField("fb_art", "Betriebsfaktor", [("auto", "aus Laststoß, Laufzeit, Schaltungen"),
                                                 ("frei", "vorgeben (Herstellerkatalog)")], "auto"),
        ChoiceField("stoss", "Laststoßgrad", LASTSTOSS, "II", visible_if=FB_AUTO),
        NumberField("h", "Laufzeit pro Tag", "t_d", "hour", 16, min=0, max=24, decimals=1, visible_if=FB_AUTO),
        NumberField("z", "Schaltungen pro Stunde", "Z", "1/hour", 20, min=0, min_inclusive=True, decimals=0,
                    visible_if=FB_AUTO),
        NumberField("fb", "Betriebsfaktor", "f_B", "", 1.4, min=0.5, max=4, decimals=2, visible_if=FB_FREI),
        NumberField("M2N", "Nennmoment des gewählten Getriebes", "M₂N", "N*m", 0, min=0, min_inclusive=True,
                    decimals=0, tooltip="Aus dem Katalog; 0 = keine Prüfung"),
        ChoiceField("element", "Übertragungselement am Abtrieb", [(k, v[0]) for k, v in F_Z.items()], "keins"),
        NumberField("d0", "Wirkdurchmesser des Elements", "d₀", "mm", 200, min=0, decimals=1, visible_if=QUER),
        NumberField("FRzul", "Zulässige Querkraft (Katalog)", "F_R,zul", "N", 0, min=0, min_inclusive=True,
                    decimals=0, visible_if=QUER, tooltip="Zulässige Querkraft am Abtrieb aus dem Katalog; 0 = keine "
                                                         "Prüfung"),
        NumberField("J", "Massenträgheit der Last (Abtrieb)", "J_L", "kg*m**2", 0, min=0, min_inclusive=True,
                    decimals=3, tooltip="Für die Hochlaufzeit; 0 = ohne"),
        NumberField("JM", "Massenträgheit Motor", "J_M", "kg*m**2", 0.01, min=0, min_inclusive=True, decimals=4),
        NumberField("kH", "Mittleres Hochlaufmoment / Nennmoment", "M_H/M_N", "", 1.8, min=1, max=4, decimals=2),
    ]

    def compute(self, inp) -> None:
        n2 = inp["n2"].to("1/minute").magnitude
        n1 = inp["n1"].to("1/minute").magnitude
        if n2 <= 0 or n1 <= 0:
            raise ValueError("Die Drehzahlen müssen größer als null sein.")
        w2 = 2 * math.pi * n2 / 60
        if inp["vorgabe"] == "moment":
            M2 = inp["M2"].to("N*m").magnitude
            P2 = M2 * w2
        else:
            P2 = inp["P2"].to("W").magnitude
            M2 = P2 / w2
        i = n1 / n2
        eta = inp["eta"].to("percent").magnitude / 100
        P1 = P2 / eta
        self.step("Übersetzung", "i = n₁ / n₂", f"i = {fmt_num(n1, 0)} / {fmt_num(n2, 2)}", fmt_num(i, 2))
        self.step("Abtriebsleistung", "P₂ = M₂ · 2π·n₂/60", f"P₂ = {fmt_num(M2, 1)} N·m · {fmt_num(w2, 3)} 1/s",
                  f"{fmt_num(P2 / 1000, 3)} kW")
        self.step("Antriebsleistung", "P₁ = P₂ / η_G", f"P₁ = {fmt_num(P2 / 1000, 3)} kW / {fmt_num(eta, 3)}",
                  f"{fmt_num(P1 / 1000, 3)} kW")
        if inp["fb_art"] == "auto":
            fb, grund, zu = betriebsfaktor(inp["stoss"], inp["h"].to("hour").magnitude, inp["z"].to("1/hour").magnitude)
            self.step("Betriebsfaktor", "f_B = Grundwert(Laststoß, Laufzeit) + Zuschlag(Schaltungen)",
                      f"Laststoß {inp['stoss']}, {fmt_num(inp['h'].to('hour').magnitude, 1)} h/d, "
                      f"{fmt_num(inp['z'].to('1/hour').magnitude, 0)} 1/h: {fmt_num(grund, 2)} + {fmt_num(zu, 2)}",
                      f"f_B = {fmt_num(fb, 2)}")
        else:
            fb = float(inp["fb"])
        M2erf = fb * M2
        self.step("Erforderliches Getriebe-Nennmoment", "M₂,erf = f_B · M₂",
                  f"M₂,erf = {fmt_num(fb, 2)} · {fmt_num(M2, 1)} N·m", f"{fmt_num(M2erf, 0)} N·m")
        sel = motor_groesse(P1 / 1000)
        if sel is None:
            raise ValueError("Antriebsleistung über 315 kW – außerhalb der hinterlegten IEC-Reihe.")
        PN = sel[1]
        MN = PN * 1000 / (2 * math.pi * n1 / 60)
        self.step("Motorbaugröße", "P_N ≥ P₁ (nächste IEC-Normleistung)", "", f"P_N = {fmt_num(PN, 2)} kW")

        self.result("i", "Übersetzung", "i", Q_(i, ""), "", 2, highlight=True)
        self.result("M2", "Lastmoment am Abtrieb", "M₂", Q_(M2, "N*m"), "N*m", 1)
        self.result("fB", "Betriebsfaktor", "f_B", Q_(fb, ""), "", 2, highlight=True)
        self.result("M2erf", "Erforderliches Getriebe-Nennmoment", "M₂,erf", Q_(M2erf, "N*m"), "N*m", 0,
                    highlight=True)
        self.result("P1", "Erforderliche Motorleistung", "P₁", Q_(P1, "W"), "kW", 3)
        self.result("PN", "Motor-Bemessungsleistung", "P_N", Q_(PN, "kW"), "kW", 2, highlight=True)
        self.result("M1", "Antriebsmoment (Motorwelle)", "M₁", Q_(P1 / (2 * math.pi * n1 / 60), "N*m"), "N*m", 2)
        self.result("MN", "Motor-Nennmoment", "M_N", Q_(MN, "N*m"), "N*m", 2)
        if PN / (P1 / 1000) > 1.6:
            self.info("Der Motor ist deutlich größer als nötig – Getriebe auf Motorleistung prüfen (Katalog: "
                      "f_B bezogen auf P_N).")

        M2N = inp["M2N"].to("N*m").magnitude
        if M2N > 0:
            fb_vorh = M2N / M2
            self.result("fBvorh", "Vorhandener Betriebsfaktor", "f_B,vorh", Q_(fb_vorh, ""), "", 2, highlight=True)
            (self.warn if fb_vorh < fb else self.info)(
                f"Gewähltes Getriebe: M₂N = {fmt_num(M2N, 0)} N·m → f_B,vorh = {fmt_num(fb_vorh, 2)} "
                + ("< erforderlich – größeres Getriebe wählen." if fb_vorh < fb else f"≥ {fmt_num(fb, 2)} ✔"))
        if inp["element"] != "keins":
            fz = F_Z[inp["element"]][1]
            d0 = inp["d0"].to("mm").magnitude
            FQ = 2000 * M2 / d0 * fz
            self.step("Querkraft am Abtrieb", "F_Q = 2000 · M₂ / d₀ · f_Z",
                      f"F_Q = 2000 · {fmt_num(M2, 1)} / {fmt_num(d0, 1)} · {fmt_num(fz, 2)}", f"{fmt_num(FQ, 0)} N")
            self.result("FQ", "Querkraft am Abtrieb", "F_Q", Q_(FQ, "N"), "N", 0, highlight=True)
            FRzul = inp["FRzul"].to("N").magnitude
            if FRzul > 0:
                (self.warn if FQ > FRzul else self.info)(
                    f"Querkraft {fmt_num(FQ, 0)} N " + ("> zulässig " if FQ > FRzul else "≤ zulässig ")
                    + f"{fmt_num(FRzul, 0)} N" + (" – Getriebe mit verstärkter Lagerung, größerer d₀ oder "
                                                  "Lagerung am Abtriebselement." if FQ > FRzul else " ✔"))
        J = inp["J"].to("kg*m**2").magnitude
        if J > 0:
            Jred = J / i**2
            Jges = inp["JM"].to("kg*m**2").magnitude + Jred
            ML1 = M2 / (i * eta)
            MH = float(inp["kH"]) * MN
            w1 = 2 * math.pi * n1 / 60
            if MH <= ML1:
                self.warn("Das Hochlaufmoment reicht nicht aus, um die Last zu beschleunigen.")
            else:
                tA = Jges * w1 / (MH - ML1)
                self.step("Hochlaufzeit", "t_A = (J_M + J_L/i²) · ω₁ / (M_H − M_L/(i·η))",
                          f"J_red = {fmt_num(Jred, 5)} kg·m², M_H = {fmt_num(MH, 1)} N·m, M_L' = {fmt_num(ML1, 1)} N·m",
                          f"{fmt_num(tA, 2)} s")
                self.result("Jred", "Reduziertes Massenträgheitsmoment", "J_red", Q_(Jred, "kg*m**2"), "kg*m**2", 5)
                self.result("tA", "Hochlaufzeit", "t_A", Q_(tA, "s"), "s", 2)
                if Jred / max(inp["JM"].to("kg*m**2").magnitude, 1e-9) > 10:
                    self.info("Massenträgheitsverhältnis J_red/J_M > 10 – Stoßbelastung beim Anlauf; Betriebsfaktor "
                              "bzw. Sanftanlauf prüfen.")
        self.info("Betriebsfaktoren sind Richtwerte; maßgeblich ist die Systematik des Getriebeherstellers "
                  "(Laststoßgrad aus Massenbeschleunigungsfaktor, thermische Grenzleistung beachten).")

    def sketch_svg(self, raw) -> str:
        s = Svg()
        s.rect(20, 80, 80, 60, fill="#f5d7d3").text(60, 115, "Motor", 12, INK, bold=True)
        s.line(100, 110, 130, 110, INK, 5)
        s.rect(130, 60, 100, 100, fill="#eef3f8").text(180, 114, "Getriebe", 12, INK, bold=True)
        s.line(230, 110, 290, 110, INK, 7)
        s.circle(300, 110, 30, fill="#dce6f1")
        s.text(60, 70, "n₁, P₁", 12, INK, italic=True).text(300, 70, "n₂, M₂", 12, INK, italic=True)
        s.arrow(300, 150, 300, 200, ACCENT).text(306, 190, "F_Q", 12, INK, "start", True)
        s.text(180, 200, "M₂,erf = Betriebsfaktor · M₂", 12, MUTED)
        return s.render()
