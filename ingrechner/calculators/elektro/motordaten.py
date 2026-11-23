"""Asynchronmotor – Kenndaten aus dem Typenschild, Drehmomentkennlinie (Kloss) und Betriebspunkt mit der Last."""

from __future__ import annotations

import math

import numpy as np

from ingrechner.calculators.pumpen._pumpe import nullstelle
from ingrechner.core.model import Calculator, ChoiceField, NumberField
from ingrechner.core.svg import ACCENT, INK, MUTED, Svg
from ingrechner.core.units import Q_, fmt_num

from ._motor import Kennlinie, polzahl, strom, synchron, teillast

LAST = {"last": ["konstant", "quadratisch", "linear"]}


def motor_felder(PN: float = 4.0, nN: float = 1445) -> list:
    """Typenschild-/Katalogfelder (gemeinsam für Motordaten, Anlauf und FU)."""
    return [
        NumberField("PN", "Bemessungsleistung", "P_N", "kW", PN, min=0, decimals=2),
        NumberField("UN", "Bemessungsspannung (verkettet)", "U_N", "V", 400, min=0, decimals=0),
        NumberField("f", "Bemessungsfrequenz", "f_N", "Hz", 50, min=1, decimals=0),
        NumberField("nN", "Bemessungsdrehzahl", "n_N", "1/minute", nN, min=0, decimals=0),
        NumberField("eta", "Wirkungsgrad", "η_N", "percent", 88.6, min=10, max=99.9, decimals=1),
        NumberField("cosphi", "Leistungsfaktor", "cos φ_N", "", 0.82, min=0.1, max=1, decimals=2),
        NumberField("ia", "Anlaufstromverhältnis", "I_A/I_N", "", 7.0, min=1, max=15, decimals=1),
        NumberField("ma", "Anlaufmomentverhältnis", "M_A/M_N", "", 2.3, min=0.2, max=5, decimals=1),
        NumberField("mk", "Kippmomentverhältnis", "M_K/M_N", "", 2.9, min=1.1, max=6, decimals=1),
    ]


class MotorDaten:
    """Abgeleitete Größen eines Asynchronmotors aus den Typenschilddaten."""

    def __init__(self, inp) -> None:
        self.PN = inp["PN"].to("W").magnitude
        self.UN = inp["UN"].to("V").magnitude
        self.f = inp["f"].to("Hz").magnitude
        self.nN = inp["nN"].to("1/minute").magnitude
        self.eta = inp["eta"].to("percent").magnitude / 100
        self.cosphi = float(inp["cosphi"])
        self.ia, self.ma, self.mk = float(inp["ia"]), float(inp["ma"]), float(inp["mk"])
        self.pole = polzahl(self.f, self.nN)
        self.n_syn = synchron(self.f, self.pole)
        if self.nN >= self.n_syn:
            raise ValueError("Die Bemessungsdrehzahl muss unter der Synchrondrehzahl liegen.")
        self.sN = 1 - self.nN / self.n_syn
        self.MN = self.PN / (2 * math.pi * self.nN / 60)
        self.P1 = self.PN / self.eta
        self.IN = self.P1 / (math.sqrt(3) * self.UN * self.cosphi)
        self.kl = Kennlinie(self.MN, self.sN, self.mk, self.ma)

    def M(self, n):
        return self.kl.M(1 - np.asarray(n, dtype=float) / self.n_syn)


def last_moment(art: str, ML: float, n, n_ref: float, M0: float = 0.0):
    """Lastmoment über der Drehzahl: konstant, quadratisch (Pumpe/Lüfter) oder linear; M0 = Losbrechmoment."""
    n = np.asarray(n, dtype=float)
    x = n / n_ref
    if art == "quadratisch":
        m = ML * x**2
    elif art == "linear":
        m = ML * x
    else:
        m = np.full_like(n, ML)
    return np.maximum(m, np.where(n < 0.02 * n_ref, M0, 0.0))


