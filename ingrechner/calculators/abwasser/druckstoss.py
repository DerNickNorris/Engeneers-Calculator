"""Druckstoß (Joukowsky) beim Pumpenausfall bzw. schnellem Schließen – Abschätzung."""

from __future__ import annotations

import math

import numpy as np

from ingrechner.core.model import Calculator, ChoiceField, NumberField
from ingrechner.core.svg import ACCENT, INK, MUTED, Svg
from ingrechner.core.units import Q_, fmt_num

# Elastizitätsmodul der Rohrwand in N/mm² (Kurzzeitwerte)
E_ROHR = {
    "stahl": ("Stahl", 210000),
    "guss": ("Guss duktil", 170000),
    "pe100": ("PE 100 (Kurzzeit-E ≈ 1100 N/mm²)", 1100),
    "pvc": ("PVC-U", 3000),
    "gfk": ("GFK", 15000),
    "beton": ("Stahlbeton / Spannbeton", 30000),
    "frei": ("Eigener Wert", None),
}
FREI = {"werkstoff": ["frei"]}


def wellengeschwindigkeit(K: float, rho: float, E: float, di: float, s: float) -> float:
    """Druckwellengeschwindigkeit a in m/s im elastischen Rohr (dünnwandig, Korteweg/Joukowsky)."""
    return math.sqrt(K / rho / (1 + K * di / (E * s)))


