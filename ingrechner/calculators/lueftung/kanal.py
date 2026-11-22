"""Luftkanal: Dimensionierung (rund/rechteckig) und Druckverlust einer Teilstrecke."""

from __future__ import annotations

import math

import numpy as np

from ingrechner.calculators.fluid.druckverlust_rohr import rohrreibungszahl
from ingrechner.core.model import Calculator, ChoiceField, NumberField
from ingrechner.core.svg import ACCENT, INK, MUTED, Svg
from ingrechner.core.units import Q_, fmt_num

from ._lu import RAUHEIT, RECHTECK, RUND, d_gleichwertig, d_hydraulisch, luft, luft_felder, rauheit_feld

RUND_V = {"form": ["rund"], "dim": ["vorgabe"]}
RECHT_V = {"form": ["rechteck"], "dim": ["vorgabe"]}
RECHT = {"form": ["rechteck"]}


class Luftkanal(Calculator):
    id = "lu.kanal"
    title = "Luftkanal – Dimensionierung"
    category = "Lüftung / RLT"
    description = (
        "Querschnitt und Druckverlust eines runden oder rechteckigen Luftkanals: automatische Wahl der "
        "Normgröße nach maximaler Geschwindigkeit, Strömungsgeschwindigkeit, hydraulischer und gleichwertiger "
        "Durchmesser, Druckgefälle R, Einzelwiderstände; Luftdichte aus der Mediendatenbank (Temperatur, Höhe)."
    )
    norm = "Darcy-Weisbach/Colebrook mit d_h = 2ab/(a+b); Rundrohre DIN EN 1506, Rechteckkanäle DIN EN 1505"
    keywords = ("luftkanal", "kanal", "lüftungskanal", "wickelfalzrohr", "rechteckkanal", "dimensionierung",
                "luftgeschwindigkeit", "druckverlust", "lüftung", "rlt", "hydraulischer durchmesser")

    fields = [
        NumberField("V", "Volumenstrom", "V̇", "m**3/hour", 2000, min=0, decimals=0),
        ChoiceField("form", "Querschnitt", [("rund", "rund"), ("rechteck", "rechteckig")], "rund"),
        ChoiceField("dim", "Abmessung", [("auto", "automatisch nach v_max"), ("vorgabe", "vorgeben")], "auto"),
        NumberField("d", "Durchmesser", "d", "mm", 315, min=0, decimals=0, visible_if=RUND_V),
        NumberField("a", "Breite", "a", "mm", 500, min=0, decimals=0, visible_if=RECHT_V),
        NumberField("b", "Höhe", "b", "mm", 300, min=0, decimals=0, visible_if=RECHT,
                    tooltip="Bei automatischer Dimensionierung: feste Kanalhöhe (z. B. Deckenhohlraum)"),
        NumberField("vmax", "Maximale Luftgeschwindigkeit", "v_max", "m/s", 5, min=0, decimals=1,
                    tooltip="Wohnungslüftung ≤ 2–3 m/s, Büro-Nebenkanäle 3–5 m/s, Hauptkanäle 5–8 m/s, "
                            "Zentrale/Schacht bis 10 m/s"),
        NumberField("L", "Länge", "L", "m", 20, min=0, min_inclusive=True, decimals=1),
        NumberField("zeta", "Summe Einzelwiderstände", "Σζ", "", 1.5, min=0, min_inclusive=True, decimals=2,
                    tooltip="Bogen 90° rund ≈ 0,2–0,3; Rechteckbogen ≈ 0,3–1,2; T-Abzweig ≈ 0,5–1,5; Gitter 2–3"),
        rauheit_feld(),
        *luft_felder(20),
    ]

    def _abmessung(self, inp, V: float) -> tuple[str, float, float, float, float]:
        """(Bezeichnung, A m², d_h m, a m, b m) – bei rund a = b = d."""
        vmax = inp["vmax"].to("m/s").magnitude
        if inp["form"] == "rund":
            if inp["dim"] == "auto":
                d = next((dd / 1000 for dd in RUND if V / (math.pi * (dd / 1000) ** 2 / 4) <= vmax), RUND[-1] / 1000)
            else:
                d = inp["d"].to("m").magnitude
            return f"Ø {fmt_num(d * 1000, 0)} mm", math.pi * d**2 / 4, d, d, d
        b = inp["b"].to("m").magnitude
        if inp["dim"] == "auto":
            a = next((aa / 1000 for aa in RECHTECK if V / (aa / 1000 * b) <= vmax), RECHTECK[-1] / 1000)
        else:
            a = inp["a"].to("m").magnitude
        return f"{fmt_num(a * 1000, 0)} × {fmt_num(b * 1000, 0)} mm", a * b, d_hydraulisch(a, b), a, b

    def compute(self, inp) -> None:
        med, z = luft(inp)
        V = inp["V"].to("m**3/s").magnitude
        name, A, dh, a, b = self._abmessung(inp, V)
        k = RAUHEIT[inp["rauheit"]][1] / 1000
        v = V / A
        pdyn = z.rho * v**2 / 2
        lam = rohrreibungszahl(v * dh / z.nu, k / dh)     # tatsächliche Geschwindigkeit, d_h
        R = lam / dh * pdyn
        dp_r = R * inp["L"].to("m").magnitude
        dp_z = float(inp["zeta"]) * pdyn
        self.step("Luftzustand", "ρ = p·M/(Z·R·T)", f"{med.name}, θ = {fmt_num(z.theta, 1)} °C, "
                  f"p = {fmt_num(z.p / 100, 0)} hPa", f"ρ = {fmt_num(z.rho, 3)} kg/m³, ν = {fmt_num(z.nu * 1e6, 2)} mm²/s")
        self.step("Querschnitt", "A; d_h = 4A/U" + (" = 2ab/(a+b)" if inp["form"] == "rechteck" else ""),
                  name + (" (automatisch)" if inp["dim"] == "auto" else ""),
                  f"A = {fmt_num(A, 4)} m², d_h = {fmt_num(dh * 1000, 0)} mm")
        re = v * dh / z.nu
        self.step("Geschwindigkeit", "v = V̇ / A;  Re = v · d_h / ν", f"V̇ = {fmt_num(V * 3600, 0)} m³/h",
                  f"v = {fmt_num(v, 2)} m/s, Re = {fmt_num(re, 0)}")
        self.step("Druckgefälle", "R = λ / d_h · ρ v²/2", f"λ = {fmt_num(lam, 4)}, p_dyn = {fmt_num(pdyn, 2)} Pa",
                  f"R = {fmt_num(R, 2)} Pa/m")
        self.step("Druckverlust", "Δp = R · L + Σζ · ρ v²/2",
                  f"Δp = {fmt_num(R, 2)} · {fmt_num(inp['L'].to('m').magnitude, 1)} + {fmt_num(float(inp['zeta']), 2)} · "
                  f"{fmt_num(pdyn, 2)}", f"{fmt_num(dp_r + dp_z, 1)} Pa")

        self.result("v", "Luftgeschwindigkeit", "v", Q_(v, "m/s"), "m/s", 2, highlight=True)
        self.result("dp", "Druckverlust", "Δp", Q_(dp_r + dp_z, "Pa"), "Pa", 1, highlight=True)
        self.result("R", "Druckgefälle", "R", Q_(R, "Pa/m"), "Pa/m", 2, highlight=True)
        self.result("pdyn", "Dynamischer Druck", "p_dyn", Q_(pdyn, "Pa"), "Pa", 2)
        self.result("A", "Querschnittsfläche", "A", Q_(A, "m**2"), "m**2", 4)
        self.result("dh", "Hydraulischer Durchmesser", "d_h", Q_(dh * 1000, "mm"), "mm", 0)
        if inp["form"] == "rechteck":
            self.result("a", "Kanalbreite", "a", Q_(a * 1000, "mm"), "mm", 0, highlight=inp["dim"] == "auto")
            self.result("de", "Gleichwertiger Durchmesser", "d_e", Q_(d_gleichwertig(a, b) * 1000, "mm"), "mm", 0)
            if max(a, b) / min(a, b) > 4:
                self.warn("Seitenverhältnis > 4:1 – unwirtschaftlich (Blechbedarf, Druckverlust); 1:1 bis 3:1 "
                          "anstreben.")
        else:
            self.result("d", "Durchmesser", "d", Q_(a * 1000, "mm"), "mm", 0, highlight=inp["dim"] == "auto")
        vmax = inp["vmax"].to("m/s").magnitude
        if v > vmax * 1.001:
            self.warn(f"v = {fmt_num(v, 2)} m/s > v_max = {fmt_num(vmax, 1)} m/s – Strömungsgeräusche; größeren "
                      "Querschnitt wählen" + (" (größte Normgröße erreicht)." if inp["dim"] == "auto" else "."))
        if R > 2:
            self.info(f"Druckgefälle {fmt_num(R, 2)} Pa/m – übliche Auslegung 0,5–1,5 Pa/m (Hauptkanäle).")
        self.info("Schallleistung und Regelbarkeit getrennt prüfen; Luftdichtheitsklasse nach DIN EN 16798-3.")

    def plot(self, fig, raw, result) -> bool:
        if not result.ok:
            return False
        V0 = float(raw["V"])
        Vs = np.linspace(V0 * 0.2, V0 * 2, 60)
        dp0, v0 = result.value("dp"), result.value("v")
        ax = fig.subplots()
        ax.plot(Vs, dp0 * (Vs / V0) ** 1.9, color="#1f6fb2", lw=2, label="Δp (≈ V̇^1,9)")
        ax.plot([V0], [dp0], "o", color="#c0392b")
        ax2 = ax.twinx()
        ax2.plot(Vs, v0 * Vs / V0, color="#27ae60", lw=1.5, ls="--", label="v")
        ax2.axhline(float(raw["vmax"]), color="#27ae60", lw=0.8, ls=":")
        ax2.set_ylabel("v  [m/s]", color="#27ae60")
        ax.set_xlabel("Volumenstrom V̇  [m³/h]")
        ax.set_ylabel("Δp  [Pa]")
        ax.set_title("Druckverlust und Geschwindigkeit des gewählten Querschnitts")
        ax.grid(True, alpha=0.3)
        return True

    def sketch_svg(self, raw) -> str:
        s = Svg()
        if raw.get("form", "rund") == "rund":
            s.circle(110, 110, 60, fill="#dce6f1").text(110, 114, "d", 16, INK, italic=True)
        else:
            s.rect(40, 70, 140, 80, fill="#dce6f1").text(110, 64, "a", 14, INK, italic=True)
            s.text(190, 114, "b", 14, INK, "start", True)
        s.arrow(220, 110, 330, 110, ACCENT).text(275, 100, "V̇, v", 12, INK, italic=True)
        s.text(275, 140, "R · L + Σζ · ρv²/2", 11, MUTED)
        return s.render()
