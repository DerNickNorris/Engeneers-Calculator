"""Druckverlust in geraden Rohrleitungen (Darcy-Weisbach / Colebrook-White)."""

from __future__ import annotations

import math

import numpy as np

from ingrechner.core.model import Calculator, ChoiceField, NumberField
from ingrechner.core.svg import ACCENT, INK, MUTED, Svg
from ingrechner.core.units import Q_, fmt_num, fmt_q

# Stoffwerte bei ca. 1 bar: (Name, Dichte kg/m³, kin. Viskosität mm²/s)
MEDIEN = {
    "wasser_10": ("Wasser 10 °C", 999.7, 1.306),
    "wasser_20": ("Wasser 20 °C", 998.2, 1.004),
    "wasser_60": ("Wasser 60 °C", 983.2, 0.474),
    "luft_20": ("Luft 20 °C, 1,013 bar", 1.204, 15.11),
}
BENUTZER = {"medium": ["benutzer"]}
G = Q_(9.80665, "m/s**2")


def lambda_colebrook(re: float, k_rel: float, tol: float = 1e-12) -> float:
    """Rohrreibungszahl nach Colebrook-White (iterativ, Startwert Swamee-Jain)."""
    lam = 0.25 / math.log10(k_rel / 3.7 + 5.74 / re**0.9) ** 2
    for _ in range(100):
        rhs = -2.0 * math.log10(k_rel / 3.71 + 2.51 / (re * math.sqrt(lam)))
        new = 1.0 / rhs**2
        if abs(new - lam) < tol:
            return new
        lam = new
    return lam


def rohrreibungszahl(re: float, k_rel: float) -> float:
    return 64.0 / re if re < 2320 else lambda_colebrook(re, k_rel)


