"""Biegeknicken eines Druckstabs nach DIN EN 1993-1-1, Abschnitt 6.3.1."""

from __future__ import annotations

import math

import numpy as np

from ingrechner.core.model import Calculator, ChoiceField, NumberField
from ingrechner.core.svg import ACCENT, INK, Svg
from ingrechner.core.units import Q_, fmt_num, fmt_q

# Imperfektionsbeiwerte α (EN 1993-1-1, Tabelle 6.1)
KNICKLINIEN = {"a0": 0.13, "a": 0.21, "b": 0.34, "c": 0.49, "d": 0.76}
# Euler-Fälle -> Knicklängenbeiwert β
EULER = {
    "1": (2.0, "Fall 1: eingespannt – frei (β = 2,0)"),
    "2": (1.0, "Fall 2: gelenkig – gelenkig (β = 1,0)"),
    "3": (0.699, "Fall 3: eingespannt – gelenkig (β ≈ 0,7)"),
    "4": (0.5, "Fall 4: eingespannt – eingespannt (β = 0,5)"),
}


def chi(lam_bar: float, alpha: float) -> float:
    """Abminderungsbeiwert χ nach EN 1993-1-1 Gl. (6.49)."""
    if lam_bar <= 0.2:
        return 1.0
    phi = 0.5 * (1 + alpha * (lam_bar - 0.2) + lam_bar**2)
    return min(1.0, 1 / (phi + math.sqrt(phi**2 - lam_bar**2)))


