"""Wärmeleistung eines Wasserkreises: Massen-/Volumenstrom und Rohrdimensionierung."""

from __future__ import annotations

import math

from ingrechner.core.model import Calculator, ChoiceField, NumberField
from ingrechner.core.svg import ACCENT, INK, Svg
from ingrechner.core.units import Q_, fmt_num, fmt_q

from .druckverlust_rohr import rohrreibungszahl

# Mittelschwere Gewinderohre DIN EN 10255 (M): Nennweite -> Innendurchmesser [mm]
ROHRE = {"DN 10": 12.5, "DN 15": 16.1, "DN 20": 21.7, "DN 25": 27.3, "DN 32": 36.0, "DN 40": 41.9,
         "DN 50": 53.1, "DN 65": 68.9, "DN 80": 80.9, "DN 100": 105.3}
# Wärmeträger bei ca. 40 °C: (Name, c [kJ/(kg·K)], ρ [kg/m³], ν [mm²/s])
MEDIEN = {
    "wasser": ("Wasser (≈ 40 °C)", 4.18, 992.2, 0.658),
    "glykol30": ("Ethylenglykol 30 % (≈ 20 °C)", 3.70, 1040.0, 2.6),
}
BENUTZER = {"medium": ["benutzer"]}
K_ROHR = 0.045  # mm, Stahlrohr neu


def dn_vorschlag(d_min_mm: float) -> str | None:
    return next((dn for dn, di in ROHRE.items() if di >= d_min_mm), None)


