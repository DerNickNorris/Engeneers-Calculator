"""Stirnradpaar: Geometrie nach DIN 3960 / ISO 21771 mit Profilverschiebung, Überdeckung und Prüfmaßen."""

from __future__ import annotations

import math

from ingrechner.core.model import Calculator, ChoiceField, NumberField
from ingrechner.core.svg import ACCENT, INK, MUTED, Svg
from ingrechner.core.units import Q_, fmt_num

from ._getriebe import Radpaar, inv, inv_umkehr, radpaar, radpaar_felder

ACHS = {"x_art": ["achsabstand"]}


class Stirnrad(Calculator):
    id = "mb.stirnrad"
    title = "Stirnradpaar – Geometrie"
    category = "Maschinenbau"
    description = (
        "Geometrie eines außenverzahnten Stirnradpaars (gerad- oder schrägverzahnt): Teil-, Kopf-, Fuß-, Grund- "
        "und Wälzkreise, Achsabstand mit Profilverschiebung (oder Profilverschiebungssumme aus vorgegebenem "
        "Achsabstand), Profil- und Sprungüberdeckung, Zahnweite mit Messzähnezahl, Unterschnitt- und "
        "Spitzengrenze."
    )
    norm = "DIN 3960 / ISO 21771; inv α_wt = 2·Σx·tan α_n/(z₁+z₂) + inv α_t; Bezugsprofil DIN 867 (20°, 1,0/1,25)"
    keywords = ("stirnrad", "zahnrad", "verzahnung", "geometrie", "profilverschiebung", "achsabstand", "modul",
                "schrägverzahnung", "überdeckung", "zahnweite", "kopfkreis", "fußkreis", "unterschnitt", "evolvente")

    fields = [
        *radpaar_felder(),
        ChoiceField("x_art", "Profilverschiebung", [("vorgabe", "x₁, x₂ vorgeben"),
                                                    ("achsabstand", "aus vorgegebenem Achsabstand")], "vorgabe"),
        NumberField("a_soll", "Achsabstand (Vorgabe)", "a", "mm", 140, min=0, decimals=3, visible_if=ACHS,
                    tooltip="Σx wird berechnet und im Verhältnis der Zähnezahlen auf Ritzel/Rad aufgeteilt "
                            "(x₁ − x₂ wie eingegeben bleibt erhalten)"),
    ]

    def _paar(self, inp) -> Radpaar:
        rp = radpaar(inp)
        if inp["x_art"] != "achsabstand":
            return rp
        a = inp["a_soll"].to("mm").magnitude
        cos_wt = rp.ad * math.cos(rp.alpha_t) / a
        if not 0 < cos_wt < 1:
            raise ValueError("Der Achsabstand ist mit diesen Zähnezahlen und diesem Modul nicht erreichbar.")
        sx = (inv(math.acos(cos_wt)) - inv(rp.alpha_t)) * (rp.z1 + rp.z2) / (2 * math.tan(rp.alpha_n))
        diff = rp.x1 - rp.x2
        x1 = (sx + diff) / 2
        self.step("Profilverschiebungssumme aus a", "Σx = (inv α_wt − inv α_t)·(z₁+z₂)/(2·tan α_n);  cos α_wt = a_d·cos α_t/a",
                  f"a = {fmt_num(a, 3)} mm, a_d = {fmt_num(rp.ad, 3)} mm", f"Σx = {fmt_num(sx, 4)} → x₁ = {fmt_num(x1, 4)}, "
                  f"x₂ = {fmt_num(sx - x1, 4)}")
        return Radpaar(rp.mn, rp.z1, rp.z2, rp.beta, rp.alpha_n, x1, sx - x1, rp.b)

    def compute(self, inp) -> None:
        rp = self._paar(inp)
        deg = 180 / math.pi
        self.step("Stirnschnitt", "m_t = m_n/cos β;  tan α_t = tan α_n/cos β",
                  f"β = {fmt_num(rp.beta * deg, 2)}°", f"m_t = {fmt_num(rp.mt, 4)} mm, α_t = {fmt_num(rp.alpha_t * deg, 4)}°")
        self.step("Teil- und Grundkreise", "d = z·m_t;  d_b = d·cos α_t",
                  f"d₁ = {fmt_num(rp.d1, 3)} mm, d₂ = {fmt_num(rp.d2, 3)} mm",
                  f"d_b1 = {fmt_num(rp.db1, 3)} mm, d_b2 = {fmt_num(rp.db2, 3)} mm")
        self.step("Betriebseingriffswinkel", "inv α_wt = 2·(x₁+x₂)·tan α_n/(z₁+z₂) + inv α_t",
                  f"Σx = {fmt_num(rp.x1 + rp.x2, 4)}", f"α_wt = {fmt_num(rp.alpha_wt * deg, 4)}°")
        self.step("Achsabstand", "a = a_d · cos α_t / cos α_wt;  a_d = (z₁+z₂)·m_t/2",
                  f"a_d = {fmt_num(rp.ad, 3)} mm", f"a = {fmt_num(rp.a, 3)} mm")
        self.step("Kopf- und Fußkreise", "d_a = d + 2m_n(h_a* + x + k);  d_f = d − 2m_n(h_f* − x)",
                  f"k = {fmt_num(rp.k, 4)} (Kopfhöhenänderung)",
                  f"d_a1 = {fmt_num(rp.da1, 3)}, d_a2 = {fmt_num(rp.da2, 3)}, d_f1 = {fmt_num(rp.df1, 3)}, "
                  f"d_f2 = {fmt_num(rp.df2, 3)} mm")
        self.step("Überdeckung", "ε_α = g_α/(π·m_t·cos α_t);  ε_β = b·sin β/(π·m_n)", "",
                  f"ε_α = {fmt_num(rp.eps_a, 3)}, ε_β = {fmt_num(rp.eps_b, 3)}, ε_γ = {fmt_num(rp.eps_g, 3)}")
        k1, w1 = rp.zahnweite(rp.z1, rp.x1)
        k2, w2 = rp.zahnweite(rp.z2, rp.x2)
        self.step("Zahnweite", "W_k = m_n·cos α_n·[(k − 0,5)·π + z·inv α_t] + 2·x·m_n·sin α_n", "",
                  f"W_{k1} (Ritzel) = {fmt_num(w1, 3)} mm, W_{k2} (Rad) = {fmt_num(w2, 3)} mm")

        self.result("a", "Achsabstand", "a", Q_(rp.a, "mm"), "mm", 3, highlight=True)
        self.result("i", "Übersetzung", "u", Q_(rp.u, ""), "", 4, highlight=True)
        self.result("d1", "Teilkreis Ritzel", "d₁", Q_(rp.d1, "mm"), "mm", 3)
        self.result("d2", "Teilkreis Rad", "d₂", Q_(rp.d2, "mm"), "mm", 3)
        self.result("dw1", "Wälzkreis Ritzel", "d_w1", Q_(rp.dw1, "mm"), "mm", 3)
        self.result("dw2", "Wälzkreis Rad", "d_w2", Q_(rp.dw2, "mm"), "mm", 3)
        self.result("da1", "Kopfkreis Ritzel", "d_a1", Q_(rp.da1, "mm"), "mm", 3, highlight=True)
        self.result("da2", "Kopfkreis Rad", "d_a2", Q_(rp.da2, "mm"), "mm", 3, highlight=True)
        self.result("df1", "Fußkreis Ritzel", "d_f1", Q_(rp.df1, "mm"), "mm", 3)
        self.result("df2", "Fußkreis Rad", "d_f2", Q_(rp.df2, "mm"), "mm", 3)
        self.result("db1", "Grundkreis Ritzel", "d_b1", Q_(rp.db1, "mm"), "mm", 3)
        self.result("db2", "Grundkreis Rad", "d_b2", Q_(rp.db2, "mm"), "mm", 3)
        self.result("awt", "Betriebseingriffswinkel", "α_wt", Q_(rp.alpha_wt * deg, "degree"), "degree", 4)
        self.result("eps_a", "Profilüberdeckung", "ε_α", Q_(rp.eps_a, ""), "", 3, highlight=True)
        self.result("eps_b", "Sprungüberdeckung", "ε_β", Q_(rp.eps_b, ""), "", 3)
        self.result("x1", "Profilverschiebung Ritzel", "x₁", Q_(rp.x1, ""), "", 4)
        self.result("x2", "Profilverschiebung Rad", "x₂", Q_(rp.x2, ""), "", 4)
        self.result("W1", f"Zahnweite Ritzel (k = {k1})", "W_k1", Q_(w1, "mm"), "mm", 3)
        self.result("W2", f"Zahnweite Rad (k = {k2})", "W_k2", Q_(w2, "mm"), "mm", 3)

        if rp.eps_a < 1.1:
            (self.error if rp.eps_a < 1.0 else self.warn)(
                f"Profilüberdeckung ε_α = {fmt_num(rp.eps_a, 3)} – mindestens 1,1 (besser ≥ 1,2) erforderlich.")
        for name, z, x in (("Ritzel", rp.z1, rp.x1), ("Rad", rp.z2, rp.x2)):
            xm = rp.x_min(z)
            if x < xm - 1e-6:
                self.warn(f"{name}: Unterschnitt – x = {fmt_num(x, 3)} < x_min = {fmt_num(xm, 3)} (Zahnfuß geschwächt, "
                          "Eingriffsstrecke verkürzt).")
        for name, z, x, da, d in (("Ritzel", rp.z1, rp.x1, rp.da1, rp.d1), ("Rad", rp.z2, rp.x2, rp.da2, rp.d2)):
            sa = rp.kopfdicke(z, x, da, d)
            self.result(f"sa_{name[0]}", f"Zahndicke am Kopf {name}", f"s_an,{name[0].lower()}", Q_(sa, "mm"), "mm", 3)
            if sa < 0.2 * rp.mn:
                self.warn(f"{name}: Zahnkopf zu spitz (s_an = {fmt_num(sa, 2)} mm < 0,2·m_n) – Profilverschiebung "
                          "verringern; gehärtete Zahnräder ≥ 0,4·m_n.")
        if rp.k < -0.01:
            self.info(f"Kopfkürzung k·m_n = {fmt_num(rp.k * rp.mn, 3)} mm berücksichtigt (Kopfspiel erhalten).")
        if rp.beta > 0 and rp.eps_b < 1:
            self.info("Sprungüberdeckung < 1 – für ruhigen Lauf b ≥ π·m_n / sin β anstreben.")
        self.info("Spiel- und Toleranzangaben (Zahndickenabmaße, Achsabstandsabmaße) nach DIN 3967 / DIN 58405 "
                  "sind nicht enthalten; Zahnweite ohne Abmaße.")

    def sketch_svg(self, raw) -> str:
        s = Svg()
        try:
            z1, z2 = float(raw.get("z1", 19)), float(raw.get("z2", 71))
        except (TypeError, ValueError):
            z1, z2 = 19.0, 71.0
        r_tot = min(150.0, 80 * (z1 + z2) / max(z2, 1))
        r1 = r_tot * z1 / (z1 + z2)
        r2 = r_tot - r1
        x1 = 180 - r_tot + r1
        x2 = x1 + r1 + r2
        y = 100
        r2s = r2
        s.circle(x2, y, r2s * 1.04, fill="#eef3f8").circle(x2, y, r2s, fill="#ffffff", stroke=MUTED, width=0.8)
        s.circle(x1, y, r1 * 1.12, fill="#f5d7d3").circle(x1, y, r1, fill="#ffffff", stroke=MUTED, width=0.8)
        s.line(x1, y, x2, y, ACCENT, 1.2, "5 4")
        s.text((x1 + x2) / 2, y - 6, "a", 13, INK, italic=True)
        s.text(x1, max(y + r1 * 1.12 + 14, 30), "Ritzel z₁", 10, INK).text(x2, y + r2 * 1.04 + 14, "Rad z₂", 10, INK)
        return s.render()
