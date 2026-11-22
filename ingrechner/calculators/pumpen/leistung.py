"""Leistungsbedarf einer Pumpe: Wirkungsgradkette, Verluste je Stufe, Motorgröße nach IEC-Reihe."""

from __future__ import annotations

from ingrechner.core.model import Calculator, ChoiceField, NumberField
from ingrechner.core.svg import INK, MUTED, Svg
from ingrechner.core.units import Q_, fmt_num

from ._pumpe import G, IE3, IE4, IEC_GROESSEN, motor_groesse, motor_zuschlag, pumpe_svg

MOT_FREI = {"motor": ["frei"]}
FU = {"fu": ["ja"]}
ENERGIE = {"energie": ["ja"]}


class PumpenLeistung(Calculator):
    id = "pu.leistung"
    title = "Pumpenleistung & Motor"
    category = "Pumpen"
    description = (
        "Hydraulische Leistung, Wellen- und elektrische Leistungsaufnahme über die Wirkungsgradkette Pumpe – "
        "Motor – Frequenzumrichter, Verluste je Stufe und Wahl der Motorbaugröße mit üblicher Leistungsreserve; "
        "optional Jahresenergie und -kosten im Dauerbetrieb."
    )
    norm = "P_hyd = ρ·g·V̇·H; P₁ = P_hyd / (η_P·η_M·η_FU); Motor-Mindestwirkungsgrade IEC 60034-30-1 (4-polig, 50 Hz)"
    keywords = ("pumpenleistung", "wellenleistung", "leistungsaufnahme", "motor", "motorleistung", "wirkungsgrad",
                "ie3", "ie4", "frequenzumrichter", "iec", "baugröße", "energie", "stromkosten")

    fields = [
        NumberField("V", "Förderstrom", "V̇", "m**3/hour", 25, min=0, decimals=3),
        NumberField("H", "Förderhöhe", "H", "m", 18, min=0, decimals=2),
        NumberField("rho", "Dichte des Mediums", "ρ", "kg/m**3", 998, min=0, decimals=1),
        NumberField("etaP", "Pumpenwirkungsgrad im Betriebspunkt", "η_P", "percent", 72, min=1, max=95, decimals=1,
                    tooltip="Aus der Kennlinie; kleine Nassläufer 20–50 %, Normpumpen 60–85 %"),
        ChoiceField("motor", "Motorwirkungsgrad", [("ie3", "IE3 – Mindestwert der Baugröße"),
                                                   ("ie4", "IE4 – Mindestwert der Baugröße"),
                                                   ("frei", "Eigener Wert (Datenblatt, EC-Motor)")], "ie3"),
        NumberField("etaM", "Motorwirkungsgrad", "η_M", "percent", 90, min=1, max=99.5, decimals=1,
                    visible_if=MOT_FREI),
        ChoiceField("fu", "Frequenzumrichter", [("nein", "ohne"), ("ja", "mit Frequenzumrichter")], "nein"),
        NumberField("etaFU", "Wirkungsgrad Frequenzumrichter", "η_FU", "percent", 97, min=50, max=99.9, decimals=1,
                    visible_if=FU),
        ChoiceField("energie", "Jahresenergie", [("nein", "nicht berechnen"), ("ja", "bei Dauerbetrieb berechnen")],
                    "nein"),
        NumberField("t", "Betriebsstunden pro Jahr", "t", "hour", 6000, min=0, max=8760, decimals=0,
                    visible_if=ENERGIE),
        NumberField("preis", "Strompreis", "k_E", "EUR/(kW*h)", 0.30, min=0, decimals=3, visible_if=ENERGIE),
    ]

    def compute(self, inp) -> None:
        V = inp["V"].to("m**3/s").magnitude
        H = inp["H"].to("m").magnitude
        rho = inp["rho"].to("kg/m**3").magnitude
        etaP = inp["etaP"].to("percent").magnitude / 100
        P_hyd = rho * G * V * H
        P2 = P_hyd / etaP
        self.step("Hydraulische Leistung", "P_hyd = ρ · g · V̇ · H",
                  f"P_hyd = {fmt_num(rho, 1)} · 9,81 · {fmt_num(V, 5)} m³/s · {fmt_num(H, 2)} m",
                  f"{fmt_num(P_hyd / 1000, 3)} kW")
        self.step("Wellenleistung", "P₂ = P_hyd / η_P", f"P₂ = {fmt_num(P_hyd / 1000, 3)} kW / {fmt_num(etaP, 3)}",
                  f"{fmt_num(P2 / 1000, 3)} kW")

        zu = motor_zuschlag(P2 / 1000)
        P_min = P2 * (1 + zu)
        self.step("Motor-Mindestleistung", "P_M ≥ P₂ · (1 + Zuschlag)",
                  f"Zuschlag {fmt_num(zu * 100, 0)} % (≤ 7,5 kW: 20 %, ≤ 40 kW: 15 %, darüber 10 %)",
                  f"{fmt_num(P_min / 1000, 3)} kW")
        sel = motor_groesse(P_min / 1000)
        if sel is None:
            raise ValueError("Leistung über 315 kW – außerhalb der hinterlegten IEC-Normreihe.")
        idx, P_N = sel
        self.step("Motorbaugröße", "nächste Normleistung der IEC-Reihe", "", f"P_N = {fmt_num(P_N, 2)} kW")

        if inp["motor"] == "frei":
            etaM, mot_txt = inp["etaM"].to("percent").magnitude / 100, "Datenblatt"
        else:
            tab = IE3 if inp["motor"] == "ie3" else IE4
            etaM, mot_txt = tab[idx] / 100, f"{inp['motor'].upper()}-Mindestwert bei {fmt_num(P_N, 2)} kW"
        etaFU = inp["etaFU"].to("percent").magnitude / 100 if inp["fu"] == "ja" else 1.0
        P_M = P2 / etaM            # elektrische Leistung am Motor
        P1 = P_M / etaFU          # Netzleistung
        self.step("Elektrische Leistungsaufnahme", "P₁ = P₂ / (η_M · η_FU)",
                  f"η_M = {fmt_num(etaM * 100, 1)} % ({mot_txt})"
                  + (f", η_FU = {fmt_num(etaFU * 100, 1)} %" if inp["fu"] == "ja" else ""),
                  f"{fmt_num(P1 / 1000, 3)} kW")
        eta_ges = P_hyd / P1
        self.step("Gesamtwirkungsgrad", "η_ges = P_hyd / P₁ = η_P · η_M · η_FU",
                  f"η_ges = {fmt_num(etaP, 3)} · {fmt_num(etaM, 3)} · {fmt_num(etaFU, 3)}",
                  f"{fmt_num(eta_ges * 100, 1)} %")

        self.result("Phyd", "Hydraulische Leistung", "P_hyd", Q_(P_hyd, "W"), "kW", 3)
        self.result("P2", "Wellenleistung", "P₂", Q_(P2, "W"), "kW", 3, highlight=True)
        self.result("P1", "Elektrische Leistungsaufnahme", "P₁", Q_(P1, "W"), "kW", 3, highlight=True)
        self.result("PN", "Motor-Bemessungsleistung", "P_N", Q_(P_N, "kW"), "kW", 2, highlight=True)
        self.result("eta", "Gesamtwirkungsgrad", "η_ges", Q_(eta_ges * 100, "percent"), "percent", 1)
        self.result("vP", "Verlust Pumpe", "P_V,P", Q_(P2 - P_hyd, "W"), "kW", 3)
        self.result("vM", "Verlust Motor", "P_V,M", Q_(P_M - P2, "W"), "kW", 3)
        if inp["fu"] == "ja":
            self.result("vF", "Verlust Frequenzumrichter", "P_V,FU", Q_(P1 - P_M, "W"), "kW", 3)
        self.result("last", "Motorauslastung", "P₂/P_N", Q_(P2 / (P_N * 1000) * 100, "percent"), "percent", 0)

        if inp["energie"] == "ja":
            t = inp["t"].to("hour").magnitude
            preis = inp["preis"].to("EUR/(kW*h)").magnitude
            E = P1 / 1000 * t
            self.step("Jahresenergie", "E = P₁ · t", f"E = {fmt_num(P1 / 1000, 3)} kW · {fmt_num(t, 0)} h",
                      f"{fmt_num(E, 0)} kWh/a")
            self.step("Energiekosten", "K = E · k_E", f"K = {fmt_num(E, 0)} kWh · {fmt_num(preis, 3)} €/kWh",
                      f"{fmt_num(E * preis, 0)} €/a")
            self.result("E", "Jahresenergie", "E", Q_(E, "kW*h/year"), "kW*h/year", 0)
            self.result("K", "Energiekosten", "K", Q_(E * preis, "EUR/year"), "EUR/year", 0, highlight=True)
            self.info("Dauerbetrieb im Auslegungspunkt angenommen – für Teillast und Regelungsarten den Rechner "
                      "„Energiekosten & Regelung“ verwenden.")

        if P2 / (P_N * 1000) < 0.5:
            self.info("Der Motor ist weniger als halb ausgelastet – im Teillastbereich sinkt der Motorwirkungsgrad.")
        if inp["motor"] != "frei":
            self.info("IE-Werte sind Mindestwirkungsgrade bei Bemessungsleistung (4-polig, 50 Hz); reale Motoren "
                      "liegen oft etwas darüber. Pumpen mit Motoren < 0,12 kW und Nassläufer: Datenblattwert "
                      "verwenden.")
        if P_N < IEC_GROESSEN[0] * 1.01 and P2 < 60:
            self.info("Sehr kleine Leistung – bei Heizungsumwälzpumpen (Nassläufer) gibt der Hersteller P₁ direkt an.")
        self.info("Motor-Mindestleistung auch auf das Kennlinienende (Maximalförderstrom) prüfen, wenn die Pumpe "
                  "ungeregelt nach rechts auslaufen kann.")

    def plot(self, fig, raw, result) -> bool:
        if not result.ok:
            return False
        ax = fig.subplots()
        labels = ["Hydraulik", "Verlust Pumpe", "Verlust Motor"]
        vals = [result.value("Phyd"), result.value("vP"), result.value("vM")]
        cols = ["#1f6fb2", "#e59866", "#c0392b"]
        if raw.get("fu") == "ja":
            labels.append("Verlust FU")
            vals.append(result.value("vF"))
            cols.append("#8e44ad")
        left = 0.0
        for lab, v, c in zip(labels, vals, cols):
            ax.barh([0], [v], left=left, color=c, label=f"{lab}: {fmt_num(v, 3)} kW", height=0.5)
            left += v
        ax.axvline(result.value("PN"), color="#2b3a4a", ls="--", lw=1.2,
                   label=f"Motor P_N = {fmt_num(result.value('PN'), 2)} kW")
        ax.set_yticks([])
        ax.set_xlabel("Leistung  [kW]")
        ax.set_title(f"Leistungsbilanz – Gesamtwirkungsgrad {fmt_num(result.value('eta'), 1)} %")
        ax.set_xlim(0, max(left, result.value("PN")) * 1.15)
        ax.set_ylim(-0.8, 1.6)
        ax.legend(loc="upper left", fontsize=8, ncol=2)
        ax.grid(True, axis="x", alpha=0.3)
        return True

    def sketch_svg(self, raw) -> str:
        s = Svg()
        fu = raw.get("fu") == "ja"
        x = 20
        s.text(x + 22, 100, "Netz", 11, MUTED).text(x + 22, 132, "P₁", 13, INK, italic=True)
        s.arrow(x, 110, x + 42, 110, "#8e44ad")
        x += 45
        if fu:
            s.rect(x, 90, 56, 40, fill="#ece2f3").text(x + 28, 115, "FU", 12, INK, bold=True)
            s.text(x + 28, 152, "η_FU", 12, MUTED, italic=True)
            s.arrow(x + 58, 110, x + 84, 110, "#8e44ad")
            x += 87
        s.rect(x, 85, 76, 50, fill="#f5d7d3").text(x + 38, 115, "Motor", 12, INK, bold=True)
        s.text(x + 38, 152, "η_M", 12, MUTED, italic=True)
        s.line(x + 76, 110, x + 112, 110, INK, 5)
        s.text(x + 94, 98, "P₂", 13, INK, italic=True)
        pumpe_svg(s, x + 140, 110, 28)
        s.text(x + 140, 157, "η_P", 12, MUTED, italic=True)
        s.arrow(x + 170, 110, 350, 110, "#1f6fb2")
        s.text(348, 98, "P_hyd", 13, INK, "end", True)
        s.text(180, 200, "Gesamtwirkungsgrad = Produkt der Einzelwirkungsgrade", 11, INK)
        return s.render()
