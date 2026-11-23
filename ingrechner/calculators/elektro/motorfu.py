"""Asynchronmotor am Frequenzumrichter: Drehmomentgrenzen über der Frequenz, Umrichterstrom, Bremswiderstand."""

from __future__ import annotations

import math

import numpy as np

from ingrechner.core.model import Calculator, ChoiceField, NumberField
from ingrechner.core.svg import ACCENT, INK, MUTED, Svg
from ingrechner.core.units import Q_, fmt_num

from .motordaten import MotorDaten, motor_felder

G = 9.80665
EIGEN = [(0, 0.55), (5, 0.65), (15, 0.8), (25, 0.9), (35, 0.95), (50, 1.0)]   # M_zul/M_N eigenbelüftet (Richtwert)
FREMD = [(0, 0.9), (3, 1.0), (50, 1.0)]
BREMS_J = {"bremsen": ["massen"]}
BREMS_H = {"bremsen": ["hub"]}
BREMS = {"bremsen": ["massen", "hub"]}


class MotorFU:
    """Zulässiges Dauer- und Kippmoment über der Frequenz."""

    def __init__(self, md: MotorDaten, eck: float, kuehlung: str) -> None:
        self.md, self.eck, self.kuehlung = md, eck, kuehlung

    def m_dauer(self, f):
        f = np.asarray(f, dtype=float)
        tab = EIGEN if self.kuehlung == "eigen" else FREMD
        k = np.interp(f * 50.0 / self.md.f, *zip(*tab))    # Lüfterwirkung hängt an der Drehzahl (Tabelle für 50 Hz)
        return np.where(f <= self.eck, self.md.MN * k, self.md.MN * self.eck / np.maximum(f, 1e-9))

    def m_kipp(self, f):
        f = np.asarray(f, dtype=float)
        return np.where(f <= self.eck, self.md.mk * self.md.MN, self.md.mk * self.md.MN * (self.eck / np.maximum(f, 1e-9)) ** 2)


