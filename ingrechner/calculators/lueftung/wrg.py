"""Wärmerückgewinnung: Zulufttemperatur, Leistung, Jahreseinsparung und Vereisungsgefahr."""

from __future__ import annotations

import numpy as np

from ingrechner.core import feuchte, medien
from ingrechner.core.model import Calculator, ChoiceField, NumberField
from ingrechner.core.svg import ACCENT, INK, MUTED, Svg
from ingrechner.core.units import Q_, fmt_num

GAS = {"energie": ["gas"]}
WP = {"energie": ["strom"]}
ANDERS = {"energie": ["frei"]}


class Waermerueckgewinnung(Calculator):
    id = "lu.wrg"
    title = "Wärmerückgewinnung (WRG)"
    category = "Lüftung / RLT"
    description = (
        "Zulufttemperatur nach der WRG aus dem Temperaturänderungsgrad, zurückgewonnene Leistung, verbleibende "
        "Nachheizleistung, Fortlufttemperatur mit Vereisungs-/Kondensatprüfung und Jahreseinsparung über "
        "Heizgradstunden – abzüglich der zusätzlichen Ventilatorenergie durch den WRG-Druckverlust. Brennstoff "
        "z. B. Erdgas aus der Mediendatenbank."
    )
    norm = "Φ_t = (θ_ZU − θ_AU)/(θ_AB − θ_AU) nach DIN EN 308 / EN 13053; Q = V̇·ρ·c_p·Φ·G_h"
    keywords = ("wärmerückgewinnung", "wrg", "rotationswärmetauscher", "plattenwärmetauscher", "kvs",
                "temperaturänderungsgrad", "rückwärmzahl", "vereisung", "fortluft", "heizgradstunden",
                "lüftung", "rlt", "einsparung", "erdgas")

    fields = [
        NumberField("V", "Zuluftvolumenstrom", "V̇_ZU", "m**3/hour", 4000, min=0, decimals=0),
        NumberField("Vab", "Abluftvolumenstrom", "V̇_AB", "m**3/hour", 4000, min=0, decimals=0),
        NumberField("phi_t", "Temperaturänderungsgrad", "Φ_t", "percent", 75, min=0, max=100, decimals=1,
                    tooltip="Plattentauscher 50–80 %, Rotor 70–85 %, KVS 40–70 % (bei ausgeglichenen Massenströmen)"),
        NumberField("tau", "Außenluft (Auslegung)", "θ_AU", "degC", -12, min=-30, max=20, decimals=1),
        NumberField("tab", "Abluft", "θ_AB", "degC", 22, min=0, max=40, decimals=1),
        NumberField("phi_ab", "Relative Feuchte Abluft", "φ_AB", "percent", 40, min=1, max=100, decimals=0),
        NumberField("tzu", "Zuluft-Solltemperatur", "θ_ZU,soll", "degC", 20, min=0, max=40, decimals=1),
        NumberField("Gh", "Heizgradstunden der Lüftungszeit", "G_h", "kelvin*hour/year", 50000, min=0, decimals=0,
                    tooltip="Σ (θ_AB − θ_AU) über die Betriebsstunden mit Heizbedarf; Tagbetrieb Mo–Fr ≈ 35–55 kKh/a, "
                            "Dauerbetrieb ≈ 80–100 kKh/a (Deutschland, θ_AB 20–22 °C)"),
        NumberField("dp", "Zusätzlicher Druckverlust WRG (je Seite)", "Δp_WRG", "Pa", 150, min=0, min_inclusive=True,
                    decimals=0),
        NumberField("t", "Betriebsstunden pro Jahr", "t", "hour", 3000, min=0, max=8760, decimals=0),
        NumberField("eta_v", "Ventilator-Systemwirkungsgrad", "η_V", "percent", 55, min=5, max=90, decimals=0),
        ChoiceField("energie", "Wärmeerzeugung", [("gas", "Gaskessel"),
                                                  ("strom", "Wärmepumpe (Strom)"), ("frei", "Wärmepreis vorgeben")],
                    "gas"),
        ChoiceField("brenngas", "Brennstoff", [(m, n) for m, n in medien.auswahl("gas")
                                               if m.startswith(("erdgas", "klaergas"))], "erdgas_h", visible_if=GAS),
        NumberField("eta_k", "Nutzungsgrad Kessel", "η_K", "percent", 95, min=30, max=110, decimals=0,
                    visible_if=GAS, tooltip="bezogen auf den Heizwert H_i; Brennwertkessel bis ≈ 105 %"),
        NumberField("p_gas", "Gaspreis (je kWh H_i)", "k_G", "EUR/(kW*h)", 0.10, min=0, decimals=3, visible_if=GAS),
        NumberField("jaz", "Jahresarbeitszahl Wärmepumpe", "JAZ", "", 3.2, min=1, decimals=2, visible_if=WP),
        NumberField("p_waerme", "Wärmepreis", "k_W", "EUR/(kW*h)", 0.12, min=0, decimals=3, visible_if=ANDERS),
        NumberField("p_strom", "Strompreis", "k_E", "EUR/(kW*h)", 0.30, min=0, decimals=3),
    ]

    def compute(self, inp) -> None:
        V = inp["V"].to("m**3/s").magnitude
        Vab = inp["Vab"].to("m**3/s").magnitude
        phi = inp["phi_t"].to("percent").magnitude / 100
        tau, tab, tzu = (inp[k].to("degC").magnitude for k in ("tau", "tab", "tzu"))
        if tab <= tau:
            raise ValueError("Die Ablufttemperatur muss über der Außenlufttemperatur liegen.")
        z_au = medien.medium("luft").zustand(tau)
        rho_cp = z_au.rho * z_au.cp            # kJ/(m³·K)
        t_nach = tau + phi * (tab - tau)
        Q_wrg = V * rho_cp * (t_nach - tau)    # kW
        Q_nach = max(0.0, V * rho_cp * (tzu - t_nach))
        self.step("Zuluft nach WRG", "θ_ZU,WRG = θ_AU + Φ_t · (θ_AB − θ_AU)",
                  f"θ = {fmt_num(tau, 1)} + {fmt_num(phi, 3)} · ({fmt_num(tab, 1)} − {fmt_num(tau, 1)})",
                  f"{fmt_num(t_nach, 1)} °C")
        self.step("Rückgewonnene Leistung", "Q̇_WRG = V̇ · ρ · c_p · (θ_ZU,WRG − θ_AU)",
                  f"ρ·c_p = {fmt_num(rho_cp, 3)} kJ/(m³·K) (Außenluft)", f"{fmt_num(Q_wrg, 1)} kW")
        self.step("Nachheizung", "Q̇_NH = V̇ · ρ · c_p · (θ_ZU,soll − θ_ZU,WRG)", "", f"{fmt_num(Q_nach, 1)} kW")
        # Fortluft (Energiebilanz, sensibel)
        t_fo = tab - (V / Vab if Vab else 1) * (t_nach - tau)
        ab = feuchte.Zustand(tab, inp["phi_ab"].to("percent").magnitude / 100)
        self.step("Fortlufttemperatur", "θ_FO = θ_AB − V̇_ZU/V̇_AB · (θ_ZU,WRG − θ_AU)",
                  f"Taupunkt der Abluft θ_τ = {fmt_num(ab.tau, 1)} °C", f"{fmt_num(t_fo, 1)} °C")

        Gh = inp["Gh"].to("kelvin*hour/year").magnitude
        E_wrg = V * rho_cp * phi * Gh                       # kWh/a
        dp = inp["dp"].to("Pa").magnitude
        eta_v = inp["eta_v"].to("percent").magnitude / 100
        t = inp["t"].to("hour").magnitude
        E_v = (V + Vab) * dp / eta_v * t / 1000             # kWh/a
        p_strom = inp["p_strom"].to("EUR/(kW*h)").magnitude
        brennstoff = None
        if inp["energie"] == "gas":
            g = medien.medium(inp["brenngas"])
            y = g.zusammensetzung
            hi = (y.get("CH4", 0) * 9.97 + y.get("C2H6", 0) * 17.4) / sum(y.values())   # kWh/m³ (Norm)
            eta_k = inp["eta_k"].to("percent").magnitude / 100
            E_br = E_wrg / eta_k
            K_w = E_br * inp["p_gas"].to("EUR/(kW*h)").magnitude
            self.step("Brennstoffeinsparung", "B = E_WRG / (η_K · H_i)",
                      f"{g.name}: H_i = {fmt_num(hi, 2)} kWh/m³, η_K = {fmt_num(eta_k, 2)}",
                      f"{fmt_num(E_br / hi, 0)} m³/a ({fmt_num(E_br, 0)} kWh/a)")
            brennstoff = E_br / hi
        elif inp["energie"] == "strom":
            jaz = float(inp["jaz"])
            K_w = E_wrg / jaz * p_strom
            self.step("Strom der Wärmepumpe", "E_el = E_WRG / JAZ", f"JAZ = {fmt_num(jaz, 2)}",
                      f"{fmt_num(E_wrg / jaz, 0)} kWh/a")
        else:
            K_w = E_wrg * inp["p_waerme"].to("EUR/(kW*h)").magnitude
        K_v = E_v * p_strom
        self.step("Jahreswärme der WRG", "E_WRG = V̇ · ρ · c_p · Φ_t · G_h",
                  f"G_h = {fmt_num(Gh / 1000, 1)} kKh/a", f"{fmt_num(E_wrg / 1000, 1)} MWh/a")
        self.step("Zusätzliche Ventilatorenergie", "E_V = (V̇_ZU + V̇_AB) · Δp_WRG / η_V · t",
                  f"Δp_WRG = {fmt_num(dp, 0)} Pa je Seite", f"{fmt_num(E_v, 0)} kWh/a")
        self.step("Netto-Einsparung", "ΔK = K_Wärme − E_V · k_E",
                  f"{fmt_num(K_w, 0)} €/a − {fmt_num(K_v, 0)} €/a", f"{fmt_num(K_w - K_v, 0)} €/a")

        self.result("tnach", "Zulufttemperatur nach WRG", "θ_ZU,WRG", Q_(t_nach, "degC"), "degC", 1, highlight=True)
        self.result("Qwrg", "Rückgewonnene Leistung", "Q̇_WRG", Q_(Q_wrg, "kW"), "kW", 1, highlight=True)
        self.result("Qnh", "Nachheizleistung", "Q̇_NH", Q_(Q_nach, "kW"), "kW", 1, highlight=True)
        self.result("tfo", "Fortlufttemperatur", "θ_FO", Q_(t_fo, "degC"), "degC", 1)
        self.result("E", "Rückgewonnene Jahreswärme", "E_WRG", Q_(E_wrg / 1000, "MW*h/year"), "MW*h/year", 1)
        self.result("Ev", "Zusätzlicher Ventilatorstrom", "E_V", Q_(E_v, "kW*h/year"), "kW*h/year", 0)
        self.result("dK", "Netto-Einsparung", "ΔK", Q_(K_w - K_v, "EUR/year"), "EUR/year", 0, highlight=True)
        if brennstoff is not None:
            self.result("B", "Eingesparter Brennstoff", "B", Q_(brennstoff, "m**3/year"), "m**3/year", 0)

        if t_fo < ab.tau:
            if t_fo < 0:
                self.warn(f"Fortluft {fmt_num(t_fo, 1)} °C unter dem Taupunkt ({fmt_num(ab.tau, 1)} °C) und unter 0 °C "
                          "– Vereisungsgefahr: Abtau-/Frostschutzschaltung (Bypass, Vorerhitzer, Drehzahl Rotor) "
                          "vorsehen.")
            else:
                self.info(f"Fortluft unter dem Taupunkt der Abluft ({fmt_num(ab.tau, 1)} °C) – Kondensatablauf am "
                          "Wärmetauscher vorsehen.")
        if K_w - K_v < 0:
            self.warn("Die zusätzliche Ventilatorenergie übersteigt die Wärmeeinsparung – WRG mit geringerem "
                      "Druckverlust oder längere Heizperiode prüfen.")
        if abs(V - Vab) / max(V, Vab) > 0.1:
            self.info("Unausgeglichene Volumenströme: Φ_t bezieht sich auf ausgeglichene Massenströme – "
                      "Herstellerangabe für das tatsächliche Verhältnis verwenden.")

    def plot(self, fig, raw, result) -> bool:
        if not result.ok:
            return False
        phi = float(raw["phi_t"]) / 100
        tab = float(raw["tab"])
        taus = np.linspace(-20, tab - 1, 80)
        ax = fig.subplots()
        ax.plot(taus, taus + phi * (tab - taus), color="#c0392b", lw=2, label="Zuluft nach WRG")
        ax.plot(taus, tab - phi * (tab - taus) * float(raw["V"]) / max(float(raw["Vab"]), 1), color="#1f6fb2", lw=2,
                label="Fortluft")
        ax.axhline(0, color="#6b7b8c", lw=0.8)
        ax.axhline(float(raw["tzu"]), color="#d68910", ls="--", lw=1.2, label="Zuluft-Soll")
        ax.set_xlabel("Außenlufttemperatur θ_AU  [°C]")
        ax.set_ylabel("Temperatur  [°C]")
        ax.set_title(f"Temperaturen bei Φ_t = {fmt_num(phi * 100, 0)} %")
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=8)
        return True

    def sketch_svg(self, raw) -> str:
        s = Svg()
        s.polygon([(150, 60), (210, 110), (150, 160), (90, 110)], fill="#eef3f8")
        s.line(90, 110, 210, 110, INK, 1).line(150, 60, 150, 160, INK, 1)
        s.arrow(20, 80, 120, 80, ACCENT).text(20, 72, "Außenluft", 10, INK, "start")
        s.arrow(180, 80, 330, 80, "#d68910").text(330, 72, "Zuluft", 10, INK, "end")
        s.arrow(330, 140, 180, 140, "#c0392b").text(330, 160, "Abluft", 10, INK, "end")
        s.arrow(120, 140, 20, 140, MUTED).text(20, 160, "Fortluft", 10, INK, "start")
        s.text(150, 200, "Φ_t", 13, INK, italic=True)
        return s.render()