class Druckstoss(Calculator):
    id = "aw.druckstoss"
    title = "Druckstoß (Joukowsky)"
    category = "Abwasser / Klärwerk"
    description = (
        "Abschätzung des Druckstoßes in einer Druckleitung beim Pumpenausfall oder schnellen Schließen: "
        "Druckwellengeschwindigkeit aus Rohrelastizität, Reflexionszeit, Druckerhöhung nach Joukowsky bzw. "
        "Michaud, Maximal- und Minimaldruck im Vergleich zu Nenndruck und Dampfdruck."
    )
    norm = "Δp = ρ · a · Δv (Joukowsky, T_s ≤ 2L/a); Δp = 2ρLΔv/T_s (Michaud); vgl. DVGW W 303, DWA-A 134"
    keywords = ("druckstoß", "druckstoss", "joukowsky", "michaud", "wellengeschwindigkeit", "pumpenausfall",
                "wasserschlag", "unterdruck", "kavitation", "druckleitung", "reflexionszeit", "nenndruck")

    fields = [
        NumberField("v0", "Fließgeschwindigkeit vor dem Ereignis", "v₀", "m/s", 1.2, min=0, decimals=2,
                    tooltip="Geschwindigkeitsänderung Δv = v₀ (vollständiger Stillstand)"),
        NumberField("L", "Leitungslänge", "L", "m", 850, min=0, decimals=1),
        NumberField("da", "Außendurchmesser", "d_a", "mm", 160, min=0, decimals=1),
        NumberField("s", "Wanddicke", "s", "mm", 14.6, min=0, decimals=2),
        ChoiceField("werkstoff", "Rohrwerkstoff", [(k, v[0]) for k, v in E_ROHR.items()], "pe100"),
        NumberField("E", "Elastizitätsmodul Rohr", "E", "N/mm**2", 1100, min=0, decimals=0, visible_if=FREI),
        NumberField("rho", "Dichte des Mediums", "ρ", "kg/m**3", 1000, min=0, decimals=1),
        NumberField("K", "Kompressionsmodul des Mediums", "K", "N/mm**2", 2100, min=0, decimals=0,
                    tooltip="Wasser ≈ 2100 N/mm²; Luft- oder Gaseinschlüsse verringern K stark"),
        NumberField("Ts", "Schließ- bzw. Auslaufzeit", "T_s", "s", 1.0, min=0, min_inclusive=True, decimals=2,
                    tooltip="Pumpenausfall: Auslaufzeit des Förderstroms (kleine Tauchmotorpumpen < 1 s)"),
        NumberField("p0", "Betriebsdruck an der Pumpe (Überdruck)", "p₀", "bar", 1.5, decimals=2,
                    tooltip="z. B. Förderhöhe H · ρ · g im Betrieb"),
        NumberField("PN", "Nenndruck der Leitung", "PN", "bar", 10, min=0, decimals=1),
        NumberField("pv", "Dampfdruck des Mediums (absolut)", "p_v", "kPa", 2.3, min=0, min_inclusive=True,
                    decimals=2),
    ]

    def compute(self, inp) -> None:
        v0 = inp["v0"].to("m/s").magnitude
        L = inp["L"].to("m").magnitude
        da, s = inp["da"].to("m").magnitude, inp["s"].to("m").magnitude
        if 2 * s >= da:
            raise ValueError("Die Wanddicke muss kleiner als der halbe Außendurchmesser sein.")
        di = da - 2 * s
        E = (inp["E"].to("N/mm**2").magnitude if inp["werkstoff"] == "frei" else E_ROHR[inp["werkstoff"]][1]) * 1e6
        rho = inp["rho"].to("kg/m**3").magnitude
        K = inp["K"].to("Pa").magnitude
        a = wellengeschwindigkeit(K, rho, E, di, s)
        a0 = math.sqrt(K / rho)
        self.step("Druckwellengeschwindigkeit", "a = √( K/ρ / (1 + K · d_i / (E · s)) )",
                  f"K = {fmt_num(K / 1e6, 0)} N/mm², E = {fmt_num(E / 1e6, 0)} N/mm², d_i = {fmt_num(di * 1000, 1)} mm, "
                  f"s = {fmt_num(s * 1000, 2)} mm", f"a = {fmt_num(a, 0)} m/s  (starres Rohr {fmt_num(a0, 0)} m/s)")
        Tr = 2 * L / a
        Ts = inp["Ts"].to("s").magnitude
        self.step("Reflexionszeit", "T_r = 2 · L / a", f"T_r = 2 · {fmt_num(L, 1)} / {fmt_num(a, 0)}",
                  f"{fmt_num(Tr, 2)} s")
        dp_j = rho * a * v0
        if Ts <= Tr:
            dp = dp_j
            self.step("Druckstoß (schnell: T_s ≤ T_r)", "Δp = ρ · a · Δv  (Joukowsky)",
                      f"Δp = {fmt_num(rho, 1)} · {fmt_num(a, 0)} · {fmt_num(v0, 2)}", f"{fmt_num(dp / 1e5, 2)} bar")
        else:
            dp = 2 * rho * L * v0 / Ts
            self.step("Druckstoß (langsam: T_s > T_r)", "Δp = 2 · ρ · L · Δv / T_s  (Michaud)",
                      f"Δp = 2 · {fmt_num(rho, 1)} · {fmt_num(L, 1)} · {fmt_num(v0, 2)} / {fmt_num(Ts, 2)}",
                      f"{fmt_num(dp / 1e5, 2)} bar")
        p0 = inp["p0"].to("bar").magnitude
        pmax, pmin = p0 + dp / 1e5, p0 - dp / 1e5
        pmin_abs = pmin + 1.01325
        pv = inp["pv"].to("bar").magnitude
        self.step("Druckgrenzen", "p_max = p₀ + Δp;  p_min = p₀ − Δp",
                  f"p₀ = {fmt_num(p0, 2)} bar Ü", f"p_max = {fmt_num(pmax, 2)} bar, p_min = {fmt_num(pmin, 2)} bar Ü")

        self.result("dp", "Druckstoß", "Δp", Q_(dp, "Pa"), "bar", 2, highlight=True)
        self.result("dh", "Druckstoß als Höhe", "Δh", Q_(dp / (rho * 9.80665), "m"), "m", 1)
        self.result("pmax", "Maximaldruck (Überdruck)", "p_max", Q_(pmax, "bar"), "bar", 2, highlight=True)
        self.result("pmin", "Minimaldruck (Überdruck)", "p_min", Q_(pmin, "bar"), "bar", 2, highlight=True)
        self.result("a", "Druckwellengeschwindigkeit", "a", Q_(a, "m/s"), "m/s", 0)
        self.result("Tr", "Reflexionszeit", "T_r", Q_(Tr, "s"), "s", 2)
        self.result("dpj", "Joukowsky-Stoß (Obergrenze)", "Δp_J", Q_(dp_j, "Pa"), "bar", 2)

        PN = inp["PN"].to("bar").magnitude
        if PN > 0 and pmax > PN:
            self.warn(f"Maximaldruck {fmt_num(pmax, 2)} bar über dem Nenndruck PN {fmt_num(PN, 0)} – "
                      "Druckstoßsicherung (Windkessel, Schwungmasse, Belüfter) oder höhere Druckstufe erforderlich.")
        if pmin_abs <= pv:
            self.warn("Der Minimaldruck erreicht den Dampfdruck: Kavitation bzw. Abreißen der Wassersäule mit "
                      "anschließendem Rückschlag – deutlich höhere Drücke als Joukowsky möglich! Belüftungsventile "
                      "an Hochpunkten oder Windkessel vorsehen.")
        elif pmin < -0.5:
            self.warn(f"Unterdruck bis {fmt_num(pmin, 2)} bar – Beulsicherheit (besonders PE-Rohre) und Ansaugen von "
                      "Fremdwasser/Luft prüfen.")
        if Ts > Tr:
            self.info(f"Langsamer Vorgang (T_s = {fmt_num(Ts, 2)} s > T_r): reduzierter Stoß nach Michaud. Ein "
                      f"vollständiger Joukowsky-Stoß beträgt {fmt_num(dp_j / 1e5, 2)} bar.")
        if E < 5e9:
            self.info("Kunststoffrohr: niedrige Wellengeschwindigkeit dämpft den Druckstoß; Kurzzeit-E-Modul hängt von "
                      "Temperatur und Belastungsdauer ab.")
        self.info("Abschätzung für eine einfache Leitung ohne Hochpunkte und Luftpolster. Für Planung und "
                  "Druckstoßsicherung Berechnung nach dem Charakteristikenverfahren (vgl. DVGW W 303) durchführen.")

    def plot(self, fig, raw, result) -> bool:
        if not result.ok:
            return False
        L = float(raw["L"])
        a = result.value("a")
        Tr = result.value("Tr")
        Ts = float(raw["Ts"])
        rho, v0 = float(raw["rho"]), float(raw["v0"])
        p0 = float(raw["p0"])
        ts = np.linspace(0, max(4 * Tr, 2 * Ts, 1.0), 400)
        dpj = rho * a * v0 / 1e5
        ramp = np.clip(ts / max(Ts, 1e-6), 0, 1) if Ts > 0 else np.ones_like(ts)
        # schematische Druckschwingung am Leitungsende (verlustfrei, Rechteckwelle mit Rampe)
        phase = np.floor(ts / Tr) % 2
        sign = np.where(phase == 0, 1.0, -1.0)
        amp = result.value("dp")
        p = p0 + sign * np.minimum(ramp * dpj, amp)
        ax = fig.subplots()
        ax.plot(ts, p, color="#1f6fb2", lw=1.8, label="Druck (schematisch, verlustfrei)")
        ax.axhline(float(raw["PN"]), color="#c0392b", ls="--", lw=1.2, label="PN")
        ax.axhline(float(raw["pv"]) / 100 - 1.01325, color="#8e44ad", ls=":", lw=1.2, label="Dampfdruck")
        ax.axhline(p0, color="#6b7b8c", lw=0.8)
        ax.set_xlabel("Zeit t  [s]")
        ax.set_ylabel("Druck  [bar Ü]")
        ax.set_title(f"Druckverlauf an der Pumpe – a = {fmt_num(a, 0)} m/s, T_r = {fmt_num(Tr, 2)} s")
        ax.grid(True, alpha=0.3)
        ax.legend(loc="upper right", fontsize=8)
        return True

    def sketch_svg(self, raw) -> str:
        s = Svg()
        s.line(30, 120, 330, 120, INK, 2).line(30, 150, 330, 150, INK, 2)
        s.rect(30, 121, 300, 28, fill="#cfe0f1", stroke="#cfe0f1", width=0)
        s.rect(330, 105, 12, 60, fill="#9aa7b4")
        s.arrow(80, 135, 140, 135, ACCENT).text(110, 128, "v₀", 12, INK, italic=True)
        s.arrow(320, 100, 240, 100, "#c0392b").text(280, 92, "Druckwelle a", 11, "#c0392b")
        s.dim_h(30, 330, 180, "L")
        s.text(336, 210, "Pumpe / Schließorgan", 10, MUTED, "end")
        s.text(180, 40, "Δp = ρ · a · Δv", 14, INK, bold=True)
        s.text(180, 62, "für Schließzeit ≤ 2L/a", 11, MUTED)
        return s.render()
