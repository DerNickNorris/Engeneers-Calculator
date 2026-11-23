"""Motor-Energieeffizienz: Vergleich IE-Klassen bzw. Katalogwerte, Jahresenergie, Kosten, CO₂, Amortisation."""

from __future__ import annotations

import numpy as np

from ingrechner.calculators.pumpen._pumpe import IEC_GROESSEN, motor_groesse
from ingrechner.core.model import Calculator, ChoiceField, NumberField
from ingrechner.core.svg import INK, MUTED, Svg
from ingrechner.core.units import Q_, fmt_num

from ._motor import leistungsklasse, mindestklasse, teillast

KLASSEN = [("IE2", "IE2 (Mindestwert)"), ("IE3", "IE3 (Mindestwert)"), ("IE4", "IE4 (Mindestwert)"),
           ("frei", "Wirkungsgrad aus Katalog")]
A_FREI = {"a": ["frei"]}
B_FREI = {"b": ["frei"]}


class Motoreffizienz(Calculator):
    id = "et.motoreffizienz"
    title = "Motor – Energieeffizienz"
    category = "Elektrotechnik"
    description = (
        "Wirtschaftlichkeitsvergleich zweier Asynchronmotoren (IE2/IE3/IE4-Mindestwerte nach IEC 60034-30-1 oder "
        "Katalogwirkungsgrade) bei Teillast: Verlustleistung, Jahresenergie, Kosten, CO₂ und Amortisation der "
        "Mehrkosten; Mindest-Effizienzklasse nach EU-Ökodesign-Verordnung."
    )
    norm = "P_el = P_ab/η(Last); η(Last) mit 40 % lastunabhängigen Verlusten; IEC 60034-30-1 (4-polig, 50 Hz); EU 2019/1781"
    keywords = ("energieeffizienz", "ie2", "ie3", "ie4", "wirkungsgrad", "motor", "amortisation", "stromkosten",
                "ökodesign", "2019/1781", "iec 60034-30-1", "verluste", "co2", "motortausch")

    fields = [
        NumberField("PN", "Bemessungsleistung", "P_N", "kW", 11, min=0.12, max=315, decimals=2),
        ChoiceField("pole", "Polzahl", [("2", "2-polig"), ("4", "4-polig"), ("6", "6-polig"), ("8", "8-polig")], "4"),
        NumberField("last", "Mittlere Auslastung", "P/P_N", "percent", 75, min=10, max=120, decimals=0),
        NumberField("t", "Betriebsstunden pro Jahr", "t", "hour", 4000, min=0, max=8760, decimals=0),
        ChoiceField("a", "Motor A (Bestand / günstiger)", KLASSEN, "IE2"),
        NumberField("eta_a", "Wirkungsgrad Motor A", "η_A", "percent", 89.8, min=10, max=99.9, decimals=1,
                    visible_if=A_FREI),
        ChoiceField("b", "Motor B (effizienter)", KLASSEN, "IE4"),
        NumberField("eta_b", "Wirkungsgrad Motor B", "η_B", "percent", 93.3, min=10, max=99.9, decimals=1,
                    visible_if=B_FREI),
        NumberField("preis", "Strompreis", "k_E", "EUR/(kW*h)", 0.25, min=0, decimals=3),
        NumberField("co2", "CO₂-Emissionsfaktor", "f_CO₂", "g/(kW*h)", 380, min=0, min_inclusive=True, decimals=0),
        NumberField("invest", "Mehrkosten Motor B", "ΔI", "EUR", 450, min=0, min_inclusive=True, decimals=0),
    ]

    def _eta(self, inp, key: str, PN: float) -> tuple[float, str]:
        if inp[key] == "frei":
            return inp[f"eta_{key}"].to("percent").magnitude / 100, "Katalog"
        return leistungsklasse(PN, inp[key]) / 100, f"{inp[key]}-Mindestwert"

    def compute(self, inp) -> None:
        PN = inp["PN"].to("kW").magnitude
        sel = motor_groesse(PN)
        PN_n = sel[1] if sel else IEC_GROESSEN[-1]
        x = inp["last"].to("percent").magnitude / 100
        t = inp["t"].to("hour").magnitude
        preis = inp["preis"].to("EUR/(kW*h)").magnitude
        co2 = inp["co2"].to("g/(kW*h)").magnitude
        P_ab = PN * x
        res = {}
        for key, name in (("a", "A"), ("b", "B")):
            etaN, quelle = self._eta(inp, key, PN)
            eta = teillast(etaN, x)
            P_el = P_ab / eta
            E = P_el * t
            res[key] = (etaN, eta, P_el, E)
            self.step(f"Motor {name}", "η(Last) = x / (x + (1/η_N − 1)·(0,4 + 0,6·x²));  E = P_ab/η · t",
                      f"η_N = {fmt_num(etaN * 100, 1)} % ({quelle}), Last {fmt_num(x * 100, 0)} %",
                      f"η = {fmt_num(eta * 100, 2)} %, P_el = {fmt_num(P_el, 3)} kW, E = {fmt_num(E, 0)} kWh/a")
        (ea, eta_a, Pa, Ea), (eb, eta_b, Pb, Eb) = res["a"], res["b"]
        dE = Ea - Eb
        dK = dE * preis
        self.result("eta_a", "Wirkungsgrad Motor A (Last)", "η_A", Q_(eta_a * 100, "percent"), "percent", 2)
        self.result("eta_b", "Wirkungsgrad Motor B (Last)", "η_B", Q_(eta_b * 100, "percent"), "percent", 2)
        self.result("Pv_a", "Verluste Motor A", "P_V,A", Q_(Pa - P_ab, "kW"), "kW", 3)
        self.result("Pv_b", "Verluste Motor B", "P_V,B", Q_(Pb - P_ab, "kW"), "kW", 3)
        self.result("Ea", "Jahresenergie Motor A", "E_A", Q_(Ea, "kW*h/year"), "kW*h/year", 0)
        self.result("Eb", "Jahresenergie Motor B", "E_B", Q_(Eb, "kW*h/year"), "kW*h/year", 0)
        self.result("dE", "Energieeinsparung", "ΔE", Q_(dE, "kW*h/year"), "kW*h/year", 0, highlight=True)
        self.result("dK", "Kosteneinsparung", "ΔK", Q_(dK, "EUR/year"), "EUR/year", 0, highlight=True)
        self.result("dCO2", "CO₂-Einsparung", "Δm_CO₂", Q_(dE * co2 / 1000, "kg/year"), "kg/year", 0)
        inv = inp["invest"].to("EUR").magnitude
        if inv > 0 and dK > 0:
            ta = inv / dK
            self.step("Statische Amortisation", "t_A = ΔI / ΔK", f"t_A = {fmt_num(inv, 0)} € / {fmt_num(dK, 0)} €/a",
                      f"{fmt_num(ta, 1)} a")
            self.result("ta", "Amortisationszeit", "t_A", Q_(ta, "year"), "year", 1, highlight=True)
        elif dK <= 0:
            self.warn("Motor B ist bei dieser Auslastung nicht sparsamer.")
        pole = int(inp["pole"])
        klasse = mindestklasse(PN, pole)
        self.info(f"EU 2019/1781: Für {fmt_num(PN, 2)} kW, {pole}-polig ist mindestens {klasse} vorgeschrieben "
                  "(Neuinstallation/Inverkehrbringen).")
        if inp["a"] != "frei" or inp["b"] != "frei":
            self.info(f"IE-Mindestwerte für 4-polige 50-Hz-Motoren bei P_N = {fmt_num(PN_n, 2)} kW (IEC-Reihe); für "
                      "2-, 6- und 8-polige Motoren Katalogwerte eingeben.")
        if x < 0.5:
            self.info("Geringe Auslastung – ein kleinerer Motor spart oft mehr als eine höhere Effizienzklasse.")

    def plot(self, fig, raw, result) -> bool:
        if not result.ok:
            return False
        PN = float(raw["PN"])
        inp = {"a": raw["a"], "b": raw["b"], "eta_a": Q_(float(raw["eta_a"]), "percent"),
               "eta_b": Q_(float(raw["eta_b"]), "percent")}
        xs = np.linspace(0.15, 1.2, 60)
        ax = fig.subplots()
        for key, col in (("a", "#9aa7b4"), ("b", "#27ae60")):
            etaN, _ = self._eta(inp, key, PN)
            ax.plot(xs * 100, [teillast(etaN, x) * 100 for x in xs], color=col, lw=2,
                    label=f"Motor {key.upper()} ({raw[key]})")
        ax.axvline(float(raw["last"]), color="#2b3a4a", ls=":", lw=1)
        ax.set_xlabel("Auslastung  [%]")
        ax.set_ylabel("Wirkungsgrad  [%]")
        ax.set_title("Wirkungsgrad über der Last (Näherung)")
        ax.grid(True, alpha=0.3)
        ax.legend()
        return True

    def sketch_svg(self, raw) -> str:
        s = Svg()
        for i, (k, h, c) in enumerate((("IE2", 60, "#e59866"), ("IE3", 90, "#d4ac0d"), ("IE4", 120, "#27ae60"))):
            x = 80 + i * 80
            s.rect(x, 190 - h, 50, h, fill=c).text(x + 25, 206, k, 11, INK, bold=True)
        s.text(180, 40, "höhere Klasse = geringere Verluste", 11, MUTED)
        return s.render()
