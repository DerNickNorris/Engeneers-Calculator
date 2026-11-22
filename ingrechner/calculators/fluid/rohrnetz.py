"""Rohrnetz – Strangberechnung: Teilstrecken in Reihe mit Dimensionierung und Druckverlust des Strangs."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from ingrechner.calculators.pumpen._pumpe import (G, medium, medium_felder, medium_hinweise, pumpe_svg, rauheit,
                                                  rauheit_felder, rohr_dp)
from ingrechner.core.model import Calculator, ChoiceField, Column, NumberField, TableField
from ingrechner.core.rohrdaten import KUPFER, PE100, STAHL
from ingrechner.core.svg import ACCENT, INK, MUTED, Svg
from ingrechner.core.units import Q_, fmt_num

VOL = {"last": ["volumen"]}
WAERME = {"last": ["waerme"]}

REIHEN = {
    "stahl": "Stahl DN (EN 10255 / EN 10220)",
    "kupfer": "Kupfer d_a (EN 1057)",
    "pe11": "PE 100 SDR 11 d_a (EN 12201)",
    "pe17": "PE 100 SDR 17 d_a (EN 12201)",
    "frei": "Innendurchmesser d_i direkt",
}
SPALTE = {"stahl": "DN", "kupfer": "d_a [mm]", "pe11": "d_a [mm]", "pe17": "d_a [mm]", "frei": "d_i [mm]"}


def reihe(art: str) -> list[tuple[float, str, float]]:
    """(Kennzahl, Bezeichnung, Innendurchmesser m) der Rohrreihe, aufsteigend."""
    if art == "stahl":
        return [(float(k.split()[1]), k, (d - 2 * s) / 1000) for k, (d, s) in STAHL.items()]
    if art == "kupfer":
        return [(d, k, (d - 2 * s) / 1000) for k, (d, s) in KUPFER.items()]
    if art in ("pe11", "pe17"):
        sdr = 11 if art == "pe11" else 17
        return [(float(d), f"PE {d}×{s:g}".replace(".", ","), (d - 2 * s) / 1000) for d, s in PE100[sdr].items()]
    return []


def nachschlagen(art: str, wert: float) -> tuple[str, float]:
    """Bezeichnung und Innendurchmesser zu einer Tabellenangabe (DN bzw. d_a oder d_i)."""
    if art == "frei":
        return f"d_i {fmt_num(wert, 1)} mm", wert / 1000
    for k, name, di in reihe(art):
        if abs(k - wert) < 0.06:
            return name, di
    werte = ", ".join(fmt_num(k, 1).replace(",0", "") for k, _, _ in reihe(art))
    raise ValueError(f"{REIHEN[art]}: {fmt_num(wert, 1).replace(',0', '')} gibt es nicht (verfügbar: {werte}).")


@dataclass
class Strecke:
    nr: int
    name: str
    auto: bool
    V: float        # m³/s
    di: float       # m
    L: float        # m
    zeta: float
    dp_k: float     # Pa
    v: float = 0.0
    re: float = 0.0
    lam: float = 0.0
    r: float = 0.0
    dp_r: float = 0.0
    dp_z: float = 0.0

    @property
    def dp(self) -> float:
        return self.dp_r + self.dp_z + self.dp_k


class Rohrnetz(Calculator):
    id = "fl.rohrnetz"
    title = "Rohrnetz – Strangberechnung"
    category = "Fluid / Thermo"
    description = (
        "Druckverlust des ungünstigsten Strangs aus Teilstrecken (Tabelle): Volumenstrom oder Wärmeleistung je "
        "Teilstrecke, Nennweite, Länge, Einzelwiderstände und Einbauten. Leere Nennweite = automatische "
        "Dimensionierung nach maximalem Druckgefälle und Geschwindigkeit. Ergebnis: Förderstrom und Förderhöhe "
        "für die Pumpenauslegung (verknüpfbar)."
    )
    norm = "Darcy-Weisbach/Colebrook je Teilstrecke; Δp_Strang = Σ(R·L + Σζ·ρv²/2 + Δp_E); VDI 2073 / DIN EN 12828"
    keywords = ("rohrnetz", "strang", "teilstrecke", "rohrnetzberechnung", "dimensionierung", "nennweite",
                "druckverlust", "ungünstigster strang", "hydraulik", "heizungsnetz", "fernwärme", "r-wert",
                "druckgefälle", "abwasser", "druckleitung")

    fields = [
        ChoiceField("last", "Belastung je Teilstrecke", [("waerme", "Leistung Q̇ und Spreizung"),
                                                        ("volumen", "Volumenstrom V̇")], "waerme"),
        NumberField("dT", "Temperaturspreizung", "Δθ", "K", 20, min=0, decimals=1, visible_if=WAERME),
        TableField("strecken_q", "Teilstrecken (vom Erzeuger zum ungünstigsten Verbraucher)", [
            Column("Q", "Q̇", "kW", decimals=2, min=0), Column("dn", "DN / d", "", optional=True, decimals=1, min=0),
            Column("L", "L", "m", decimals=1, min=0), Column("zeta", "Σζ", "", optional=True, decimals=2, min=0),
            Column("dpk", "Δp Einb.", "kPa", optional=True, decimals=2, min=0)],
            [[120, None, 25, 3.5, None], [80, None, 18, 2.0, None], [45, None, 22, 2.0, None],
             [20, None, 15, 4.0, 10.0]],
            min_rows=1, max_rows=40, visible_if=WAERME,
            tooltip="Je Zeile eine Teilstrecke mit konstanter Belastung. DN/d leer = automatisch dimensionieren. "
                    "Δp Einbauten z. B. Wärmetauscher, Zähler, Regelventil am Strangende."),
        TableField("strecken_v", "Teilstrecken (vom Erzeuger zum ungünstigsten Verbraucher)", [
            Column("V", "V̇", "m**3/hour", decimals=3, min=0), Column("dn", "DN / d", "", optional=True, decimals=1,
                                                                    min=0),
            Column("L", "L", "m", decimals=1, min=0), Column("zeta", "Σζ", "", optional=True, decimals=2, min=0),
            Column("dpk", "Δp Einb.", "kPa", optional=True, decimals=2, min=0)],
            [[5.0, None, 25, 3.5, None], [3.4, None, 18, 2.0, None], [1.9, None, 22, 2.0, None],
             [0.86, None, 15, 4.0, 10.0]],
            min_rows=1, max_rows=40, visible_if=VOL),
        ChoiceField("reihe", "Rohrreihe (Spalte DN / d)", list(REIHEN.items()), "stahl",
                    tooltip="Stahl: Nennweite DN eintragen (z. B. 50); Kupfer/PE: Außendurchmesser (z. B. 28, 110); "
                            "Innendurchmesser direkt: d_i in mm"),
        ChoiceField("laenge", "Längenangabe", [("gesamt", "Gesamtlänge (VL + RL)"),
                                               ("trasse", "Trassenlänge (× 2 für VL + RL)")], "trasse",
                    tooltip="Bei „Trassenlänge“ werden Länge und Σζ verdoppelt, Δp Einbauten nicht."),
        *medium_felder(70),
        *rauheit_felder(),
        NumberField("Rmax", "Max. Druckgefälle (Dimensionierung)", "R_max", "Pa/m", 150, min=1, decimals=0,
                    tooltip="Heizungsverteilung 100–200 Pa/m, Fernwärme 50–150 Pa/m, Abwasser-Druckleitung nach "
                            "Geschwindigkeit"),
        NumberField("vmax", "Max. Fließgeschwindigkeit", "v_max", "m/s", 1.5, min=0, decimals=2,
                    tooltip="Heizung im Gebäude 0,5–1,0 m/s, Verteilleitungen 1,0–2,0 m/s, Fernwärme bis 2–3 m/s"),
        NumberField("dp_e", "Δp Erzeuger / Übergabestation", "Δp_WE", "kPa", 20, min=0, min_inclusive=True,
                    decimals=2, tooltip="Druckverlust im Wärmeerzeuger bzw. der Übergabestation (Herstellerangabe)"),
        NumberField("res", "Sicherheitszuschlag", "z", "percent", 10, min=0, min_inclusive=True, max=50, decimals=0),
    ]

    # ---------------------------------------------------------------- Rechnung
    def _strecken(self, inp, rho: float, cp: float) -> list[Strecke]:
        waerme = inp["last"] == "waerme"
        rows = inp["strecken_q" if waerme else "strecken_v"]
        dT = inp["dT"].to("K").magnitude
        f = 2.0 if inp["laenge"] == "trasse" else 1.0
        out = []
        for i, row in enumerate(rows, 1):
            last, dn, L, zeta, dpk = (list(row) + [None] * 5)[:5]
            V = last * 1000 / (rho * cp * 1000 * dT) if waerme else last / 3600
            if dn is None:
                name, di, auto = "", 0.0, True
            else:
                name, di = nachschlagen(inp["reihe"], dn)
                auto = False
            out.append(Strecke(i, name, auto, V, di, (L or 0) * f, (zeta or 0) * f, (dpk or 0) * 1000))
        return out

    def _dimensionieren(self, s: Strecke, inp, rho, nu, k) -> None:
        Rmax = inp["Rmax"].to("Pa/m").magnitude
        vmax = inp["vmax"].to("m/s").magnitude
        kandidaten = reihe(inp["reihe"])
        if not kandidaten:          # freie Durchmesser: erforderlichen Innendurchmesser bestimmen (auf 1 mm)
            ok = lambda d: (lambda r: r.r <= Rmax and r.v <= vmax)(rohr_dp(s.V, d, 1.0, k, 0.0, rho, nu))  # noqa: E731
            lo, hi = 0.002, 3.0
            if not ok(hi):
                raise ValueError(f"Teilstrecke {s.nr}: kein Durchmesser bis 3 m erfüllt R_max/v_max.")
            for _ in range(60):
                mid = (lo + hi) / 2
                lo, hi = (lo, mid) if ok(mid) else (mid, hi)
            s.di = math.ceil(hi * 1000) / 1000
            s.name = f"d_i,erf {fmt_num(s.di * 1000, 0)} mm"
            return
        for _, name, di in kandidaten:
            r = rohr_dp(s.V, di, 1.0, k, 0.0, rho, nu)
            if r.r <= Rmax and r.v <= vmax:
                s.name, s.di = name, di
                return
        s.name, s.di = kandidaten[-1][1], kandidaten[-1][2]
        self.warn(f"Teilstrecke {s.nr}: auch die größte Nennweite ({s.name}) hält R_max/v_max nicht ein.")

    def compute(self, inp) -> None:
        med = medium(inp)
        rho, nu = med.rho, med.nu
        k = rauheit(inp)
        self.step("Stoffwerte", "ρ, ν, c_p", med.name,
                  f"ρ = {fmt_num(rho, 1)} kg/m³, ν = {fmt_num(nu * 1e6, 3)} mm²/s, c_p = {fmt_num(med.cp, 3)} kJ/(kg·K)")
        strecken = self._strecken(inp, rho, med.cp)
        if inp["last"] == "waerme":
            self.step("Volumenstrom je Teilstrecke", "V̇ = Q̇ / (ρ · c_p · Δθ)",
                      f"Δθ = {fmt_num(inp['dT'].to('K').magnitude, 1)} K",
                      "; ".join(f"TS {s.nr}: {fmt_num(s.V * 3600, 3)} m³/h" for s in strecken))
        if inp["laenge"] == "trasse":
            self.info("Längen und Σζ wurden für Vor- und Rücklauf verdoppelt.")

        auto = [s for s in strecken if s.auto]
        for s in auto:
            self._dimensionieren(s, inp, rho, nu, k)
        if auto:
            self.step("Dimensionierung", "kleinste Nennweite mit R ≤ R_max und v ≤ v_max",
                      f"R_max = {fmt_num(inp['Rmax'].to('Pa/m').magnitude, 0)} Pa/m, "
                      f"v_max = {fmt_num(inp['vmax'].to('m/s').magnitude, 2)} m/s",
                      "; ".join(f"TS {s.nr}: {s.name}" for s in auto))

        for s in strecken:
            r = rohr_dp(s.V, s.di, s.L, k, s.zeta, rho, nu)
            s.v, s.re, s.lam, s.r, s.dp_r, s.dp_z = r.v, r.re, r.lam, r.r, r.dp_r, r.dp_z
            self.step(f"Teilstrecke {s.nr} – {s.name}" + (" (auto)" if s.auto else ""),
                      "Δp = R·L + Σζ·ρv²/2 + Δp_E",
                      f"V̇ = {fmt_num(s.V * 3600, 3)} m³/h, d_i = {fmt_num(s.di * 1000, 1)} mm, "
                      f"v = {fmt_num(s.v, 2)} m/s, λ = {fmt_num(s.lam, 4)}, R = {fmt_num(s.r, 0)} Pa/m, "
                      f"L = {fmt_num(s.L, 1)} m, Σζ = {fmt_num(s.zeta, 2)}"
                      + (f", Δp_E = {fmt_num(s.dp_k / 1000, 2)} kPa" if s.dp_k else ""),
                      f"{fmt_num(s.dp / 1000, 2)} kPa")

        dp_netz = sum(s.dp for s in strecken)
        dp_e = inp["dp_e"].to("Pa").magnitude
        z = inp["res"].to("percent").magnitude / 100
        dp_ges = (dp_netz + dp_e) * (1 + z)
        H = dp_ges / (rho * G)
        V0 = max(s.V for s in strecken)
        self.step("Druckverlust des Strangs", "Δp = (Σ Δp_TS + Δp_WE) · (1 + z)",
                  f"Δp = ({fmt_num(dp_netz / 1000, 2)} + {fmt_num(dp_e / 1000, 2)}) kPa · {fmt_num(1 + z, 2)}",
                  f"{fmt_num(dp_ges / 1000, 2)} kPa")
        self.step("Förderhöhe", "H = Δp / (ρ · g)", f"H = {fmt_num(dp_ges, 0)} Pa / ({fmt_num(rho, 1)} · 9,81)",
                  f"{fmt_num(H, 2)} m")

        self.result("V", "Förderstrom (größte Teilstrecke)", "V̇_P", Q_(V0, "m**3/s"), "m**3/hour", 3, highlight=True)
        self.result("H", "Förderhöhe des Strangs", "H_P", Q_(H, "m"), "m", 2, highlight=True)
        self.result("dp", "Druckverlust des Strangs", "Δp", Q_(dp_ges, "Pa"), "kPa", 2, highlight=True)
        self.result("dp_netz", "davon Rohrnetz (ohne Zuschlag)", "Δp_Netz", Q_(dp_netz, "Pa"), "kPa", 2)
        self.result("L", "Leitungslänge gesamt", "ΣL", Q_(sum(s.L for s in strecken), "m"), "m", 1)
        self.result("vmax", "Größte Fließgeschwindigkeit", "v_max", Q_(max(s.v for s in strecken), "m/s"), "m/s", 2)
        self.result("Rmax", "Größtes Druckgefälle", "R_max", Q_(max(s.r for s in strecken), "Pa/m"), "Pa/m", 0)
        self.result("rho", "Dichte des Mediums", "ρ", Q_(rho, "kg/m**3"), "kg/m**3", 1)
        self.result("Phyd", "Hydraulische Leistung", "P_hyd", Q_(rho * G * V0 * H, "W"), "W", 0)

        Rmax = inp["Rmax"].to("Pa/m").magnitude
        vmax = inp["vmax"].to("m/s").magnitude
        zu_hoch = [s for s in strecken if not s.auto and (s.r > Rmax * 1.05 or s.v > vmax * 1.05)]
        if zu_hoch:
            self.warn("Grenzwerte überschritten in " + ", ".join(
                f"TS {s.nr} ({s.name}: v = {fmt_num(s.v, 2)} m/s, R = {fmt_num(s.r, 0)} Pa/m)" for s in zu_hoch)
                + " – größere Nennweite prüfen.")
        klein = [s for s in strecken if s.r < 0.15 * Rmax and s.v < 0.3]
        if klein:
            self.info("Sehr geringe Belastung (evtl. überdimensioniert) in TS " + ", ".join(str(s.nr) for s in klein)
                      + ".")
        if any(s.V > strecken[i - 1].V * 1.0001 for i, s in enumerate(strecken) if i):
            self.info("Der Volumenstrom steigt entlang des Strangs an – Reihenfolge der Teilstrecken prüfen "
                      "(üblich: vom Erzeuger zum Verbraucher abnehmend).")
        medium_hinweise(self, med)
        self.info("Der ungünstigste Strang bestimmt die Förderhöhe; Parallelstränge mit geringerem Druckverlust "
                  "über Strangregulierventile abgleichen (hydraulischer Abgleich).")

    # --------------------------------------------------------------- Diagramm
    def plot(self, fig, raw, result) -> bool:
        if not result.ok:
            return False
        try:
            inp = self._inputs(raw)
            med = medium(inp)
            strecken = self._strecken(inp, med.rho, med.cp)
            k = rauheit(inp)
            for s in strecken:
                if s.auto:
                    self._dimensionieren(s, inp, med.rho, med.nu, k)
                r = rohr_dp(s.V, s.di, s.L, k, s.zeta, med.rho, med.nu)
                s.v, s.r, s.dp_r, s.dp_z = r.v, r.r, r.dp_r, r.dp_z
        except (ValueError, KeyError):
            return False
        ax1, ax2 = fig.subplots(2, 1, sharex=True, gridspec_kw={"height_ratios": [1.6, 1]})
        x = np.arange(1, len(strecken) + 1)
        a = np.array([s.dp_r for s in strecken]) / 1000
        b = np.array([s.dp_z for s in strecken]) / 1000
        c = np.array([s.dp_k for s in strecken]) / 1000
        ax1.bar(x, a, color="#1f6fb2", label="Rohrreibung")
        ax1.bar(x, b, bottom=a, color="#e59866", label="Einzelwiderstände")
        ax1.bar(x, c, bottom=a + b, color="#8e44ad", label="Einbauten")
        cum = np.cumsum(a + b + c)
        ax1b = ax1.twinx()
        ax1b.plot(x, cum, "o-", color="#c0392b", lw=1.8, ms=4, label="kumuliert")
        ax1b.set_ylabel("Σ Δp  [kPa]", color="#c0392b")
        ax1b.set_ylim(0, max(cum) * 1.15)
        ax1.set_ylabel("Δp je TS  [kPa]")
        ax1.set_title("Druckverlust entlang des Strangs")
        ax1.legend(loc="upper left", fontsize=7)
        ax1.grid(True, axis="y", alpha=0.3)
        Rmax = float(raw["Rmax"])
        ax2.bar(x, [s.r for s in strecken], color=["#c0392b" if s.r > Rmax * 1.05 else "#27ae60" for s in strecken])
        ax2.axhline(Rmax, color="#2b3a4a", ls="--", lw=1)
        for xi, s in zip(x, strecken):
            ax2.annotate(s.name.replace("DN ", ""), (xi, s.r), ha="center", va="bottom", fontsize=7,
                         xytext=(0, 2), textcoords="offset points")
        ax2.set_ylabel("R  [Pa/m]")
        ax2.set_xlabel("Teilstrecke")
        ax2.set_xticks(x)
        ax2.set_ylim(0, max(max(s.r for s in strecken), Rmax) * 1.25)
        ax2.grid(True, axis="y", alpha=0.3)
        return True

    def _inputs(self, raw):
        inp = {}
        merged = self.defaults() | dict(raw)
        for f in self.fields:
            v = merged[f.key]
            if isinstance(f, TableField):
                rows, msg = f.parse(v)
                if msg and self.is_visible(f, merged):
                    raise ValueError(msg)
                inp[f.key] = rows
            elif isinstance(f, NumberField):
                inp[f.key] = Q_(float(v), f.unit) if f.unit else float(v)
            else:
                inp[f.key] = v
        return inp

    def sketch_svg(self, raw) -> str:
        s = Svg()
        s.rect(14, 80, 40, 70, fill="#f5d7d3").text(34, 120, "WE", 11, INK, bold=True)
        s.line(54, 95, 340, 95, "#c0392b", 3).line(54, 135, 340, 135, ACCENT, 3)
        pumpe_svg(s, 80, 95, 12)
        xs = [110, 180, 250, 320]
        for i, x in enumerate(xs):
            s.line(x, 95, x, 60, "#c0392b", 2).line(x + 8, 135, x + 8, 60, ACCENT, 2)
            s.rect(x - 6, 38, 22, 22, fill="#eef3f8")
        for i, (x0, x1) in enumerate(zip([54] + xs[:-1], xs), 1):
            s.text((x0 + x1) / 2 + 10, 121, f"TS {i}", 10, INK, bold=True)
        s.text(345, 28, "ungünstigster Verbraucher", 9, MUTED, "end")
        s.text(180, 175, "Q̇ bzw. V̇ nimmt je Abzweig ab", 11, MUTED)
        s.text(180, 200, "Strang: Δp = Σ (R·L + Σζ·ρv²/2 + Einbauten)", 11, INK)
        return s.render()
