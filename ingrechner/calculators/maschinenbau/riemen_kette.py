"""Keilriemen- und Rollenkettentrieb: Geometrie, Riemenzahl bzw. Kettenwahl, Wellenbelastung."""

from __future__ import annotations

import math

from ingrechner.core.model import Calculator, ChoiceField, NumberField
from ingrechner.core.svg import ACCENT, INK, MUTED, Svg
from ingrechner.core.units import Q_, fmt_num

# Schmalkeilriemen DIN 7753-1 / ISO 4184: kleinster Richtdurchmesser (mm), max. Riemengeschwindigkeit (m/s)
KEILRIEMEN = {"SPZ": 63, "SPA": 90, "SPB": 140, "SPC": 224}
RICHTLAENGEN = [630, 710, 800, 900, 1000, 1120, 1250, 1400, 1600, 1800, 2000, 2240, 2500, 2800, 3150, 3550, 4000,
                4500, 5000, 5600, 6300, 7100, 8000, 9000, 10000, 11200, 12500]

# Rollenketten DIN 8187 / ISO 606 (B-Reihe), Einfachkette: Teilung p (mm), Bruchkraft F_B (kN), Masse q (kg/m)
KETTEN = {"06B": (9.525, 9.0, 0.41), "08B": (12.7, 18.0, 0.70), "10B": (15.875, 22.4, 0.95),
          "12B": (19.05, 29.0, 1.25), "16B": (25.4, 60.0, 2.70), "20B": (31.75, 95.0, 3.60),
          "24B": (38.1, 160.0, 6.70), "28B": (44.45, 200.0, 8.30), "32B": (50.8, 250.0, 10.50)}
STRANG = {"1": ("Einfachkette", 1.0), "2": ("Zweifachkette (Duplex)", 1.7), "3": ("Dreifachkette (Triplex)", 2.5)}


def winkelfaktor(beta_deg: float) -> float:
    """Winkelfaktor c₁ für den Umschlingungswinkel (Näherung der Katalogtabellen)."""
    return 1.25 * (1 - 5 ** (-beta_deg / 180))