class WaermeleistungRohr(Calculator):
    id = "fl.waermeleistung_rohr"
    title = "Wärmeleistung & Rohrdimension"
    category = "Fluid / Thermo"
    description = (
        "Massen- und Volumenstrom aus Wärmeleistung und Temperaturspreizung, erforderlicher "
        "Rohrinnendurchmesser für eine Zielgeschwindigkeit, Nennweiten-Vorschlag (Gewinderohr) "
        "sowie Geschwindigkeit und Druckgefälle in der gewählten Nennweite."
    )
    norm = "Q̇ = ṁ · c · Δθ; Rohre DIN EN 10255 (mittelschwer); Druckgefälle nach Colebrook-White"
    keywords = ("wärmeleistung", "heizung", "kühlung", "massenstrom", "volumenstrom", "spreizung", "rohrnetz",
                "nennweite", "dn", "dimensionierung", "pumpe")

    fields = [
        NumberField("Q", "Wärmeleistung", "Q̇", "kW", 25, min=0, decimals=2),
        NumberField("dt", "Temperaturspreizung", "Δθ", "K", 20, min=0, decimals=1,
                    tooltip="z. B. Heizkörper 70/50 → 20 K, Fußbodenheizung 5–10 K, Kaltwasser 6/12 → 6 K"),
        ChoiceField("medium", "Wärmeträger", [*[(k, v[0]) for k, v in MEDIEN.items()],
                                              ("benutzer", "Benutzerdefiniert")], "wasser"),
        NumberField("c", "Spez. Wärmekapazität", "c", "kJ/(kg*K)", 4.18, min=0, decimals=3, visible_if=BENUTZER),
        NumberField("rho", "Dichte", "ρ", "kg/m**3", 992.2, min=0, decimals=1, visible_if=BENUTZER),
        NumberField("nu", "Kinematische Viskosität", "ν", "mm**2/s", 0.658, min=0, decimals=3, visible_if=BENUTZER),
        NumberField("v", "Zielgeschwindigkeit", "v_ziel", "m/s", 0.8, min=0, decimals=2,
                    tooltip="Richtwerte Heizung: Anbindeleitungen 0,3–0,5 m/s, Verteilleitungen 0,5–1,0 m/s, "
                            "Hauptleitungen bis 1,5 m/s (Geräusche!)"),
        ChoiceField("dn", "Gewählte Nennweite", [("auto", "automatisch (Vorschlag)"),
                                                 *[(k, f"{k} (d_i = {v:g} mm)".replace(".", ","))
                                                   for k, v in ROHRE.items()]], "auto"),
    ]

    def compute(self, inp) -> None:
        if inp["medium"] == "benutzer":
            c, rho, nu = inp["c"], inp["rho"], inp["nu"]
        else:
            _, c_, rho_, nu_ = MEDIEN[inp["medium"]]
            c, rho, nu = Q_(c_, "kJ/(kg*K)"), Q_(rho_, "kg/m**3"), Q_(nu_, "mm**2/s")
            self.info(f"Stoffwerte {MEDIEN[inp['medium']][0]}: c = {fmt_num(c_, 2)} kJ/(kg·K), "
                      f"ρ = {fmt_num(rho_, 1)} kg/m³.")
        Q, dt, v = inp["Q"], inp["dt"], inp["v"]
        m = (Q / (c * dt)).to("kg/hour")
        V = (m / rho).to("m**3/hour")
        d_min = ((4 * V / (math.pi * v)) ** 0.5).to("mm")
        self.step("Massenstrom", "ṁ = Q̇ / (c · Δθ)",
                  f"ṁ = {fmt_q(Q, 'kW', 2)} / ({fmt_q(c, 'kJ/(kg*K)', 3)} · {fmt_q(dt, 'K', 1)})", fmt_q(m, "kg/hour", 1))
        self.step("Volumenstrom", "V̇ = ṁ / ρ", f"V̇ = {fmt_q(m, 'kg/hour', 1)} / {fmt_q(rho, 'kg/m**3', 1)}",
                  fmt_q(V, "m**3/hour", 3))
        self.step("Erforderlicher Innendurchmesser", "d_i = √(4 · V̇ / (π · v_ziel))",
                  f"d_i = √(4 · {fmt_q(V, 'm**3/s', 6)} / (π · {fmt_q(v, 'm/s', 2)}))", fmt_q(d_min, "mm", 1))

        auto = dn_vorschlag(d_min.magnitude)
        dn = auto if inp["dn"] == "auto" else inp["dn"]
        if dn is None:
            raise ValueError("Volumenstrom zu groß für die hinterlegten Nennweiten (bis DN 100).")
        di = Q_(ROHRE[dn], "mm")
        v_ist = (4 * V / (math.pi * di**2)).to("m/s")
        re = (v_ist * di / nu).to("").magnitude
        lam = rohrreibungszahl(re, K_ROHR / ROHRE[dn])
        R = (lam / di * rho * v_ist**2 / 2).to("Pa/m")
        self.step(f"Geschwindigkeit in {dn}", "v = 4 · V̇ / (π · d_i²)",
                  f"v = 4 · {fmt_q(V, 'm**3/s', 6)} / (π · ({fmt_q(di, 'm', 4)})²)", fmt_q(v_ist, "m/s", 3))
        self.step("Druckgefälle (Rohrreibung)", "R = λ / d_i · ρ · v² / 2",
                  f"Re = {fmt_num(re, 0)}, λ = {fmt_num(lam, 4)} (k = {fmt_num(K_ROHR, 3)} mm)", fmt_q(R, "Pa/m", 1))

        self.result("m", "Massenstrom", "ṁ", m, "kg/hour", 1, highlight=True)
        self.result("V", "Volumenstrom", "V̇", V, "m**3/hour", 3, highlight=True)
        self.result("Vls", "Volumenstrom", "V̇", V, "liter/s", 4)
        self.result("dmin", "Erforderlicher Innendurchmesser", "d_i,erf", d_min, "mm", 1)
        self.result("v_ist", f"Geschwindigkeit in {dn}", "v", v_ist, "m/s", 3, highlight=True)
        self.result("R", "Druckgefälle", "R", R, "Pa/m", 1, highlight=True)
        self.result("Rmbar", "Druckgefälle", "R", R, "mbar/m", 3)

        self.info(f"Nennweiten-Vorschlag: {auto} (d_i = {fmt_num(ROHRE[auto], 1)} mm)." if auto else "")
        if v_ist.magnitude > 1.5:
            self.warn(f"Geschwindigkeit {fmt_q(v_ist, 'm/s', 2)} > 1,5 m/s – Fließgeräusche wahrscheinlich.")
        if R.magnitude > 250:
            self.warn(f"Druckgefälle {fmt_q(R, 'Pa/m', 0)} > 250 Pa/m – für Heizungsnetze üblich sind 50–150 Pa/m.")
        elif R.magnitude < 30:
            self.info("Druckgefälle < 30 Pa/m – Rohr eventuell überdimensioniert.")
        self.info("Einzelwiderstände (Bögen, Ventile, Wärmeübertrager) kommen hinzu – siehe Rechner "
                  "„Druckverlust Rohrleitung“.")
        self._messages = [msg for msg in self._messages if msg.text]

    def sketch_svg(self, raw) -> str:
        s = Svg()
        s.rect(30, 70, 70, 80, fill="#ffffff").text(65, 105, "Erzeuger", 11, INK).text(65, 122, "Q̇", 13, ACCENT,
                                                                                         italic=True)
        s.rect(260, 70, 70, 80, fill="#ffffff").text(295, 105, "Verbraucher", 11, INK)
        s.line(100, 85, 260, 85, "#c0392b", 4).line(100, 135, 260, 135, "#1f6fb2", 4)
        s.arrow(150, 70, 210, 70, "#c0392b").text(180, 62, "θ_VL", 12, "#c0392b", italic=True)
        s.arrow(210, 150, 150, 150, "#1f6fb2").text(180, 168, "θ_RL", 12, "#1f6fb2", italic=True)
        s.text(180, 112, "ṁ, V̇, DN", 12, ACCENT, italic=True)
        s.text(180, 200, "Spreizung Δθ = Vorlauf − Rücklauf", 11, "#6b7b8c")
        return s.render()
