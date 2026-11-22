"""Abwasser-Druckleitung: Mindestgeschwindigkeit, Förderhöhe, Leitungsinhalt und Aufenthaltszeit."""

from __future__ import annotations

import math

import numpy as np

from ingrechner.calculators.pumpen._pumpe import G, medium, medium_felder, medium_hinweise, pumpe_svg, rohr_dp
from ingrechner.core.model import Calculator, NumberField
from ingrechner.core.svg import ACCENT, INK, MUTED, Svg
from ingrechner.core.units import Q_, fmt_num

from ._aw import rohr_felder, rohr_geometrie


class Druckleitung(Calculator):
    id = "aw.druckleitung"
    title = "Abwasser-Druckleitung"
    category = "Abwasser / Klärwerk"
    description = (
        "Fließgeschwindigkeit, Druckverlust und Förderhöhe einer Abwasser- oder Schlammdruckleitung mit Prüfung "
        "der Mindestgeschwindigkeit gegen Ablagerungen; Leitungsinhalt, Aufenthaltszeit (Faulung/H₂S) und "
        "Pumpenlaufzeit für einen vollständigen Austausch des Leitungsinhalts."
    )
    norm = "Darcy-Weisbach/Colebrook mit betrieblicher Rauheit k_b; v_min ≈ 0,7 m/s; vgl. DWA-A 134, DWA-A 110"
    keywords = ("druckleitung", "abwasserdruckleitung", "schlammleitung", "mindestgeschwindigkeit", "ablagerung",
                "aufenthaltszeit", "h2s", "schwefelwasserstoff", "pumpwerk", "abwasser", "pe 100", "förderhöhe")

    fields = [
        NumberField("QP", "Förderstrom (Pumpe in Betrieb)", "Q_P", "liter/second", 20, min=0, decimals=2),
        NumberField("Qd", "Mittlerer Tageszufluss (optional)", "Q_d", "m**3/day", 400, min=0, min_inclusive=True,
                    decimals=1, tooltip="Für die mittlere Aufenthaltszeit des Abwassers in der Leitung; 0 = ohne"),
        *medium_felder(12, default="abwasser_zulauf"),
        *rohr_felder("pe11:160"),
        NumberField("L", "Leitungslänge", "L", "m", 850, min=0, decimals=1),
        NumberField("kb", "Betriebliche Rauheit", "k_b", "mm", 0.25, min=0, min_inclusive=True, decimals=3,
                    tooltip="Abwasserdruckleitungen: k_b = 0,25 mm (enthält Krümmer, Muffen, Ablagerungen; "
                            "vgl. DWA-A 110); zusätzliche Σζ nur für besondere Einbauten"),
        NumberField("zeta", "Summe Einzelwiderstände (zusätzlich)", "Σζ", "", 5, min=0, min_inclusive=True,
                    decimals=2, tooltip="Rückschlagklappe, Schieber, Auslauf (ζ = 1), Belüftungs-/Spülanschlüsse"),
        NumberField("hgeo", "Geodätische Förderhöhe", "H_geo", "m", 8, decimals=2,
                    tooltip="Höhe Hochpunkt bzw. Auslauf über dem Ausschaltpegel im Pumpensumpf"),
        NumberField("vmin", "Mindestgeschwindigkeit", "v_min", "m/s", 0.7, min=0, decimals=2,
                    tooltip="Üblich 0,7 m/s (Abwasser); Schlamm und Sand eher 1,0 m/s"),
    ]

    def compute(self, inp) -> None:
        med = medium(inp)
        rho, nu = med.rho, med.nu
        name, di, da, s = rohr_geometrie(inp)
        Q = inp["QP"].to("m**3/s").magnitude
        L = inp["L"].to("m").magnitude
        k = inp["kb"].to("m").magnitude
        r = rohr_dp(Q, di, L, k, float(inp["zeta"]), rho, nu)
        self.step("Stoffwerte", "ρ, ν", med.name, f"ρ = {fmt_num(rho, 1)} kg/m³, ν = {fmt_num(nu * 1e6, 3)} mm²/s")
        self.step("Fließgeschwindigkeit", "v = 4 · Q_P / (π · d_i²)",
                  f"{name}: d_i = {fmt_num(di * 1000, 1)} mm", f"v = {fmt_num(r.v, 2)} m/s, Re = {fmt_num(r.re, 0)}")
        self.step("Reibungsverlust", "h_R = λ · L/d_i · v²/(2g);  λ nach Colebrook mit k_b",
                  f"λ = {fmt_num(r.lam, 4)}, L = {fmt_num(L, 1)} m", f"{fmt_num(r.dp_r / (rho * G), 2)} m")
        hz = r.dp_z / (rho * G)
        hgeo = inp["hgeo"].to("m").magnitude
        H = hgeo + (r.dp_r + r.dp_z) / (rho * G)
        self.step("Förderhöhe", "H = H_geo + h_R + Σζ · v²/(2g)",
                  f"H = {fmt_num(hgeo, 2)} + {fmt_num(r.dp_r / (rho * G), 2)} + {fmt_num(hz, 2)} m", f"{fmt_num(H, 2)} m")
        VL = math.pi * di**2 / 4 * L
        self.step("Leitungsinhalt", "V_L = π · d_i² / 4 · L", f"V_L = π · {fmt_num(di, 4)}² / 4 · {fmt_num(L, 1)}",
                  f"{fmt_num(VL, 2)} m³")

        self.result("v", "Fließgeschwindigkeit", "v", Q_(r.v, "m/s"), "m/s", 2, highlight=True)
        self.result("H", "Förderhöhe", "H", Q_(H, "m"), "m", 2, highlight=True)
        self.result("V", "Förderstrom", "Q_P", Q_(Q, "m**3/s"), "m**3/hour", 2)
        self.result("Hstat", "davon geodätisch", "H_geo", Q_(hgeo, "m"), "m", 2)
        self.result("hv", "Verlusthöhe", "h_v", Q_(H - hgeo, "m"), "m", 2)
        self.result("J", "Energieliniengefälle", "J", Q_(r.dp_r / (rho * G) / L * 1000 if L else 0, "m/km"),
                    "m/km", 2)
        self.result("p", "Förderdruck an der Pumpe", "p", Q_(H * rho * G, "Pa"), "bar", 2)
        self.result("VL", "Leitungsinhalt", "V_L", Q_(VL, "m**3"), "m**3", 2)
        self.result("taus", "Pumpenlaufzeit für Austausch", "t_aus", Q_(VL / Q, "s"), "minute", 1)
        self.result("di", "Innendurchmesser", "d_i", Q_(di * 1000, "mm"), "mm", 1)
        self.result("da", "Außendurchmesser", "d_a", Q_(da * 1000, "mm"), "mm", 1)
        self.result("s", "Wanddicke", "s", Q_(s * 1000, "mm"), "mm", 1)
        self.result("rho", "Dichte des Mediums", "ρ", Q_(rho, "kg/m**3"), "kg/m**3", 1)

        Qd = inp["Qd"].to("m**3/s").magnitude
        if Qd > 0:
            t = VL / Qd
            self.step("Mittlere Aufenthaltszeit", "t_A = V_L / Q_d", f"t_A = {fmt_num(VL, 2)} m³ / "
                      f"{fmt_num(Qd * 86400, 1)} m³/d", f"{fmt_num(t / 3600, 2)} h")
            self.result("tA", "Mittlere Aufenthaltszeit", "t_A", Q_(t, "s"), "hour", 2, highlight=True)
            if t > 2 * 3600:
                self.warn(f"Aufenthaltszeit {fmt_num(t / 3600, 1)} h > 2 h: anaerobe Verhältnisse, H₂S-Bildung, "
                          "Geruch und Betonkorrosion am Übergabeschacht möglich – Spülung, Belüftung oder "
                          "Dosierung prüfen.")
        vmin = inp["vmin"].to("m/s").magnitude
        if r.v < vmin:
            self.warn(f"v = {fmt_num(r.v, 2)} m/s < v_min = {fmt_num(vmin, 2)} m/s – Ablagerungsgefahr. Kleinere "
                      "Nennweite oder höheren Förderstrom wählen bzw. regelmäßige Spülung vorsehen.")
        elif r.v > 2.5:
            self.warn(f"v = {fmt_num(r.v, 2)} m/s hoch – große Verlusthöhe und Druckstoßgefahr (Rechner Druckstoß).")
        else:
            self.info(f"Mindestgeschwindigkeit eingehalten (v = {fmt_num(r.v, 2)} m/s ≥ {fmt_num(vmin, 2)} m/s).")
        if di < 0.08:
            self.warn("Innendurchmesser < 80 mm – Verstopfungsgefahr bei Rohabwasser (Ausnahme: Druckentwässerung "
                      "mit Schneidradpumpen).")
        medium_hinweise(self, med)
        self.info("Hoch- und Tiefpunkte: Be-/Entlüftung und Entleerung vorsehen; Druckstoß beim Pumpenausfall "
                  "prüfen (Rechner „Druckstoß“).")

    def plot(self, fig, raw, result) -> bool:
        if not result.ok:
            return False
        merged = self.defaults() | raw
        _, di, _, _ = rohr_geometrie({"rohr": merged["rohr"], "da": Q_(float(merged["da"]), "mm"),
                                      "s": Q_(float(merged["s"]), "mm")})
        inp = {"medium": merged["medium"], "theta": Q_(float(merged["theta"]), "degC"),
               "rho": Q_(float(merged["rho"]), "kg/m**3"), "nu": Q_(float(merged["nu"]), "mm**2/s")}
        med = medium(inp)
        QP = float(merged["QP"])
        qs = np.linspace(QP * 0.05, QP * 1.8, 100)
        hs = [float(merged["hgeo"]) + (lambda r: (r.dp_r + r.dp_z) / (med.rho * G))(
            rohr_dp(q / 1000, di, float(merged["L"]), float(merged["kb"]) / 1000, float(merged["zeta"]), med.rho,
                    med.nu)) for q in qs]
        ax = fig.subplots()
        ax.plot(qs, hs, color="#1f6fb2", lw=2, label="Anlagenkennlinie")
        q_min = float(merged["vmin"]) * math.pi * di**2 / 4 * 1000
        ax.axvspan(0, q_min, color="#f5d7d3", alpha=0.5, label=f"v < v_min ({fmt_num(q_min, 1)} l/s)")
        ax.plot([QP], [result.value("H")], "o", color="#c0392b", label="Betriebspunkt")
        ax.set_xlim(0, qs[-1])
        ax.set_xlabel("Förderstrom Q  [l/s]")
        ax.set_ylabel("Förderhöhe H  [m]")
        ax.set_title("Anlagenkennlinie der Druckleitung")
        ax.grid(True, alpha=0.3)
        ax.legend(loc="upper left", fontsize=8)
        return True

    def sketch_svg(self, raw) -> str:
        s = Svg()
        s.rect(20, 130, 70, 70, fill="#ffffff").rect(21, 165, 68, 34, fill="#cfe0f1", stroke="#cfe0f1", width=0)
        pumpe_svg(s, 55, 185, 11)
        s.line(66, 185, 110, 185, ACCENT, 3).line(110, 185, 110, 160, ACCENT, 3)
        pts = [(110, 160), (180, 120), (240, 135), (300, 60)]
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            s.line(x1, y1, x2, y2, ACCENT, 3)
        s.rect(300, 40, 50, 40, fill="#eef3f8").text(325, 64, "Ü-S", 10, INK, bold=True)
        s.line(20, 165, 350, 165, MUTED, 0.8, "4 3").line(240, 60, 350, 60, MUTED, 0.8, "4 3")
        s.dim_v(355, 60, 165, "")
        s.text(345, 118, "H_geo", 11, INK, "end", True)
        s.text(185, 108, "Länge L, Rauheit k", 11, MUTED)
        s.text(160, 210, "Pumpensumpf → Übergabeschacht", 11, MUTED)
        return s.render()
