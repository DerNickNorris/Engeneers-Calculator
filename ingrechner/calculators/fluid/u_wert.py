"""Wärmedurchgangskoeffizient (U-Wert) eines mehrschichtigen Bauteils nach DIN EN ISO 6946."""

from __future__ import annotations

from ingrechner.core.model import Calculator, ChoiceField, NumberField
from ingrechner.core.svg import ACCENT, INK, MUTED, Svg
from ingrechner.core.units import Q_, fmt_num, fmt_q

# Wärmeübergangswiderstände [m²·K/W] (DIN EN ISO 6946, Tab. 7)
RSI = {"horizontal": 0.13, "aufwaerts": 0.10, "abwaerts": 0.17}
RICHTUNG = [("horizontal", "horizontal – Wand"), ("aufwaerts", "aufwärts – Dach / Decke nach oben"),
            ("abwaerts", "abwärts – Boden / Decke nach unten")]
AUSSEN = [("luft", "Außenluft (R_se = 0,04)"), ("erdreich", "Erdreich (R_se = 0)"),
          ("unbeheizt", "unbeheizter Raum (R_se = R_si)")]
N_SCHICHTEN = 6
# Beispielaufbau: Außenwand Kalksandstein mit WDVS
DEFAULTS = [("Innenputz", 15, 0.70), ("Kalksandstein", 175, 0.99), ("Mineralwolle WLS 035", 140, 0.035),
            ("Außenputz", 10, 0.87), ("", 0, 1.0), ("", 0, 1.0)]


def _layer_fields():
    out = []
    for i, (name, d, lam) in enumerate(DEFAULTS, 1):
        example = f"Beispiel: {name}. " if name else ""
        out.append(NumberField(f"d{i}", f"Schicht {i} – Dicke", f"d_{i}", "mm", d, min=0, min_inclusive=True,
                               decimals=1, tooltip=f"{example}0 = Schicht nicht vorhanden"))
        out.append(NumberField(f"l{i}", f"Schicht {i} – λ", f"λ_{i}", "W/(m*K)", lam, min=0, decimals=3,
                               tooltip=f"{example}Bemessungswert der Wärmeleitfähigkeit nach DIN 4108-4 "
                                       "bzw. Herstellerangabe"))
    return out


