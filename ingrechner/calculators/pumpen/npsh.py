"""NPSH-Nachweis: vorhandene Haltedruckhöhe der Anlage gegen die erforderliche der Pumpe (Kavitation)."""

from __future__ import annotations

import numpy as np

from ingrechner.core.model import Calculator, ChoiceField, NumberField
from ingrechner.core.rohrdaten import rohr, rohr_optionen
from ingrechner.core import medien
from ingrechner.core.svg import ACCENT, INK, MUTED, Svg
from ingrechner.core.units import Q_, fmt_num

from ._pumpe import G, medium, medium_felder, medium_hinweise, nullstelle, pumpe_svg, rauheit, rauheit_felder, rohr_dp

ROHR = {"verlust": ["rohr"]}
DIREKT = {"verlust": ["direkt"]}
FREI = {"verlust": ["rohr"], "rohr": ["frei"]}


class NPSH(Calculator):
    id = "pu.npsh"
    title = "NPSH / Kavitation"
    category = "Pumpen"
    description = (
        "Vorhandene Haltedruckhöhe NPSH_A aus Behälterdruck, Dampfdruck, Zulauf- bzw. Saughöhe und Verlusten der "
        "Saugleitung im Vergleich zur erforderlichen NPSH_R der Pumpe mit Sicherheitszuschlag. Dazu die "
        "höchstzulässige Medientemperatur und die erforderliche Mindestzulaufhöhe."
    )
    norm = "NPSH_A = (p_e − p_v)/(ρ·g) + H_z − H_v,s ≥ NPSH_R + S;  DIN EN ISO 17769-1, DIN EN 12723"
    keywords = ("npsh", "kavitation", "haltedruckhöhe", "saughöhe", "zulaufhöhe", "dampfdruck", "saugleitung",
                "npsha", "npshr", "ansaugen", "brunnen", "behälter", "kondensat")

    fields = [
        NumberField("p", "Absolutdruck auf dem Flüssigkeitsspiegel", "p_e", "kPa", 101.3, min=0, decimals=2,
                    tooltip="Offener Behälter: Luftdruck ≈ 101,3 kPa auf Meereshöhe, je 100 m Höhe ≈ −1,2 kPa; "
                            "geschlossene Behälter: Überdruck + Luftdruck; Kondensatbehälter ≈ Dampfdruck"),
        NumberField("hz", "Zulaufhöhe (+) / Saughöhe (−)", "H_z", "m", -2.0, decimals=2,
                    tooltip="Höhe des Flüssigkeitsspiegels über der Pumpen-Laufradmitte; negativ bei Saugbetrieb"),
        *medium_felder(20, mit_pv=True),
        ChoiceField("verlust", "Verluste der Saugleitung", [("rohr", "Aus Saugleitung berechnen"),
                                                            ("direkt", "Verlusthöhe vorgeben")], "rohr"),
        NumberField("Hv", "Verlusthöhe Saugleitung", "H_v,s", "m", 0.5, min=0, min_inclusive=True, decimals=2,
                    visible_if=DIREKT),
        NumberField("V", "Förderstrom", "V̇", "m**3/hour", 20, min=0, decimals=3, visible_if=ROHR),
        ChoiceField("rohr", "Saugleitung", [*rohr_optionen()[:-1], ("frei", "Innendurchmesser eingeben")],
                    "st:DN 80", visible_if=ROHR),
        NumberField("di", "Rohrinnendurchmesser", "d_i", "mm", 82.5, min=0, decimals=1, visible_if=FREI),
        NumberField("L", "Länge der Saugleitung", "L_s", "m", 8, min=0, min_inclusive=True, decimals=1,
                    visible_if=ROHR),
        *rauheit_felder(vis=ROHR),
        NumberField("zeta", "Summe Einzelwiderstände Saugseite", "Σζ_s", "", 3.0, min=0, min_inclusive=True,
                    decimals=2, visible_if=ROHR,
                    tooltip="Einlauf ≈ 0,5; Fußventil mit Saugkorb ≈ 2–3; Bogen ≈ 0,3; Absperrklappe ≈ 0,3"),
        NumberField("npshr", "Erforderliche NPSH der Pumpe", "NPSH_R", "m", 3.0, min=0, decimals=2,
                    tooltip="Aus der NPSH-Kurve des Datenblatts beim Betriebsförderstrom (NPSH3)"),
        NumberField("S", "Sicherheitszuschlag", "S", "m", 0.5, min=0, min_inclusive=True, decimals=2,
                    tooltip="Mindestens 0,5 m; bei heißem Wasser, Kondensat und großen Pumpen höher "
                            "(z. B. 1–1,5 m bzw. NPSH_A ≥ 1,3 · NPSH_R)"),
    ]

    def _verlust(self, inp, rho: float, nu: float) -> tuple[float, float]:
        """Verlusthöhe in m und Geschwindigkeit in der Saugleitung (0, wenn vorgegeben)."""
        if inp["verlust"] == "direkt":
            return inp["Hv"].to("m").magnitude, 0.0
        if inp["rohr"] == "frei":
            di, name = inp["di"].to("m").magnitude, f"d_i = {fmt_num(inp['di'].to('mm').magnitude, 1)} mm"
        else:
            da, s, _ = rohr(inp["rohr"])
            di, name = (da - 2 * s) / 1000, inp["rohr"].split(":", 1)[1]
        V = inp["V"].to("m**3/s").magnitude
        r = rohr_dp(V, di, inp["L"].to("m").magnitude, rauheit(inp), float(inp["zeta"]), rho, nu)
        Hv = (r.dp_r + r.dp_z) / (rho * G)
        self.step("Verluste der Saugleitung", "H_v,s = (λ·L/d_i + Σζ) · v²/(2g)",
                  f"{name}: v = {fmt_num(r.v, 2)} m/s, Re = {fmt_num(r.re, 0)}, λ = {fmt_num(r.lam, 4)}",
                  f"{fmt_num(Hv, 3)} m")
        return Hv, r.v

    def compute(self, inp) -> None:
        med = medium(inp)
        rho, pv = med.rho, med.pv
        p = inp["p"].to("Pa").magnitude
        hz = inp["hz"].to("m").magnitude
        self.step("Stoffwerte", "ρ, p_v", med.name, f"ρ = {fmt_num(rho, 1)} kg/m³, p_v = {fmt_num(pv / 1000, 3)} kPa")
        if pv >= p:
            self.warn("Der Dampfdruck erreicht den Behälterdruck – das Medium siedet (Siedezustand): NPSH_A ergibt "
                      "sich nur noch aus Zulaufhöhe minus Verlusten.")
        Hv, v = self._verlust(inp, rho, med.nu)
        Hp = (p - pv) / (rho * G)
        npsha = Hp + hz - Hv
        self.step("Druckhöhenanteil", "(p_e − p_v) / (ρ·g)",
                  f"({fmt_num(p / 1000, 2)} − {fmt_num(pv / 1000, 3)}) kPa / ({fmt_num(rho, 1)} · 9,81)",
                  f"{fmt_num(Hp, 3)} m")
        self.step("Vorhandene Haltedruckhöhe", "NPSH_A = (p_e − p_v)/(ρ·g) + H_z − H_v,s",
                  f"NPSH_A = {fmt_num(Hp, 3)} {'+' if hz >= 0 else '−'} {fmt_num(abs(hz), 2)} − {fmt_num(Hv, 3)} m",
                  f"{fmt_num(npsha, 2)} m")
        npshr, S = inp["npshr"].to("m").magnitude, inp["S"].to("m").magnitude
        erf = npshr + S
        reserve = npsha - npshr
        self.step("Nachweis", "NPSH_A ≥ NPSH_R + S", f"{fmt_num(npsha, 2)} m ≥ {fmt_num(npshr, 2)} + "
                  f"{fmt_num(S, 2)} = {fmt_num(erf, 2)} m", "erfüllt" if npsha >= erf else "NICHT erfüllt")
        hz_min = erf - Hp + Hv
        self.step("Mindestzulaufhöhe", "H_z,min = NPSH_R + S − (p_e − p_v)/(ρ·g) + H_v,s",
                  f"H_z,min = {fmt_num(erf, 2)} − {fmt_num(Hp, 3)} + {fmt_num(Hv, 3)}", f"{fmt_num(hz_min, 2)} m")

        self.result("npsha", "Vorhandene NPSH", "NPSH_A", Q_(npsha, "m"), "m", 2, highlight=True)
        self.result("erf", "Erforderlich inkl. Zuschlag", "NPSH_R + S", Q_(erf, "m"), "m", 2)
        self.result("res", "Reserve gegenüber der Pumpe", "NPSH_A − NPSH_R", Q_(reserve, "m"), "m", 2, highlight=True)
        self.result("verh", "Verhältnis", "NPSH_A/NPSH_R", Q_(npsha / npshr, ""), "", 2)
        self.result("hzmin", "Mindestzulaufhöhe (− = max. Saughöhe)", "H_z,min", Q_(hz_min, "m"), "m", 2,
                    highlight=True)
        self.result("Hv", "Verlusthöhe Saugleitung", "H_v,s", Q_(Hv, "m"), "m", 3)

        if inp["medium"] != "benutzer" and med.pv > 0:
            t_max = self._t_max(inp, p, hz, Hv, erf)
            if t_max is not None:
                self.result("tmax", "Höchste Medientemperatur", "θ_max", Q_(t_max, "degC"), "degC", 1)
                self.step("Höchstzulässige Temperatur", "NPSH_A(θ) = NPSH_R + S  (ρ, p_v temperaturabhängig)",
                          "Bisektion über θ", f"θ_max = {fmt_num(t_max, 1)} °C")

        if npsha < npshr:
            self.warn(f"KAVITATION: NPSH_A = {fmt_num(npsha, 2)} m liegt unter NPSH_R = {fmt_num(npshr, 2)} m – "
                       f"Zulaufhöhe auf mindestens {fmt_num(hz_min, 2)} m erhöhen, Saugleitung vergrößern/kürzen "
                       "oder Medientemperatur senken.")
        elif npsha < erf:
            self.warn(f"Sicherheitszuschlag nicht eingehalten (Reserve {fmt_num(reserve, 2)} m < {fmt_num(S, 2)} m) – "
                      "Förderhöhenabfall und Kavitationsverschleiß möglich.")
        else:
            self.info(f"Nachweis erfüllt: Reserve {fmt_num(reserve, 2)} m gegenüber NPSH_R.")
        if hz < 0 and -hz > 7:
            self.warn("Saughöhen über 7 m sind bei Wasser praktisch nicht beherrschbar (Luftdruck ≈ 10 m WS minus "
                      "Verluste und Dampfdruck).")
        if hz < 0:
            self.info("Saugbetrieb: Saugleitung steigend zur Pumpe verlegen (Luftsackfreiheit), Fußventil bzw. "
                      "selbstansaugende Pumpe vorsehen.")
        medium_hinweise(self, med)
        if v > 1.5:
            self.warn(f"Fließgeschwindigkeit in der Saugleitung {fmt_num(v, 2)} m/s – üblich ≤ 1,0–1,5 m/s.")
        self.info("NPSH_R wird in Datenblättern meist als NPSH3 (3 % Förderhöhenabfall) angegeben; beginnende "
                  "Kavitation tritt bereits früher auf.")

    @staticmethod
    def _npsha_t(mid: str, t: float, p: float, hz: float, Hv: float) -> float:
        z = medien.medium(mid).zustand(t)
        return (p - z.pv) / (z.rho * G) + hz - Hv

    def _t_max(self, inp, p: float, hz: float, Hv: float, erf: float) -> float | None:
        m = medien.medium(inp["medium"])
        lo, hi = m.t_min, min(m.t_max, 150.0)

        def f(t: float) -> float:
            return self._npsha_t(m.id, t, p, hz, Hv) - erf

        if f(lo) < 0:
            return None
        if f(hi) >= 0:
            return hi
        return nullstelle(f, lo, hi)

    def plot(self, fig, raw, result) -> bool:
        if not result.ok or raw.get("medium") == "benutzer":
            return False
        m = medien.medium(raw["medium"])
        if m.zustand(m.t_max).pv <= 0:
            return False
        p = float(raw["p"]) * 1000
        hz = float(raw["hz"])
        Hv = result.value("Hv")
        erf = result.value("erf")
        ts = np.linspace(m.t_min, min(m.t_max, 150.0), 151)
        na = [self._npsha_t(m.id, t, p, hz, Hv) for t in ts]
        ax = fig.subplots()
        ax.plot(ts, na, color="#1f6fb2", lw=2, label="NPSH_A der Anlage")
        ax.axhline(erf, color="#c0392b", ls="--", lw=1.5, label="NPSH_R + S")
        ax.axhline(erf - float(raw["S"]), color="#e59866", ls=":", lw=1.2, label="NPSH_R")
        ax.plot([float(raw["theta"])], [result.value("npsha")], "o", color="#2b3a4a", ms=6, label="Betrieb")
        unten = -max(2.0, erf)
        ax.fill_between(ts, unten - 5, erf, color="#f5d7d3", alpha=0.35, zorder=0)
        ax.text(3, erf, " Kavitationsgefahr", va="top", fontsize=8, color="#c0392b")
        ax.set_xlabel("Medientemperatur θ  [°C]")
        ax.set_ylabel("Haltedruckhöhe  [m]")
        ax.set_title("NPSH_A über der Medientemperatur")
        ax.set_xlim(ts[0], ts[-1])
        ax.set_ylim(unten, max(max(na), erf) * 1.15 + 0.5)
        ax.grid(True, alpha=0.3)
        ax.legend(loc="lower left", fontsize=8)
        return True

    def sketch_svg(self, raw) -> str:
        s = Svg()
        try:
            hz = float(raw.get("hz", -2))
        except (TypeError, ValueError):
            hz = -2.0
        y_p = 120
        y_w = 60 if hz >= 0 else 180
        top = y_w - 25
        s.rect(30, top, 90, 205 - top if hz < 0 else 70, fill="#ffffff")
        s.rect(31, y_w, 88, (205 - y_w if hz < 0 else top + 70 - y_w) - 1, fill="#cfe0f1", stroke="#cfe0f1", width=0)
        s.line(31, y_w, 119, y_w, ACCENT, 1.5)
        s.text(75, y_w - 6, "p_e", 12, INK, italic=True)
        if hz < 0:
            s.line(100, 195, 100, y_p, ACCENT, 3).line(100, y_p, 228, y_p, ACCENT, 3)
        else:
            s.line(119, y_w + 50, 170, y_w + 50, ACCENT, 3).line(170, y_w + 50, 170, y_p, ACCENT, 3)
            s.line(170, y_p, 228, y_p, ACCENT, 3)
        pumpe_svg(s, 250, y_p)
        s.line(272, y_p, 340, y_p, ACCENT, 3)
        s.line(130, y_p, 330, y_p, MUTED, 0.8, "4 3") if hz < 0 else s.line(250, y_p, 330, y_p, MUTED, 0.8, "4 3")
        s.line(130, y_w, 330, y_w, MUTED, 0.8, "4 3")
        s.dim_v(320, min(y_w, y_p), max(y_w, y_p), "H_z" if hz >= 0 else "−H_z")
        s.text(250, y_p + 40, "NPSH_R", 11, "#c0392b", italic=True)
        s.text(150, 210, "Zulauf" if hz >= 0 else "Saugbetrieb", 11, MUTED)
        return s.render()
