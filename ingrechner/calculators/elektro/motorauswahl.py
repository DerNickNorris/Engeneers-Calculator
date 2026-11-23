"""Asynchronmotor – Auswahl aus dem Lastfall: Leistungsbedarf, Betriebsart, Aufstellbedingungen, IEC-Baugröße."""

from __future__ import annotations

import math

import numpy as np

from ingrechner.calculators.pumpen._pumpe import motor_groesse
from ingrechner.core.model import Calculator, ChoiceField, NumberField
from ingrechner.core.svg import ACCENT, INK, MUTED, Svg
from ingrechner.core.units import Q_, fmt_num

from ._motor import mindestklasse, synchron, typwerte

G = 9.80665
FREI = {"anwendung": ["frei"]}
QUAD = {"anwendung": ["quadratisch"]}
BAND = {"anwendung": ["band"]}
HUB = {"anwendung": ["hub"]}
FAHR = {"anwendung": ["fahr"]}
MASSE = {"anwendung": ["band", "hub", "fahr"]}
V = {"anwendung": ["band", "hub", "fahr"]}
S2 = {"betriebsart": ["S2"]}
ED = {"betriebsart": ["S3", "S6"]}

# Leistungsfaktoren für Kurzzeit- und Aussetzbetrieb (Richtwerte Herstellerkataloge): P_zul = f · P_N(S1)
F_S2 = {"10": 1.4, "30": 1.15, "60": 1.07, "90": 1.0}
F_S3 = {"15": 1.4, "25": 1.3, "40": 1.15, "60": 1.1}
F_S6 = {"15": 1.5, "25": 1.4, "40": 1.3, "60": 1.15}
# Abminderung nach Kühlmitteltemperatur und Aufstellhöhe (IEC 60034-1 / Herstellerangaben)
K_T = [(40, 1.0), (45, 0.96), (50, 0.92), (55, 0.87), (60, 0.82)]
K_H = [(1000, 1.0), (1500, 0.97), (2000, 0.94), (2500, 0.90), (3000, 0.86), (3500, 0.82), (4000, 0.77)]