class Keilriementrieb(Calculator):
    id = "mb.keilriemen"
    title = "Keilriementrieb"
    category = "Maschinenbau"
    description = (
        "Schmalkeilriementrieb (SPZ/SPA/SPB/SPC): Scheibendurchmesser aus der Übersetzung, Riemenlänge mit "
        "Normlänge und tatsächlichem Achsabstand, Umschlingungswinkel, Riemengeschwindigkeit, erforderliche "
        "Riemenanzahl mit Winkel-, Längen- und Betriebsfaktor sowie Wellenbelastung."
    )
    norm = "L = 2a + π/2·(d₁+d₂) + (d₂−d₁)²/(4a); z = P·c₂/(P_N·c₁·c₃); DIN 7753 / ISO 4184, Leistungswerte aus Herstellertabellen"
    keywords = ("keilriemen", "riemen", "riementrieb", "spz", "spa", "spb", "spc", "riemenscheibe", "achsabstand",
                "umschlingungswinkel", "riemenlänge", "antrieb")

    fields = [
        NumberField("P", "Zu übertragende Leistung", "P", "kW", 7.5, min=0, decimals=2),
        NumberField("n1", "Drehzahl kleine Scheibe", "n₁", "1/minute", 1450, min=0, decimals=0),
        ChoiceField("profil", "Riemenprofil", [(k, f"{k} (d_min = {v} mm)") for k, v in KEILRIEMEN.items()], "SPA"),
        NumberField("d1", "Richtdurchmesser kleine Scheibe", "d_d1", "mm", 125, min=0, decimals=1),
        NumberField("d2", "Richtdurchmesser große Scheibe", "d_d2", "mm", 315, min=0, decimals=1),
        NumberField("a0", "Achsabstand (Entwurf)", "a₀", "mm", 500, min=0, decimals=0,
                    tooltip="Richtwert 0,7·(d₁+d₂) … 2·(d₁+d₂); wird an die Normlänge angepasst"),
        NumberField("PN", "Nennleistung je Riemen (Katalog)", "P_N", "kW", 3.5, min=0, decimals=2,
                    tooltip="Herstellertabelle für Profil, d_d1, n₁ und Übersetzung (inkl. Übersetzungszuschlag)"),
        NumberField("c2", "Betriebsfaktor", "c₂", "", 1.2, min=0.8, max=3, decimals=2,
                    tooltip="Leichter Betrieb 1,0–1,1, mittel 1,1–1,3, schwer 1,3–1,6 (+0,1 je höherer Laufzeitklasse)"),
        NumberField("c3", "Längenfaktor", "c₃", "", 1.0, min=0.7, max=1.3, decimals=2,
                    tooltip="Aus der Herstellertabelle für die gewählte Riemenlänge"),
    ]

    def compute(self, inp) -> None:
        d1, d2 = inp["d1"].to("mm").magnitude, inp["d2"].to("mm").magnitude
        if d2 < d1:
            raise ValueError("Die große Scheibe muss mindestens so groß wie die kleine sein.")
        P = inp["P"].to("kW").magnitude
        n1 = inp["n1"].to("1/minute").magnitude
        a0 = inp["a0"].to("mm").magnitude
        L0 = 2 * a0 + math.pi / 2 * (d1 + d2) + (d2 - d1) ** 2 / (4 * a0)
        L = next((x for x in RICHTLAENGEN if x >= L0), RICHTLAENGEN[-1])
        pp = L / 4 - math.pi * (d1 + d2) / 8
        a = pp + math.sqrt(pp**2 - (d2 - d1) ** 2 / 8)
        beta = 2 * math.degrees(math.acos((d2 - d1) / (2 * a)))
        v = math.pi * d1 / 1000 * n1 / 60
        c1 = winkelfaktor(beta)
        c2, c3 = float(inp["c2"]), float(inp["c3"])
        PN = inp["PN"].to("kW").magnitude
        z_erf = P * c2 / (PN * c1 * c3)
        z = math.ceil(z_erf - 1e-9)
        Ft = P * 1000 / v
        FW = 1.75 * Ft
        self.step("Übersetzung", "i = d₂/d₁", f"i = {fmt_num(d2, 1)} / {fmt_num(d1, 1)}", fmt_num(d2 / d1, 3))
        self.step("Riemenlänge (Entwurf)", "L₀ = 2a₀ + π/2·(d₁+d₂) + (d₂−d₁)²/(4a₀)", f"a₀ = {fmt_num(a0, 0)} mm",
                  f"L₀ = {fmt_num(L0, 0)} mm → Normlänge L = {L} mm")
        self.step("Achsabstand", "a = p + √(p² − q);  p = L/4 − π(d₁+d₂)/8, q = (d₂−d₁)²/8", "",
                  f"a = {fmt_num(a, 1)} mm")
        self.step("Umschlingungswinkel", "β₁ = 2·arccos((d₂−d₁)/(2a))", "",
                  f"β₁ = {fmt_num(beta, 1)}° → c₁ = {fmt_num(c1, 3)}")
        self.step("Riemenanzahl", "z = P·c₂ / (P_N·c₁·c₃)",
                  f"z = {fmt_num(P, 2)}·{fmt_num(c2, 2)} / ({fmt_num(PN, 2)}·{fmt_num(c1, 3)}·{fmt_num(c3, 2)})",
                  f"{fmt_num(z_erf, 2)} → {z} Riemen")
        self.result("z", "Anzahl Riemen", "z", Q_(z, ""), "", 0, highlight=True)
        self.result("L", "Riemen-Richtlänge (Norm)", "L_d", Q_(L, "mm"), "mm", 0, highlight=True)
        self.result("a", "Achsabstand", "a", Q_(a, "mm"), "mm", 1, highlight=True)
        self.result("beta", "Umschlingungswinkel", "β₁", Q_(beta, "degree"), "degree", 1)
        self.result("v", "Riemengeschwindigkeit", "v", Q_(v, "m/s"), "m/s", 2)
        self.result("n2", "Drehzahl große Scheibe", "n₂", Q_(n1 * d1 / d2, "1/minute"), "1/minute", 1)
        self.result("Ft", "Umfangskraft", "F_t", Q_(Ft, "N"), "N", 0)
        self.result("FW", "Wellenbelastung (Richtwert)", "F_W", Q_(FW, "N"), "N", 0, highlight=True)
        dmin = KEILRIEMEN[inp["profil"]]
        if d1 < dmin:
            self.warn(f"d_d1 = {fmt_num(d1, 0)} mm < Mindestdurchmesser {dmin} mm für {inp['profil']} – Biegewechsel, "
                      "Lebensdauer sinkt.")
        if v > 42:
            self.warn(f"Riemengeschwindigkeit {fmt_num(v, 1)} m/s > 42 m/s – Scheiben dynamisch auswuchten, "
                      "Herstellerfreigabe.")
        elif v < 5:
            self.info("Riemengeschwindigkeit < 5 m/s – große Umfangskräfte; Zahnriemen oder Kette prüfen.")
        if beta < 120:
            self.warn(f"Umschlingungswinkel {fmt_num(beta, 0)}° < 120° – Achsabstand vergrößern.")
        if not 0.7 * (d1 + d2) <= a <= 2 * (d1 + d2):
            self.info("Achsabstand außerhalb 0,7…2·(d₁+d₂).")
        if z > 6:
            self.info("Mehr als 6 Riemen – größeres Profil oder größere Scheiben wählen.")
        self.info("Wellenbelastung als Richtwert (Vorspannung nach Herstellerangabe, z. B. Durchbiegungsmethode).")

    def sketch_svg(self, raw) -> str:
        s = Svg()
        try:
            d1, d2 = float(raw.get("d1", 125)), float(raw.get("d2", 315))
        except (TypeError, ValueError):
            d1, d2 = 125, 315
        r2 = 70
        r1 = max(12, r2 * d1 / max(d2, 1))
        x1, x2, y = 80, 270, 110
        s.circle(x1, y, r1, fill="#f5d7d3").circle(x2, y, r2, fill="#dce6f1")
        s.line(x1, y - r1, x2, y - r2, INK, 3).line(x1, y + r1, x2, y + r2, INK, 3)
        s.text(x1, y + 4, "d₁", 11, INK, italic=True).text(x2, y + 4, "d₂", 12, INK, italic=True)
        s.dim_h(x1, x2, 205, "a")
        return s.render()


