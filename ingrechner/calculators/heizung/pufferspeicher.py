"""Pufferspeicher: gespeicherte Wärme, Entlade-/Ladezeit oder erforderliches Volumen."""

from __future__ import annotations

import numpy as np

from ingrechner.core.model import Calculator, ChoiceField, NumberField
from ingrechner.core.stoffwerte import stoffwerte
from ingrechner.core.svg import INK, Svg
from ingrechner.core.units import Q_, fmt_num

INHALT = {"modus": ["inhalt"]}
VOLUMEN = {"modus": ["volumen"]}


class Pufferspeicher(Calculator):
    id = "hz.pufferspeicher"
    title = "Pufferspeicher"
    category = "Heizung / Wärme"
    description = (
        "Nutzbare Wärmemenge eines Wasserspeichers zwischen oberer und unterer Temperatur, Entlade- und "
        "Ladezeit – oder das erforderliche Volumen für eine Mindestlaufzeit des Wärmeerzeugers."
    )
    norm = "Q = V · ρ · c_p · Δθ (ideal geschichteter Speicher); Stoffwerte VDI-Wärmeatlas"
    keywords = ("pufferspeicher", "speicher", "puffer", "wärmespeicher", "speichervolumen", "laufzeit",
                "taktung", "wärmepumpe", "kessel", "kwh")

    fields = [
        ChoiceField("modus", "Gesucht", [("inhalt", "Wärmeinhalt eines Speichers"),
                                         ("volumen", "Erforderliches Speichervolumen")], "inhalt"),
        NumberField("V", "Speichervolumen", "V", "liter", 800, min=0, decimals=0, visible_if=INHALT),
        NumberField("to", "Obere Temperatur (geladen)", "θ_o", "degC", 70, min=1, max=150, decimals=1),
        NumberField("tu", "Untere Temperatur (entladen)", "θ_u", "degC", 35, min=0, max=150, min_inclusive=True,
                    decimals=1, tooltip="Niedrigste noch nutzbare Temperatur bzw. Rücklauftemperatur"),
        NumberField("P", "Entnahmeleistung (Verbraucher)", "P_E", "kW", 8, min=0, decimals=2, visible_if=INHALT),
        NumberField("Pl", "Ladeleistung (Erzeuger)", "P_L", "kW", 12, min=0, decimals=2,
                    tooltip="Leistung des Wärmeerzeugers beim Laden"),
        NumberField("t", "Mindestlaufzeit des Erzeugers", "t_min", "minute", 30, min=0, decimals=0,
                    visible_if=VOLUMEN, tooltip="z. B. Wärmepumpe ≥ 10–20 min, Pelletkessel ≥ 60 min"),
        NumberField("Pv", "Gleichzeitige Abnahme beim Laden", "P_V", "kW", 0, min=0, min_inclusive=True,
                    decimals=2, visible_if=VOLUMEN,
                    tooltip="Verbraucherleistung während des Ladens – nur der Überschuss lädt den Speicher"),
    ]

    def compute(self, inp) -> None:
        to, tu = inp["to"].to("degC").magnitude, inp["tu"].to("degC").magnitude
        if to <= tu:
            raise ValueError("Die obere Temperatur muss über der unteren liegen.")
        sw = stoffwerte("wasser", (to + tu) / 2)
        rho_cp = sw.rho * sw.cp            # kJ/(m³·K)
        dt = to - tu
        self.step("Stoffwerte bei Mitteltemperatur", "θ_m = (θ_o + θ_u) / 2", f"θ_m = {fmt_num(sw.theta, 1)} °C",
                  f"ρ = {fmt_num(sw.rho, 1)} kg/m³, c_p = {fmt_num(sw.cp, 3)} kJ/(kg·K)")
        Pl = inp["Pl"].to("kW").magnitude

        if inp["modus"] == "inhalt":
            V = inp["V"].to("m**3").magnitude
            E = V * rho_cp * dt / 3600          # kWh
            self.step("Nutzbare Wärmemenge", "Q = V · ρ · c_p · (θ_o − θ_u)",
                      f"Q = {fmt_num(V, 3)} m³ · {fmt_num(sw.rho, 1)} · {fmt_num(sw.cp, 3)} · {fmt_num(dt, 1)} K",
                      f"{fmt_num(E, 2)} kWh")
            P = inp["P"].to("kW").magnitude
            t_ent = E / P
            t_lad = E / Pl
            self.step("Entladedauer", "t_E = Q / P_E", f"t_E = {fmt_num(E, 2)} kWh / {fmt_num(P, 2)} kW",
                      f"{fmt_num(t_ent, 2)} h")
            self.step("Ladedauer", "t_L = Q / P_L", f"t_L = {fmt_num(E, 2)} kWh / {fmt_num(Pl, 2)} kW",
                      f"{fmt_num(t_lad, 2)} h")
            self.result("E", "Nutzbare Wärmemenge", "Q", Q_(E, "kW*h"), "kW*h", 2, highlight=True)
            self.result("tE", "Entladedauer", "t_E", Q_(t_ent * 60, "minute"), "minute", 0, highlight=True)
            self.result("tL", "Ladedauer", "t_L", Q_(t_lad * 60, "minute"), "minute", 0)
            self.result("spez", "Spezifisch", "Q/V", Q_(E / (V * 1000), "kW*h/liter"), "kW*h/liter", 4)
        else:
            Pv = inp["Pv"].to("kW").magnitude
            if Pl <= Pv:
                raise ValueError("Die Ladeleistung muss größer als die gleichzeitige Abnahme sein.")
            t = inp["t"].to("hour").magnitude
            E = (Pl - Pv) * t
            V = E * 3600 / (rho_cp * dt)        # m³
            self.step("Zu speichernde Wärme während der Mindestlaufzeit", "Q = (P_L − P_V) · t_min",
                      f"Q = ({fmt_num(Pl, 2)} − {fmt_num(Pv, 2)}) kW · {fmt_num(t, 3)} h", f"{fmt_num(E, 2)} kWh")
            self.step("Erforderliches Volumen", "V = Q / (ρ · c_p · (θ_o − θ_u))",
                      f"V = {fmt_num(E, 2)} kWh · 3600 / ({fmt_num(rho_cp, 1)} kJ/(m³·K) · {fmt_num(dt, 1)} K)",
                      f"{fmt_num(V * 1000, 0)} l")
            self.result("V", "Erforderliches Speichervolumen", "V_erf", Q_(V * 1000, "liter"), "liter", 0,
                        highlight=True)
            self.result("E", "Gespeicherte Wärmemenge", "Q", Q_(E, "kW*h"), "kW*h", 2)
            self.result("spezP", "Volumen je kW Erzeugerleistung", "V/P_L", Q_(V * 1000 / Pl, "liter/kW"),
                        "liter/kW", 1)
        if dt < 5:
            self.warn("Sehr kleine nutzbare Spreizung – der Speicher ist wenig wirksam.")
        self.info("Ideal geschichteter Speicher ohne Wärmeverluste und Durchmischung; real sind 10–20 % Zuschlag "
                  "üblich. Mindestvolumen des Herstellers (z. B. Wärmepumpe) beachten.")

    def plot(self, fig, raw, result) -> bool:
        if not result.ok:
            return False
        ax = fig.subplots()
        to, tu = float(raw["to"]), float(raw["tu"])
        sw = stoffwerte("wasser", (to + tu) / 2)
        rc = sw.rho * sw.cp
        if raw["modus"] == "inhalt":
            vs = np.linspace(100, max(2000, float(raw["V"]) * 2), 100)
            ax.plot(vs, vs / 1000 * rc * (to - tu) / 3600, color="#1f6fb2", lw=2)
            ax.plot([float(raw["V"])], [result.value("E")], "o", color="#c0392b")
            ax.set_xlabel("Speichervolumen  [l]")
            ax.set_ylabel("Nutzbare Wärmemenge  [kWh]")
            ax.set_title(f"Wärmeinhalt bei {fmt_num(to, 0)}/{fmt_num(tu, 0)} °C")
        else:
            ts = np.linspace(5, max(120, float(raw["t"]) * 2), 100)
            p = float(raw["Pl"]) - float(raw.get("Pv", 0) or 0)
            ax.plot(ts, p * ts / 60 * 3600 / (rc * (to - tu)) * 1000, color="#1f6fb2", lw=2)
            ax.plot([float(raw["t"])], [result.value("V")], "o", color="#c0392b")
            ax.set_xlabel("Mindestlaufzeit  [min]")
            ax.set_ylabel("Erforderliches Volumen  [l]")
            ax.set_title("Speichervolumen über der Mindestlaufzeit")
        ax.grid(True, alpha=0.3)
        return True

    def sketch_svg(self, raw) -> str:
        s = Svg()
        s.rect(140, 30, 80, 160, fill="#ffffff")
        for i in range(16):
            col = f"#{max(31, 0xc0 - i * 10):02x}{0x39 + i * 4:02x}{0x2b + i * 8:02x}"
            s.rect(141, 31 + i * 10, 78, 10, fill=col, stroke=col, width=0)
        s.text(180, 52, "θ_o", 13, "#ffffff", italic=True).text(180, 178, "θ_u", 13, "#ffffff", italic=True)
        s.arrow(60, 50, 138, 50, "#c0392b").text(60, 42, "Laden", 11, INK, "start")
        s.arrow(222, 50, 300, 50, "#c0392b").text(300, 42, "Verbraucher", 11, INK, "end")
        s.arrow(300, 175, 222, 175, "#1f6fb2").arrow(138, 175, 60, 175, "#1f6fb2")
        return s.render()