class UWert(Calculator):
    id = "fl.u_wert"
    title = "U-Wert Bauteil"
    category = "Fluid / Thermo"
    description = (
        "Wärmedurchgangskoeffizient eines Bauteils aus bis zu sechs homogenen Schichten, "
        "Transmissionswärmestrom und Oberflächentemperatur innen (Tauwasser-/Schimmelkriterium f_Rsi)."
    )
    norm = "DIN EN ISO 6946 (homogene Schichten); f_Rsi nach DIN 4108-2"
    keywords = ("u-wert", "wärmedurchgang", "dämmung", "wand", "wärmeschutz", "iso 6946", "geg",
                "wärmeverlust", "schichten")

    fields = [
        ChoiceField("richtung", "Wärmestromrichtung", RICHTUNG, "horizontal"),
        ChoiceField("aussen", "Außenseite", AUSSEN, "luft"),
        *_layer_fields(),
        NumberField("A", "Bauteilfläche", "A", "m**2", 10, min=0, decimals=2),
        NumberField("ti", "Innentemperatur", "θ_i", "degC", 20, min=-50, max=100, min_inclusive=True, decimals=1),
        NumberField("te", "Außentemperatur", "θ_e", "degC", -12, min=-60, max=60, min_inclusive=True, decimals=1,
                    tooltip="Norm-Außentemperatur nach DIN/TS 12831-1 (z. B. Frankfurt −12 °C)"),
    ]

    def compute(self, inp) -> None:
        rsi = RSI[inp["richtung"]]
        rse = {"luft": 0.04, "erdreich": 0.0, "unbeheizt": rsi}[inp["aussen"]]
        layers = []
        for i in range(1, N_SCHICHTEN + 1):
            d = inp[f"d{i}"].to("m").magnitude
            if d > 0:
                lam = inp[f"l{i}"].to("W/(m*K)").magnitude
                layers.append((i, d, lam, d / lam))
        if not layers:
            raise ValueError("Mindestens eine Schicht mit Dicke > 0 angeben.")

        parts = []
        for i, d, lam, r in layers:
            parts.append(f"{fmt_num(d, 3)}/{fmt_num(lam, 3)}")
            self.step(f"Wärmedurchlasswiderstand Schicht {i}", f"R_{i} = d_{i} / λ_{i}",
                      f"R_{i} = {fmt_num(d, 3)} m / {fmt_num(lam, 3)} W/(m·K)", f"{fmt_num(r, 4)} m²·K/W")
        R = sum(l[3] for l in layers)
        RT = rsi + R + rse
        U = 1 / RT
        self.step("Wärmedurchgangswiderstand", "R_T = R_si + Σ d/λ + R_se",
                  f"R_T = {fmt_num(rsi, 2)} + {fmt_num(R, 4)} + {fmt_num(rse, 2)}", f"{fmt_num(RT, 4)} m²·K/W")
        self.step("U-Wert", "U = 1 / R_T", f"U = 1 / {fmt_num(RT, 4)} m²·K/W", f"{fmt_num(U, 3)} W/(m²·K)")

        ti = inp["ti"].to("degC").magnitude
        te = inp["te"].to("degC").magnitude
        dT = ti - te
        A = inp["A"].to("m**2").magnitude
        phi = U * A * dT
        tsi = ti - rsi * U * dT
        f_rsi = (tsi - te) / dT if dT else 1.0
        self.step("Transmissionswärmestrom", "Φ = U · A · (θ_i − θ_e)",
                  f"Φ = {fmt_num(U, 3)} · {fmt_num(A, 2)} m² · {fmt_num(dT, 1)} K", f"{fmt_num(phi, 1)} W")
        self.step("Oberflächentemperatur innen", "θ_si = θ_i − R_si · U · (θ_i − θ_e)",
                  f"θ_si = {fmt_num(ti, 1)} − {fmt_num(rsi, 2)} · {fmt_num(U, 3)} · {fmt_num(dT, 1)}",
                  f"{fmt_num(tsi, 2)} °C")

        self.result("U", "Wärmedurchgangskoeffizient", "U", Q_(U, "W/(m**2*K)"), "W/(m**2*K)", 3, highlight=True)
        self.result("RT", "Wärmedurchgangswiderstand", "R_T", Q_(RT, "m**2*K/W"), "m**2*K/W", 3)
        self.result("phi", "Wärmestrom durch das Bauteil", "Φ", Q_(phi, "W"), "W", 1, highlight=True)
        self.result("q", "Wärmestromdichte", "q", Q_(U * dT, "W/m**2"), "W/m**2", 2)
        self.result("tsi", "Oberflächentemperatur innen", "θ_si", Q_(tsi, "degC"), "degC", 2)
        self.result("frsi", "Temperaturfaktor", "f_Rsi", Q_(f_rsi, ""), "", 3)

        if inp["richtung"] == "horizontal" and inp["aussen"] == "luft":
            if U <= 0.24:
                self.info(f"U = {fmt_num(U, 3)} W/(m²·K) ≤ 0,24 – Höchstwert GEG Anlage 7 für Außenwände "
                          "bei Erneuerung eingehalten.")
            else:
                self.warn(f"U = {fmt_num(U, 3)} W/(m²·K) > 0,24 – Höchstwert GEG Anlage 7 für Außenwände "
                          "bei Erneuerung überschritten.")
        if inp["aussen"] == "luft" and f_rsi < 0.70:
            self.warn(f"f_Rsi = {fmt_num(f_rsi, 2)} < 0,70: Schimmelpilzgefahr nach DIN 4108-2.")
        if inp["aussen"] == "erdreich":
            self.info("Erdberührte Bauteile: Wärmestrom vereinfacht – genauer nach DIN EN ISO 13370.")
        self.info("Nur homogene Schichten; Wärmebrücken, Befestigungsmittel, Luftschichten und inhomogene "
                  "Schichten (z. B. Holzständer) erfordern Korrekturen nach DIN EN ISO 6946.")

    def plot(self, fig, raw, result) -> bool:
        if not result.ok:
            return False
        rsi = RSI[raw["richtung"]]
        rse = {"luft": 0.04, "erdreich": 0.0, "unbeheizt": rsi}[raw["aussen"]]
        ti, te = float(raw["ti"]), float(raw["te"])
        U = result.value("U")
        q = U * (ti - te)
        xs, ts = [0.0], [ti - q * rsi]
        x, t = 0.0, ts[0]
        ax = fig.subplots()
        shades = ["#dce6f1", "#c6d6e8", "#eef3f8", "#d4dfeb", "#e3ebf4", "#cfdcea"]
        for i in range(1, N_SCHICHTEN + 1):
            d = float(raw[f"d{i}"])
            if d <= 0:
                continue
            lam = float(raw[f"l{i}"])
            ax.axvspan(x, x + d, color=shades[(i - 1) % len(shades)], alpha=0.9, lw=0)
            ax.text(x + d / 2, ti + 1, str(i), ha="center", va="bottom", fontsize=8, color="#5f6f7f")
            x += d
            t -= q * d / 1000 / lam
            xs.append(x)
            ts.append(t)
        ax.plot([-20, 0], [ti, ts[0]], color="#c0392b", lw=1.2, ls=":")
        ax.plot([x, x + 20], [ts[-1], te], color="#c0392b", lw=1.2, ls=":")
        ax.plot(xs, ts, color="#c0392b", lw=2, marker="o", ms=3)
        ax.axhline(0, color="#9aa7b4", lw=0.8)
        ax.set_xlim(-20, x + 20)
        ax.set_xlabel("Bauteildicke von innen  [mm]")
        ax.set_ylabel("Temperatur  [°C]")
        ax.set_title("Temperaturverlauf im Bauteil")
        ax.grid(True, axis="y", alpha=0.3)
        return True

    def sketch_svg(self, raw) -> str:
        s = Svg()
        try:
            ds = [max(0.0, float(raw.get(f"d{i}", 0))) for i in range(1, N_SCHICHTEN + 1)]
        except (TypeError, ValueError):
            ds = [d for _, d, _ in DEFAULTS]
        total = sum(ds) or 1
        x, w = 90, 180
        fills = ["#dce6f1", "#b9cde3", "#f3f6fa", "#cfdcea", "#e3ebf4", "#c6d6e8"]
        for i, d in enumerate(ds):
            if d <= 0:
                continue
            width = w * d / total
            s.rect(x, 40, width, 140, fill=fills[i % len(fills)])
            if width > 12:
                s.text(x + width / 2, 116, str(i + 1), 12, INK)
            x += width
        s.text(50, 112, "innen", 12, MUTED).text(310, 112, "außen", 12, MUTED)
        s.arrow(30, 150, 80, 150).text(55, 170, "Φ", 13, ACCENT, italic=True)
        s.text(180, 205, "Schichten von innen nach außen", 11, MUTED)
        return s.render()
