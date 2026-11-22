"""Jahresenergie, Kosten und CO₂ einer Pumpe nach Lastprofil – Vergleich der Regelungsarten."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ingrechner.core.model import Calculator, ChoiceField, NumberField
from ingrechner.core.svg import ACCENT, INK, MUTED, Svg
from ingrechner.core.units import Q_, fmt_num

from ._pumpe import G

EIGEN = {"profil": ["eigen"]}
LASTEN = (1.0, 0.75, 0.5, 0.25)
EU_PROFIL = (6.0, 15.0, 35.0, 44.0)   # Zeitanteile in % (Referenzprofil Umwälzpumpen, EU 641/2009 bzw. EN 16297)

MODI = {
    "ungeregelt": "Ungeregelt (Drosselung)",
    "dpc": "Δp-konstant",
    "dpv": "Δp-variabel",
    "ideal": "Regelung auf Anlagenkennlinie",
}


@dataclass
class Punkt:
    x: float        # relativer Förderstrom
    H: float        # m
    n: float        # relative Drehzahl
    eta: float      # Gesamtwirkungsgrad
    P1: float       # W


def _eta_hyd(x_n: float, etaN: float) -> float:
    """Wirkungsgrad längs der Pumpenkennlinie (Bestpunkt im Auslegungspunkt): η = η_N·(2ξ − ξ²)."""
    return max(etaN * (2 * x_n - x_n**2), 0.05 * etaN)


def betriebspunkt(modus: str, x: float, VN: float, HN: float, H0: float, Hs: float, etaN: float,
                  rho: float) -> Punkt:
    """Betriebspunkt bei relativem Förderstrom x für die gegebene Regelungsart.

    Pumpenkennlinie (Nenndrehzahl): H(ξ) = H₀ − (H₀ − H_N)·ξ² mit ξ = V̇/V̇_N.
    Drehzahlgeregelt: H(ξ, n) = n²·H₀ − (H₀ − H_N)·ξ²  ⇒  n² = (H + (H₀ − H_N)·ξ²) / H₀.
    """
    if modus == "ungeregelt":
        H = H0 - (H0 - HN) * x**2
        n = 1.0
        eta = _eta_hyd(x, etaN)
    else:
        if modus == "dpc":
            H = HN
        elif modus == "dpv":
            H = HN * (0.5 + 0.5 * x)
        else:
            H = Hs + (HN - Hs) * x**2
        H = max(H, Hs + (HN - Hs) * x**2)      # mindestens die Anlagenkennlinie, sonst wird V̇ nicht erreicht
        n = min(1.0, ((H + (H0 - HN) * x**2) / H0) ** 0.5)
        # Antriebsverluste bei Teildrehzahl (EC-Motor/FU): vereinfacht 1 − 0,35·(1 − n)²
        eta = _eta_hyd(min(x / n, 1.6), etaN) * (1 - 0.35 * (1 - n) ** 2)
    P1 = rho * G * x * VN * H / eta
    return Punkt(x, H, n, eta, P1)


class Energiekosten(Calculator):
    id = "pu.energie"
    title = "Energiekosten & Regelung"
    category = "Pumpen"
    description = (
        "Jahresstromverbrauch, Kosten und CO₂-Emissionen einer Pumpe über ein Lastprofil (EU-Referenzprofil "
        "für Umwälzpumpen oder eigene Zeitanteile). Vergleich ungeregelt / Δp-konstant / Δp-variabel / "
        "Regelung auf der Anlagenkennlinie mit Einsparung und Amortisation."
    )
    norm = "Lastprofil 100/75/50/25 % mit 6/15/35/44 % Zeitanteil (VO (EG) 641/2009, DIN EN 16297); Affinitätsgesetze"
    keywords = ("energiekosten", "stromkosten", "regelung", "drehzahlregelung", "lastprofil", "eu-profil",
                "hocheffizienzpumpe", "delta p", "dp-c", "dp-v", "amortisation", "co2", "einsparung",
                "umwälzpumpe", "pumpentausch", "eei")

    fields = [
        NumberField("VN", "Förderstrom Auslegung (100 %)", "V̇_N", "m**3/hour", 3.0, min=0, decimals=3),
        NumberField("HN", "Förderhöhe Auslegung", "H_N", "m", 4.0, min=0, decimals=2),
        NumberField("H0", "Nullförderhöhe der Pumpe", "H₀", "m", 6.0, min=0, decimals=2,
                    tooltip="Förderhöhe bei V̇ = 0 und Nenndrehzahl (Kennlinie, Datenblatt)"),
        NumberField("Hs", "Statischer Anteil der Anlage", "H_stat", "m", 0, min=0, min_inclusive=True, decimals=2,
                    tooltip="Geschlossene Heiz-/Kältekreise 0; offene Systeme H_geo"),
        NumberField("eta", "Gesamtwirkungsgrad im Auslegungspunkt", "η_N", "percent", 45, min=1, max=95, decimals=1,
                    tooltip="Pumpe · Motor (· FU): Nassläufer-Hocheffizienzpumpen 30–55 %, Trockenläufer 55–75 %"),
        NumberField("rho", "Dichte des Mediums", "ρ", "kg/m**3", 983, min=0, decimals=1),
        ChoiceField("profil", "Lastprofil", [("eu", "EU-Referenzprofil (6/15/35/44 %)"),
                                             ("eigen", "Eigene Zeitanteile"),
                                             ("voll", "Dauerbetrieb 100 %")], "eu"),
        NumberField("a100", "Zeitanteil 100 % Last", "t₁₀₀", "percent", 6, min=0, max=100, min_inclusive=True,
                    decimals=1, visible_if=EIGEN),
        NumberField("a75", "Zeitanteil 75 % Last", "t₇₅", "percent", 15, min=0, max=100, min_inclusive=True,
                    decimals=1, visible_if=EIGEN),
        NumberField("a50", "Zeitanteil 50 % Last", "t₅₀", "percent", 35, min=0, max=100, min_inclusive=True,
                    decimals=1, visible_if=EIGEN),
        NumberField("a25", "Zeitanteil 25 % Last", "t₂₅", "percent", 44, min=0, max=100, min_inclusive=True,
                    decimals=1, visible_if=EIGEN),
        NumberField("t", "Betriebsstunden pro Jahr", "t_a", "hour", 5000, min=0, max=8760, decimals=0,
                    tooltip="Heizperiode ca. 5000 h; ganzjährige Kälte/Prozesse bis 8760 h"),
        ChoiceField("plan", "Geplante Regelungsart", [(k, v) for k, v in MODI.items() if k != "ungeregelt"], "dpv"),
        NumberField("preis", "Strompreis", "k_E", "EUR/(kW*h)", 0.30, min=0, decimals=3),
        NumberField("co2", "CO₂-Emissionsfaktor Strom", "f_CO₂", "g/(kW*h)", 380, min=0, min_inclusive=True,
                    decimals=0, tooltip="Strommix Deutschland ca. 350–400 g/kWh; Ökostrom-Vertrag nach Nachweis"),
        NumberField("invest", "Mehrkosten geregelte Pumpe", "I", "EUR", 0, min=0, min_inclusive=True, decimals=0,
                    tooltip="Für die Amortisation; 0 = ohne"),
    ]

    def _anteile(self, inp) -> tuple[tuple[float, ...], tuple[float, ...]]:
        if inp["profil"] == "voll":
            return (1.0,), (1.0,)
        if inp["profil"] == "eu":
            return LASTEN, tuple(a / 100 for a in EU_PROFIL)
        a = tuple(inp[k].to("percent").magnitude / 100 for k in ("a100", "a75", "a50", "a25"))
        if abs(sum(a) - 1) > 0.005:
            raise ValueError(f"Die Zeitanteile ergeben {fmt_num(sum(a) * 100, 1)} % – sie müssen 100 % ergeben.")
        return LASTEN, a

    def compute(self, inp) -> None:
        VN = inp["VN"].to("m**3/s").magnitude
        HN, H0, Hs = (inp[k].to("m").magnitude for k in ("HN", "H0", "Hs"))
        if H0 <= HN:
            raise ValueError("Die Nullförderhöhe muss über der Auslegungsförderhöhe liegen.")
        if Hs >= HN:
            raise ValueError("Der statische Anteil muss unter der Auslegungsförderhöhe liegen.")
        etaN = inp["eta"].to("percent").magnitude / 100
        rho = inp["rho"].to("kg/m**3").magnitude
        t = inp["t"].to("hour").magnitude
        preis = inp["preis"].to("EUR/(kW*h)").magnitude
        co2 = inp["co2"].to("g/(kW*h)").magnitude
        lasten, anteile = self._anteile(inp)

        self.step("Modell der Pumpenkennlinie", "H(ξ) = H₀ − (H₀ − H_N)·ξ²;  ξ = V̇/V̇_N",
                  f"H₀ = {fmt_num(H0, 2)} m, H_N = {fmt_num(HN, 2)} m",
                  "η = η_N·(2ξ − ξ²)  (Bestpunkt im Auslegungspunkt)")
        self.step("Lastprofil", "Zeitanteile je Förderstromstufe",
                  ", ".join(f"{fmt_num(x * 100, 0)} %: {fmt_num(a * 100, 1)} %" for x, a in zip(lasten, anteile)),
                  f"{fmt_num(t, 0)} h/a")

        energie: dict[str, float] = {}
        for modus, name in MODI.items():
            pts = [betriebspunkt(modus, x, VN, HN, H0, Hs, etaN, rho) for x in lasten]
            P_m = sum(a * p.P1 for a, p in zip(anteile, pts))
            energie[modus] = P_m / 1000 * t
            detail = "; ".join(f"{fmt_num(p.x * 100, 0)} %: H = {fmt_num(p.H, 2)} m, n = {fmt_num(p.n * 100, 0)} %, "
                               f"η = {fmt_num(p.eta * 100, 0)} %, P₁ = {fmt_num(p.P1, 0)} W" for p in pts)
            self.step(f"{name}", "P̄₁ = Σ tᵢ · ρ·g·V̇ᵢ·Hᵢ / ηᵢ;  E = P̄₁ · t_a", detail,
                      f"P̄₁ = {fmt_num(P_m, 0)} W → {fmt_num(energie[modus], 0)} kWh/a")

        plan = inp["plan"]
        E0, E1 = energie["ungeregelt"], energie[plan]
        self.result("E0", "Jahresenergie ungeregelt", "E₀", Q_(E0, "kW*h/year"), "kW*h/year", 0)
        for k in ("dpc", "dpv", "ideal"):
            self.result(f"E_{k}", f"Jahresenergie {MODI[k]}", f"E_{k}", Q_(energie[k], "kW*h/year"),
                        "kW*h/year", 0, highlight=k == plan)
        self.result("K0", "Energiekosten ungeregelt", "K₀", Q_(E0 * preis, "EUR/year"), "EUR/year", 0)
        self.result("K1", f"Energiekosten {MODI[plan]}", "K", Q_(E1 * preis, "EUR/year"), "EUR/year", 0,
                    highlight=True)
        dE = E0 - E1
        self.result("dK", "Einsparung gegenüber ungeregelt", "ΔK", Q_(dE * preis, "EUR/year"), "EUR/year", 0,
                    highlight=True)
        self.result("dE", "Einsparung Energie", "ΔE", Q_(dE / E0 * 100 if E0 else 0, "percent"), "percent", 0)
        self.result("CO2", "CO₂-Einsparung", "Δm_CO₂", Q_(dE * co2 / 1000, "kg/year"), "kg/year", 0)
        self.step("Einsparung", "ΔK = (E₀ − E) · k_E", f"({fmt_num(E0, 0)} − {fmt_num(E1, 0)}) kWh/a · "
                  f"{fmt_num(preis, 3)} €/kWh", f"{fmt_num(dE * preis, 0)} €/a")
        invest = inp["invest"].to("EUR").magnitude
        if invest > 0:
            if dE > 0:
                ta = invest / (dE * preis)
                self.step("Statische Amortisation", "t_A = I / ΔK", f"t_A = {fmt_num(invest, 0)} € / "
                          f"{fmt_num(dE * preis, 0)} €/a", f"{fmt_num(ta, 1)} a")
                self.result("ta", "Amortisationszeit", "t_A", Q_(ta, "year"), "year", 1, highlight=True)
            else:
                self.warn("Keine Einsparung – die Mehrkosten amortisieren sich nicht.")

        if inp["profil"] == "voll":
            self.info("Dauerbetrieb bei 100 % Last: Die Regelung spart nur durch das Wegfallen der Drosselung.")
        if plan == "dpc" and Hs == 0:
            self.info("In geschlossenen Heizkreisen mit Thermostatventilen ist Δp-variabel meist sparsamer als "
                      "Δp-konstant; Δp-konstant eignet sich für Fußbodenheizungen und Anlagen mit großem "
                      "Verbraucher-Druckverlust.")
        if Hs > 0.5 * HN and plan == "dpv":
            self.warn("Hoher statischer Anteil (offenes System): Die Δp-variabel-Kennlinie unterschreitet bei Teillast "
                      "die Anlagenkennlinie – gerechnet wurde mit der Anlagenkennlinie als Mindestwert. Regelung auf "
                      "Druck/Niveau bzw. Anlagenkennlinie vorsehen.")
        self.info("Vereinfachtes Modell: parabolische Kennlinie mit Bestpunkt im Auslegungspunkt, Antriebsverluste "
                  "bei Teildrehzahl pauschal. Für genaue Werte Herstellerkennlinien bzw. den EEI verwenden.")

    def plot(self, fig, raw, result) -> bool:
        if not result.ok:
            return False
        ax1, ax2 = fig.subplots(1, 2, gridspec_kw={"width_ratios": [1.15, 1]})
        VN, HN, H0, Hs = (float(raw[k]) for k in ("VN", "HN", "H0", "Hs"))
        xs = np.linspace(0, 1.15, 100)
        ax1.plot(xs * VN, H0 - (H0 - HN) * xs**2, color="#9aa7b4", lw=1.5, label="Pumpe n_N (ungeregelt)")
        ax1.plot(xs * VN, Hs + (HN - Hs) * xs**2, color="#1f6fb2", lw=1.5, ls="--", label="Anlage")
        xr = np.linspace(0.15, 1, 50)
        ax1.plot(xr * VN, np.full_like(xr, HN), color="#d68910", lw=2, label="Δp-konstant")
        ax1.plot(xr * VN, HN * (0.5 + 0.5 * xr), color="#27ae60", lw=2, label="Δp-variabel")
        for x in LASTEN:
            ax1.axvline(x * VN, color="#dce6f1", lw=0.8, zorder=0)
        ax1.plot([VN], [HN], "o", color="#c0392b", ms=6)
        ax1.set_xlabel("Förderstrom V̇  [m³/h]")
        ax1.set_ylabel("Förderhöhe H  [m]")
        ax1.set_title("Regelkennlinien")
        ax1.set_xlim(0, VN * 1.15)
        ax1.set_ylim(0, H0 * 1.1)
        ax1.grid(True, alpha=0.3)
        ax1.legend(fontsize=7, loc="lower left")

        names = ["ungeregelt", "Δp-c", "Δp-v", "Anlage"]
        vals = [result.value("E0"), result.value("E_dpc"), result.value("E_dpv"), result.value("E_ideal")]
        plan = raw.get("plan", "dpv")
        idx = {"dpc": 1, "dpv": 2, "ideal": 3}[plan]
        cols = ["#9aa7b4", "#d68910", "#27ae60", "#1f6fb2"]
        bars = ax2.bar(names, vals, color=cols, edgecolor=["#2b3a4a" if i == idx else c for i, c in enumerate(cols)],
                       linewidth=[2 if i == idx else 0 for i in range(4)])
        for b, v in zip(bars, vals):
            ax2.annotate(fmt_num(v, 0), (b.get_x() + b.get_width() / 2, v), ha="center", va="bottom", fontsize=8,
                         xytext=(0, 2), textcoords="offset points")
        ax2.set_ylabel("Jahresenergie  [kWh/a]")
        ax2.set_title("Energiebedarf je Regelungsart")
        ax2.set_ylim(0, max(vals) * 1.18)
        ax2.grid(True, axis="y", alpha=0.3)
        ax2.tick_params(axis="x", labelsize=8)
        return True

    def sketch_svg(self, raw) -> str:
        s = Svg()
        prof = raw.get("profil", "eu")
        if prof == "eigen":
            anteile = [float(raw.get(k, 0) or 0) for k in ("a100", "a75", "a50", "a25")]
        elif prof == "voll":
            anteile = [100, 0, 0, 0]
        else:
            anteile = list(EU_PROFIL)
        s.text(180, 22, "Lastprofil (Zeitanteile)", 12, INK, bold=True)
        x = 40
        tot = max(sum(anteile), 1e-9)
        for last, a in zip(LASTEN, anteile):
            w = 280 * a / tot
            if w <= 0:
                continue
            h = 140 * last
            s.rect(x, 190 - h, w, h, fill="#cfe0f1", stroke=ACCENT, width=1.2)
            if w > 26:
                s.text(x + w / 2, 182, f"{a:.0f} %", 10, INK)
                s.text(x + w / 2, 186 - h - 6, f"{last * 100:.0f} %", 10, MUTED)
            x += w
        s.line(40, 190, 320, 190, INK, 1.5).line(40, 190, 40, 40, INK, 1.5)
        s.text(320, 208, "Zeit", 11, MUTED, "end").text(34, 40, "Last", 10, MUTED, "end")
        return s.render()