class MotorUmrichter(Calculator):
    id = "et.motorfu"
    title = "Asynchronmotor – Frequenzumrichter"
    category = "Elektrotechnik"
    description = (
        "Betrieb eines Asynchronmotors am Frequenzumrichter: Grunddrehzahl- und Feldschwächbereich (auch "
        "87-Hz-Kennlinie), zulässiges Dauermoment über der Frequenz bei Eigen- oder Fremdbelüftung, Kippgrenze, "
        "Prüfung der Lastkennlinie im Stellbereich, erforderlicher Umrichterstrom sowie Bremsleistung und "
        "Bremswiderstand für Massenbremsung oder Senken."
    )
    norm = "M ≤ M_N bis f_Eck, darüber M ≤ M_N·f_Eck/f (P = konst.), M_K ~ (f_Eck/f)²; R_Br ≤ U_DC²/P_Br"
    keywords = ("frequenzumrichter", "fu", "umrichter", "drehzahlregelung", "feldschwächung", "87 hz",
                "bremswiderstand", "bremschopper", "fremdlüfter", "eigenbelüftet", "motor", "asynchronmotor", "u/f")

    fields = [
        *motor_felder(),
        ChoiceField("schaltung", "Kennlinie", [("50", "Standard (Eckfrequenz = Bemessungsfrequenz)"),
                                               ("87", "87-Hz-Kennlinie (230/400-V-Motor im Dreieck an 400 V)")], "50"),
        ChoiceField("kuehlung", "Kühlung", [("eigen", "eigenbelüftet (IC 411)"), ("fremd", "fremdbelüftet (IC 416)")],
                    "eigen"),
        NumberField("fmin", "Kleinste Betriebsfrequenz", "f_min", "Hz", 20, min=0, min_inclusive=True, decimals=1),
        NumberField("fmax", "Größte Betriebsfrequenz", "f_max", "Hz", 60, min=1, decimals=1),
        ChoiceField("last", "Lastkennlinie", [("konstant", "konstantes Moment"),
                                              ("quadratisch", "quadratisch (Pumpe, Lüfter)")], "konstant"),
        NumberField("ML", "Lastmoment bei Bemessungsfrequenz", "M_L", "N*m", 20, min=0, min_inclusive=True, decimals=2),
        NumberField("ueber", "Überlastfähigkeit FU (60 s)", "I_max/I_FU", "percent", 150, min=100, max=300, decimals=0),
        ChoiceField("bremsen", "Bremsbetrieb", [("keins", "kein generatorischer Betrieb"),
                                                ("massen", "Massen abbremsen"), ("hub", "Senken (Hubwerk)")], "massen"),
        NumberField("J", "Massenträgheit gesamt (Motorwelle)", "J_ges", "kg*m**2", 0.1, min=0, decimals=4,
                    visible_if=BREMS_J),
        NumberField("tb", "Bremszeit", "t_Br", "s", 1.0, min=0, decimals=2, visible_if=BREMS_J),
        NumberField("m", "Last beim Senken", "m", "kg", 500, min=0, decimals=0, visible_if=BREMS_H),
        NumberField("v", "Senkgeschwindigkeit", "v", "m/s", 0.5, min=0, decimals=3, visible_if=BREMS_H),
        NumberField("eta_mech", "Wirkungsgrad Mechanik (generatorisch)", "η_mech", "percent", 85, min=10, max=100,
                    decimals=0, visible_if=BREMS_H),
        NumberField("ED", "Bremseinschaltdauer", "ED_Br", "percent", 20, min=1, max=100, decimals=0,
                    visible_if=BREMS, tooltip="Anteil der Bremszeit an der Spielzeit (z. B. 120 s)"),
        NumberField("Rmin", "Mindestwiderstand des FU (Datenblatt)", "R_min", "ohm", 56, min=0, decimals=1,
                    visible_if=BREMS),
        NumberField("Udc", "Einschaltschwelle Bremschopper", "U_DC", "V", 780, min=100, decimals=0, visible_if=BREMS,
                    tooltip="400-V-Netz typisch 750–800 V"),
    ]

    def compute(self, inp) -> None:
        md = MotorDaten(inp)
        eck = md.f * (math.sqrt(3) if inp["schaltung"] == "87" else 1.0)
        fu = MotorFU(md, eck, inp["kuehlung"])
        fmin, fmax = inp["fmin"].to("Hz").magnitude, inp["fmax"].to("Hz").magnitude
        if fmax <= fmin:
            raise ValueError("Die größte Frequenz muss über der kleinsten liegen.")
        if inp["schaltung"] == "87":
            PN87 = md.PN * math.sqrt(3)
            IN = md.IN * math.sqrt(3)
            self.step("87-Hz-Kennlinie", "U/f bis 87 Hz konstant (Δ an 400 V): P ≈ √3·P_N, I ≈ √3·I_N(400 V)",
                      f"I_N,Δ = {fmt_num(IN, 2)} A", f"P = {fmt_num(PN87 / 1000, 2)} kW bei 87 Hz")
        else:
            IN = md.IN
        self.step("Eckfrequenz", "Grunddrehzahlbereich bis f_Eck, darüber Feldschwächung", "",
                  f"f_Eck = {fmt_num(eck, 1)} Hz, n_Eck ≈ {fmt_num(md.nN * eck / md.f, 0)} 1/min")
        fs = np.linspace(max(fmin, 0.5), fmax, 200)
        ML = inp["ML"].to("N*m").magnitude
        ml = ML if inp["last"] == "konstant" else ML * (fs / md.f) ** 2
        ml = np.broadcast_to(ml, fs.shape)
        md_zul = fu.m_dauer(fs)
        mk = fu.m_kipp(fs)
        ausl = float(np.max(ml / md_zul))
        f_krit = float(fs[np.argmax(ml / md_zul)])
        kipp_res = float(np.min(mk / np.maximum(ml, 1e-9)))
        self.step("Dauerbetrieb im Stellbereich", "M_L(f) ≤ M_zul(f) (Kühlung, Feldschwächung)",
                  f"{fmt_num(fmin, 1)} … {fmt_num(fmax, 1)} Hz, ungünstigste Stelle {fmt_num(f_krit, 1)} Hz",
                  f"Auslastung max. {fmt_num(ausl * 100, 0)} %")
        I_last = float(np.max(np.where(fs <= eck, ml / md.MN, ml * fs / (md.MN * eck)))) * IN
        I_FU = max(I_last, IN) * 1.0
        ueb = inp["ueber"].to("percent").magnitude / 100
        self.step("Umrichter-Ausgangsstrom", "I_FU ≥ max(I_Motor im Stellbereich, I_N)",
                  f"Überlast {fmt_num(ueb * 100, 0)} % → Beschleunigungsmoment bis ≈ {fmt_num(ueb, 2)}·M_N",
                  f"I_FU ≥ {fmt_num(I_FU, 2)} A")
        self.result("feck", "Eckfrequenz", "f_Eck", Q_(eck, "Hz"), "Hz", 1)
        self.result("ausl", "Höchste Motorauslastung im Stellbereich", "M_L/M_zul", Q_(ausl * 100, "percent"),
                    "percent", 0, highlight=True)
        self.result("fkrit", "Kritische Frequenz", "f_krit", Q_(f_krit, "Hz"), "Hz", 1)
        self.result("kipp", "Kippreserve (min.)", "M_K/M_L", Q_(kipp_res, ""), "", 2)
        self.result("IFU", "Erforderlicher FU-Ausgangsstrom", "I_FU", Q_(I_FU, "A"), "A", 2, highlight=True)
        self.result("nmax", "Höchste Drehzahl", "n_max", Q_(md.nN * fmax / md.f, "1/minute"), "1/minute", 0)
        if ausl > 1.0:
            self.warn(f"Bei {fmt_num(f_krit, 1)} Hz übersteigt das Lastmoment das zulässige Dauermoment "
                      f"({fmt_num(ausl * 100, 0)} %) – " + ("Fremdlüfter, " if inp["kuehlung"] == "eigen" else "")
                      + "größerer Motor oder andere Übersetzung.")
        if kipp_res < 1.6:
            self.warn(f"Kippreserve nur {fmt_num(kipp_res, 2)} im Feldschwächbereich – f_max senken (Kippmoment ~ 1/f²).")
        if fmax > 2 * eck:
            self.warn("f_max > 2·f_Eck – mechanische Grenzdrehzahl (Lager, Lüfter, Wuchtgüte) beim Hersteller prüfen.")

        br = inp["bremsen"]
        if br != "keins":
            if br == "massen":
                J = inp["J"].to("kg*m**2").magnitude
                w = 2 * math.pi * md.nN * fmax / md.f / 60
                E = J * w**2 / 2 * md.eta
                tb = inp["tb"].to("s").magnitude
                P_peak = 2 * E / tb          # lineare Rampe: Leistung fällt linear auf 0
                self.step("Bremsenergie", "E = J·ω²/2 · η_Motor;  P_Br,max = 2E/t_Br (lineare Rampe)",
                          f"ω = {fmt_num(w, 1)} 1/s, t_Br = {fmt_num(tb, 2)} s",
                          f"E = {fmt_num(E / 1000, 2)} kJ, P_max = {fmt_num(P_peak / 1000, 2)} kW")
                P_mean_br = E / tb
            else:
                m, v = inp["m"].to("kg").magnitude, inp["v"].to("m/s").magnitude
                eta_m = inp["eta_mech"].to("percent").magnitude / 100
                P_peak = m * G * v * eta_m * md.eta
                P_mean_br = P_peak
                self.step("Senkleistung", "P_Br = m·g·v·η_mech·η_Motor", f"m = {fmt_num(m, 0)} kg, v = {fmt_num(v, 3)} m/s",
                          f"{fmt_num(P_peak / 1000, 2)} kW")
            Udc = inp["Udc"].to("V").magnitude
            Rmax = Udc**2 / P_peak if P_peak > 0 else float("inf")
            Rmin = inp["Rmin"].to("ohm").magnitude
            ED = inp["ED"].to("percent").magnitude / 100
            P_dauer = P_mean_br * ED
            self.step("Bremswiderstand", "R_min ≤ R ≤ U_DC²/P_Br,max;  P_Dauer = P̄_Br · ED",
                      f"U_DC = {fmt_num(Udc, 0)} V, ED = {fmt_num(ED * 100, 0)} %",
                      f"R ≤ {fmt_num(Rmax, 1)} Ω, P_Dauer ≥ {fmt_num(P_dauer, 0)} W")
            self.result("Pbr", "Spitzen-Bremsleistung", "P_Br", Q_(P_peak, "W"), "kW", 2, highlight=True)
            self.result("Rmax", "Größter Bremswiderstand", "R_max", Q_(Rmax, "ohm"), "ohm", 1, highlight=True)
            self.result("Pdauer", "Dauerleistung Bremswiderstand", "P_Dauer", Q_(P_dauer, "W"), "W", 0, highlight=True)
            if Rmax < Rmin:
                self.warn(f"Erforderlicher Widerstand ({fmt_num(Rmax, 1)} Ω) kleiner als der FU-Mindestwert "
                          f"({fmt_num(Rmin, 1)} Ω) – längere Bremszeit, größerer FU oder Rückspeiseeinheit.")
            else:
                self.info(f"Bremswiderstand zwischen {fmt_num(Rmin, 1)} Ω und {fmt_num(Rmax, 1)} Ω wählen, "
                          f"Dauerleistung ≥ {fmt_num(P_dauer, 0)} W (Spitzenbelastbarkeit nach Datenblatt).")
        self.info("Zulässiges Dauermoment bei Eigenbelüftung als Richtwertkurve; Herstellerangaben zur "
                  "Umrichtertauglichkeit (Isolation, Lagerströme, dU/dt) beachten.")

    def plot(self, fig, raw, result) -> bool:
        if not result.ok:
            return False
        inp = {}
        for f in self.fields:
            v = (self.defaults() | raw)[f.key]
            inp[f.key] = Q_(float(v), f.unit) if isinstance(f, NumberField) and f.unit else v
        md = MotorDaten(inp)
        eck = result.value("feck")
        fu = MotorFU(md, eck, inp["kuehlung"])
        fmax = float(raw["fmax"])
        fs = np.linspace(0.5, max(fmax * 1.1, eck * 1.2), 200)
        ax = fig.subplots()
        ax.plot(fs, fu.m_dauer(fs), color="#c0392b", lw=2, label="zul. Dauermoment")
        ax.plot(fs, fu.m_kipp(fs), color="#c0392b", lw=1, ls="--", label="Kippmoment")
        ML = float(raw["ML"])
        ml = np.full_like(fs, ML) if raw.get("last") == "konstant" else ML * (fs / md.f) ** 2
        ax.plot(fs, ml, color="#1f6fb2", lw=2, label="Lastmoment")
        ax.axvspan(float(raw["fmin"]), fmax, color="#dce6f1", alpha=0.4, label="Stellbereich")
        ax.axvline(eck, color="#6b7b8c", ls=":", lw=1)
        ax.set_xlabel("Frequenz f  [Hz]")
        ax.set_ylabel("Moment  [N·m]")
        ax.set_title("Drehmomentgrenzen am Frequenzumrichter")
        ax.set_ylim(0, md.mk * md.MN * 1.1)
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=8)
        return True

    def sketch_svg(self, raw) -> str:
        s = Svg()
        s.rect(20, 80, 80, 60, fill="#eef3f8").text(60, 115, "FU", 14, INK, bold=True)
        s.line(100, 110, 150, 110, INK, 2).circle(180, 110, 30, fill="#f5d7d3").text(180, 115, "M 3~", 11, INK, bold=True)
        s.line(210, 110, 260, 110, INK, 5).circle(290, 110, 26, fill="#dce6f1")
        if raw.get("bremsen", "massen") != "keins":
            s.line(60, 140, 60, 170, INK, 2).rect(40, 170, 40, 20, fill="#e59866").text(60, 206, "R_Br", 10, INK)
        s.text(180, 40, "U/f-Kennlinie bis zur Eckfrequenz", 11, MUTED)
        return s.render()
