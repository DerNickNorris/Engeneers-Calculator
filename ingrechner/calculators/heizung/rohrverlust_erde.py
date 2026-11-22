"""Wärmeverlust erdverlegter Rohrleitungen (Einzelrohr oder Vor-/Rücklauf) – Fernwärme/Nahwärme."""

from __future__ import annotations

import math

from ingrechner.core.model import Calculator, ChoiceField, NumberField
from ingrechner.core.rohrdaten import KMR, LAMBDA_ROHR
from ingrechner.core.svg import ACCENT, INK, MUTED, Svg
from ingrechner.core.units import Q_, fmt_num

from ._rohr import aufloesen, rohr_felder

R0_OBERFLAECHE = 0.0685   # m²·K/W, Wärmeübergang Erdoberfläche (DIN EN 13941)
KMR_FELD = {"bauart": ["kmr"]}
EIGEN = {"bauart": ["frei"]}
PAAR = {"anordnung": ["paar"]}


def r_erdreich(H: float, D: float, lam_e: float) -> float:
    """Erdreichwiderstand eines Rohres [m·K/W]: arcosh(2·H_eff/D) / (2π·λ_E), H_eff = H + R0·λ_E."""
    h_eff = H + R0_OBERFLAECHE * lam_e
    x = 2 * h_eff / D
    return math.log(x + math.sqrt(x * x - 1)) / (2 * math.pi * lam_e)


def r_gegenseitig(H: float, C: float, lam_e: float) -> float:
    """Gegenseitige Beeinflussung zweier Rohre im Achsabstand C [m·K/W] (Multipol 0. Ordnung)."""
    h_eff = H + R0_OBERFLAECHE * lam_e
    return math.log(1 + (2 * h_eff / C) ** 2) / (4 * math.pi * lam_e)


def verlust_paar(t1: float, t2: float, te: float, R: float, Rh: float) -> tuple[float, float]:
    """Wärmeverluste [W/m] von Vor- und Rücklauf: R = Isolation + Erdreich je Rohr, Rh = Kopplung."""
    n = R * R - Rh * Rh
    q1 = (R * (t1 - te) - Rh * (t2 - te)) / n
    q2 = (R * (t2 - te) - Rh * (t1 - te)) / n
    return q1, q2


