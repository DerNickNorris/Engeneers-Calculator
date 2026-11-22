"""Außenluftvolumenstrom nach Personen/Fläche, Luftwechsel, Kühllast oder CO₂-Bilanz."""

from __future__ import annotations

import numpy as np

from ingrechner.core.model import Calculator, ChoiceField, NumberField
from ingrechner.core.svg import ACCENT, INK, MUTED, Svg
from ingrechner.core.units import Q_, fmt_num

from ._lu import luft, luft_felder

PERS = {"modus": ["personen"]}
LW = {"modus": ["luftwechsel"]}
LAST = {"modus": ["last"]}
CO2 = {"modus": ["co2"]}
PERS_CO2 = {"modus": ["personen", "co2"]}

# DIN EN 16798-1, Anhang B (Tab. B.6/B.7): l/s je Person und l/(s·m²) je Gebäudeemission
KATEGORIE = {"I": 10.0, "II": 7.0, "III": 4.0}
GEBAEUDE = {"I": {"sehr": 0.5, "schad": 1.0, "nicht": 2.0}, "II": {"sehr": 0.35, "schad": 0.7, "nicht": 1.4},
            "III": {"sehr": 0.2, "schad": 0.4, "nicht": 0.8}}


class Luftmenge(Calculator):
    id = "lu.luftmenge"
    title = "Luftvolumenstrom"
    category = "Lüftung / RLT"
    description = (
        "Erforderlicher Außenluftvolumenstrom eines Raumes: nach Personen und Gebäudeemissionen (DIN EN 16798-1, "
        "Kategorien I–III), nach Luftwechselzahl, aus der Kühllast mit Zuluft-Untertemperatur oder aus der "
        "CO₂-Bilanz mit zulässiger Raumkonzentration."
    )
    norm = "DIN EN 16798-1 Anhang B; V̇ = Q̇/(ρ·c_p·Δθ); V̇ = Ġ_CO₂ / (c_i − c_a)"
    keywords = ("luftvolumenstrom", "luftmenge", "außenluft", "luftwechsel", "personen", "co2", "kühllast",
                "lüftung", "rlt", "16798", "zuluft", "frischluft", "raumluft")

    fields = [
        ChoiceField("modus", "Bemessung nach", [("personen", "Personen und Fläche (EN 16798-1)"),
                                                ("luftwechsel", "Luftwechselzahl"),
                                                ("last", "Kühllast / Heizlast (Zulufttemperatur)"),
                                                ("co2", "CO₂-Bilanz")], "personen"),
        NumberField("n_p", "Anzahl Personen", "n_P", "", 25, min=0, min_inclusive=True, decimals=0, visible_if=PERS_CO2),
        NumberField("A", "Nettogrundfläche", "A", "m**2", 80, min=0, decimals=1, visible_if=PERS),
        ChoiceField("kat", "Raumluftkategorie", [("I", "I – hohe Erwartung"), ("II", "II – normale Erwartung"),
                                                 ("III", "III – mäßige Erwartung")], "II", visible_if=PERS),
        ChoiceField("emission", "Gebäudeemission", [("sehr", "sehr schadstoffarm"), ("schad", "schadstoffarm"),
                                                    ("nicht", "nicht schadstoffarm")], "schad", visible_if=PERS),
        NumberField("Vr", "Raumvolumen", "V_R", "m**3", 240, min=0, decimals=1,
                    tooltip="Für Luftwechselzahl (Ergebnis bzw. Vorgabe)"),
        NumberField("n", "Luftwechselzahl", "n", "1/hour", 3, min=0, decimals=2, visible_if=LW),
        NumberField("Q", "Kühllast (sensibel)", "Q̇", "kW", 4, min=0, decimals=2, visible_if=LAST),
        NumberField("dT", "Zuluft-Untertemperatur", "Δθ", "K", 6, min=0, decimals=1, visible_if=LAST,
                    tooltip="Raum- minus Zulufttemperatur; Mischlüftung 6–10 K, Quelllüftung 3–4 K"),
        NumberField("co2_p", "CO₂-Abgabe je Person", "Ġ", "liter/hour", 18, min=0, decimals=1, visible_if=CO2,
                    tooltip="Sitzend ≈ 18 l/h, leichte Tätigkeit ≈ 24 l/h, Sport ≈ 60–100 l/h"),
        NumberField("ci", "Zulässige Raumkonzentration", "c_i", "ppm", 1000, min=0, decimals=0, visible_if=CO2,
                    tooltip="Pettenkofer-Zahl 1000 ppm; AGW Arbeitsplatz 5000 ppm"),
        NumberField("ca", "Außenluftkonzentration", "c_a", "ppm", 420, min=0, min_inclusive=True, decimals=0,
                    visible_if=CO2),
        *luft_felder(18),
    ]

    def compute(self, inp) -> None:
        modus = inp["modus"]
        Vr = inp["Vr"].to("m**3").magnitude
        if modus == "personen":
            n_p, A = float(inp["n_p"]), inp["A"].to("m**2").magnitude
            qp = KATEGORIE[inp["kat"]]
            qb = GEBAEUDE[inp["kat"]][inp["emission"]]
            V = (n_p * qp + A * qb) / 1000      # m³/s
            self.step("Außenluft nach Personen und Fläche", "V̇ = n_P · q_P + A · q_B  (DIN EN 16798-1, Anhang B)",
                      f"Kat. {inp['kat']}: V̇ = {fmt_num(n_p, 0)} · {fmt_num(qp, 1)} l/s + {fmt_num(A, 1)} m² · "
                      f"{fmt_num(qb, 2)} l/(s·m²)", f"{fmt_num(V * 1000, 1)} l/s = {fmt_num(V * 3600, 0)} m³/h")
            if n_p:
                self.result("Vp", "je Person", "V̇/n_P", Q_(V / n_p, "m**3/s"), "m**3/hour", 1)
        elif modus == "luftwechsel":
            n = inp["n"].to("1/hour").magnitude
            V = n * Vr / 3600
            self.step("Luftwechsel", "V̇ = n · V_R", f"V̇ = {fmt_num(n, 2)} 1/h · {fmt_num(Vr, 1)} m³",
                      f"{fmt_num(V * 3600, 0)} m³/h")
        elif modus == "last":
            _, z = luft(inp)
            Q, dT = inp["Q"].to("W").magnitude, inp["dT"].to("K").magnitude
            V = Q / (z.rho * z.cp * 1000 * dT)
            self.step("Luftdichte (Zuluft)", "ρ = p·M/(Z·R·T)", f"θ = {fmt_num(z.theta, 1)} °C, "
                      f"p = {fmt_num(z.p / 100, 0)} hPa", f"ρ = {fmt_num(z.rho, 3)} kg/m³, c_p = {fmt_num(z.cp, 3)} kJ/(kg·K)")
            self.step("Volumenstrom aus der Last", "V̇ = Q̇ / (ρ · c_p · Δθ)",
                      f"V̇ = {fmt_num(Q / 1000, 2)} kW / ({fmt_num(z.rho, 3)} · {fmt_num(z.cp, 3)} · {fmt_num(dT, 1)} K)",
                      f"{fmt_num(V * 3600, 0)} m³/h")
        else:
            n_p = float(inp["n_p"])
            G = n_p * inp["co2_p"].to("m**3/s").magnitude
            dc = (inp["ci"].to("ppm").magnitude - inp["ca"].to("ppm").magnitude) * 1e-6
            if dc <= 0:
                raise ValueError("Die Raumkonzentration muss über der Außenluftkonzentration liegen.")
            V = G / dc
            self.step("CO₂-Bilanz (stationär)", "V̇ = n_P · Ġ / (c_i − c_a)",
                      f"V̇ = {fmt_num(n_p, 0)} · {fmt_num(G / max(n_p, 1) * 3.6e6, 1)} l/h / ({fmt_num(dc * 1e6, 0)} ppm)",
                      f"{fmt_num(V * 3600, 0)} m³/h")
            if n_p:
                self.result("Vp", "je Person", "V̇/n_P", Q_(V / n_p, "m**3/s"), "m**3/hour", 1)

        self.result("V", "Außenluftvolumenstrom", "V̇", Q_(V, "m**3/s"), "m**3/hour", 0, highlight=True)
        self.result("Vls", "Außenluftvolumenstrom", "V̇", Q_(V, "m**3/s"), "liter/second", 1)
        if Vr > 0:
            n_res = V * 3600 / Vr
            self.result("n", "Luftwechsel", "n", Q_(n_res, "1/hour"), "1/hour", 2, highlight=modus != "luftwechsel")
            if n_res > 8:
                self.warn(f"Luftwechsel {fmt_num(n_res, 1)} 1/h sehr hoch – Zugluftgefahr, Luftführung und "
                          "Zulufttemperatur prüfen.")
            elif n_res < 0.5:
                self.info("Luftwechsel unter 0,5 1/h – Feuchteschutz (Mindestlüftung DIN 1946-6) prüfen.")
        self.info("Außenluftanteil; bei Kühl-/Heizlastabfuhr kann ein größerer Zuluftvolumenstrom (Umluft) nötig "
                  "sein. Regionale Vorgaben (ASR A3.6, VDI 6022/3804, DIN 1946-4) beachten.")

    def plot(self, fig, raw, result) -> bool:
        if not result.ok or raw.get("modus") != "co2":
            return False
        n_p, g = float(raw["n_p"]), float(raw["co2_p"]) / 1000 / 3600
        ca = float(raw["ca"])
        Vs = np.linspace(result.value("V") * 0.3, result.value("V") * 2.5, 100)
        ax = fig.subplots()
        ax.plot(Vs, ca + n_p * g / (Vs / 3600) * 1e6, color="#1f6fb2", lw=2)
        ax.axhline(float(raw["ci"]), color="#c0392b", ls="--", label="zulässig")
        ax.axhline(ca, color="#6b7b8c", ls=":", label="Außenluft")
        ax.set_xlabel("Außenluftvolumenstrom  [m³/h]")
        ax.set_ylabel("CO₂-Konzentration (stationär)  [ppm]")
        ax.set_title("Raum-CO₂ über dem Volumenstrom")
        ax.grid(True, alpha=0.3)
        ax.legend()
        return True

    def sketch_svg(self, raw) -> str:
        s = Svg()
        s.rect(70, 50, 220, 130, fill="#f4f8fc")
        s.arrow(10, 70, 68, 70, ACCENT).text(12, 62, "Außenluft V̇", 10, INK, "start")
        s.arrow(292, 160, 350, 160, "#c0392b").text(348, 152, "Abluft", 10, INK, "end")
        for x in (130, 180, 230):
            s.circle(x, 135, 9, fill="#dce6f1").line(x, 144, x, 170, INK, 2)
        s.text(180, 80, "Personen · Fläche · Last · CO₂", 11, MUTED)
        return s.render()
