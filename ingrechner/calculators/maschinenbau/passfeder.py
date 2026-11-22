"""Passfederverbindung (DIN 6885 / DIN 6892 vereinfacht): Flächenpressung an Welle und Nabe, erforderliche Länge."""

from __future__ import annotations

import math

from ingrechner.core.model import Calculator, ChoiceField, NumberField
from ingrechner.core.svg import INK, MUTED, Svg
from ingrechner.core.units import Q_, fmt_num

from ._getriebe import PASSFEDER_LAENGEN, passfeder

# Zulässige Flächenpressung (Richtwerte, ruhende bis schwellende Last) in N/mm²
P_ZUL = {"stahl": ("Stahl (S355, C45)", 180), "stahl_v": ("Stahl vergütet (42CrMo4)", 250),
         "gjs": ("Gusseisen mit Kugelgraphit (GJS)", 140), "gjl": ("Grauguss (GJL)", 80),
         "alu": ("Aluminiumlegierung", 60)}


class Passfeder(Calculator):
    id = "mb.passfeder"
    title = "Passfederverbindung"
    category = "Maschinenbau"
    description = (
        "Welle-Nabe-Verbindung mit Passfeder nach DIN 6885-1: Passfederquerschnitt aus dem Wellendurchmesser, "
        "tragende Länge (Form A/B), Flächenpressung an Welle und Nabe mit Anwendungsfaktor gegen zulässige "
        "Pressungen sowie erforderliche Mindestlänge mit Normlängenvorschlag."
    )
    norm = "p = 2·T·K_A / (d · h' · l_tr · n · φ);  Abmessungen DIN 6885-1;  Nachweis vereinfacht nach DIN 6892 (Methode C)"
    keywords = ("passfeder", "welle-nabe", "nabe", "flächenpressung", "din 6885", "din 6892", "wellenverbindung",
                "getriebe", "kupplung", "drehmoment", "nut")

    fields = [
        NumberField("d", "Wellendurchmesser", "d", "mm", 45, min=6, max=230, decimals=1),
        NumberField("T", "Drehmoment", "T", "N*m", 400, min=0, decimals=1),
        NumberField("KA", "Anwendungsfaktor", "K_A", "", 1.25, min=1, max=3, min_inclusive=True, decimals=2,
                    tooltip="Betriebsfaktor bzw. Stoßfaktor (Rechner „Antriebsauslegung“)"),
        NumberField("L", "Passfederlänge", "l", "mm", 56, min=0, decimals=0),
        ChoiceField("form", "Form", [("A", "Form A (rundstirnig)"),
                                     ("B", "Form B (geradstirnig)")], "A",
                    tooltip="Tragende Länge: Form A l − b, Form B l"),
        ChoiceField("anzahl", "Anzahl Passfedern", [("1", "eine"), ("2", "zwei (um 180° versetzt, Traganteil 75 %)")],
                    "1"),
        ChoiceField("nabe", "Nabenwerkstoff", [(k, v[0]) for k, v in P_ZUL.items()], "stahl"),
        ChoiceField("welle", "Wellenwerkstoff", [(k, v[0]) for k, v in P_ZUL.items() if k.startswith("stahl")],
                    "stahl"),
    ]

    def compute(self, inp) -> None:
        d = inp["d"].to("mm").magnitude
        pf = passfeder(d)
        if pf is None:
            raise ValueError("Wellendurchmesser außerhalb der Tabelle DIN 6885-1 (6 … 230 mm).")
        b, h, t1, t2 = pf
        T = inp["T"].to("N*mm").magnitude
        KA = float(inp["KA"])
        L = inp["L"].to("mm").magnitude
        l_tr = L - b if inp["form"] == "A" else L
        if l_tr <= 0:
            raise ValueError("Die Passfeder ist kürzer als ihre Breite.")
        n, phi = (1, 1.0) if inp["anzahl"] == "1" else (2, 0.75)
        h_n = h - t1          # tragende Höhe in der Nabe
        h_w = t1              # tragende Höhe in der Welle (vereinfacht)
        F = 2 * T * KA / d
        pN = F / (h_n * l_tr * n * phi)
        pW = F / (h_w * l_tr * n * phi)
        pzN, pzW = P_ZUL[inp["nabe"]][1], P_ZUL[inp["welle"]][1]
        self.step("Passfeder DIN 6885-1", f"d = {fmt_num(d, 1)} mm → b × h, t₁, t₂", "",
                  f"{fmt_num(b, 0)} × {fmt_num(h, 0)} mm, t₁ = {fmt_num(t1, 1)} mm, t₂ = {fmt_num(t2, 1)} mm")
        self.step("Umfangskraft am Wellenumfang", "F = 2·T·K_A / d",
                  f"F = 2·{fmt_num(T / 1000, 1)} N·m·{fmt_num(KA, 2)} / {fmt_num(d, 1)} mm", f"{fmt_num(F, 0)} N")
        self.step("Flächenpressung Nabe", "p_N = F / ((h − t₁)·l_tr·n·φ)",
                  f"l_tr = {fmt_num(l_tr, 1)} mm, h − t₁ = {fmt_num(h_n, 1)} mm", f"{fmt_num(pN, 0)} N/mm²")
        self.step("Flächenpressung Welle", "p_W = F / (t₁·l_tr·n·φ)", f"t₁ = {fmt_num(h_w, 1)} mm",
                  f"{fmt_num(pW, 0)} N/mm²")
        l_tr_erf = max(F / (h_n * pzN * n * phi), F / (h_w * pzW * n * phi))
        l_erf = l_tr_erf + (b if inp["form"] == "A" else 0)
        l_norm = next((x for x in PASSFEDER_LAENGEN if x >= l_erf), None)
        self.step("Erforderliche Länge", "l_tr,erf = F / (h'·p_zul·n·φ)", f"p_zul Nabe/Welle = {pzN}/{pzW} N/mm²",
                  f"l_erf = {fmt_num(l_erf, 1)} mm" + (f" → Normlänge {l_norm} mm" if l_norm else ""))

        self.result("b", "Passfederbreite", "b", Q_(b, "mm"), "mm", 0)
        self.result("h", "Passfederhöhe", "h", Q_(h, "mm"), "mm", 0)
        self.result("pN", "Flächenpressung Nabe", "p_N", Q_(pN, "N/mm**2"), "N/mm**2", 0, highlight=True)
        self.result("pW", "Flächenpressung Welle", "p_W", Q_(pW, "N/mm**2"), "N/mm**2", 0, highlight=True)
        self.result("SN", "Auslastung Nabe", "p_N/p_zul", Q_(pN / pzN * 100, "percent"), "percent", 0, highlight=True)
        self.result("SW", "Auslastung Welle", "p_W/p_zul", Q_(pW / pzW * 100, "percent"), "percent", 0)
        self.result("lerf", "Erforderliche Passfederlänge", "l_erf", Q_(l_erf, "mm"), "mm", 1, highlight=True)
        if l_norm:
            self.result("lnorm", "Nächste Normlänge", "l_Norm", Q_(l_norm, "mm"), "mm", 0)
        self.result("t1", "Wellennuttiefe", "t₁", Q_(t1, "mm"), "mm", 1)
        self.result("t2", "Nabennuttiefe", "t₂", Q_(t2, "mm"), "mm", 1)
        if pN > pzN or pW > pzW:
            self.warn(f"Zulässige Flächenpressung überschritten – Länge auf ≥ {fmt_num(l_erf, 0)} mm erhöhen, zweite "
                      "Passfeder oder Pressverband/Keilwelle vorsehen.")
        else:
            self.info("Flächenpressung zulässig.")
        if L > 1.6 * d:
            self.warn("Passfederlänge > 1,6·d – ungleichmäßiges Tragen; Nabenlänge ≈ 1,0–1,5·d, sonst Keilwelle "
                      "oder Pressverband.")
        if n == 2:
            self.info("Zwei Passfedern schwächen Welle und Nabe zusätzlich; Fertigungstoleranzen bestimmen den "
                      "Lastanteil (hier 75 % angesetzt).")
        self.info("Richtwerte p_zul für ruhende bis schwellende Last; bei Wechsel-/Stoßbelastung niedriger. "
                  "Wellen- und Nabenfestigkeit (Kerbwirkung der Nut) gesondert nachweisen.")

    def sketch_svg(self, raw) -> str:
        s = Svg()
        s.circle(180, 110, 80, fill="#dce6f1").circle(180, 110, 50, fill="#eef3f8")
        s.rect(168, 52, 24, 20, fill="#f5d7d3")
        s.text(180, 115, "Welle d", 12, INK).text(180, 180, "Nabe", 11, MUTED)
        s.text(200, 50, "b × h", 11, INK, "start", True)
        return s.render()
