"""Pumpenauslegung: Förderstrom und Förderhöhe aus Rohrnetz, Einbauten und statischem Anteil."""

from __future__ import annotations

import numpy as np

from ingrechner.core.model import Calculator, ChoiceField, NumberField
from ingrechner.core.rohrdaten import rohr, rohr_optionen
from ingrechner.core.svg import ACCENT, INK, MUTED, Svg
from ingrechner.core.units import Q_, fmt_num

from ._pumpe import G, medium, medium_felder, medium_hinweise, pumpe_svg, rauheit, rauheit_felder, rohr_dp

VOL = {"quelle": ["volumen"]}
WAERME = {"quelle": ["waerme"]}
FREI = {"rohr": ["frei"]}


def _di(inp) -> tuple[float, str]:
    if inp["rohr"] == "frei":
        return inp["di"].to("m").magnitude, f"d_i = {fmt_num(inp['di'].to('mm').magnitude, 1)} mm"
    da, s, _ = rohr(inp["rohr"])
    return (da - 2 * s) / 1000, inp["rohr"].split(":", 1)[1]


class PumpenAuslegung(Calculator):
    id = "pu.auslegung"
    title = "Pumpenauslegung (Förderhöhe)"
    category = "Pumpen"
    description = (
        "Auslegungspunkt einer Kreiselpumpe: Förderstrom direkt oder aus Wärmeleistung und Spreizung, "
        "Förderhöhe aus Rohrreibung, Einzelwiderständen, Komponenten und Regelventil sowie statischem Anteil "
        "(geodätische Höhe, Behälterdrücke) für geschlossene und offene Systeme. Mit Anlagenkennlinie."
    )
    norm = "H = H_stat + Σ Δp / (ρ·g); Darcy-Weisbach/Colebrook; VDI 2073, DIN EN 12828; Δp_V = (V̇/k_vs)² bar"
    keywords = ("pumpe", "pumpenauslegung", "förderhöhe", "förderstrom", "anlagenkennlinie", "umwälzpumpe",
                "heizungspumpe", "druckverlust", "auslegungspunkt", "abwasser", "kreiselpumpe", "kvs")

    fields = [
        ChoiceField("quelle", "Förderstrom", [("volumen", "Volumenstrom vorgeben"),
                                              ("waerme", "Aus Leistung und Spreizung")], "waerme"),
        NumberField("V", "Volumenstrom", "V̇", "m**3/hour", 3.5, min=0, decimals=3, visible_if=VOL),
        NumberField("P", "Wärme-/Kälteleistung", "Q̇", "kW", 80, min=0, decimals=2, visible_if=WAERME),
        NumberField("dT", "Temperaturspreizung", "Δθ", "K", 20, min=0, decimals=1, visible_if=WAERME,
                    tooltip="Heizung 10–20 K, Fernwärme 30–50 K, Kälte 5–6 K"),
        *medium_felder(60),
        ChoiceField("rohr", "Rohrleitung (ungünstigster Strang)", [*rohr_optionen()[:-1], ("frei", "Innendurchmesser eingeben")],
                    "st:DN 40"),
        NumberField("di", "Rohrinnendurchmesser", "d_i", "mm", 41.9, min=0, decimals=1, visible_if=FREI),
        NumberField("L", "Leitungslänge (Vor- + Rücklauf)", "L", "m", 120, min=0, min_inclusive=True, decimals=1,
                    tooltip="Länge des hydraulisch ungünstigsten Strangs einschließlich Rücklauf"),
        *rauheit_felder(),
        NumberField("zeta", "Summe Einzelwiderstände", "Σζ", "", 12, min=0, min_inclusive=True, decimals=2,
                    tooltip="Bögen ≈ 0,3–0,5; T-Stück Durchgang ≈ 0,3, Abzweig ≈ 1,3; Absperrklappe ≈ 0,3; "
                            "Rückschlagventil ≈ 2–4; Schmutzfänger ≈ 1–2"),
        NumberField("dp_k", "Druckverlust Komponenten", "Δp_K", "kPa", 25, min=0, min_inclusive=True, decimals=2,
                    tooltip="Wärmeerzeuger, Wärmetauscher, Wärmemengenzähler, Heizkörper/Verbraucher, Filter … "
                            "(Herstellerangaben)"),
        NumberField("kvs", "Regelventil kvs-Wert (0 = keins)", "k_vs", "m**3/hour", 0, min=0, min_inclusive=True,
                    decimals=2, tooltip="Δp_V = (V̇ / k_vs)² · 1 bar; Ventilautorität ≥ 0,3–0,5 anstreben"),
        NumberField("hgeo", "Geodätische Förderhöhe", "H_geo", "m", 0, decimals=2,
                    tooltip="Höhenunterschied Ziel- minus Saugspiegel; im geschlossenen Kreislauf 0"),
        NumberField("dp_b", "Druckdifferenz Behälter", "Δp_B", "kPa", 0, decimals=2,
                    tooltip="Überdruck im Zielbehälter minus Überdruck im Saugbehälter (offene Systeme, "
                            "Druckbehälter); geschlossener Kreislauf 0"),
        NumberField("res", "Sicherheitszuschlag Rohrnetz", "z", "percent", 10, min=0, min_inclusive=True, max=50,
                    decimals=0, tooltip="Zuschlag auf den dynamischen Anteil (Rohrnetz-Unsicherheiten); "
                                        "zu große Zuschläge führen zu überdimensionierten Pumpen"),
    ]

    def _volumenstrom(self, inp, med) -> float:
        rho = med.rho
        if inp["quelle"] == "volumen":
            return inp["V"].to("m**3/s").magnitude
        P, dT = inp["P"].to("W").magnitude, inp["dT"].to("K").magnitude
        cp = med.cp * 1000
        if inp["medium"] == "benutzer":
            self.info("Benutzerdefiniertes Medium: c_p = 4,186 kJ/(kg·K) angenommen – für andere Medien die "
                      "Mediendatenbank verwenden oder den Förderstrom direkt vorgeben.")
        V = P / (rho * cp * dT)
        self.step("Förderstrom aus der Leistung", "V̇ = Q̇ / (ρ · c_p · Δθ)",
                  f"V̇ = {fmt_num(P / 1000, 2)} kW / ({fmt_num(rho, 1)} kg/m³ · {fmt_num(cp / 1000, 3)} kJ/(kg·K) · "
                  f"{fmt_num(dT, 1)} K)", f"{fmt_num(V * 3600, 3)} m³/h")
        return V

    def compute(self, inp) -> None:
        med = medium(inp)
        rho, nu = med.rho, med.nu
        self.step("Stoffwerte", "ρ, ν", med.name, f"ρ = {fmt_num(rho, 1)} kg/m³, ν = {fmt_num(nu * 1e6, 3)} mm²/s")
        V = self._volumenstrom(inp, med)
        di, rohr_name = _di(inp)
        k = rauheit(inp)
        L, zeta = inp["L"].to("m").magnitude, float(inp["zeta"])
        r = rohr_dp(V, di, L, k, zeta, rho, nu)
        self.step("Strömung im Rohr", "v = 4·V̇ / (π·d_i²);  Re = v·d_i / ν",
                  f"{rohr_name}, d_i = {fmt_num(di * 1000, 1)} mm",
                  f"v = {fmt_num(r.v, 2)} m/s, Re = {fmt_num(r.re, 0)}")
        self.step("Rohrreibungszahl", "Colebrook-White (laminar: λ = 64/Re)",
                  f"k = {fmt_num(k * 1000, 4)} mm, k/d = {fmt_num(k / di, 6)}", f"λ = {fmt_num(r.lam, 5)}")
        self.step("Rohrreibung", "Δp_R = λ · L/d_i · ρ·v²/2",
                  f"R = {fmt_num(r.r, 1)} Pa/m · {fmt_num(L, 1)} m", f"{fmt_num(r.dp_r / 1000, 2)} kPa")
        self.step("Einzelwiderstände", "Δp_Z = Σζ · ρ·v²/2", f"Σζ = {fmt_num(zeta, 2)}",
                  f"{fmt_num(r.dp_z / 1000, 2)} kPa")
        dp_k = inp["dp_k"].to("Pa").magnitude
        kvs = inp["kvs"].to("m**3/hour").magnitude
        dp_v = (V * 3600 / kvs) ** 2 * 1e5 if kvs > 0 else 0.0
        if kvs > 0:
            self.step("Regelventil", "Δp_V = (V̇ / k_vs)² · 1 bar",
                      f"Δp_V = ({fmt_num(V * 3600, 3)} / {fmt_num(kvs, 2)})² bar", f"{fmt_num(dp_v / 1000, 2)} kPa")
        dp_dyn = r.dp_r + r.dp_z + dp_k + dp_v
        z = inp["res"].to("percent").magnitude / 100
        H_dyn = dp_dyn * (1 + z) / (rho * G)
        self.step("Dynamische Förderhöhe", "H_dyn = (Δp_R + Δp_Z + Δp_K + Δp_V) · (1 + z) / (ρ·g)",
                  f"H_dyn = {fmt_num(dp_dyn / 1000, 2)} kPa · {fmt_num(1 + z, 2)} / ({fmt_num(rho, 1)} · 9,81)",
                  f"{fmt_num(H_dyn, 2)} m")
        hgeo = inp["hgeo"].to("m").magnitude
        dp_b = inp["dp_b"].to("Pa").magnitude
        H_stat = hgeo + dp_b / (rho * G)
        if hgeo or dp_b:
            self.step("Statische Förderhöhe", "H_stat = H_geo + Δp_B / (ρ·g)",
                      f"H_stat = {fmt_num(hgeo, 2)} m + {fmt_num(dp_b / 1000, 2)} kPa / ({fmt_num(rho, 1)} · 9,81)",
                      f"{fmt_num(H_stat, 2)} m")
        H = H_stat + H_dyn
        P_hyd = rho * G * V * H
        self.step("Förderhöhe im Auslegungspunkt", "H_A = H_stat + H_dyn",
                  f"H_A = {fmt_num(H_stat, 2)} m + {fmt_num(H_dyn, 2)} m", f"{fmt_num(H, 2)} m")
        self.step("Hydraulische Leistung", "P_hyd = ρ · g · V̇ · H_A",
                  f"P_hyd = {fmt_num(rho, 1)} · 9,81 · {fmt_num(V, 5)} m³/s · {fmt_num(H, 2)} m",
                  f"{fmt_num(P_hyd, 1)} W")

        self.result("V", "Förderstrom", "V̇_A", Q_(V, "m**3/s"), "m**3/hour", 3, highlight=True)
        self.result("H", "Förderhöhe", "H_A", Q_(H, "m"), "m", 2, highlight=True)
        self.result("dp", "Förderdruck", "Δp_A", Q_(H * rho * G, "Pa"), "kPa", 1)
        self.result("Hstat", "davon statisch", "H_stat", Q_(H_stat, "m"), "m", 2)
        self.result("Hdyn", "davon dynamisch (mit Zuschlag)", "H_dyn", Q_(H_dyn, "m"), "m", 2)
        self.result("v", "Fließgeschwindigkeit", "v", Q_(r.v, "m/s"), "m/s", 2)
        self.result("R", "Druckgefälle Rohr", "R", Q_(r.r, "Pa/m"), "Pa/m", 0)
        self.result("Phyd", "Hydraulische Leistung", "P_hyd", Q_(P_hyd, "W"), "W", 0)
        self.result("rho", "Dichte des Mediums", "ρ", Q_(rho, "kg/m**3"), "kg/m**3", 1)

        # Bewertung
        if r.re < 2320:
            self.info("Laminare Strömung (Re < 2320).")
        if r.v > 3.0:
            self.warn(f"Fließgeschwindigkeit {fmt_num(r.v, 2)} m/s sehr hoch – Erosion, Druckstöße, Geräusche.")
        elif r.v > 1.5 and med.id in ("wasser", "eg30", "eg40", "pg30", "pg40"):
            self.warn(f"v = {fmt_num(r.v, 2)} m/s – in Heizungs-/Kälteverteilungen sind ≤ 1,0–1,5 m/s üblich "
                      "(Strömungsgeräusche).")
        if (inp["medium"] == "benutzer" or "schlamm" in med.id or med.id == "abwasser_zulauf") and r.v < 0.7:
            self.info("Bei feststoffhaltigen Medien (Abwasser-Druckleitungen) sind v ≥ 0,7–0,8 m/s üblich, "
                      "um Ablagerungen zu vermeiden.")
        if r.r > 300:
            self.warn(f"Druckgefälle R = {fmt_num(r.r, 0)} Pa/m hoch – üblich 100–200 Pa/m; größere Nennweite "
                      "prüfen.")
        if kvs > 0:
            a = dp_v / dp_dyn
            msg = f"Ventilautorität näherungsweise a ≈ {fmt_num(a, 2)} (Δp_V / Δp_gesamt, variabler Teil)."
            (self.warn if a < 0.3 else self.info)(msg + (" Unter 0,3 regelt das Ventil schlecht." if a < 0.3 else ""))
        if H_stat < 0:
            self.warn("Negative statische Förderhöhe – das Medium fließt teilweise von selbst; Betriebspunkt "
                      "bei Teillast prüfen.")
        medium_hinweise(self, med)
        if inp["medium"] == "benutzer" or "schlamm" in med.id or med.id == "abwasser_zulauf":
            self.info("Feststoffhaltige Medien (Abwasser): Laufradform und freien Kugeldurchgang beachten, "
                      "Feststoffzuschläge zur Förderhöhe nach Herstellerangabe.")
        self.info("Die Pumpe so wählen, dass der Auslegungspunkt nahe dem Bestpunkt liegt – Kennlinie im "
                  "Rechner „Pumpenkennlinie & Betriebspunkt“ prüfen.")

    # --------------------------------------------------------------- Diagramm
    def plot(self, fig, raw, result) -> bool:
        if not result.ok:
            return False
        V_a, H_a, Hs = result.value("V"), result.value("H"), result.value("Hstat")
        # Anlagenkennlinie mit reynoldsabhängigem λ neu rechnen
        inp = self._inputs(raw)
        med = medium(inp)
        di, _ = _di(inp)
        k = rauheit(inp)
        z = float(raw["res"]) / 100
        kvs = float(raw["kvs"])
        dp_k = float(raw["dp_k"]) * 1000
        Vs = np.linspace(0, V_a * 1.5, 80)
        Hs_curve = []
        for v in Vs:
            r = rohr_dp(v / 3600, di, float(raw["L"]), k, float(raw["zeta"]), med.rho, med.nu)
            dp_v = (v / kvs) ** 2 * 1e5 if kvs > 0 else 0
            dpk = dp_k * (v / V_a) ** 2 if V_a > 0 else 0
            Hs_curve.append(Hs + (r.dp_r + r.dp_z + dpk + dp_v) * (1 + z) / (med.rho * G))
        ax = fig.subplots()
        ax.plot(Vs, Hs_curve, color="#1f6fb2", lw=2, label="Anlagenkennlinie")
        ax.axhline(Hs, color="#6b7b8c", ls="--", lw=1, label="statischer Anteil")
        ax.plot([V_a], [H_a], "o", color="#c0392b", ms=7, label="Auslegungspunkt")
        ax.annotate(f"{fmt_num(V_a, 2)} m³/h / {fmt_num(H_a, 2)} m", (V_a, H_a), textcoords="offset points",
                    xytext=(8, -14), fontsize=8)
        ax.set_xlabel("Förderstrom V̇  [m³/h]")
        ax.set_ylabel("Förderhöhe H  [m]")
        ax.set_title("Anlagenkennlinie")
        ax.set_xlim(0, Vs[-1])
        ax.set_ylim(min(0, Hs), max(Hs_curve) * 1.1)
        ax.grid(True, alpha=0.3)
        ax.legend(loc="upper left")
        return True

    def _inputs(self, raw):
        """Rohwerte → Eingaben mit Einheiten (für Diagramme)."""
        inp = {}
        for f in self.fields:
            v = raw.get(f.key, f.default)
            inp[f.key] = Q_(float(v), f.unit) if isinstance(f, NumberField) and f.unit else v
        return inp

    def sketch_svg(self, raw) -> str:
        s = Svg()
        offen = float(raw.get("hgeo", 0) or 0) != 0 or float(raw.get("dp_b", 0) or 0) != 0
        if offen:
            s.rect(20, 140, 70, 60, fill="#ffffff").rect(21, 160, 68, 39, fill="#cfe0f1", stroke="#cfe0f1", width=0)
            s.rect(270, 20, 70, 60, fill="#ffffff").rect(271, 40, 68, 39, fill="#cfe0f1", stroke="#cfe0f1", width=0)
            s.line(90, 180, 128, 180, ACCENT, 3).line(172, 180, 230, 180, ACCENT, 3)
            s.line(230, 180, 230, 50, ACCENT, 3).line(230, 50, 270, 50, ACCENT, 3)
            pumpe_svg(s, 150, 180)
            s.line(350, 160, 350, 40, MUTED, 1, "4 3")
            s.dim_v(355, 160, 40, "H_geo")
            s.text(55, 132, "Saugbehälter", 10, MUTED).text(305, 14, "Zielbehälter", 10, MUTED)
            s.text(200, 120, "Δp_R + Δp_Z", 11, INK, italic=True)
        else:
            s.rect(30, 70, 50, 80, fill="#f5d7d3").text(55, 115, "WE", 12, INK, bold=True)
            s.line(80, 85, 300, 85, "#c0392b", 3).line(300, 85, 300, 135, "#9aa7b4", 3)
            s.line(300, 135, 80, 135, ACCENT, 3)
            s.rect(285, 95, 30, 30, fill="#ffffff").text(300, 114, "V", 11, INK, bold=True)
            pumpe_svg(s, 150, 85, 18)
            s.text(190, 70, "Vorlauf", 10, "#c0392b").text(190, 155, "Rücklauf", 10, ACCENT)
            s.text(180, 195, "Geschlossener Kreislauf: H = Σ Δp / (ρ·g)", 11, INK)
            s.text(300, 152, "Verbraucher", 10, MUTED)
        return s.render()