class RohrverlustErde(Calculator):
    id = "hz.rohrverlust_erde"
    title = "Wärmeverlust erdverlegte Leitung"
    category = "Heizung / Wärme"
    description = (
        "Wärmeverlust von Nah-/Fernwärmeleitungen im Erdreich: Einzelrohr oder Vor- und Rücklauf "
        "nebeneinander, Kunststoffmantelrohre (KMR) nach EN 253 in den Dämmserien 1–3 oder frei gedämmte "
        "Rohre; Verlust je Meter, gesamt und pro Jahr."
    )
    norm = "DIN EN 13941-1 (Wärmeverluste, Multipolmethode 0. Ordnung); KMR-Abmessungen nach DIN EN 253"
    keywords = ("erdverlegt", "erdreich", "fernwärme", "nahwärme", "kmr", "kunststoffmantelrohr", "en 253",
                "en 13941", "wärmeverlust", "vorlauf", "rücklauf", "trasse")
    material_map = {"lam_rohr": "lam"}
    material_select = ("werkstoff", "frei")

    fields = [
        ChoiceField("bauart", "Rohrsystem", [("kmr", "Kunststoffmantelrohr (KMR) EN 253"),
                                             ("frei", "Rohr aus Rohrtabelle + Dämmung")], "kmr"),
        ChoiceField("kmr_dn", "Nennweite", [(k, f"{k}  (Stahl {v[0]:g} mm)".replace(".", ","))
                                            for k, v in KMR.items()], "DN 50", visible_if=KMR_FELD),
        ChoiceField("serie", "Dämmserie", [("1", "Serie 1 (Standard)"), ("2", "Serie 2 (verstärkt)"),
                                           ("3", "Serie 3 (2× verstärkt)")], "2", visible_if=KMR_FELD),
        *rohr_felder("st:DN 50", 50, vis=EIGEN, default_daemmstoff="b:pur-en253"),
        ChoiceField("anordnung", "Anordnung", [("paar", "Vor- und Rücklauf nebeneinander"),
                                               ("einzel", "Einzelrohr")], "paar"),
        NumberField("t1", "Vorlauftemperatur", "θ_VL", "degC", 80, min=0, max=150, min_inclusive=True, decimals=1),
        NumberField("t2", "Rücklauftemperatur", "θ_RL", "degC", 50, min=0, max=150, min_inclusive=True,
                    decimals=1, visible_if=PAAR),
        NumberField("te", "Erdreichtemperatur (ungestört)", "θ_E", "degC", 10, min=-10, max=40, min_inclusive=True,
                    decimals=1, tooltip="Jahresmittel in Deutschland ca. 8–10 °C"),
        NumberField("H", "Tiefe bis Rohrachse", "H", "m", 0.8, min=0, decimals=2,
                    tooltip="Überdeckung + halber Mantelrohrdurchmesser; üblich 0,6–1,2 m"),
        NumberField("abstand", "Lichter Abstand der Rohre", "a", "m", 0.15, min=0, min_inclusive=True, decimals=3,
                    visible_if=PAAR, tooltip="Abstand zwischen den Mantelrohren (meist 0,1–0,15 m); der "
                                             "Achsabstand ergibt sich zu C = D + a"),
        NumberField("lam_e", "Wärmeleitfähigkeit Erdreich", "λ_E", "W/(m*K)", 1.0, min=0, decimals=2,
                    tooltip="Sand trocken 0,4–0,7; Sand feucht 1,0–2,0; Lehm/Ton 1,2–1,8; EN 13941: oft 1,0–1,5"),
        NumberField("L", "Trassenlänge", "L", "m", 100, min=0, decimals=1),
        NumberField("stunden", "Betriebsstunden pro Jahr", "t_a", "hour", 8760, min=0, min_inclusive=True,
                    max=8784, decimals=0),
    ]

    def _geometrie(self, inp, serie: str | None = None) -> dict:
        if inp["bauart"] == "kmr":
            da, s, serien = KMR[inp["kmr_dn"]]
            Dc, wc = serien[int(serie or inp["serie"])]
            g = aufloesen({**inp, "rohr": "st:DN 50", "werkstoff": "auto", "daemm": Q_(0, "mm")})
            lam_d, d_name = g["lam_d"], g["daemmstoff"]
            d_ins = Dc - 2 * wc
            R_rohr = math.log(da / (da - 2 * s)) / (2 * math.pi * LAMBDA_ROHR["stahl"])
            R_d = math.log(d_ins / da) / (2 * math.pi * lam_d)
            R_m = math.log(Dc / d_ins) / (2 * math.pi * LAMBDA_ROHR["pe"])
            name = f"KMR {inp['kmr_dn']} Serie {serie or inp['serie']} (Mantel {Dc:g} mm)"
            return {"Dc": Dc / 1000, "R_i": R_rohr + R_d + R_m, "name": name, "daemmstoff": d_name,
                    "lam_d": lam_d, "detail": f"Stahl {da:g} × {s:g} mm, PUR bis {d_ins:g} mm, PE-Mantel "
                                              f"{Dc:g} × {wc:g} mm"}
        g = aufloesen(inp)
        D = g["da"] + 2 * g["daemm"]
        R_rohr = math.log(g["da"] / (g["da"] - 2 * g["s"])) / (2 * math.pi * g["lam_r"])
        R_d = math.log(D / g["da"]) / (2 * math.pi * g["lam_d"]) if g["daemm"] > 0 else 0.0
        return {"Dc": D, "R_i": R_rohr + R_d, "name": f"{g['rohr']} {g['werkstoff']}, {g['daemm'] * 1000:g} mm",
                "daemmstoff": g["daemmstoff"], "lam_d": g["lam_d"],
                "detail": f"{g['rohr']}, {g['werkstoff']}, Dämmung {g['daemm'] * 1000:g} mm {g['daemmstoff']}"}

    def _verlust(self, inp, geo, H=None):
        H = inp["H"].to("m").magnitude if H is None else H
        lam_e = inp["lam_e"].to("W/(m*K)").magnitude
        t1, te = inp["t1"].to("degC").magnitude, inp["te"].to("degC").magnitude
        Rs = r_erdreich(H, geo["Dc"], lam_e)
        R = geo["R_i"] + Rs
        if inp["anordnung"] == "einzel":
            return (t1 - te) / R, 0.0, Rs, 0.0
        C = geo["Dc"] + inp["abstand"].to("m").magnitude
        Rh = r_gegenseitig(H, C, lam_e)
        q1, q2 = verlust_paar(t1, inp["t2"].to("degC").magnitude, te, R, Rh)
        return q1, q2, Rs, Rh

    def compute(self, inp) -> None:
        geo = self._geometrie(inp)
        H = inp["H"].to("m").magnitude
        if H <= geo["Dc"] / 2 + 0.05:
            raise ValueError("Die Tiefe bis zur Rohrachse muss größer als der halbe Mantelrohrdurchmesser sein.")
        lam_e = inp["lam_e"].to("W/(m*K)").magnitude
        q1, q2, Rs, Rh = self._verlust(inp, geo)
        L = inp["L"].to("m").magnitude
        qges = q1 + q2
        hours = inp["stunden"].to("hour").magnitude

        self.step("Rohraufbau", "Stahl / Dämmung / Mantel", geo["detail"], f"D = {fmt_num(geo['Dc'] * 1000, 1)} mm")
        self.step("Wärmedurchlasswiderstand Rohr + Dämmung", "R_I = Σ ln(d_a,j / d_i,j) / (2π · λ_j)",
                  f"{geo['daemmstoff']}: λ = {fmt_num(geo['lam_d'], 4)} W/(m·K)", f"{fmt_num(geo['R_i'], 4)} m·K/W")
        self.step("Erdreichwiderstand", "R_E = arcosh(2·H_eff / D) / (2π · λ_E),  H_eff = H + 0,0685 · λ_E",
                  f"H = {fmt_num(H, 2)} m, D = {fmt_num(geo['Dc'] * 1000, 0)} mm, λ_E = {fmt_num(lam_e, 2)} W/(m·K)",
                  f"{fmt_num(Rs, 4)} m·K/W")
        if inp["anordnung"] == "paar":
            C = geo["Dc"] + inp["abstand"].to("m").magnitude
            self.step("Gegenseitige Beeinflussung", "R_h = ln(1 + (2·H_eff / C)²) / (4π · λ_E),  C = D + a",
                      f"C = {fmt_num(geo['Dc'], 3)} m + {fmt_num(inp['abstand'].to('m').magnitude, 3)} m = "
                      f"{fmt_num(C, 3)} m", f"{fmt_num(Rh, 4)} m·K/W")
            self.step("Wärmeverlust Vor- und Rücklauf",
                      "q_VL = [R·(θ_VL − θ_E) − R_h·(θ_RL − θ_E)] / (R² − R_h²),  R = R_I + R_E",
                      "analog q_RL mit vertauschten Temperaturen",
                      f"q_VL = {fmt_num(q1, 2)} W/m, q_RL = {fmt_num(q2, 2)} W/m")
        else:
            self.step("Wärmeverlust", "q = (θ_VL − θ_E) / (R_I + R_E)",
                      f"q = {fmt_num(inp['t1'].to('degC').magnitude - inp['te'].to('degC').magnitude, 1)} K / "
                      f"{fmt_num(geo['R_i'] + Rs, 4)} m·K/W", f"{fmt_num(q1, 2)} W/m")
        self.step("Jahreswärmeverlust", "Q_a = q_ges · L · t_a",
                  f"Q_a = {fmt_num(qges, 2)} W/m · {fmt_num(L, 1)} m · {fmt_num(hours, 0)} h",
                  f"{fmt_num(qges * L * hours / 1e6, 2)} MWh/a")

        self.result("qges", "Wärmeverlust je Trassenmeter", "q_ges", Q_(qges, "W/m"), "W/m", 2, highlight=True)
        if inp["anordnung"] == "paar":
            self.result("q1", "Verlust Vorlauf", "q_VL", Q_(q1, "W/m"), "W/m", 2)
            self.result("q2", "Verlust Rücklauf", "q_RL", Q_(q2, "W/m"), "W/m", 2)
        self.result("Q", "Wärmeverlust der Trasse", "Q̇", Q_(qges * L, "W"), "W", 0, highlight=True)
        self.result("Qa", "Jahreswärmeverlust", "Q_a", Q_(qges * L * hours / 1000, "kW*h"), "kW*h", 0,
                    highlight=True)
        self.result("RI", "Widerstand Rohr + Dämmung", "R_I", Q_(geo["R_i"], "m*K/W"), "m*K/W", 4)
        self.result("RE", "Erdreichwiderstand", "R_E", Q_(Rs, "m*K/W"), "m*K/W", 4)

        if inp["anordnung"] == "paar" and q2 < 0:
            self.info("Der Rücklauf nimmt Wärme vom Vorlauf auf (negativer Verlust) – Rohre enger beieinander als "
                      "sinnvoll oder Rücklauf kälter als das Erdreich.")
        if H < 0.6:
            self.warn("Geringe Überdeckung (< 0,6 m): Frostgefahr und Verkehrslasten prüfen.")
        self.info("Stationärer Jahresmittelwert, homogenes Erdreich, keine Grundwasserströmung; λ der PUR-Dämmung "
                  "altert (EN 253: λ₅₀ ≤ 0,029 W/(m·K)). Herstellerangaben haben Vorrang.")

    def plot(self, fig, raw, result) -> bool:
        if not result.ok:
            return False
        inp = {f.key: (raw.get(f.key, f.default) if isinstance(f, ChoiceField) else
                       (Q_(float(raw.get(f.key, f.default)), f.unit) if f.unit else float(raw.get(f.key, f.default))))
               for f in self.fields}
        ax = fig.subplots()
        if inp["bauart"] == "kmr":
            vals = []
            for s in ("1", "2", "3"):
                q1, q2, *_ = self._verlust(inp, self._geometrie(inp, s))
                vals.append(q1 + q2)
            bars = ax.bar(["Serie 1", "Serie 2", "Serie 3"], vals,
                          color=["#9aa7b4" if s != inp["serie"] else "#1f6fb2" for s in ("1", "2", "3")])
            for b, v in zip(bars, vals):
                ax.text(b.get_x() + b.get_width() / 2, v, fmt_num(v, 1), ha="center", va="bottom", fontsize=8)
            ax.set_ylabel("Wärmeverlust q_ges  [W/m]")
            ax.set_title(f"Dämmserien im Vergleich – {inp['kmr_dn']}")
        else:
            geo = self._geometrie(inp)
            hs = [geo["Dc"] / 2 + 0.1 + i * 0.02 for i in range(100)]
            qs = [sum(self._verlust(inp, geo, h)[:2]) for h in hs]
            ax.plot(hs, qs, color="#1f6fb2", lw=2)
            ax.plot([inp["H"].to("m").magnitude], [result.value("qges")], "o", color="#c0392b")
            ax.set_xlabel("Tiefe bis Rohrachse H  [m]")
            ax.set_ylabel("Wärmeverlust q_ges  [W/m]")
            ax.set_title("Einfluss der Verlegetiefe")
        ax.grid(True, axis="y", alpha=0.3)
        return True

    def sketch_svg(self, raw) -> str:
        s = Svg()
        s.line(20, 40, 340, 40, INK, 2)
        for x in range(20, 340, 12):
            s.line(x, 40, x + 8, 32, MUTED, 0.8)
        s.text(330, 30, "Gelände", 11, MUTED, "end")
        paar = raw.get("anordnung", "paar") == "paar"
        y = 150
        xs = (140, 220) if paar else (180,)
        for i, x in enumerate(xs):
            s.circle(x, y, 26, fill="#eef3f8")
            s.circle(x, y, 11, fill="#c0392b" if i == 0 else "#1f6fb2", stroke=INK)
        s.dim_v(300, 40, y, "H")
        if paar:
            s.dim_h(140, 220, 196, "C = D + a")
        s.text(50, 112, "θ_E", 12, ACCENT, italic=True).text(50, 132, "λ_E", 12, ACCENT, italic=True)
        return s.render()
