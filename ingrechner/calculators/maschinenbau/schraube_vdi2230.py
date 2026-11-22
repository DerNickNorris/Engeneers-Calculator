"""Schraubenverbindung: zulässige Montagevorspannkraft und Anziehdrehmoment (VDI 2230 Blatt 1)."""

from __future__ import annotations

import math

import numpy as np

from ingrechner.core.model import Calculator, ChoiceField, NumberField
from ingrechner.core.svg import ACCENT, FILL, INK, MUTED, Svg
from ingrechner.core.units import Q_, fmt_num, fmt_q

# Metrisches ISO-Regelgewinde (DIN 13-1): Nenndurchmesser d -> Steigung P,
# Kopfauflage-Ø d_w,min (ISO 4014/4017, Produktklasse A), Durchgangsloch d_h „mittel“ (ISO 273)
GEWINDE = {
    "M4": (4, 0.7, 5.88, 4.5), "M5": (5, 0.8, 6.88, 5.5), "M6": (6, 1.0, 8.88, 6.6),
    "M8": (8, 1.25, 11.63, 9.0), "M10": (10, 1.5, 14.63, 11.0), "M12": (12, 1.75, 16.63, 13.5),
    "M14": (14, 2.0, 19.64, 15.5), "M16": (16, 2.0, 22.49, 17.5), "M20": (20, 2.5, 28.19, 22.0),
    "M24": (24, 3.0, 33.61, 26.0), "M30": (30, 3.5, 42.75, 33.0), "M36": (36, 4.0, 51.11, 39.0),
}
# Festigkeitsklassen (ISO 898-1): Mindest-Dehngrenze R_p0,2 [N/mm²] für d ≤ 16 / d > 16 mm
KLASSEN = {"8.8": (640, 660), "10.9": (940, 940), "12.9": (1100, 1100)}


def gewinde_geometrie(d: float, P: float) -> tuple[float, float, float]:
    """Flankendurchmesser d2, Kerndurchmesser d3 und Spannungsquerschnitt A_s (DIN 13-28)."""
    d2 = d - 0.64952 * P
    d3 = d - 1.22687 * P
    As = math.pi / 4 * ((d2 + d3) / 2) ** 2
    return d2, d3, As


def montagewerte(d: float, P: float, Rp: float, mu_g: float, mu_k: float, d_km: float,
                 nu: float = 0.9) -> tuple[float, float]:
    """F_M,zul [N] und M_A [N·mm] nach VDI 2230 Blatt 1, Gl. (R2/1) bzw. (R5/…)."""
    d2, d3, As = gewinde_geometrie(d, P)
    d0 = (d2 + d3) / 2
    k = 1.5 * d2 / d0 * (P / (math.pi * d2) + 1.155 * mu_g)
    f_m = As * nu * Rp / math.sqrt(1 + 3 * k**2)
    m_a = f_m * (0.16 * P + 0.58 * d2 * mu_g + mu_k * d_km / 2)
    return f_m, m_a