class Motordaten(Calculator):
    id = "et.motordaten"
    title = "Asynchronmotor – Kenndaten & Kennlinie"
    category = "Elektrotechnik"
    description = (
        "Kenndaten eines Drehstrom-Asynchronmotors aus Typenschild bzw. Katalog: Polzahl, Synchrondrehzahl, "
        "Schlupf, Nennmoment, Nennstrom, Schein- und Blindleistung, Anlauf- und Kippmoment; Drehmoment-Drehzahl-"
        "Kennlinie nach Kloss (an das Anlaufmoment angepasst), Betriebspunkt mit der Lastkennlinie und "
        "Teillastverhalten von Wirkungsgrad, Leistungsfaktor und Strom."
    )
    norm = "I_N = P_N/(√3·U·η·cos φ); M = 2·M_K/(s/s_K + s_K/s) (Kloss); s_K = s_N·(k + √(k²−1)), k = M_K/M_N"
    keywords = ("asynchronmotor", "motor", "typenschild", "nennstrom", "nennmoment", "schlupf", "kippmoment",
                "anlaufmoment", "kloss", "kennlinie", "betriebspunkt", "teillast", "polzahl", "drehstrom")

    fields = [
        *motor_felder(),
        ChoiceField("last", "Lastkennlinie", [("keine", "ohne Last"), ("konstant", "konstantes Moment"),
                                              ("quadratisch", "quadratisch (Pumpe, Lüfter)"),
                                              ("linear", "linear steigend")], "konstant"),
        NumberField("ML", "Lastmoment bei Bemessungsdrehzahl", "M_L", "N*m", 22, min=0, min_inclusive=True,
                    decimals=2, visible_if=LAST, tooltip="An der Motorwelle (nach Getriebe: M_Last/(i·η))"),
    ]

    def compute(self, inp) -> None:
        md = MotorDaten(inp)
        S = math.sqrt(3) * md.UN * md.IN
        Q = S * math.sin(math.acos(md.cosphi))
        self.step("Polzahl und Schlupf", "n_syn = 120·f/2p;  s_N = 1 − n_N/n_syn",
                  f"f = {fmt_num(md.f, 0)} Hz, n_N = {fmt_num(md.nN, 0)} 1/min",
                  f"{md.pole}-polig, n_syn = {fmt_num(md.n_syn, 0)} 1/min, s_N = {fmt_num(md.sN * 100, 2)} %")
        self.step("Nennmoment", "M_N = P_N / (2π·n_N/60)", f"P_N = {fmt_num(md.PN / 1000, 2)} kW",
                  f"{fmt_num(md.MN, 2)} N·m")
        self.step("Nennstrom", "I_N = P_N / (√3·U_N·η·cos φ)",
                  f"I_N = {fmt_num(md.PN, 0)} W / (√3·{fmt_num(md.UN, 0)} V·{fmt_num(md.eta, 3)}·{fmt_num(md.cosphi, 2)})",
                  f"{fmt_num(md.IN, 2)} A")
        self.step("Kippschlupf", "s_K = s_N·(k + √(k² − 1));  k = M_K/M_N", f"k = {fmt_num(md.mk, 2)}",
                  f"s_K = {fmt_num(md.kl.sK * 100, 1)} %")
        self.result("IN", "Bemessungsstrom", "I_N", Q_(md.IN, "A"), "A", 2, highlight=True)
        self.result("MN", "Bemessungsmoment", "M_N", Q_(md.MN, "N*m"), "N*m", 2, highlight=True)
        self.result("pole", "Polzahl", "2p", Q_(md.pole, ""), "", 0)
        self.result("nsyn", "Synchrondrehzahl", "n_syn", Q_(md.n_syn, "1/minute"), "1/minute", 0)
        self.result("sN", "Bemessungsschlupf", "s_N", Q_(md.sN * 100, "percent"), "percent", 2)
        self.result("P1", "Aufgenommene Wirkleistung", "P₁", Q_(md.P1, "W"), "kW", 2)
        self.result("S", "Scheinleistung", "S", Q_(S, "V*A"), "kV*A", 2)
        self.result("Q", "Blindleistung", "Q", Q_(Q, "var"), "kvar", 2)
        self.result("IA", "Anlaufstrom (direkt)", "I_A", Q_(md.ia * md.IN, "A"), "A", 1)
        self.result("MA", "Anlaufmoment", "M_A", Q_(md.ma * md.MN, "N*m"), "N*m", 1)
        self.result("MK", "Kippmoment", "M_K", Q_(md.mk * md.MN, "N*m"), "N*m", 1)
        self.result("sK", "Kippschlupf", "s_K", Q_(md.kl.sK * 100, "percent"), "percent", 1)
        if inp["last"] != "keine":
            ML = inp["ML"].to("N*m").magnitude
            f = lambda n: float(md.M(n) - last_moment(inp["last"], ML, n, md.nN))  # noqa: E731
            nk = md.n_syn * (1 - md.kl.sK)
            nB = nullstelle(f, nk, md.n_syn * 0.99999)
            if nB is None:
                self.error("Kein stabiler Betriebspunkt: Das Lastmoment übersteigt das Kippmoment.")
                return
            MB = float(last_moment(inp["last"], ML, nB, md.nN))
            x = MB * nB / (md.MN * md.nN)
            IB = strom(md.IN, md.cosphi, MB / md.MN)
            eta_B = teillast(md.eta, x)
            self.step("Betriebspunkt", "M_Motor(n_B) = M_Last(n_B)", "Bisektion zwischen Kipp- und Synchrondrehzahl",
                      f"n_B = {fmt_num(nB, 0)} 1/min, M_B = {fmt_num(MB, 2)} N·m, Last {fmt_num(x * 100, 0)} %")
            self.result("nB", "Drehzahl im Betriebspunkt", "n_B", Q_(nB, "1/minute"), "1/minute", 0, highlight=True)
            self.result("MB", "Moment im Betriebspunkt", "M_B", Q_(MB, "N*m"), "N*m", 2)
            self.result("xB", "Auslastung", "P/P_N", Q_(x * 100, "percent"), "percent", 0, highlight=True)
            self.result("IB", "Strom im Betriebspunkt (Näherung)", "I_B", Q_(IB, "A"), "A", 2)
            self.result("etaB", "Wirkungsgrad im Betriebspunkt (Näherung)", "η_B", Q_(eta_B * 100, "percent"), "percent", 1)
            if x > 1.05:
                self.warn(f"Überlast {fmt_num(x * 100, 0)} % – Wicklungserwärmung; größeren Motor wählen.")
            if ML > 0 and md.ma * md.MN < float(last_moment(inp["last"], ML, 0.0, md.nN)) * 1.1:
                self.warn("Anlaufmoment knapp unter dem Lastmoment im Stillstand – Losbrechen nicht gesichert.")
        self.info("Kennlinie nach Kloss mit Anpassung an M_A; Teillastwerte als Näherung (lastunabhängige Verluste ≈ 40 %). "
                  "Für Nachweise Herstellerkennlinien verwenden.")

    def plot(self, fig, raw, result) -> bool:
        if not result.ok:
            return False
        inp = {f.key: (Q_(float(raw[f.key]), f.unit) if getattr(f, "unit", "") else raw[f.key]) for f in self.fields
               if f.key in raw}
        inp = {**{f.key: (Q_(float(f.default), f.unit) if getattr(f, "unit", "") else f.default) for f in self.fields},
               **inp}
        md = MotorDaten(inp)
        n = np.linspace(0, md.n_syn, 300)
        ax1, ax2 = fig.subplots(1, 2, gridspec_kw={"width_ratios": [1.4, 1]})
        ax1.plot(n, md.M(n), color="#c0392b", lw=2, label="Motormoment")
        if raw.get("last", "keine") != "keine":
            ax1.plot(n, last_moment(raw["last"], float(raw["ML"]), n, md.nN), color="#1f6fb2", lw=2, label="Lastmoment")
            if "nB" in [v.key for v in result.values]:
                ax1.plot([result.value("nB")], [result.value("MB")], "o", color="#2b3a4a")
        ax1.axhline(md.MN, color="#6b7b8c", ls=":", lw=1, label="M_N")
        ax1.set_xlabel("Drehzahl n  [1/min]")
        ax1.set_ylabel("Drehmoment M  [N·m]")
        ax1.set_title("Drehmomentkennlinie")
        ax1.grid(True, alpha=0.3)
        ax1.legend(fontsize=8)
        xs = np.linspace(0.1, 1.25, 60)
        ax2.plot(xs * 100, [teillast(md.eta, x) * 100 for x in xs], color="#27ae60", lw=2, label="η")
        ax2.plot(xs * 100, [strom(md.IN, md.cosphi, x) / md.IN * 100 for x in xs], color="#d68910", lw=2,
                 label="I/I_N")
        ax2.set_xlabel("Last P/P_N  [%]")
        ax2.set_ylabel("[%]")
        ax2.set_title("Teillast (Näherung)")
        ax2.grid(True, alpha=0.3)
        ax2.legend(fontsize=8)
        return True

    def sketch_svg(self, raw) -> str:
        s = Svg()
        s.line(40, 190, 330, 190, INK, 1.5).line(40, 190, 40, 30, INK, 1.5)
        pts = [(40, 100), (100, 110), (160, 105), (220, 70), (255, 45), (285, 90), (315, 190)]
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            s.line(x1, y1, x2, y2, "#c0392b", 2.4)
        s.line(40, 150, 330, 150, ACCENT, 2)
        s.text(330, 208, "n", 12, INK, "end", True).text(30, 36, "M", 12, INK, "end", True)
        s.text(48, 92, "M_A", 10, MUTED, "start").text(255, 36, "M_K", 10, MUTED).text(305, 142, "B", 11, INK, bold=True)
        return s.render()