class Kettentrieb(Calculator):
    id = "mb.kette"
    title = "Rollenkettentrieb"
    category = "Maschinenbau"
    description = (
        "Rollenkettentrieb nach DIN 8187 (B-Reihe): Teilkreise, Kettengeschwindigkeit, Kettenzug mit "
        "Betriebsfaktor und Fliehkraft, statische Bruchsicherheit, Gliederzahl (gerade) mit tatsächlichem "
        "Achsabstand, Polygoneffekt und Wellenbelastung."
    )
    norm = "d₀ = p/sin(180°/z); X = 2a/p + (z₁+z₂)/2 + ((z₂−z₁)/2π)²·p/a; S = F_B/(F_t·f_B + q·v²); DIN 8187 / ISO 606"
    keywords = ("kette", "rollenkette", "kettentrieb", "kettenrad", "din 8187", "iso 606", "gliederzahl", "teilung",
                "achsabstand", "bruchkraft", "antrieb", "polygoneffekt")

    fields = [
        NumberField("P", "Zu übertragende Leistung", "P", "kW", 4, min=0, decimals=2),
        NumberField("n1", "Drehzahl kleines Kettenrad", "n₁", "1/minute", 200, min=0, decimals=1),
        NumberField("z1", "Zähnezahl kleines Rad", "z₁", "", 19, min=9, max=150, min_inclusive=True, decimals=0,
                    tooltip="Bevorzugt ungerade, ≥ 17 (ruhiger Lauf, kleiner Polygoneffekt)"),
        NumberField("z2", "Zähnezahl großes Rad", "z₂", "", 57, min=9, max=200, min_inclusive=True, decimals=0),
        ChoiceField("kette", "Kette", [(k, f"{k} (p = {str(v[0]).replace('.', ',')} mm, Bruchkraft {v[1]:g} kN)")
                                       for k, v in KETTEN.items()], "16B"),
        ChoiceField("strang", "Ausführung", [(k, v[0]) for k, v in STRANG.items()], "1"),
        NumberField("a0", "Achsabstand (Entwurf)", "a₀", "mm", 800, min=0, decimals=0,
                    tooltip="Richtwert 30…50·p"),
        NumberField("fB", "Betriebsfaktor", "f_B", "", 1.3, min=0.8, max=3, decimals=2,
                    tooltip="Gleichförmig 1,0, mäßige Stöße 1,3, starke Stöße 1,7–2,0"),
        NumberField("Smin", "Mindest-Bruchsicherheit", "S_min", "", 7, min=1, max=20, decimals=1,
                    tooltip="Statischer Wert gegen Bruchkraft; Richtwert ≥ 7 (Dauerfestigkeit über Leistungsdiagramm "
                            "des Herstellers prüfen)"),
    ]

    def compute(self, inp) -> None:
        p, FB_kN, q = KETTEN[inp["kette"]]
        _, k_strang = STRANG[inp["strang"]]
        FB = FB_kN * 1000 * k_strang
        q *= int(inp["strang"])
        z1, z2 = int(round(inp["z1"])), int(round(inp["z2"]))
        if z2 < z1:
            raise ValueError("Das große Kettenrad muss mindestens so viele Zähne haben wie das kleine.")
        P = inp["P"].to("W").magnitude
        n1 = inp["n1"].to("1/minute").magnitude
        d01, d02 = p / math.sin(math.pi / z1), p / math.sin(math.pi / z2)
        v = z1 * p * n1 / 60000
        Ft = P / v
        fB = float(inp["fB"])
        Ff = q * v**2
        F = Ft * fB + Ff
        S = FB / F
        a0 = inp["a0"].to("mm").magnitude
        X0 = 2 * a0 / p + (z1 + z2) / 2 + ((z2 - z1) / (2 * math.pi)) ** 2 * p / a0
        X = math.ceil(X0)
        X += X % 2
        m = X - (z1 + z2) / 2
        a = p / 4 * (m + math.sqrt(m**2 - 8 * ((z2 - z1) / (2 * math.pi)) ** 2))
        poly = (1 - math.cos(math.pi / z1)) * 100
        self.step("Teilkreise", "d₀ = p / sin(180°/z)", f"p = {fmt_num(p, 3)} mm",
                  f"d₀₁ = {fmt_num(d01, 1)} mm, d₀₂ = {fmt_num(d02, 1)} mm")
        self.step("Kettengeschwindigkeit", "v = z₁·p·n₁/60 000", "", f"{fmt_num(v, 2)} m/s")
        self.step("Kettenzug", "F = F_t·f_B + q·v²;  F_t = P/v",
                  f"F_t = {fmt_num(Ft, 0)} N, q·v² = {fmt_num(Ff, 1)} N", f"F = {fmt_num(F, 0)} N")
        self.step("Bruchsicherheit", "S = F_B / F", f"F_B = {fmt_num(FB / 1000, 1)} kN ({STRANG[inp['strang']][0]})",
                  f"S = {fmt_num(S, 2)}")
        self.step("Gliederzahl", "X₀ = 2a₀/p + (z₁+z₂)/2 + ((z₂−z₁)/2π)²·p/a₀  → gerade aufrunden",
                  f"X₀ = {fmt_num(X0, 2)}", f"X = {X} Glieder, a = {fmt_num(a, 1)} mm")
        self.result("S", "Statische Bruchsicherheit", "S", Q_(S, ""), "", 2, highlight=True)
        self.result("X", "Gliederzahl", "X", Q_(X, ""), "", 0, highlight=True)
        self.result("a", "Achsabstand", "a", Q_(a, "mm"), "mm", 1, highlight=True)
        self.result("v", "Kettengeschwindigkeit", "v", Q_(v, "m/s"), "m/s", 2)
        self.result("Ft", "Umfangskraft", "F_t", Q_(Ft, "N"), "N", 0)
        self.result("d01", "Teilkreis kleines Rad", "d₀₁", Q_(d01, "mm"), "mm", 1)
        self.result("d02", "Teilkreis großes Rad", "d₀₂", Q_(d02, "mm"), "mm", 1)
        self.result("i", "Übersetzung", "i", Q_(z2 / z1, ""), "", 3)
        self.result("FW", "Wellenbelastung (Richtwert)", "F_W", Q_(1.15 * Ft * fB, "N"), "N", 0)
        self.result("poly", "Geschwindigkeitsschwankung (Polygoneffekt)", "Δv/v", Q_(poly, "percent"), "percent", 2)
        if S < float(inp["Smin"]):
            self.warn(f"Bruchsicherheit {fmt_num(S, 2)} < {fmt_num(float(inp['Smin']), 1)} – größere Teilung oder "
                      "Mehrfachkette.")
        if z1 < 17:
            self.warn(f"z₁ = {z1} < 17 – Polygoneffekt {fmt_num(poly, 1)} %, unruhiger Lauf und Verschleiß.")
        if v > 12:
            self.info("Kettengeschwindigkeit > 12 m/s – Druckumlauf- bzw. Ölbadschmierung erforderlich.")
        if not 30 * p <= a <= 80 * p:
            self.info(f"Achsabstand außerhalb 30…80·p ({fmt_num(30 * p, 0)}…{fmt_num(80 * p, 0)} mm).")
        if (z1 % 2 == 0) and (X % 2 == 0):
            self.info("Gerade Zähnezahl und gerade Gliederzahl – ungerade Zähnezahl verteilt den Verschleiß besser.")
        self.info("Die Dauerhaltbarkeit (Gelenkverschleiß) über das Leistungsdiagramm des Kettenherstellers prüfen.")

    def sketch_svg(self, raw) -> str:
        s = Svg()
        try:
            z1, z2 = float(raw.get("z1", 19)), float(raw.get("z2", 57))
        except (TypeError, ValueError):
            z1, z2 = 19, 57
        r2 = 70
        r1 = max(14, r2 * z1 / max(z2, 1))
        x1, x2, y = 80, 270, 110
        s.circle(x1, y, r1, fill="#f5d7d3").circle(x2, y, r2, fill="#dce6f1")
        s.line(x1, y - r1, x2, y - r2, ACCENT, 4, "6 3").line(x1, y + r1, x2, y + r2, ACCENT, 4, "6 3")
        s.text(x1, y + 4, "z₁", 11, INK, italic=True).text(x2, y + 4, "z₂", 12, INK, italic=True)
        s.text(180, 30, "Rollenkette DIN 8187", 11, MUTED)
        s.dim_h(x1, x2, 205, "a")
        return s.render()
