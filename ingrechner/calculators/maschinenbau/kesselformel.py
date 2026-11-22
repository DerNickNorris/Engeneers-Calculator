"""Zylindrische Schale unter Innendruck (Rohr, Behälter) – Kesselformel."""

from __future__ import annotations

from ingrechner.core.model import Calculator, NumberField
from ingrechner.core.svg import ACCENT, Svg
from ingrechner.core.units import Q_, fmt_num, fmt_q


class Kesselformel(Calculator):
    id = "mb.kesselformel"
    title = "Rohr / Behälter unter Innendruck"
    category = "Maschinenbau"
    description = (
        "Erforderliche Wanddicke einer zylindrischen Schale unter Innendruck und Membranspannungen "
        "in Umfangs- und Längsrichtung (dünnwandig, D_a/D_i ≤ 1,2)."
    )
    norm = "Kesselformel; Wanddicke in Anlehnung an AD 2000-Merkblatt B1"
    keywords = ("kesselformel", "innendruck", "rohr", "behälter", "wanddicke", "druckbehälter", "barlow")
    material_map = {"K": "Re"}

    fields = [
        NumberField("p", "Berechnungsdruck (Überdruck)", "p", "bar", 10, min=0, decimals=2),
        NumberField("Da", "Außendurchmesser", "D_a", "mm", 168.3, min=0, decimals=1),
        NumberField("s", "Ausgeführte Wanddicke", "s_e", "mm", 4.5, min=0, decimals=2),
        NumberField("K", "Festigkeitskennwert", "K", "N/mm**2", 235, min=0, decimals=0,
                    tooltip="Streck-/Dehngrenze bei Berechnungstemperatur (z. B. P235GH bei 20 °C: 235 N/mm²)"),
        NumberField("S", "Sicherheitsbeiwert", "S", "", 1.5, min=1, min_inclusive=True, decimals=2,
                    tooltip="AD 2000-Merkblatt B0: 1,5 für Walz- und Schmiedestähle"),
        NumberField("v", "Schweißnahtfaktor", "v", "", 1.0, min=0.5, max=1, min_inclusive=True, decimals=2,
                    tooltip="1,0 bei voller Prüfung der Naht, sonst 0,85 (AD 2000 HP 0)"),
        NumberField("c", "Zuschläge (Toleranz + Korrosion)", "c₁+c₂", "mm", 1.0, min=0, min_inclusive=True,
                    decimals=2),
    ]

    def compute(self, inp) -> None:
        p, Da, s, K, S, v, c = inp["p"], inp["Da"], inp["s"], inp["K"], inp["S"], inp["v"], inp["c"]
        if 2 * s >= Da:
            raise ValueError("Die Wanddicke ist zu groß für den Außendurchmesser.")
        f = K / S
        p_mpa = p.to("N/mm**2")
        s0 = (Da * p_mpa / (2 * f * v + p_mpa)).to("mm")
        s_erf = s0 + c
        self.step("Zulässige Spannung", "f = K / S", f"f = {fmt_q(K, 'N/mm**2', 0)} / {fmt_num(S, 2)}",
                  fmt_q(f, "N/mm**2", 2))
        self.step("Erforderliche Wanddicke", "s₀ = D_a · p / (20 · K/S · v + p)   (p in bar)",
                  f"s₀ = {fmt_q(Da, 'mm', 1)} · {fmt_num(p.to('bar').magnitude, 2)} / "
                  f"(20 · {fmt_num(f.to('N/mm**2').magnitude, 2)} · {fmt_num(v, 2)} + "
                  f"{fmt_num(p.to('bar').magnitude, 2)})", fmt_q(s0, "mm", 3))
        self.step("Mit Zuschlägen", "s_erf = s₀ + c₁ + c₂", f"s_erf = {fmt_q(s0, 'mm', 3)} + {fmt_q(c, 'mm', 2)}",
                  fmt_q(s_erf, "mm", 3))

        s_calc = s - c   # tragende Wanddicke
        if s_calc.magnitude <= 0:
            raise ValueError("Die Zuschläge sind größer als die Wanddicke.")
        dm = Da - s_calc
        sig_t = (p_mpa * dm / (2 * s_calc)).to("N/mm**2")
        sig_a = (p_mpa * dm / (4 * s_calc)).to("N/mm**2")
        eta = (sig_t / (f * v)).to("").magnitude
        p_max = (2 * f * v * s_calc / (Da - s_calc)).to("bar")
        self.step("Umfangsspannung (Mittendurchmesser)", "σ_t = p · (D_a − s) / (2 · s),  s = s_e − c",
                  f"σ_t = {fmt_q(p_mpa, 'N/mm**2', 3)} · {fmt_q(dm, 'mm', 2)} / (2 · {fmt_q(s_calc, 'mm', 2)})",
                  fmt_q(sig_t, "N/mm**2", 2))
        self.step("Längsspannung", "σ_a = p · (D_a − s) / (4 · s)", "σ_a = σ_t / 2", fmt_q(sig_a, "N/mm**2", 2))
        self.step("Zulässiger Druck", "p_zul = 2 · f · v · s / (D_a − s)",
                  f"p_zul = 2 · {fmt_q(f, 'N/mm**2', 2)} · {fmt_num(v, 2)} · {fmt_q(s_calc, 'mm', 2)} / "
                  f"{fmt_q(dm, 'mm', 2)}", fmt_q(p_max, "bar", 2))

        self.result("s_erf", "Erforderliche Wanddicke", "s_erf", s_erf, "mm", 3, highlight=True)
        self.result("sig_t", "Umfangsspannung", "σ_t", sig_t, "N/mm**2", 2, highlight=True)
        self.result("sig_a", "Längsspannung", "σ_a", sig_a, "N/mm**2", 2)
        self.result("eta", "Ausnutzung", "η", Q_(eta * 100, "percent"), "percent", 1, highlight=True)
        self.result("p_zul", "Zulässiger Druck", "p_zul", p_max, "bar", 2)

        if s < s_erf:
            self.warn(f"Wanddicke zu gering: {fmt_q(s, 'mm', 2)} < s_erf = {fmt_q(s_erf, 'mm', 2)}.")
        else:
            self.info(f"Wanddicke ausreichend ({fmt_num(eta * 100, 1)} % Ausnutzung).")
        ratio = (Da / (Da - 2 * s)).to("").magnitude
        if ratio > 1.2:
            self.warn(f"D_a/D_i = {fmt_num(ratio, 3)} > 1,2: Die Formel gilt nur für dünnwandige Schalen.")
        self.info("Nicht erfasst: Ausschnitte, Böden, Stutzen, äußere Lasten, Wechselbeanspruchung. Für "
                  "Druckgeräte sind die einschlägigen Regelwerke (AD 2000, DIN EN 13445/13480) maßgebend.")

    def sketch_svg(self, raw) -> str:
        s = Svg()
        cx, cy, r = 150, 110, 70
        s.circle(cx, cy, r)
        s.circle(cx, cy, r - 12, fill="#ffffff")
        for ang in range(0, 360, 45):
            import math

            a = math.radians(ang)
            s.arrow(cx + 22 * math.cos(a), cy + 22 * math.sin(a), cx + 52 * math.cos(a), cy + 52 * math.sin(a))
        s.text(cx, cy + 5, "p", 15, ACCENT, italic=True)
        s.dim_v(cx + r + 30, cy - r, cy + r, "D_a")
        s.text(cx + r - 4, cy - r + 6, "s", 12, "#6b7b8c", "start", True)
        s.arrow(300, 60, 300, 30).text(306, 48, "σ_t", 12, ACCENT, "start", True)
        return s.render()