class DruckverlustRohr(Calculator):
    id = "fl.druckverlust_rohr"
    title = "Druckverlust Rohrleitung"
    category = "Fluid / Thermo"
    description = (
        "Strömungsgeschwindigkeit, Reynoldszahl, Rohrreibungszahl und Druckverlust einer "
        "geraden Rohrleitung inklusive Einzelwiderständen und geodätischer Höhe "
        "(inkompressible Strömung)."
    )
    norm = "Darcy-Weisbach mit Colebrook-White; vgl. VDI-Wärmeatlas, Abschnitt L1"
    keywords = ("druckverlust", "rohr", "rohrleitung", "reynolds", "colebrook", "strömung",
                "hydraulik", "lambda", "zeta")

    fields = [
        NumberField("Q", "Volumenstrom", "V̇", "m**3/h", 10, min=0, decimals=3),
        NumberField("d", "Rohrinnendurchmesser", "d_i", "mm", 50, min=0, decimals=1),
        NumberField("L", "Rohrlänge", "L", "m", 100, min=0, min_inclusive=True, decimals=1),
        NumberField("k", "Absolute Rauheit", "k", "mm", 0.05, min=0, min_inclusive=True, decimals=4,
                    tooltip="Stahl neu 0,02–0,1 mm; Stahl leicht verrostet 0,15–0,4 mm; "
                            "Kunststoff/Kupfer 0,0015–0,007 mm; Guss 0,25–1 mm"),
        NumberField("zeta", "Summe Einzelwiderstände", "Σζ", "", 0, min=0, min_inclusive=True, decimals=2,
                    tooltip="z. B. Bogen 90° ≈ 0,3–0,5; Absperrschieber offen ≈ 0,2; Rückschlagventil ≈ 2–4"),
        NumberField("dz", "Höhendifferenz (Ende − Anfang)", "Δz", "m", 0, decimals=2,
                    tooltip="Positiv, wenn das Fluid nach oben gefördert wird"),
        ChoiceField("medium", "Medium", [
            *[(k, v[0]) for k, v in MEDIEN.items()],
            ("benutzer", "Benutzerdefiniert"),
        ], "wasser_20"),
        NumberField("rho", "Dichte", "ρ", "kg/m**3", 998.2, min=0, decimals=1, visible_if=BENUTZER),
        NumberField("nu", "Kinematische Viskosität", "ν", "mm**2/s", 1.004, min=0, decimals=4,
                    visible_if=BENUTZER),
    ]

    def _stoff(self, inp):
        if inp["medium"] == "benutzer":
            return inp["rho"], inp["nu"]
        _, rho, nu = MEDIEN[inp["medium"]]
        return Q_(rho, "kg/m**3"), Q_(nu, "mm**2/s")

    def compute(self, inp) -> None:
        Qv, d, L, k = inp["Q"], inp["d"], inp["L"], inp["k"]
        rho, nu = self._stoff(inp)
        if inp["medium"] != "benutzer":
            self.info(f"Stoffwerte {MEDIEN[inp['medium']][0]}: ρ = {fmt_q(rho, 'kg/m**3', 1)}, "
                      f"ν = {fmt_q(nu, 'mm**2/s', 3)}.")

        A = math.pi * d**2 / 4
        v = (Qv / A).to("m/s")
        re = (v * d / nu).to("").magnitude
        k_rel = (k / d).to("").magnitude
        lam = rohrreibungszahl(re, k_rel)

        self.step("Strömungsgeschwindigkeit", "v = V̇ / (π · d_i² / 4)",
                  f"v = {fmt_q(Qv, 'm**3/s', 6)} / (π · ({fmt_q(d, 'm', 4)})² / 4)", fmt_q(v, "m/s", 3))
        self.step("Reynoldszahl", "Re = v · d_i / ν",
                  f"Re = {fmt_q(v, 'm/s', 3)} · {fmt_q(d, 'm', 4)} / {fmt_q(nu, 'm**2/s', 9)}",
                  fmt_num(re, 0))
        if re < 2320:
            self.step("Rohrreibungszahl (laminar)", "λ = 64 / Re", f"λ = 64 / {fmt_num(re, 0)}", fmt_num(lam, 5))
        else:
            self.step("Rohrreibungszahl (Colebrook-White)",
                      "1/√λ = −2 · lg( k/(3,71·d_i) + 2,51/(Re·√λ) )",
                      f"k/d_i = {fmt_num(k_rel, 6)}; Re = {fmt_num(re, 0)}; iterativ gelöst", fmt_num(lam, 5))

        dyn = (rho * v**2 / 2).to("Pa")
        dp_r = (lam * L / d * dyn).to("Pa")
        dp_e = (inp["zeta"] * dyn).to("Pa")
        dp_g = (rho * G * inp["dz"]).to("Pa")
        dp = dp_r + dp_e + dp_g

        self.step("Dynamischer Druck", "p_dyn = ρ · v² / 2",
                  f"p_dyn = {fmt_q(rho, 'kg/m**3', 1)} · ({fmt_q(v, 'm/s', 3)})² / 2", fmt_q(dyn, "Pa", 1))
        self.step("Reibungsdruckverlust", "Δp_R = λ · L / d_i · p_dyn",
                  f"Δp_R = {fmt_num(lam, 5)} · {fmt_q(L, 'm', 1)} / {fmt_q(d, 'm', 4)} · {fmt_q(dyn, 'Pa', 1)}",
                  fmt_q(dp_r, "bar", 4))
        self.step("Einzelwiderstände", "Δp_E = Σζ · p_dyn",
                  f"Δp_E = {fmt_num(inp['zeta'], 2)} · {fmt_q(dyn, 'Pa', 1)}", fmt_q(dp_e, "bar", 4))
        self.step("Geodätischer Anteil", "Δp_geo = ρ · g · Δz",
                  f"Δp_geo = {fmt_q(rho, 'kg/m**3', 1)} · 9,807 m/s² · {fmt_q(inp['dz'], 'm', 2)}",
                  fmt_q(dp_g, "bar", 4))
        self.step("Gesamtdruckdifferenz", "Δp = Δp_R + Δp_E + Δp_geo",
                  f"Δp = {fmt_q(dp_r, 'bar', 4)} + {fmt_q(dp_e, 'bar', 4)} + {fmt_q(dp_g, 'bar', 4)}",
                  fmt_q(dp, "bar", 4))

        hv = ((dp_r + dp_e) / (rho * G)).to("m")
        self.result("v", "Strömungsgeschwindigkeit", "v", v, "m/s", 3, highlight=True)
        self.result("Re", "Reynoldszahl", "Re", Q_(re, ""), "", 0)
        self.result("lam", "Rohrreibungszahl", "λ", Q_(lam, ""), "", 5)
        self.result("dp_r", "Reibungsdruckverlust", "Δp_R", dp_r, "bar", 4)
        self.result("dp_e", "Druckverlust Einzelwiderstände", "Δp_E", dp_e, "bar", 4)
        self.result("dp_g", "Geodätische Druckdifferenz", "Δp_geo", dp_g, "bar", 4)
        self.result("dp", "Gesamtdruckdifferenz", "Δp", dp, "bar", 4, highlight=True)
        self.result("dp_mbar", "Gesamtdruckdifferenz", "Δp", dp, "mbar", 1)
        self.result("hv", "Verlusthöhe (ohne Δz)", "h_v", hv, "m", 3)

        # Bewertung
        if re < 2320:
            self.info("Laminare Strömung (Re < 2320).")
        elif re < 4000:
            self.warn("Übergangsbereich 2320 ≤ Re < 4000: Strömungsform instabil, λ unsicher "
                      "(hier turbulent nach Colebrook gerechnet, eher konservativ).")
        else:
            self.info("Turbulente Strömung (Re ≥ 4000).")
        is_water = inp["medium"].startswith("wasser")
        if is_water and v.magnitude > 3:
            self.warn(f"Hohe Geschwindigkeit v = {fmt_q(v, 'm/s', 2)} > 3 m/s: Geräusche, Erosion und "
                      "Druckstöße möglich.")
        elif is_water and v.magnitude < 0.3:
            self.info("Sehr geringe Geschwindigkeit (< 0,3 m/s): Ablagerungen möglich, Rohr eventuell überdimensioniert.")
        if inp["medium"] == "luft_20" and abs(dp.to("bar").magnitude) > 0.1:
            self.warn("Druckverlust > 10 % des Absolutdrucks: Annahme inkompressibler Strömung ist "
                      "für Gase nicht mehr zulässig.")

    # -------------------------------------------------------------- Diagramm
    def plot(self, fig, raw, result) -> bool:
        if not result.ok:
            return False
        inp = {f.key: raw.get(f.key, f.default) for f in self.fields}
        rho, nu = self._stoff({**inp, "rho": Q_(float(inp["rho"]), "kg/m**3"),
                               "nu": Q_(float(inp["nu"]), "mm**2/s")})
        d = float(inp["d"]) / 1000
        L, k = float(inp["L"]), float(inp["k"]) / 1000
        zeta, dz = float(inp["zeta"]), float(inp["dz"])
        rho_v, nu_v = rho.to("kg/m**3").magnitude, nu.to("m**2/s").magnitude
        q_op = float(inp["Q"])
        qs = np.linspace(q_op * 0.02, q_op * 2, 120)
        dps = []
        for q in qs:
            v = (q / 3600) / (math.pi * d**2 / 4)
            lam = rohrreibungszahl(v * d / nu_v, k / d)
            dps.append(((lam * L / d + zeta) * rho_v * v**2 / 2 + rho_v * 9.80665 * dz) / 1e5)
        ax = fig.subplots()
        ax.plot(qs, dps, color="#1f6fb2", lw=2, label="Anlagenkennlinie")
        ax.plot([q_op], [result.value("dp")], "o", color="#2b3a4a", label="Betriebspunkt")
        ax.set_xlabel("Volumenstrom V̇  [m³/h]")
        ax.set_ylabel("Δp  [bar]")
        ax.set_title("Rohrkennlinie")
        ax.grid(True, alpha=0.3)
        ax.legend(loc="upper left")
        return True

    # ---------------------------------------------------------------- Skizze
    def sketch_svg(self, raw) -> str:
        s = Svg()
        s.rect(40, 85, 280, 50)
        s.rect(40, 95, 280, 30, fill="#ffffff", stroke="#ffffff", width=0)
        s.line(40, 95, 320, 95, INK, 1.2).line(40, 125, 320, 125, INK, 1.2)
        s.arrow(120, 110, 240, 110).text(180, 104, "V̇", 14, ACCENT, italic=True)
        s.text(34, 75, "p₁", 13, INK, "start", italic=True).text(326, 75, "p₂", 13, INK, "end", italic=True)
        s.dim_v(338, 95, 125, "", "right")
        s.text(346, 114, "dᵢ", 12, MUTED, "start", italic=True)
        s.dim_h(40, 320, 170, "L")
        s.text(180, 205, "Δp = p₁ − p₂", 12, MUTED)
        return s.render()