class Motorauswahl(Calculator):
    id = "et.motorauswahl"
    title = "Asynchronmotor – Auswahl"
    category = "Elektrotechnik"
    description = (
        "Leistungsbedarf aus dem Lastfall (freie Vorgabe, Pumpe/Lüfter/Rührwerk, Förderband, Hubwerk, Fahrwerk) und "
        "Auswahl eines Drehstrom-Asynchronmotors: Betriebsart S1/S2/S3/S6, Abminderung für Kühlmitteltemperatur und "
        "Aufstellhöhe, IEC-Baugröße, Nennmoment, Auslastung, typische Katalogkennwerte und Mindest-Effizienzklasse "
        "nach EU-Ökodesign-Verordnung."
    )
    norm = "P_N ≥ P_Last/(η_mech · f_BA · k_T · k_H); Betriebsarten IEC 60034-1; Effizienz EU 2019/1781 / IEC 60034-30-1"
    keywords = ("motor", "asynchronmotor", "elektromotor", "drehstrommotor", "motorauswahl", "motorleistung",
                "hubwerk", "fahrwerk", "förderband", "pumpe", "lüfter", "betriebsart", "s1", "s3", "aufstellhöhe",
                "iec", "ie3", "ökodesign", "polzahl")

    fields = [
        ChoiceField("anwendung", "Anwendung", [("frei", "Moment/Drehzahl der Arbeitsmaschine vorgeben"),
                                               ("quadratisch", "Pumpe / Lüfter / Rührwerk (Wellenleistung)"),
                                               ("band", "Förderband / Rollenbahn"),
                                               ("hub", "Hubwerk"), ("fahr", "Fahrwerk")], "band"),
        NumberField("ML", "Lastmoment der Arbeitsmaschine", "M_L", "N*m", 300, min=0, decimals=1, visible_if=FREI),
        NumberField("nL", "Drehzahl der Arbeitsmaschine", "n_L", "1/minute", 100, min=0, decimals=1, visible_if=FREI),
        NumberField("PW", "Wellenleistung der Arbeitsmaschine", "P_W", "kW", 7.5, min=0, decimals=3, visible_if=QUAD,
                    tooltip="Pumpe: Rechner „Pumpenleistung & Motor“ (P₂); Lüfter: „Ventilator“"),
        NumberField("m", "Bewegte Masse (Last + Fördergut/Fahrzeug)", "m", "kg", 2000, min=0, decimals=0,
                    visible_if=MASSE),
        NumberField("v", "Geschwindigkeit", "v", "m/s", 0.5, min=0, decimals=3, visible_if=V),
        NumberField("mu", "Reibwert (Band/Rollen)", "μ", "", 0.03, min=0, decimals=3, visible_if=BAND,
                    tooltip="Gurtförderer auf Tragrollen 0,02–0,04; auf Gleitblech 0,3–0,5; Rollenbahn 0,03–0,05"),
        NumberField("steig", "Steigung", "α", "degree", 5, min=-30, max=30, min_inclusive=True, decimals=1,
                    visible_if=BAND),
        NumberField("w", "Fahrwiderstandsbeiwert", "w", "", 0.007, min=0, decimals=4, visible_if=FAHR,
                    tooltip="Stahlrad auf Schiene 0,005–0,007; Vollgummi auf Beton 0,01–0,02"),
        NumberField("steig_f", "Steigung Fahrbahn", "s", "percent", 0, min=0, max=30, min_inclusive=True, decimals=1,
                    visible_if=FAHR),
        NumberField("a", "Beschleunigung", "a", "m/s**2", 0.3, min=0, min_inclusive=True, decimals=2, visible_if=FAHR,
                    tooltip="Beschleunigungsleistung beim Anfahren (Motor kurzzeitig überlastbar, siehe Hinweis)"),
        NumberField("eta", "Wirkungsgrad Getriebe/Mechanik", "η_mech", "percent", 90, min=10, max=100, decimals=1),
        NumberField("i", "Übersetzung zwischen Motor und Maschine", "i", "", 15, min=0.1, decimals=3,
                    visible_if=FREI, tooltip="1 = Direktantrieb"),
        ChoiceField("pole", "Polzahl", [("2", "2-polig (≈ 3000 1/min)"), ("4", "4-polig (≈ 1500 1/min)"),
                                        ("6", "6-polig (≈ 1000 1/min)"), ("8", "8-polig (≈ 750 1/min)")], "4"),
        NumberField("f", "Netzfrequenz", "f", "Hz", 50, min=1, decimals=0),
        ChoiceField("betriebsart", "Betriebsart", [("S1", "S1 Dauerbetrieb"), ("S2", "S2 Kurzzeitbetrieb"),
                                                   ("S3", "S3 Aussetzbetrieb"),
                                                   ("S6", "S6 Durchlaufbetrieb mit Aussetzbelastung")], "S1"),
        ChoiceField("s2", "Betriebsdauer (S2)", [(k, f"{k} min") for k in F_S2], "30", visible_if=S2),
        ChoiceField("ed", "Relative Einschaltdauer", [(k, f"ED {k} %") for k in F_S3], "40", visible_if=ED),
        NumberField("tk", "Kühlmitteltemperatur", "θ_K", "degC", 40, min=-30, max=60, decimals=0),
        NumberField("h", "Aufstellhöhe über NN", "h", "m", 400, min=0, max=4000, min_inclusive=True, decimals=0),
        NumberField("reserve", "Zusätzliche Leistungsreserve", "z", "percent", 10, min=0, min_inclusive=True, max=100,
                    decimals=0),
    ]

    def compute(self, inp) -> None:
        app = inp["anwendung"]
        eta = inp["eta"].to("percent").magnitude / 100
        pole = int(inp["pole"])
        f = inp["f"].to("Hz").magnitude
        n_syn = synchron(f, pole)
        n_mot = n_syn * 0.97
        if app == "frei":
            ML, nL = inp["ML"].to("N*m").magnitude, inp["nL"].to("1/minute").magnitude
            P_L = ML * 2 * math.pi * nL / 60
            self.step("Lastleistung", "P_L = M_L · 2π·n_L/60", f"P_L = {fmt_num(ML, 1)} N·m · {fmt_num(nL, 1)} 1/min",
                      f"{fmt_num(P_L / 1000, 3)} kW")
            i_gew = float(inp["i"])
            if abs(nL * i_gew / n_mot - 1) > 0.1:
                self.info(f"Mit i = {fmt_num(i_gew, 2)} ergibt sich n_Motor ≈ {fmt_num(nL * i_gew, 0)} 1/min – für "
                          f"{pole}-polig passt i ≈ {fmt_num(n_mot / nL, 2)}.")
        elif app == "quadratisch":
            P_L = inp["PW"].to("W").magnitude
            self.info("Quadratische Lastkennlinie (M ~ n²): kleines Anlaufmoment, Drehzahlregelung sehr wirksam.")
        else:
            m, v = inp["m"].to("kg").magnitude, inp["v"].to("m/s").magnitude
            if app == "band":
                al = inp["steig"].to("radian").magnitude
                F = m * G * (float(inp["mu"]) * math.cos(al) + math.sin(al))
                txt = "F = m·g·(μ·cos α + sin α)"
            elif app == "hub":
                F = m * G
                txt = "F = m·g"
            else:
                s = inp["steig_f"].to("percent").magnitude / 100
                F = m * (G * (float(inp["w"]) + s) + inp["a"].to("m/s**2").magnitude)
                txt = "F = m·(g·(w + s) + a)"
            P_L = F * v
            self.step("Bewegungswiderstand", txt, f"m = {fmt_num(m, 0)} kg", f"F = {fmt_num(F, 0)} N")
            self.step("Lastleistung", "P_L = F · v", f"P_L = {fmt_num(F, 0)} N · {fmt_num(v, 3)} m/s",
                      f"{fmt_num(P_L / 1000, 3)} kW")
            if app == "fahr" and inp["a"].to("m/s**2").magnitude > 0:
                self.info("Beschleunigungsanteil voll eingerechnet; bei kurzer Anfahrzeit genügt oft ein kleinerer Motor "
                          "(Kippmoment, Hochlaufnachweis im Rechner „Anlauf & Hochlauf“).")
            if app == "hub":
                self.info("Hubwerk: Absenken generatorisch – Bremse bzw. Bremswiderstand (Rechner „Frequenzumrichter“) "
                          "vorsehen; Hubklasse nach DIN EN 60204-32 / FEM 9.511 beachten.")

        P_W = P_L / eta
        ba = inp["betriebsart"]
        f_ba = {"S1": 1.0, "S2": F_S2.get(inp["s2"], 1.0), "S3": F_S3.get(inp["ed"], 1.0),
                "S6": F_S6.get(inp["ed"], 1.0)}[ba]
        tk, h = inp["tk"].to("degC").magnitude, inp["h"].to("m").magnitude
        k_t = float(np.interp(tk, *zip(*K_T)))
        k_h = float(np.interp(h, *zip(*K_H)))
        z = 1 + inp["reserve"].to("percent").magnitude / 100
        P_erf = P_W * z / (f_ba * k_t * k_h)
        self.step("Leistung an der Motorwelle", "P_W = P_L / η_mech", f"η_mech = {fmt_num(eta, 3)}",
                  f"{fmt_num(P_W / 1000, 3)} kW")
        self.step("Erforderliche Bemessungsleistung (S1)", "P_N ≥ P_W · (1+z) / (f_BA · k_T · k_H)",
                  f"f_BA = {fmt_num(f_ba, 2)} ({ba}), k_T = {fmt_num(k_t, 3)} ({fmt_num(tk, 0)} °C), "
                  f"k_H = {fmt_num(k_h, 3)} ({fmt_num(h, 0)} m), z = {fmt_num(z - 1, 2)}", f"{fmt_num(P_erf / 1000, 3)} kW")
        sel = motor_groesse(P_erf / 1000)
        if sel is None:
            raise ValueError("Leistung über 315 kW – außerhalb der hinterlegten IEC-Reihe.")
        PN = sel[1]
        typ = typwerte(PN)
        n_N = n_syn * (1 - 0.04 if PN < 2 else 1 - 0.03 if PN < 15 else 1 - 0.015)
        MN = PN * 1000 / (2 * math.pi * n_N / 60)
        M_mot = P_W / (2 * math.pi * n_N / 60)
        self.step("Motor", "nächste IEC-Normleistung; M_N = P_N/(2π·n_N/60)", f"{pole}-polig, n_syn = {fmt_num(n_syn, 0)} 1/min",
                  f"P_N = {fmt_num(PN, 2)} kW, n_N ≈ {fmt_num(n_N, 0)} 1/min, M_N = {fmt_num(MN, 1)} N·m")

        self.result("PL", "Leistungsbedarf der Last", "P_L", Q_(P_L, "W"), "kW", 3)
        self.result("PW", "Leistung an der Motorwelle", "P_W", Q_(P_W, "W"), "kW", 3, highlight=True)
        self.result("Perf", "Erforderliche Bemessungsleistung", "P_N,erf", Q_(P_erf, "W"), "kW", 3)
        self.result("PN", "Motor-Bemessungsleistung", "P_N", Q_(PN, "kW"), "kW", 2, highlight=True)
        self.result("nN", "Nenndrehzahl (typisch)", "n_N", Q_(n_N, "1/minute"), "1/minute", 0)
        self.result("MN", "Nennmoment", "M_N", Q_(MN, "N*m"), "N*m", 1, highlight=True)
        self.result("ML", "Lastmoment an der Motorwelle", "M_L", Q_(M_mot, "N*m"), "N*m", 1)
        self.result("last", "Auslastung", "P_W/P_N", Q_(P_W / (PN * 1000) * 100, "percent"), "percent", 0)
        self.result("eta_typ", "Wirkungsgrad (IE3, typisch)", "η_N", Q_(typ.eta, "percent"), "percent", 1)
        self.result("cos_typ", "Leistungsfaktor (typisch)", "cos φ_N", Q_(typ.cosphi, ""), "", 2)
        self.result("ia_typ", "Anlaufstromverhältnis (typisch)", "I_A/I_N", Q_(typ.ia, ""), "", 1)
        self.result("ma_typ", "Anlaufmomentverhältnis (typisch)", "M_A/M_N", Q_(typ.ma, ""), "", 1)
        self.result("mk_typ", "Kippmomentverhältnis (typisch)", "M_K/M_N", Q_(typ.mk, ""), "", 1)
        self.result("J_typ", "Massenträgheit Motor (typisch)", "J_M", Q_(typ.J, "kg*m**2"), "kg*m**2", 4)
        klasse = mindestklasse(PN, pole)
        self.info(f"Mindest-Effizienzklasse nach EU 2019/1781 für {fmt_num(PN, 2)} kW, {pole}-polig: {klasse}. "
                  "Typische Kennwerte sind Richtwerte 4-poliger IE3-Motoren – Herstellerkatalog verwenden.")
        if P_W / (PN * 1000) < 0.5:
            self.info("Auslastung unter 50 % – Wirkungsgrad und Leistungsfaktor sinken; kleinere Baugröße prüfen.")
        if tk > 40 or h > 1000:
            self.info(f"Abminderung wegen {'Kühlmitteltemperatur > 40 °C' if tk > 40 else ''}"
                      f"{' und ' if tk > 40 and h > 1000 else ''}{'Aufstellhöhe > 1000 m' if h > 1000 else ''} "
                      "berücksichtigt (IEC 60034-1; Herstellerwerte haben Vorrang).")
        if ba != "S1":
            self.info("Faktoren für S2/S3/S6 sind Richtwerte; bei häufigen Anläufen zusätzlich die Schalthäufigkeit "
                      "prüfen (Rechner „Anlauf & Hochlauf“).")

    def sketch_svg(self, raw) -> str:
        s = Svg()
        s.rect(30, 80, 90, 60, fill="#f5d7d3").text(75, 115, "M 3~", 13, INK, bold=True)
        s.line(120, 110, 170, 110, INK, 5)
        app = raw.get("anwendung", "band")
        if app == "hub":
            s.circle(200, 80, 26, fill="#dce6f1").line(226, 80, 226, 170, INK, 2).rect(206, 170, 40, 30, fill="#9aa7b4")
            s.arrow(270, 190, 270, 150, ACCENT).text(276, 175, "v", 12, INK, "start", True)
        elif app in ("band", "fahr"):
            s.circle(200, 110, 18, fill="#dce6f1").circle(320, 110, 18, fill="#dce6f1")
            s.line(200, 92, 320, 92, INK, 3).line(200, 128, 320, 128, INK, 3)
            s.rect(240, 66, 40, 26, fill="#9aa7b4").arrow(240, 50, 300, 50, ACCENT)
            s.text(270, 44, "v", 12, INK, italic=True)
        else:
            s.circle(220, 110, 40, fill="#dce6f1").text(220, 114, "Last", 11, INK)
        s.text(180, 205, "Bemessungsleistung ≥ Bedarf mit Zuschlägen", 11, MUTED)
        return s.render()
