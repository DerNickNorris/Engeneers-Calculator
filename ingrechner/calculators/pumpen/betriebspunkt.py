"""Pumpenkennlinie aus Datenblattpunkten, Betriebspunkt mit der Anlagenkennlinie, Drehzahl, Parallel/Reihe."""

from __future__ import annotations

import numpy as np

from ingrechner.core.model import Calculator, ChoiceField, NumberField
from ingrechner.core.svg import ACCENT, INK, MUTED, Svg
from ingrechner.core.units import Q_, fmt_num

from ._pumpe import G, Kennlinie, kennlinie_feld, nullstelle, pumpe_svg

FEST = {"drehzahl": ["fest"]}
MEHR = {"schaltung": ["parallel", "reihe"]}


class Schaltung:
    """Kennlinie von z gleichen Pumpen bei relativer Drehzahl n."""

    def __init__(self, kl: Kennlinie, art: str, z: int, n: float) -> None:
        self.kl, self.art, self.z, self.n = kl, art, z, n

    def H(self, Q):
        Q = np.asarray(Q, dtype=float)
        if self.art == "parallel":
            return self.kl.H(Q / self.z, self.n)
        if self.art == "reihe":
            return self.z * self.kl.H(Q, self.n)
        return self.kl.H(Q, self.n)

    def q_pumpe(self, Q: float) -> float:
        return Q / self.z if self.art == "parallel" else Q

    @property
    def q_max(self) -> float:
        """Größter Förderstrom im Datenbereich (ohne Extrapolation)."""
        return self.kl.q_max * self.n * (self.z if self.art == "parallel" else 1)


