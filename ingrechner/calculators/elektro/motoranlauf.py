"""Asynchronmotor – Anlauf & Hochlauf: Anlaufarten, Hochlaufzeit, Anlaufwärme, Schalthäufigkeit, Spannungsfall."""

from __future__ import annotations

import math

import numpy as np

from ingrechner.core.model import Calculator, ChoiceField, NumberField
from ingrechner.core.svg import ACCENT, INK, MUTED, Svg
from ingrechner.core.units import Q_, fmt_num

from .motordaten import MotorDaten, last_moment, motor_felder

SANFT = {"art": ["sanft"]}
FU = {"art": ["fu"]}
LEITUNG = {"leitung": ["ja"]}
KAPPA_CU = 56.0 / (1 + 0.00393 * 50)        # S·m/mm² bei 70 °C


class Anlauf:
    """Motor- und Strommoment über der Drehzahl je Anlaufart."""

    def __init__(self, md: MotorDaten, art: str, k_i: float, M_fu: float) -> None:
        self.md, self.art, self.k_i, self.M_fu = md, art, k_i, M_fu

    def faktor(self, n):
        """Moment- und Stromfaktor gegenüber Direktanlauf (Spannungsabsenkung: M ~ U², I ~ U)."""
        n = np.asarray(n, dtype=float)
        if self.art == "stern_dreieck":
            stern = n < 0.85 * self.md.nN
            return np.where(stern, 1 / 3, 1.0), np.where(stern, 1 / 3, 1.0)
        if self.art == "sanft":
            # Strombegrenzung auf k_i · I_N: Spannungsfaktor u = min(1, k_i / (I_direkt/I_N))
            I_dir = self.strom_direkt(n) / self.md.IN
            u = np.minimum(1.0, self.k_i / np.maximum(I_dir, 1e-9))
            return u**2, u
        return np.ones_like(n), np.ones_like(n)

    def strom_direkt(self, n):
        """Strom bei Direktanlauf (Näherung): von I_A im Stillstand auf I_N bei Bemessungsdrehzahl."""
        md = self.md
        s = 1 - np.asarray(n, dtype=float) / md.n_syn
        s = np.clip(s, md.sN, 1.0)
        return md.IN * np.sqrt(1 + (md.ia**2 - 1) * ((s - md.sN) / (1 - md.sN)) ** 0.6)

    def M(self, n):
        if self.art == "fu":
            return np.full_like(np.asarray(n, dtype=float), self.M_fu)
        fm, _ = self.faktor(n)
        return self.md.M(n) * fm

    def I(self, n):
        if self.art == "fu":
            return np.full_like(np.asarray(n, dtype=float), self.md.IN * max(self.M_fu / self.md.MN, 0.4))
        _, fi = self.faktor(n)
        return self.strom_direkt(n) * fi


