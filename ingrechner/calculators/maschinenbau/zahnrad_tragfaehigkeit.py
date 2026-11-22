"""Zahnradtragfähigkeit (vereinfacht): Flankenpressung und Zahnfußspannung, angelehnt an DIN 3990 / ISO 6336."""

from __future__ import annotations

import math

import numpy as np

from ingrechner.core.model import Calculator, ChoiceField, NumberField
from ingrechner.core.svg import ACCENT, INK, MUTED, Svg
from ingrechner.core.units import Q_, fmt_num

from ._getriebe import ZAHN_WERKSTOFFE, radpaar, radpaar_felder, y_fs

WERKSTOFFE = [(k, w.name) for k, w in ZAHN_WERKSTOFFE.items()]


class ZahnradTragfaehigkeit(Calculator):
    id = "mb.zahnrad_tragfaehigkeit"
    title = "Zahnradtragfähigkeit (vereinfacht)"
    category = "Maschinenbau"
    description = (
        "Vereinfachter Tragfähigkeitsnachweis eines Stirnradpaars für die Vorbemessung bzw. Plausibilitätsprüfung: "
        "Umfangs-, Radial- und Axialkraft, Hertzsche Flankenpressung σ_H und Zahnfußspannung σ_F mit "
        "Anwendungs- und Lastfaktoren, Sicherheiten S_H und S_F gegen Dauerfestigkeitswerte der Werkstoffe."
    )
    norm = ("σ_H = Z_H·Z_E·Z_ε·Z_β·√(F_t/(d₁·b)·(u+1)/u·K_A·K_v·K_Hβ·K_Hα); σ_F = F_t/(b·m_n)·Y_FS·Y_ε·Y_β·K_A·K_v·K_Fβ·K_Fα; "
            "angelehnt an DIN 3990 / ISO 6336 (vereinfacht)")
    keywords = ("zahnrad", "tragfähigkeit", "flankenpressung", "grübchen", "zahnfuß", "zahnbruch", "sicherheit",
                "din 3990", "iso 6336", "verzahnung", "zahnkraft", "umfangskraft", "getriebe", "16mncr5")

    fields = [
        *radpaar_felder(),
        NumberField("M1", "Drehmoment am Ritzel", "T₁", "N*m", 120, min=0, decimals=2),
        NumberField("n1", "Drehzahl Ritzel", "n₁", "1/minute", 1450, min=0, decimals=0),
        ChoiceField("w1", "Werkstoff Ritzel", WERKSTOFFE, "16mncr5"),
        ChoiceField("w2", "Werkstoff Rad", WERKSTOFFE, "16mncr5"),
        NumberField("KA", "Anwendungsfaktor", "K_A", "", 1.25, min=1, max=3, min_inclusive=True, decimals=2,
                    tooltip="Entspricht etwa dem Betriebsfaktor (Rechner „Antriebsauslegung“): gleichförmig 1,0, "
                            "mäßige Stöße 1,25–1,5, starke Stöße 1,75–2,25"),
        NumberField("Kv", "Dynamikfaktor", "K_v", "", 1.1, min=1, max=2, min_inclusive=True, decimals=2,
                    tooltip="Langsame bzw. genaue Verzahnung 1,0–1,1; v > 10 m/s oder Qualität > 8 bis 1,3"),
        NumberField("KHb", "Breitenlastfaktor", "K_Hβ", "", 1.3, min=1, max=3, min_inclusive=True, decimals=2,
                    tooltip="Steife Lagerung, Ritzel mittig, Breitenballig: 1,1–1,3; fliegend/weich: 1,5–2,0. "
                            "K_Fβ ≈ K_Hβ^0,9 wird daraus abgeleitet"),
        NumberField("KHa", "Stirnlastfaktor", "K_Hα = K_Fα", "", 1.0, min=1, max=2, min_inclusive=True, decimals=2,
                    tooltip="Gute Verzahnungsqualität (≤ 7): 1,0; Qualität 8–9: 1,1–1,2"),
        NumberField("SHmin", "Mindestsicherheit Flanke", "S_H,min", "", 1.0, min=0.5, max=3, decimals=2),
        NumberField("SFmin", "Mindestsicherheit Zahnfuß", "S_F,min", "", 1.4, min=0.5, max=4, decimals=2),
    ]

    def compute(self, inp) -> None:
        rp = radpaar(inp)
        w1, w2 = ZAHN_WERKSTOFFE[inp["w1"]], ZAHN_WERKSTOFFE[inp["w2"]]
        T1 = inp["M1"].to("N*m").magnitude
        n1 = inp["n1"].to("1/minute").magnitude
        Ft = 2000 * T1 / rp.d1
        Fr = Ft * math.tan(rp.alpha_wt) / math.cos(rp.beta)
        Fa = Ft * math.tan(rp.beta)
        v = math.pi * rp.d1 / 1000 * n1 / 60
        self.step("Zahnkräfte", "F_t = 2000·T₁/d₁;  F_r = F_t·tan α_wt/cos β;  F_a = F_t·tan β",
                  f"d₁ = {fmt_num(rp.d1, 3)} mm, α_wt = {fmt_num(math.degrees(rp.alpha_wt), 3)}°",
                  f"F_t = {fmt_num(Ft, 0)} N, F_r = {fmt_num(Fr, 0)} N, F_a = {fmt_num(Fa, 0)} N")
        KA, Kv, KHb, KHa = (float(inp[k]) for k in ("KA", "Kv", "KHb", "KHa"))
        KFb = KHb ** 0.9
        # ---------------- Flanke
        ZH = math.sqrt(2 * math.cos(rp.beta_b) * math.cos(rp.alpha_wt) /
                       (math.cos(rp.alpha_t) ** 2 * math.sin(rp.alpha_wt)))
        ZE = math.sqrt(1 / (math.pi * ((1 - w1.nu**2) / w1.E + (1 - w2.nu**2) / w2.E)))
        ea, eb = rp.eps_a, rp.eps_b
        Zeps = math.sqrt((4 - ea) / 3 * (1 - eb) + eb / ea) if eb < 1 else math.sqrt(1 / ea)
        Zbeta = math.sqrt(math.cos(rp.beta))
        sH0 = ZH * ZE * Zeps * Zbeta * math.sqrt(Ft / (rp.d1 * rp.b) * (rp.u + 1) / rp.u)
        sH = sH0 * math.sqrt(KA * Kv * KHb * KHa)
        self.step("Zonenfaktor, Elastizitätsfaktor", "Z_H = √(2·cos β_b·cos α_wt/(cos²α_t·sin α_wt));  "
                  "Z_E = √(1/(π·Σ(1−ν²)/E))", "",
                  f"Z_H = {fmt_num(ZH, 3)}, Z_E = {fmt_num(ZE, 1)} √(N/mm²), Z_ε = {fmt_num(Zeps, 3)}, Z_β = {fmt_num(Zbeta, 3)}")
        self.step("Flankenpressung", "σ_H = σ_H0·√(K_A·K_v·K_Hβ·K_Hα)",
                  f"σ_H0 = {fmt_num(sH0, 1)} N/mm², K = {fmt_num(KA, 2)}·{fmt_num(Kv, 2)}·{fmt_num(KHb, 2)}·{fmt_num(KHa, 2)}",
                  f"σ_H = {fmt_num(sH, 0)} N/mm²")
        SH1, SH2 = w1.sigma_hlim / sH, w2.sigma_hlim / sH
        # ---------------- Zahnfuß
        ean = ea / math.cos(rp.beta_b) ** 2
        Yeps = 0.25 + 0.75 / ean
        Ybeta = max(1 - eb * math.degrees(rp.beta) / 120, 1 - 0.25 * min(eb, 1), 0.75)
        Y1, Y2 = y_fs(rp.zn1, rp.x1), y_fs(rp.zn2, rp.x2)
        f = Ft / (rp.b * rp.mn) * Yeps * Ybeta * KA * Kv * KFb * KHa
        sF1, sF2 = f * Y1, f * Y2
        self.step("Kopffaktor, Überdeckungs- und Schrägenfaktor", "Y_FS(z_n, x);  Y_ε = 0,25 + 0,75/ε_αn;  "
                  "Y_β = 1 − ε_β·β/120°", f"z_n1 = {fmt_num(rp.zn1, 1)}, z_n2 = {fmt_num(rp.zn2, 1)}",
                  f"Y_FS1 = {fmt_num(Y1, 2)}, Y_FS2 = {fmt_num(Y2, 2)}, Y_ε = {fmt_num(Yeps, 3)}, Y_β = {fmt_num(Ybeta, 3)}")
        self.step("Zahnfußspannung", "σ_F = F_t/(b·m_n)·Y_FS·Y_ε·Y_β·K_A·K_v·K_Fβ·K_Fα",
                  f"K_Fβ = K_Hβ^0,9 = {fmt_num(KFb, 3)}",
                  f"σ_F1 = {fmt_num(sF1, 0)} N/mm², σ_F2 = {fmt_num(sF2, 0)} N/mm²")
        SF1, SF2 = 2 * w1.sigma_flim / sF1, 2 * w2.sigma_flim / sF2
        self.step("Sicherheiten", "S_H = σ_Hlim/σ_H;  S_F = σ_FE/σ_F mit σ_FE = 2·σ_Flim",
                  f"σ_Hlim = {fmt_num(w1.sigma_hlim, 0)}/{fmt_num(w2.sigma_hlim, 0)}, "
                  f"σ_Flim = {fmt_num(w1.sigma_flim, 0)}/{fmt_num(w2.sigma_flim, 0)} N/mm²",
                  f"S_H = {fmt_num(SH1, 2)}/{fmt_num(SH2, 2)}, S_F = {fmt_num(SF1, 2)}/{fmt_num(SF2, 2)}")

        self.result("SH1", "Sicherheit Flanke Ritzel", "S_H1", Q_(SH1, ""), "", 2, highlight=True)
        self.result("SH2", "Sicherheit Flanke Rad", "S_H2", Q_(SH2, ""), "", 2, highlight=True)
        self.result("SF1", "Sicherheit Zahnfuß Ritzel", "S_F1", Q_(SF1, ""), "", 2, highlight=True)
        self.result("SF2", "Sicherheit Zahnfuß Rad", "S_F2", Q_(SF2, ""), "", 2, highlight=True)
        self.result("sH", "Flankenpressung", "σ_H", Q_(sH, "N/mm**2"), "N/mm**2", 0)
        self.result("sF1", "Zahnfußspannung Ritzel", "σ_F1", Q_(sF1, "N/mm**2"), "N/mm**2", 0)
        self.result("sF2", "Zahnfußspannung Rad", "σ_F2", Q_(sF2, "N/mm**2"), "N/mm**2", 0)
        self.result("Ft", "Umfangskraft", "F_t", Q_(Ft, "N"), "N", 0)
        self.result("Fr", "Radialkraft", "F_r", Q_(Fr, "N"), "N", 0)
        self.result("Fa", "Axialkraft", "F_a", Q_(Fa, "N"), "N", 0)
        self.result("v", "Umfangsgeschwindigkeit", "v", Q_(v, "m/s"), "m/s", 2)
        self.result("dw1", "Wälzkreis Ritzel", "d_w1", Q_(rp.dw1, "mm"), "mm", 2)

        SHmin, SFmin = float(inp["SHmin"]), float(inp["SFmin"])
        for name, S, Smin in (("Flanke Ritzel", SH1, SHmin), ("Flanke Rad", SH2, SHmin),
                              ("Zahnfuß Ritzel", SF1, SFmin), ("Zahnfuß Rad", SF2, SFmin)):
            if S < Smin:
                self.warn(f"{name}: Sicherheit {fmt_num(S, 2)} < {fmt_num(Smin, 2)} – Breite, Modul oder Werkstoff erhöhen.")
        if min(SH1, SH2) >= SHmin and min(SF1, SF2) >= SFmin:
            self.info("Mindestsicherheiten eingehalten (Dauerfestigkeitsbereich, vereinfachter Nachweis).")
        if v > 20:
            self.warn(f"Umfangsgeschwindigkeit {fmt_num(v, 1)} m/s – Dynamikfaktor und Schmierung gesondert prüfen.")
        if rp.b / rp.d1 > 1.2:
            self.info(f"Breitenverhältnis b/d₁ = {fmt_num(rp.b / rp.d1, 2)} > 1,2 – ungleichmäßiges Tragen; K_Hβ höher ansetzen.")
        self.info("Vereinfachter Nachweis: Lebensdauer-, Schmierstoff-, Rauheits- und Größenfaktoren = 1 "
                  "(Dauerfestigkeit), Werkstoffkennwerte als Richtwerte (Qualität MQ). Für die Endauslegung "
                  "ISO 6336 / DIN 3990 Methode B bzw. Herstellerberechnung verwenden.")

    def plot(self, fig, raw, result) -> bool:
        if not result.ok:
            return False
        ax = fig.subplots()
        names = ["Flanke\nRitzel", "Flanke\nRad", "Fuß\nRitzel", "Fuß\nRad"]
        vals = [result.value(k) for k in ("SH1", "SH2", "SF1", "SF2")]
        mins = [float(raw["SHmin"])] * 2 + [float(raw["SFmin"])] * 2
        cols = ["#27ae60" if v >= m else "#c0392b" for v, m in zip(vals, mins)]
        bars = ax.bar(names, vals, color=cols)
        for b_, m in zip(bars, mins):
            ax.plot([b_.get_x(), b_.get_x() + b_.get_width()], [m, m], color="#2b3a4a", lw=2)
        for b_, v in zip(bars, vals):
            ax.annotate(fmt_num(v, 2), (b_.get_x() + b_.get_width() / 2, v), ha="center", va="bottom", fontsize=8)
        ax.set_ylabel("Sicherheit  [–]")
        ax.set_title("Sicherheiten gegen Grübchen und Zahnbruch (Strich = Mindestwert)")
        ax.set_ylim(0, max(max(vals), max(mins)) * 1.2)
        ax.grid(True, axis="y", alpha=0.3)
        return True

    def sketch_svg(self, raw) -> str:
        s = Svg()
        s.circle(130, 120, 60, fill="#f5d7d3").circle(250, 120, 60, fill="#dce6f1")
        s.arrow(190, 120, 190, 40, "#c0392b").text(196, 50, "F_t", 12, INK, "start", True)
        s.arrow(190, 120, 160, 120, ACCENT).text(150, 112, "F_r", 12, INK, "end", True)
        s.text(130, 125, "1", 14, INK, bold=True).text(250, 125, "2", 14, INK, bold=True)
        s.text(190, 205, "Flankenpressung und Zahnfußspannung", 11, MUTED)
        return s.render()