class Betriebspunkt(Calculator):
    id = "pu.betriebspunkt"
    title = "Pumpenkennlinie & Betriebspunkt"
    category = "Pumpen"
    description = (
        "Auswertung einer Pumpenkennlinie aus Datenblattpunkten (V̇, H, η): Ausgleichskurve, Schnittpunkt mit der "
        "Anlagenkennlinie, Wirkungsgrad und Wellenleistung im Betriebspunkt, Lage zum Bestpunkt. Drehzahl"
        "anpassung nach den Affinitätsgesetzen sowie Parallel- und Reihenbetrieb gleicher Pumpen."
    )
    norm = "Affinitätsgesetze V̇ ~ n, H ~ n², P ~ n³; Betriebsbereich nach DIN EN ISO 9906 / Europump (0,7–1,2·V̇_opt)"
    keywords = ("pumpenkennlinie", "kennlinie", "betriebspunkt", "anlagenkennlinie", "affinitätsgesetze",
                "drehzahl", "parallelbetrieb", "reihenbetrieb", "bestpunkt", "wirkungsgrad", "schnittpunkt",
                "frequenzumrichter", "laufrad")

    fields = [
        kennlinie_feld(),
        NumberField("Va", "Auslegungs-Förderstrom", "V̇_A", "m**3/hour", 3.0, min=0, decimals=3,
                    tooltip="Aus dem Rechner „Pumpenauslegung“"),
        NumberField("Ha", "Auslegungs-Förderhöhe", "H_A", "m", 4.0, min=0, decimals=2),
        NumberField("Hs", "Statischer Anteil der Anlage", "H_stat", "m", 0, decimals=2,
                    tooltip="Geschlossener Kreislauf 0; offene Systeme H_geo + Δp_B/(ρ·g)"),
        ChoiceField("schaltung", "Schaltung", [("einzel", "Einzelpumpe"), ("parallel", "Parallelbetrieb (gleiche Pumpen)"),
                                               ("reihe", "Reihenbetrieb (gleiche Pumpen)")], "einzel"),
        NumberField("z", "Anzahl Pumpen in Betrieb", "z", "", 2, min=2, max=4, min_inclusive=True, decimals=0,
                    visible_if=MEHR),
        ChoiceField("drehzahl", "Drehzahl", [("nenn", "Nenndrehzahl (Kennlinie wie Datenblatt)"),
                                             ("fest", "Relative Drehzahl vorgeben"),
                                             ("anpassen", "Drehzahl auf den Auslegungspunkt regeln")], "nenn"),
        NumberField("n", "Relative Drehzahl", "n/n_N", "percent", 85, min=20, max=120, decimals=1, visible_if=FEST),
        NumberField("nN", "Nenndrehzahl (optional)", "n_N", "1/minute", 2900, min=0, min_inclusive=True, decimals=0,
                    tooltip="Nur zur Angabe der Drehzahl in 1/min; 0 = ohne"),
        NumberField("rho", "Dichte des Mediums", "ρ", "kg/m**3", 983, min=0, decimals=1,
                    tooltip="Für die Wellenleistung P₂ = ρ·g·V̇·H / η"),
    ]

    def compute(self, inp) -> None:
        kl = Kennlinie(inp["kennlinie"])
        a2, a1, a0 = kl.ch
        self.step("Ausgleichskurve der Datenblattpunkte", "H(V̇) = a₀ + a₁·V̇ + a₂·V̇²  (kleinste Quadrate)",
                  f"{len(kl.q)} Punkte, max. Abweichung {fmt_num(kl.abw * 100, 1)} %", kl.koeff_text())
        if kl.abw > 0.03:
            self.warn(f"Die Ausgleichsparabel weicht bis {fmt_num(kl.abw * 100, 1)} % von den Datenblattpunkten ab "
                      "– Punkte prüfen oder Kennlinie im Arbeitsbereich enger stützen.")
        if a2 > 0:
            self.warn("Die Ausgleichskurve ist nach oben gekrümmt – untypisch für Kreiselpumpen; Punkte prüfen.")
        if kl.instabil:
            self.warn("Instabile (labile) Kennlinie: Die Förderhöhe steigt zunächst mit dem Förderstrom an – "
                      "im Parallelbetrieb und bei flachen Anlagenkennlinien kann die Pumpe pendeln.")

        Va, Ha, Hs = (inp[k].to(u).magnitude for k, u in (("Va", "m**3/hour"), ("Ha", "m"), ("Hs", "m")))
        if Ha <= Hs:
            raise ValueError("Die Auslegungs-Förderhöhe muss über dem statischen Anteil liegen.")
        c = (Ha - Hs) / Va**2
        anlage = lambda Q: Hs + c * np.asarray(Q, dtype=float) ** 2  # noqa: E731
        self.step("Anlagenkennlinie", "H_A(V̇) = H_stat + c·V̇²;  c = (H_A − H_stat) / V̇_A²",
                  f"c = ({fmt_num(Ha, 2)} − {fmt_num(Hs, 2)}) / {fmt_num(Va, 3)}²",
                  f"c = {fmt_num(c, 5)} m/(m³/h)²")

        art = inp["schaltung"]
        z = int(round(inp["z"])) if art != "einzel" else 1
        if inp["drehzahl"] == "fest":
            n = inp["n"].to("percent").magnitude / 100
        elif inp["drehzahl"] == "anpassen":
            f = lambda nn: float(Schaltung(kl, art, z, nn).H(Va)) - Ha  # noqa: E731
            n = nullstelle(f, 0.2, 1.2)
            if n is None:
                raise ValueError("Der Auslegungspunkt ist mit dieser Pumpe auch mit 120 % Drehzahl nicht "
                                 "erreichbar – größere Pumpe oder anderes Laufrad wählen.")
            self.step("Drehzahl für den Auslegungspunkt", "H_P(V̇_A; n) = H_A  (Affinität: H(V̇, n) = n²·H(V̇/n))",
                      "Bisektion", f"n/n_N = {fmt_num(n * 100, 1)} %")
            if n > 1.0:
                self.warn(f"Dafür wären {fmt_num(n * 100, 1)} % der Nenndrehzahl nötig – Überdrehzahl nur nach "
                          "Freigabe durch den Hersteller (Motorleistung, Frequenz > 50 Hz).")
        else:
            n = 1.0
        sch = Schaltung(kl, art, z, n)
        if art != "einzel":
            self.step("Kennlinie der Schaltung",
                      "parallel: H(V̇) = H₁(V̇ / z)" if art == "parallel" else "Reihe: H(V̇) = z · H₁(V̇)",
                      f"z = {z} gleiche Pumpen", "")

        diff = lambda Q: float(sch.H(Q) - anlage(Q))  # noqa: E731
        if diff(0) <= 0:
            raise ValueError("Die Nullförderhöhe der Pumpe(n) liegt unter dem statischen Anteil – kein Förderstrom.")
        q_end = sch.q_max * 2.0
        Qb = nullstelle(diff, 0.0, q_end)
        if Qb is None:
            raise ValueError("Kein Schnittpunkt der Pumpen- mit der Anlagenkennlinie gefunden – Eingaben prüfen.")
        Hb = float(anlage(Qb))
        self.step("Betriebspunkt", "H_P(V̇_B) = H_A(V̇_B)  (Schnittpunkt der Kennlinien)", "Bisektion",
                  f"V̇_B = {fmt_num(Qb, 3)} m³/h, H_B = {fmt_num(Hb, 2)} m")
        if Qb > sch.q_max * 1.02:
            self.warn("Der Betriebspunkt liegt rechts des letzten Datenblattpunkts – die Kennlinie ist extrapoliert "
                      "(Kavitations- und Überlastgefahr).")

        self.result("Qb", "Förderstrom im Betriebspunkt", "V̇_B", Q_(Qb, "m**3/hour"), "m**3/hour", 3, highlight=True)
        self.result("Hb", "Förderhöhe im Betriebspunkt", "H_B", Q_(Hb, "m"), "m", 2, highlight=True)
        self.result("abw", "Abweichung vom Auslegungsstrom", "V̇_B/V̇_A", Q_(Qb / Va * 100, "percent"), "percent", 1)
        self.result("n", "Relative Drehzahl", "n/n_N", Q_(n * 100, "percent"), "percent", 1,
                    highlight=inp["drehzahl"] == "anpassen")
        nN = inp["nN"].to("1/minute").magnitude
        if nN > 0 and n != 1.0:
            self.result("nabs", "Drehzahl", "n", Q_(n * nN, "1/minute"), "1/minute", 0)
        if art == "parallel":
            self.result("Qp", "Förderstrom je Pumpe", "V̇_B,1", Q_(Qb / z, "m**3/hour"), "m**3/hour", 3)

        qp = sch.q_pumpe(Qb)
        Hp = Hb / z if art == "reihe" else Hb
        rho = inp["rho"].to("kg/m**3").magnitude
        if kl.hat_eta:
            eta = float(kl.eta(qp, n))
            bep = kl.bep()
            q_opt = bep[0] * n
            P2 = rho * G * (qp / 3600) * Hp / max(eta, 1e-3)
            self.step("Wirkungsgrad im Betriebspunkt", "η(V̇, n) = η(V̇/n)  (Affinität)",
                      f"V̇/n = {fmt_num(qp / n, 3)} m³/h", f"η = {fmt_num(eta * 100, 1)} %")
            self.step("Wellenleistung je Pumpe", "P₂ = ρ · g · V̇ · H / η",
                      f"P₂ = {fmt_num(rho, 1)} · 9,81 · {fmt_num(qp / 3600, 5)} · {fmt_num(Hp, 2)} / "
                      f"{fmt_num(eta, 3)}", f"{fmt_num(P2, 0)} W")
            lage = qp / q_opt
            self.step("Lage zum Bestpunkt", "V̇_opt(n) = n · V̇_opt;  x = V̇ / V̇_opt",
                      f"V̇_opt = {fmt_num(q_opt, 3)} m³/h (η_max = {fmt_num(bep[1] * 100, 1)} %)",
                      f"x = {fmt_num(lage, 2)}")
            self.result("eta", "Wirkungsgrad im Betriebspunkt", "η_B", Q_(eta * 100, "percent"), "percent", 1,
                        highlight=True)
            self.result("P2", "Leistung je Pumpe", "P₂", Q_(P2, "W"), "kW", 3)
            self.result("Qopt", "Bestpunkt-Förderstrom", "V̇_opt", Q_(q_opt, "m**3/hour"), "m**3/hour", 3)
            self.result("lage", "Lage zum Bestpunkt", "V̇/V̇_opt", Q_(lage * 100, "percent"), "percent", 0)
            if lage < 0.7 or lage > 1.2:
                self.warn(f"Betrieb bei {fmt_num(lage * 100, 0)} % des Bestpunkt-Förderstroms – außerhalb des "
                          "zulässigen Bereichs 70–120 %: erhöhter Verschleiß, Vibrationen, Kavitationsgefahr.")
            elif lage < 0.8 or lage > 1.1:
                self.info(f"Betrieb bei {fmt_num(lage * 100, 0)} % des Bestpunkts – zulässig, bevorzugt sind "
                          "80–110 %.")
            else:
                self.info(f"Betrieb im bevorzugten Bereich ({fmt_num(lage * 100, 0)} % des Bestpunkts).")
        else:
            self.info("Ohne Wirkungsgradangaben in der Kennlinie werden η, P₂ und die Lage zum Bestpunkt nicht "
                      "berechnet.")
        if abs(Qb / Va - 1) > 0.1 and inp["drehzahl"] != "anpassen":
            self.info(f"Der Betriebspunkt weicht um {fmt_num((Qb / Va - 1) * 100, 0)} % vom Auslegungsstrom ab – "
                      "Drehzahlregelung oder Laufradabdrehen prüfen.")
        if art == "parallel":
            self.info("Parallelbetrieb: Der Gesamtförderstrom steigt wegen der Anlagenkennlinie weniger als "
                      "proportional zur Pumpenzahl; Einzelpumpe auf Überlast im Solobetrieb prüfen.")
        self.info("Datenblattkennlinien gelten meist für Wasser; Toleranzen nach DIN EN ISO 9906 beachten.")

    # --------------------------------------------------------------- Diagramm
    def plot(self, fig, raw, result) -> bool:
        if not result.ok:
            return False
        rows, msg = self.field("kennlinie").parse(raw["kennlinie"])
        if msg:
            return False
        kl = Kennlinie(rows)
        art = raw["schaltung"]
        z = int(round(float(raw.get("z", 2)))) if art != "einzel" else 1
        n = result.value("n") / 100
        sch = Schaltung(kl, art, z, n)
        Qb, Hb = result.value("Qb"), result.value("Hb")
        Va, Ha, Hs = float(raw["Va"]), float(raw["Ha"]), float(raw["Hs"])
        qmax = max(sch.q_max, Qb) * 1.1
        qs = np.linspace(0, qmax, 200)
        ax = fig.subplots()
        ax.plot(kl.q, kl.h, "s", color="#2b3a4a", ms=4, label="Datenblatt (n_N)")
        q1 = np.linspace(0, kl.q_max, 100)
        ax.plot(q1, kl.H(q1), color="#9aa7b4", lw=1.2, ls="--", label="Einzelpumpe n_N")
        hp = sch.H(qs)
        lbl = "Pumpe" if art == "einzel" else ("Parallel" if art == "parallel" else "Reihe") + f" ×{z}"
        if n != 1.0:
            lbl += f", n = {fmt_num(n * 100, 0)} %"
        ok = hp >= 0
        ax.plot(qs[ok], hp[ok], color="#c0392b", lw=2, label=lbl)
        c = (Ha - Hs) / Va**2
        ax.plot(qs, Hs + c * qs**2, color="#1f6fb2", lw=2, label="Anlagenkennlinie")
        ax.plot([Va], [Ha], "x", color="#1f6fb2", ms=8, mew=2, label="Auslegungspunkt")
        ax.plot([Qb], [Hb], "o", color="#c0392b", ms=7, label="Betriebspunkt")
        ax.set_xlim(0, qmax)
        ax.set_ylim(0, max(float(np.nanmax(hp)), Ha) * 1.6)
        ax.set_xlabel("Förderstrom V̇  [m³/h]")
        ax.set_ylabel("Förderhöhe H  [m]")
        ax.grid(True, alpha=0.3)
        if kl.hat_eta:
            ax2 = ax.twinx()
            qe = np.linspace(kl.q_eta.min(), kl.q_eta.max(), 100)
            qe_s = qe * n * (z if art == "parallel" else 1)
            ax2.plot(qe_s, kl.eta(qe * n, n) * 100, color="#27ae60", lw=1.5, label="η")
            ax2.plot(kl.q_eta * n * (z if art == "parallel" else 1), kl.eta_pts * 100, "^", color="#27ae60", ms=4)
            ax2.set_ylabel("Wirkungsgrad η  [%]", color="#27ae60")
            ax2.set_ylim(0, min(100.0, float(kl.eta_pts.max()) * 100 * 1.6))
            ax2.tick_params(axis="y", colors="#27ae60")
        ax.legend(loc="upper right", fontsize=7.5, ncol=2)
        ax.set_title("Pumpen- und Anlagenkennlinie")
        return True

    def sketch_svg(self, raw) -> str:
        s = Svg()
        art = raw.get("schaltung", "einzel")
        if art == "parallel":
            s.line(30, 110, 90, 110, ACCENT, 3).line(90, 60, 90, 160, ACCENT, 3)
            s.line(90, 60, 270, 60, ACCENT, 3).line(90, 160, 270, 160, ACCENT, 3)
            s.line(270, 60, 270, 160, ACCENT, 3).line(270, 110, 330, 110, ACCENT, 3)
            pumpe_svg(s, 180, 60, 18)
            pumpe_svg(s, 180, 160, 18)
            s.text(180, 205, "Parallelbetrieb: V̇ addiert sich bei gleicher Förderhöhe", 11, INK)
        elif art == "reihe":
            s.line(20, 110, 340, 110, ACCENT, 3)
            pumpe_svg(s, 120, 110, 18)
            pumpe_svg(s, 240, 110, 18)
            s.text(180, 170, "Reihenbetrieb: H addiert sich bei gleichem Förderstrom", 11, INK)
        else:
            # Kennliniendiagramm schematisch
            s.line(60, 190, 330, 190, INK, 1.5).line(60, 190, 60, 20, INK, 1.5)
            s.text(330, 208, "V̇", 12, INK, "end", True).text(48, 30, "H", 12, INK, italic=True)
            pts_p = [(60 + x, 50 + (x / 230) ** 2 * 130) for x in range(0, 240, 10)]
            pts_a = [(60 + x, 170 - (x / 230) ** 2 * 120) for x in range(0, 240, 10)]
            for (x1, y1), (x2, y2) in zip(pts_p, pts_p[1:]):
                s.line(x1, y1, x2, y2, "#c0392b", 2.2)
            for (x1, y1), (x2, y2) in zip(pts_a, pts_a[1:]):
                s.line(x1, y1, x2, y2, ACCENT, 2.2)
            xb = 230 * (120 / 250) ** 0.5
            s.circle(60 + xb, 50 + (xb / 230) ** 2 * 130, 5, fill="#c0392b", stroke="#c0392b")
            s.text(296, 52, "Anlage", 11, ACCENT, "start").text(296, 176, "Pumpe", 11, "#c0392b", "start")
            s.text(60 + xb, 98, "B", 12, INK, bold=True)
            s.text(66, 182, "H_stat", 10, MUTED, "start")
        return s.render()