class Schraube(Calculator):
    id = "mb.schraube_vdi2230"
    title = "Schraube: Vorspannkraft & Anziehdrehmoment"
    category = "Maschinenbau"
    description = (
        "Zulässige Montagevorspannkraft F_M,zul und Anziehdrehmoment M_A für Sechskantschrauben mit "
        "metrischem Regelgewinde bei 90 % Ausnutzung der Streckgrenze während der Montage."
    )
    norm = "VDI 2230 Blatt 1 (2015), Abschnitt 5.5.1; Gewinde DIN 13, Festigkeitsklassen ISO 898-1"
    keywords = ("schraube", "vorspannkraft", "anziehdrehmoment", "anzugsmoment", "vdi 2230", "gewinde",
                "drehmoment", "verschraubung")

    fields = [
        ChoiceField("gewinde", "Gewinde", [(k, f"{k} × {GEWINDE[k][1]:g}".replace(".", ",")) for k in GEWINDE], "M10"),
        ChoiceField("klasse", "Festigkeitsklasse", [(k, k) for k in KLASSEN], "8.8"),
        NumberField("mu_g", "Reibungszahl im Gewinde", "μ_G", "", 0.12, min=0.04, max=0.4, min_inclusive=True,
                    decimals=2, tooltip="VDI 2230 Tab. A5: verzinkt/geölt 0,10–0,16; ungeschmiert 0,14–0,24; "
                                        "MoS₂-Paste 0,08–0,12"),
        NumberField("mu_k", "Reibungszahl Kopfauflage", "μ_K", "", 0.12, min=0.04, max=0.4, min_inclusive=True,
                    decimals=2, tooltip="Meist gleich μ_G angesetzt"),
        NumberField("nu", "Ausnutzung der Streckgrenze", "ν", "", 0.9, min=0.5, max=1.0, min_inclusive=True,
                    decimals=2, tooltip="VDI 2230: ν = 0,9 (90 % von R_p0,2 durch Zug- und Torsionsspannung)"),
        NumberField("streuung", "Anziehfaktor", "α_A", "", 1.6, min=1, max=4, min_inclusive=True, decimals=2,
                    tooltip="Streuung des Anziehverfahrens (VDI 2230 Tab. A8): Drehmomentschlüssel 1,4–1,6; "
                            "Schlagschrauber 2,5–4; Streckgrenzgesteuert 1,0"),
    ]

    def compute(self, inp) -> None:
        d, P, dw, dh = GEWINDE[inp["gewinde"]]
        Rp = KLASSEN[inp["klasse"]][0 if d <= 16 else 1]
        mu_g, mu_k, nu, alpha = inp["mu_g"], inp["mu_k"], inp["nu"], inp["streuung"]
        d2, d3, As = gewinde_geometrie(d, P)
        d0 = (d2 + d3) / 2
        d_km = (dw + dh) / 2

        self.step("Gewindegeometrie", "d₂ = d − 0,64952·P;  d₃ = d − 1,22687·P",
                  f"d = {fmt_num(d, 0)} mm, P = {fmt_num(P, 2)} mm",
                  f"d₂ = {fmt_num(d2, 3)} mm, d₃ = {fmt_num(d3, 3)} mm")
        self.step("Spannungsquerschnitt", "A_s = π/4 · ((d₂ + d₃)/2)²",
                  f"A_s = π/4 · ({fmt_num(d0, 3)} mm)²", f"{fmt_num(As, 1)} mm²")
        self.step("Mittlerer Kopfauflage-Ø", "D_Km = (d_w + d_h)/2",
                  f"D_Km = ({fmt_num(dw, 2)} + {fmt_num(dh, 1)}) mm / 2", f"{fmt_num(d_km, 2)} mm")

        k = 1.5 * d2 / d0 * (P / (math.pi * d2) + 1.155 * mu_g)
        f_m, m_a = montagewerte(d, P, Rp, mu_g, mu_k, d_km, nu)
        self.step("Zulässige Montagevorspannkraft",
                  "F_M,zul = A_s · ν · R_p0,2 / √(1 + 3·[3/2 · d₂/d₀ · (P/(π·d₂) + 1,155·μ_G)]²)",
                  f"F_M,zul = {fmt_num(As, 1)} mm² · {fmt_num(nu, 2)} · {fmt_num(Rp, 0)} N/mm² / "
                  f"√(1 + 3 · {fmt_num(k, 4)}²)", fmt_q(Q_(f_m, "N"), "kN", 2))
        self.step("Anziehdrehmoment", "M_A = F_M,zul · (0,16·P + 0,58·d₂·μ_G + μ_K·D_Km/2)",
                  f"M_A = {fmt_num(f_m, 0)} N · (0,16·{fmt_num(P, 2)} + 0,58·{fmt_num(d2, 3)}·{fmt_num(mu_g, 2)} "
                  f"+ {fmt_num(mu_k, 2)}·{fmt_num(d_km, 2)}/2) mm", fmt_q(Q_(m_a, "N*mm"), "N*m", 1))

        sigma_m = f_m / As
        m_g = f_m * d2 / 2 * (P / (math.pi * d2) + 1.155 * mu_g)
        tau = m_g / (math.pi * d0**3 / 16)
        f_min = f_m / alpha
        self.step("Montage-Zugspannung", "σ_M = F_M,zul / A_s", f"σ_M = {fmt_num(f_m, 0)} N / {fmt_num(As, 1)} mm²",
                  f"{fmt_num(sigma_m, 1)} N/mm²")
        self.step("Torsionsspannung im Gewinde", "τ_M = M_G / W_p,  M_G = F_M · d₂/2 · (P/(π·d₂) + 1,155·μ_G)",
                  f"τ_M = {fmt_num(m_g, 0)} N·mm / {fmt_num(math.pi * d0 ** 3 / 16, 1)} mm³", f"{fmt_num(tau, 1)} N/mm²")
        self.step("Mindest-Vorspannkraft (Streuung)", "F_M,min = F_M,zul / α_A",
                  f"F_M,min = {fmt_num(f_m / 1000, 2)} kN / {fmt_num(alpha, 2)}", fmt_q(Q_(f_min, "N"), "kN", 2))

        self.result("FM", "Zul. Montagevorspannkraft", "F_M,zul", Q_(f_m, "N"), "kN", 2, highlight=True)
        self.result("MA", "Anziehdrehmoment", "M_A", Q_(m_a, "N*mm"), "N*m", 1, highlight=True)
        self.result("FMmin", "Mindest-Vorspannkraft", "F_M,min", Q_(f_min, "N"), "kN", 2)
        self.result("Rp", "Mindest-Dehngrenze", "R_p0,2", Q_(Rp, "N/mm**2"), "N/mm**2", 0)
        self.result("As", "Spannungsquerschnitt", "A_s", Q_(As, "mm**2"), "mm**2", 1)
        self.result("sigma", "Montage-Zugspannung", "σ_M", Q_(sigma_m, "N/mm**2"), "N/mm**2", 1)
        self.result("tau", "Torsionsspannung", "τ_M", Q_(tau, "N/mm**2"), "N/mm**2", 1)

        if abs(mu_g - mu_k) > 0.04:
            self.info("μ_G und μ_K weichen deutlich voneinander ab – Reibungszahlen möglichst durch Versuche absichern.")
        if mu_g < 0.08:
            self.warn("Sehr kleine Reibungszahl: Gefahr des Überdrehens, wenn die tatsächliche Reibung höher ist.")
        self.info(f"Annahmen: Sechskantschraube ISO 4017 (d_w = {fmt_num(dw, 2)} mm), Durchgangsloch mittel "
                  f"(d_h = {fmt_num(dh, 1)} mm), Schaftschraube ohne Taillierung.")
        self.info("Nicht nachgewiesen: Betriebskraft, Klemmkraft, Flächenpressung, Dauerhaltbarkeit und Setzen "
                  "– dafür ist die vollständige Rechnung nach VDI 2230 erforderlich.")

    def plot(self, fig, raw, result) -> bool:
        if not result.ok:
            return False
        d, P, dw, dh = GEWINDE[raw["gewinde"]]
        Rp = KLASSEN[raw["klasse"]][0 if d <= 16 else 1]
        mus = np.linspace(0.06, 0.24, 60)
        vals = [montagewerte(d, P, Rp, m, m, (dw + dh) / 2, float(raw["nu"])) for m in mus]
        ax1 = fig.subplots()
        ax2 = ax1.twinx()
        ax1.plot(mus, [v[0] / 1000 for v in vals], color="#1f6fb2", lw=2, label="F_M,zul")
        ax2.plot(mus, [v[1] / 1000 for v in vals], color="#c0392b", lw=2, ls="--", label="M_A")
        ax1.axvline(float(raw["mu_g"]), color="#9aa7b4", lw=1)
        ax1.set_xlabel("Reibungszahl μ_G = μ_K")
        ax1.set_ylabel("F_M,zul  [kN]", color="#1f6fb2")
        ax2.set_ylabel("M_A  [N·m]", color="#c0392b")
        ax2.spines["right"].set_visible(True)
        ax1.set_title(f"{raw['gewinde']} – {raw['klasse']}: Einfluss der Reibung")
        ax1.grid(True, alpha=0.3)
        return True

    def sketch_svg(self, raw) -> str:
        s = Svg()
        cx = 180
        s.rect(90, 80, 180, 34)                       # Bauteil 1
        s.rect(90, 114, 180, 34)                      # Bauteil 2
        s.rect(cx - 13, 60, 26, 112, fill="#ffffff")  # Schaft
        for y in range(122, 172, 6):                  # Gewinde
            s.line(cx - 13, y, cx + 13, y + 3, MUTED, 0.8)
        s.rect(cx - 30, 42, 60, 18, fill=FILL)        # Kopf
        s.rect(cx - 30, 172, 60, 16, fill=FILL)       # Mutter
        s.arrow(cx + 70, 50, cx + 34, 50).text(cx + 74, 46, "M_A", 13, ACCENT, "start", True)
        s.arrow(60, 97, 88, 97).arrow(60, 131, 88, 131)
        s.text(56, 118, "F_M", 13, ACCENT, "end", True)
        s.text(cx, 210, f"{raw.get('gewinde', 'M10')} · {raw.get('klasse', '8.8')}", 12, INK)
        return s.render()