class Motoranlauf(Calculator):
    id = "et.motoranlauf"
    title = "Asynchronmotor – Anlauf & Hochlauf"
    category = "Elektrotechnik"
    description = (
        "Anlauf eines Asynchronmotors direkt, in Stern-Dreieck, mit Sanftanlauf (Strombegrenzung) oder am "
        "Frequenzumrichter: Anlaufstrom und -moment, Losbrechprüfung, Hochlaufzeit durch Integration von Motor- "
        "minus Lastmoment, Anlaufwärme im Läufer, zulässige Schalthäufigkeit und Spannungsfall der Zuleitung beim Anlauf."
    )
    norm = "t_A = ∫ J_ges·dω / (M_M(n) − M_L(n)); W_R = ∫ M_M·ω_syn·s dt; Z = Z₀·J_M/J_ges·(1 − M_L/M_H)"
    keywords = ("anlauf", "hochlauf", "hochlaufzeit", "stern-dreieck", "sanftanlauf", "softstarter", "direktanlauf",
                "anlaufstrom", "anlaufmoment", "losbrechmoment", "schalthäufigkeit", "massenträgheit",
                "spannungsfall", "motor", "asynchronmotor")

    fields = [
        *motor_felder(),
        NumberField("JM", "Massenträgheit Motor", "J_M", "kg*m**2", 0.013, min=0, decimals=4),
        ChoiceField("art", "Anlaufart", [("direkt", "Direktanlauf"), ("stern_dreieck", "Stern-Dreieck"),
                                         ("sanft", "Sanftanlauf (Strombegrenzung)"), ("fu", "Frequenzumrichter")],
                    "direkt"),
        NumberField("ki", "Strombegrenzung Sanftanlauf", "I_max/I_N", "", 3.5, min=1, max=8, decimals=1,
                    visible_if=SANFT),
        NumberField("mfu", "Beschleunigungsmoment FU", "M_FU/M_N", "", 1.5, min=0.5, max=2.5, decimals=2,
                    visible_if=FU, tooltip="Begrenzt durch den Überlaststrom des Umrichters (typisch 150 % für 60 s)"),
        ChoiceField("last", "Lastkennlinie", [("konstant", "konstantes Moment"),
                                              ("quadratisch", "quadratisch (Pumpe, Lüfter)"),
                                              ("linear", "linear steigend")], "quadratisch",
                    tooltip="Konstantes Moment mit Sanftanlauf/Stern-Dreieck nur bei kleinem Lastmoment"),
        NumberField("ML", "Lastmoment bei Bemessungsdrehzahl (Motorwelle)", "M_L", "N*m", 20, min=0,
                    min_inclusive=True, decimals=2),
        NumberField("M0", "Losbrechmoment (Motorwelle)", "M_L0", "N*m", 0, min=0, min_inclusive=True, decimals=2,
                    tooltip="Haftreibung im Stillstand, z. B. Förderband 1,2–1,5 · M_L; 0 = wie Lastkennlinie"),
        NumberField("JL", "Massenträgheit Last (auf Motorwelle reduziert)", "J_L'", "kg*m**2", 0.08, min=0,
                    min_inclusive=True, decimals=4, tooltip="J_L/i² bzw. m·(v/ω)² – z. B. aus „Getriebe – Antriebsauslegung“"),
        NumberField("Z0", "Leerschalthäufigkeit (Katalog)", "Z₀", "1/hour", 2000, min=0, min_inclusive=True,
                    decimals=0, tooltip="Zulässige Schaltungen/h ohne Last und Zusatzmasse; 0 = ohne Prüfung"),
        ChoiceField("leitung", "Spannungsfall beim Anlauf", [("nein", "nicht prüfen"), ("ja", "Zuleitung prüfen")], "ja"),
        NumberField("L", "Leitungslänge (einfach)", "L", "m", 60, min=0, decimals=1, visible_if=LEITUNG),
        NumberField("S", "Querschnitt Cu", "S", "mm**2", 2.5, min=0, decimals=1, visible_if=LEITUNG),
        NumberField("du_max", "Zulässiger Spannungsfall beim Anlauf", "Δu_A", "percent", 10, min=0, decimals=1,
                    visible_if=LEITUNG),
    ]

    def _hochlauf(self, an: Anlauf, md: MotorDaten, inp):
        J = inp["JM"].to("kg*m**2").magnitude + inp["JL"].to("kg*m**2").magnitude
        ML = inp["ML"].to("N*m").magnitude
        M0 = inp["M0"].to("N*m").magnitude
        n_end = 0.98 * md.nN
        ns = np.linspace(0, n_end, 600)
        Mm = an.M(ns)
        Ml = last_moment(inp["last"], ML, ns, md.nN, M0)
        Mb = Mm - Ml
        if np.any(Mb <= 0):
            n_stop = float(ns[np.argmax(Mb <= 0)])
            return None, n_stop, J, ns, Mm, Ml
        w = ns * 2 * math.pi / 60
        dt = J * np.diff(w) / ((Mb[1:] + Mb[:-1]) / 2)
        t = np.concatenate([[0.0], np.cumsum(dt)])
        return t, None, J, ns, Mm, Ml

    def compute(self, inp) -> None:
        md = MotorDaten(inp)
        art = inp["art"]
        an = Anlauf(md, art, float(inp["ki"]), float(inp["mfu"]) * md.MN)
        I0, M0m = float(an.I(0.0)), float(an.M(0.0))
        self.step("Bemessungsdaten", "I_N = P_N/(√3·U·η·cos φ);  M_N = P_N/ω_N", "",
                  f"I_N = {fmt_num(md.IN, 2)} A, M_N = {fmt_num(md.MN, 2)} N·m, n_syn = {fmt_num(md.n_syn, 0)} 1/min")
        regel = {"direkt": "I = I_A, M = M_A", "stern_dreieck": "I_Y = I_A/3, M_Y = M_A/3 (Umschaltung bei ≈ 85 % n_N)",
                 "sanft": "Spannung u so, dass I ≤ k·I_N; M ~ u²", "fu": "M = M_FU (konstant), I ≈ I_N·M/M_N"}[art]
        self.step("Anlauf im Stillstand", regel, "", f"I = {fmt_num(I0, 1)} A ({fmt_num(I0 / md.IN, 2)}·I_N), "
                  f"M = {fmt_num(M0m, 1)} N·m ({fmt_num(M0m / md.MN, 2)}·M_N)")
        t, n_stop, J, ns, Mm, Ml = self._hochlauf(an, md, inp)
        self.result("IA", "Anlaufstrom", "I_A", Q_(I0, "A"), "A", 1, highlight=True)
        self.result("MA", "Anlaufmoment", "M_A", Q_(M0m, "N*m"), "N*m", 1, highlight=True)
        self.result("IN", "Bemessungsstrom", "I_N", Q_(md.IN, "A"), "A", 2)
        if t is None:
            self.error(f"Kein Hochlauf: Das Motormoment unterschreitet bei n ≈ {fmt_num(n_stop, 0)} 1/min das Lastmoment"
                       + (" (Stern-Dreieck: Lastmoment im Stern zu groß)." if art == "stern_dreieck" else "."))
            return
        tA = float(t[-1])
        w_syn = 2 * math.pi * md.n_syn / 60
        s = 1 - ns / md.n_syn
        Pv = Mm * w_syn * s
        self.step("Hochlaufzeit", "t_A = ∫ J_ges·dω / (M_M(n) − M_L(n))  (numerisch bis 98 % n_N)",
                  f"J_ges = {fmt_num(J, 4)} kg·m²", f"t_A = {fmt_num(tA, 2)} s")
        self.result("tA", "Hochlaufzeit", "t_A", Q_(tA, "s"), "s", 2, highlight=True)
        if art != "fu":
            WR = float(np.sum((Pv[1:] + Pv[:-1]) / 2 * np.diff(t)))
            self.step("Anlaufwärme im Läufer", "W_R = ∫ M_M·ω_syn·s dt", "", f"{fmt_num(WR / 1000, 2)} kJ")
            self.result("WR", "Anlaufwärme im Läufer", "W_R", Q_(WR, "J"), "kJ", 2)
        self.result("J", "Massenträgheit gesamt", "J_ges", Q_(J, "kg*m**2"), "kg*m**2", 4)
        Z0 = inp["Z0"].to("1/hour").magnitude
        if Z0 > 0:
            MH = float(np.mean(Mm))
            ML_m = float(np.mean(Ml))
            Z = Z0 * inp["JM"].to("kg*m**2").magnitude / J * max(0.0, 1 - ML_m / MH)
            self.step("Zulässige Schalthäufigkeit", "Z = Z₀ · J_M/J_ges · (1 − M_L,m/M_H,m)",
                      f"Z₀ = {fmt_num(Z0, 0)} 1/h, M_H,m = {fmt_num(MH, 1)} N·m, M_L,m = {fmt_num(ML_m, 1)} N·m",
                      f"Z ≈ {fmt_num(Z, 0)} 1/h")
            self.result("Z", "Zulässige Schalthäufigkeit (Richtwert)", "Z", Q_(Z, "1/hour"), "1/hour", 0)
        if inp["leitung"] == "ja":
            L, S = inp["L"].to("m").magnitude, inp["S"].to("mm**2").magnitude
            R = L / (KAPPA_CU * S)
            X = 0.08e-3 * L
            cos_a = 0.35 if art != "fu" else md.cosphi
            du = math.sqrt(3) * I0 * (R * cos_a + X * math.sqrt(1 - cos_a**2)) / md.UN * 100
            self.step("Spannungsfall beim Anlauf", "Δu = √3·I_A·(R·cos φ_A + X·sin φ_A)/U_N",
                      f"R = {fmt_num(R * 1000, 1)} mΩ, X = {fmt_num(X * 1000, 1)} mΩ, cos φ_A ≈ {fmt_num(cos_a, 2)}",
                      f"{fmt_num(du, 2)} %")
            self.result("duA", "Spannungsfall beim Anlauf", "Δu_A", Q_(du, "percent"), "percent", 2, highlight=True)
            if du > inp["du_max"].to("percent").magnitude:
                self.warn(f"Spannungsfall beim Anlauf {fmt_num(du, 1)} % – Querschnitt erhöhen oder Anlaufstrom begrenzen "
                          "(Stern-Dreieck, Sanftanlauf, FU). Netzimpedanz zusätzlich beachten.")
            self.info("Spannungsfall nur über die Zuleitung (ohne Netz-/Trafoimpedanz).")
        if art == "stern_dreieck":
            self.info("Stern-Dreieck: Umschaltstromspitze beim Wechsel auf Dreieck; nur für Lasten mit kleinem "
                      "Anlaufmoment (≤ ≈ 1/3 · M_A) geeignet.")
        if tA > 10:
            self.warn(f"Hochlaufzeit {fmt_num(tA, 1)} s lang – Motorschutz (Schweranlauf, Klasse 20/30) und "
                      "Läufererwärmung prüfen.")
        self.info("Stromverlauf und Kennlinie als Näherung (Kloss, angepasst an M_A); Herstellerdaten haben Vorrang.")

    def plot(self, fig, raw, result) -> bool:
        if "tA" not in [v.key for v in result.values]:
            return False
        inp = {}
        for f in self.fields:
            v = (self.defaults() | raw)[f.key]
            inp[f.key] = Q_(float(v), f.unit) if isinstance(f, NumberField) and f.unit else v
        md = MotorDaten(inp)
        an = Anlauf(md, inp["art"], float(inp["ki"]), float(inp["mfu"]) * md.MN)
        t, _, _, ns, Mm, Ml = self._hochlauf(an, md, inp)
        ax1, ax2 = fig.subplots(1, 2)
        ax1.plot(ns, Mm, color="#c0392b", lw=2, label="Motor")
        ax1.plot(ns, Ml, color="#1f6fb2", lw=2, label="Last")
        ax1b = ax1.twinx()
        ax1b.plot(ns, an.I(ns), color="#d68910", lw=1.4, ls="--", label="Strom")
        ax1b.set_ylabel("Strom  [A]", color="#d68910")
        ax1.set_xlabel("Drehzahl  [1/min]")
        ax1.set_ylabel("Moment  [N·m]")
        ax1.set_title("Momente beim Hochlauf")
        ax1.grid(True, alpha=0.3)
        ax1.legend(fontsize=8, loc="upper left")
        ax2.plot(t, ns, color="#27ae60", lw=2)
        ax2.set_xlabel("Zeit  [s]")
        ax2.set_ylabel("Drehzahl  [1/min]")
        ax2.set_title(f"Hochlauf (t_A = {fmt_num(t[-1], 2)} s)")
        ax2.grid(True, alpha=0.3)
        return True

    def sketch_svg(self, raw) -> str:
        s = Svg()
        s.text(60, 40, "L1 L2 L3", 11, INK)
        s.rect(30, 60, 70, 40, fill="#eef3f8").text(65, 85, raw.get("art", "direkt").replace("_", "-")[:8], 10, INK)
        s.line(65, 100, 65, 130, INK, 2)
        s.circle(65, 160, 28, fill="#f5d7d3").text(65, 165, "M 3~", 11, INK, bold=True)
        s.line(93, 160, 160, 160, INK, 5).circle(200, 160, 36, fill="#dce6f1").text(200, 165, "J_L", 11, INK)
        s.arrow(250, 160, 330, 160, ACCENT).text(290, 150, "n(t)", 11, INK, italic=True)
        return s.render()