class KnickenEN1993(Calculator):
    id = "st.knicken_en1993"
    title = "Biegeknicken Druckstab (Stahl)"
    category = "Bau / Statik"
    description = (
        "Knickwiderstand eines zentrisch gedrückten Stahlstabs mit konstantem Querschnitt: "
        "ideale Verzweigungslast, bezogener Schlankheitsgrad, Abminderungsbeiwert χ und Nachweis."
    )
    norm = "DIN EN 1993-1-1, 6.3.1 (Biegeknicken); Querschnittsklasse 1–3"
    keywords = ("knicken", "stütze", "druckstab", "eurocode", "en 1993", "schlankheit", "euler", "chi",
                "knicklinie", "stab")
    material_map = {"fy": "Re", "E": "E"}

    fields = [
        NumberField("N", "Bemessungsdruckkraft", "N_Ed", "kN", 150, min=0, min_inclusive=True, decimals=1),
        NumberField("L", "Systemlänge", "L", "mm", 3000, min=0, decimals=0),
        ChoiceField("fall", "Lagerung (Euler-Fall)", [(k, v[1]) for k, v in EULER.items()], "2"),
        NumberField("A", "Querschnittsfläche", "A", "cm**2", 28.5, min=0, decimals=2,
                    tooltip="z. B. IPE 200: A = 28,5 cm²"),
        NumberField("I", "Flächenträgheitsmoment (Knickachse)", "I", "cm**4", 142, min=0, decimals=1,
                    tooltip="Maßgebend ist meist die schwache Achse – IPE 200: I_z = 142 cm⁴, I_y = 1943 cm⁴"),
        ChoiceField("kl", "Knicklinie", [
            ("a0", "a₀ (α = 0,13)"), ("a", "a (α = 0,21)"), ("b", "b (α = 0,34)"),
            ("c", "c (α = 0,49)"), ("d", "d (α = 0,76)")], "b",
            tooltip="EN 1993-1-1 Tab. 6.2 – z. B. gewalztes I-Profil h/b > 1,2, t_f ≤ 40 mm: "
                    "Achse y-y → a, Achse z-z → b; Hohlprofil warmgefertigt → a"),
        NumberField("fy", "Streckgrenze", "f_y", "N/mm**2", 235, min=0, decimals=0),
        NumberField("E", "Elastizitätsmodul", "E", "N/mm**2", 210000, min=0, decimals=0),
        NumberField("gM1", "Teilsicherheitsbeiwert", "γ_M1", "", 1.1, min=1, min_inclusive=True, decimals=2,
                    tooltip="Deutscher Nationaler Anhang: γ_M1 = 1,1 (Empfehlung EN: 1,0)"),
    ]

    def compute(self, inp) -> None:
        A, I, E, fy, L = inp["A"], inp["I"], inp["E"], inp["fy"], inp["L"]
        beta = EULER[inp["fall"]][0]
        alpha = KNICKLINIEN[inp["kl"]]
        Lcr = beta * L
        i = (I / A) ** 0.5
        lam = (Lcr / i).to("").magnitude
        Ncr = (math.pi**2 * E * I / Lcr**2).to("kN")
        Npl = (A * fy).to("kN")
        lam_bar = math.sqrt((Npl / Ncr).to("").magnitude)
        x = chi(lam_bar, alpha)
        Nb = (x * Npl / inp["gM1"]).to("kN")
        eta = (inp["N"] / Nb).to("").magnitude

        self.step("Knicklänge", "L_cr = β · L", f"L_cr = {fmt_num(beta, 3)} · {fmt_q(L, 'mm', 0)}", fmt_q(Lcr, "mm", 0))
        self.step("Trägheitsradius / Schlankheit", "i = √(I / A);  λ = L_cr / i",
                  f"i = √({fmt_q(I, 'cm**4', 1)} / {fmt_q(A, 'cm**2', 2)})",
                  f"i = {fmt_q(i, 'cm', 2)}, λ = {fmt_num(lam, 1)}")
        self.step("Ideale Verzweigungslast", "N_cr = π² · E · I / L_cr²",
                  f"N_cr = π² · {fmt_q(E, 'N/mm**2', 0)} · {fmt_q(I, 'mm**4', 0)} / ({fmt_q(Lcr, 'mm', 0)})²",
                  fmt_q(Ncr, "kN", 1))
        self.step("Bezogener Schlankheitsgrad", "λ̄ = √(A · f_y / N_cr)",
                  f"λ̄ = √({fmt_q(Npl, 'kN', 1)} / {fmt_q(Ncr, 'kN', 1)})", fmt_num(lam_bar, 3))
        if lam_bar > 0.2:
            phi = 0.5 * (1 + alpha * (lam_bar - 0.2) + lam_bar**2)
            self.step("Hilfswert", "Φ = 0,5 · [1 + α · (λ̄ − 0,2) + λ̄²]",
                      f"Φ = 0,5 · [1 + {fmt_num(alpha, 2)} · ({fmt_num(lam_bar, 3)} − 0,2) + {fmt_num(lam_bar, 3)}²]",
                      fmt_num(phi, 4))
            self.step("Abminderungsbeiwert", "χ = 1 / (Φ + √(Φ² − λ̄²)) ≤ 1",
                      f"χ = 1 / ({fmt_num(phi, 4)} + √({fmt_num(phi, 4)}² − {fmt_num(lam_bar, 3)}²))", fmt_num(x, 4))
        else:
            self.step("Abminderungsbeiwert", "λ̄ ≤ 0,2 → χ = 1", "Knicken muss nicht berücksichtigt werden", "1")
        self.step("Knickwiderstand", "N_b,Rd = χ · A · f_y / γ_M1",
                  f"N_b,Rd = {fmt_num(x, 4)} · {fmt_q(Npl, 'kN', 1)} / {fmt_num(inp['gM1'], 2)}", fmt_q(Nb, "kN", 1))
        self.step("Nachweis", "η = N_Ed / N_b,Rd ≤ 1",
                  f"η = {fmt_q(inp['N'], 'kN', 1)} / {fmt_q(Nb, 'kN', 1)}", f"{fmt_num(eta * 100, 1)} %")

        self.result("Nb", "Knickwiderstand", "N_b,Rd", Nb, "kN", 1, highlight=True)
        self.result("eta", "Ausnutzung", "η", Q_(eta * 100, "percent"), "percent", 1, highlight=True)
        self.result("chi", "Abminderungsbeiwert", "χ", Q_(x, ""), "", 4, highlight=True)
        self.result("lam_bar", "Bezogener Schlankheitsgrad", "λ̄", Q_(lam_bar, ""), "", 3)
        self.result("lam", "Schlankheit", "λ", Q_(lam, ""), "", 1)
        self.result("Ncr", "Ideale Verzweigungslast", "N_cr", Ncr, "kN", 1)
        self.result("Npl", "Plastische Normalkraft", "N_pl,Rk", Npl, "kN", 1)
        self.result("Lcr", "Knicklänge", "L_cr", Lcr, "mm", 0)

        if eta > 1:
            self.warn(f"Knicknachweis NICHT erfüllt: Ausnutzung {fmt_num(eta * 100, 1)} % > 100 %.")
        else:
            self.info(f"Knicknachweis erfüllt ({fmt_num(eta * 100, 1)} %).")
        if lam > 200:
            self.warn(f"Sehr schlanker Stab (λ = {fmt_num(lam, 0)} > 200) – konstruktiv ungünstig.")
        if (inp["N"] / Ncr).to("").magnitude <= 0.04:
            self.info("N_Ed/N_cr ≤ 0,04: Knickeffekte dürfen nach EN 1993-1-1, 6.3.1.2(4) vernachlässigt werden.")
        self.info("Vorausgesetzt: Querschnittsklasse 1–3, zentrischer Druck, kein Biegedrillknicken. "
                  "Beide Hauptachsen getrennt nachweisen.")

    def plot(self, fig, raw, result) -> bool:
        if not result.ok:
            return False
        lb = np.linspace(0, 3, 301)
        ax = fig.subplots()
        colors = {"a0": "#9aa7b4", "a": "#7f8fa0", "b": "#5f6f7f", "c": "#46525e", "d": "#2b3a4a"}
        for k, a in KNICKLINIEN.items():
            ax.plot(lb, [chi(v, a) for v in lb], color="#1f6fb2" if k == raw["kl"] else colors[k],
                    lw=2.4 if k == raw["kl"] else 1, label=f"Linie {k}")
        ax.plot(lb[lb > 0.3], 1 / lb[lb > 0.3] ** 2, color="#c0392b", lw=1, ls="--", label="Euler 1/λ̄²")
        ax.plot([result.value("lam_bar")], [result.value("chi")], "o", color="#c0392b", ms=7)
        ax.set_ylim(0, 1.05)
        ax.set_xlim(0, 3)
        ax.set_xlabel("Bezogener Schlankheitsgrad λ̄")
        ax.set_ylabel("Abminderungsbeiwert χ")
        ax.set_title("Knicklinien nach EN 1993-1-1")
        ax.grid(True, alpha=0.3)
        ax.legend(loc="upper right")
        return True

    def sketch_svg(self, raw) -> str:
        s = Svg()
        fall = raw.get("fall", "2")
        top, bot, x = 40, 185, 150
        # Knickfigur
        import math as m

        pts = []
        for k in range(41):
            t = k / 40
            y = bot - t * (bot - top)
            amp = {"1": 18 * (1 - m.cos(m.pi * t / 2)), "2": 18 * m.sin(m.pi * t),
                   "3": 18 * (m.sin(4.49 * t) - 4.49 * t * m.cos(4.49) * 0 - t * m.sin(4.49)) * 0.9,
                   "4": 9 * (1 - m.cos(2 * m.pi * t))}[fall]
            pts.append((x + amp, y))
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            s.line(x1, y1, x2, y2, "#9aa7b4", 1.5, "4,3")
        s.line(x, top, x, bot, INK, 4)
        # Lager unten
        if fall in ("1", "3", "4"):
            s.rect(x - 22, bot, 44, 8, fill="#dce6f1")
        else:
            s.support_pin(x, bot)
        # Lager oben
        if fall == "4":
            s.rect(x - 22, top - 8, 44, 8, fill="#dce6f1")
        elif fall in ("2", "3"):
            s.polygon([(x, top), (x - 10, top - 14), (x + 10, top - 14)], fill="#ffffff")
            s.line(x - 16, top - 18, x + 16, top - 18, INK, 1.5)
        s.arrow(x, top - 36 if fall != "1" else top - 26, x, top - (20 if fall != "1" else 2))
        s.text(x + 14, 22, "N_Ed", 13, ACCENT, "start", True)
        s.dim_v(240, top, bot, "L")
        s.text(60, 120, f"β = {EULER[fall][0]:g}".replace(".", ","), 13, INK)
        return s.render()
