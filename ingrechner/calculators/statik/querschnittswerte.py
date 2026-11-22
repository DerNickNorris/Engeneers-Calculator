"""Querschnittswerte einfacher Profile."""

from __future__ import annotations

import math

from ingrechner.core.model import Calculator, ChoiceField, NumberField
from ingrechner.core.svg import INK, MUTED, Svg
from ingrechner.core.units import fmt_q

BH = {"form": ["rechteck", "rechteckrohr", "i_profil"]}
D = {"form": ["kreis", "kreisrohr"]}
T = {"form": ["rechteckrohr", "kreisrohr"]}
I_PROF = {"form": ["i_profil"]}


class Querschnittswerte(Calculator):
    id = "st.querschnittswerte"
    title = "Querschnittswerte"
    category = "Bau / Statik"
    description = (
        "Fläche, Flächenträgheitsmomente, Widerstandsmomente, Trägheitsradien und "
        "Metergewicht für Rechteck, Rechteckrohr, Kreis, Kreisrohr und I-Profil."
    )
    norm = "Elementare Querschnittsgeometrie, scharfkantig ohne Ausrundungsradien"
    keywords = ("querschnitt", "trägheitsmoment", "widerstandsmoment", "profil", "rohr",
                "fläche", "flächenmoment")
    material_map = {"rho": "rho"}

    fields = [
        ChoiceField("form", "Querschnittsform", [
            ("rechteck", "Rechteck (voll)"),
            ("rechteckrohr", "Rechteckrohr / Hohlprofil"),
            ("kreis", "Kreis (voll)"),
            ("kreisrohr", "Kreisrohr"),
            ("i_profil", "I-Profil (doppelt symmetrisch)"),
        ], "rechteck"),
        NumberField("b", "Breite", "b", "mm", 100, min=0, decimals=1, visible_if=BH),
        NumberField("h", "Höhe", "h", "mm", 200, min=0, decimals=1, visible_if=BH),
        NumberField("d", "Außendurchmesser", "D", "mm", 100, min=0, decimals=1, visible_if=D),
        NumberField("t", "Wanddicke", "t", "mm", 5, min=0, decimals=2, visible_if=T),
        NumberField("tw", "Stegdicke", "t_w", "mm", 5.6, min=0, decimals=2, visible_if=I_PROF),
        NumberField("tf", "Flanschdicke", "t_f", "mm", 8.5, min=0, decimals=2, visible_if=I_PROF),
        NumberField("rho", "Dichte", "ρ", "kg/m**3", 7850, min=0, decimals=0,
                    tooltip="Stahl 7850, Aluminium 2700, Holz (Nadel) ≈ 450 kg/m³"),
    ]

    def compute(self, inp) -> None:
        form = inp["form"]
        mm = lambda q, d=1: fmt_q(q, "mm", d)  # noqa: E731

        if form == "rechteck":
            b, h = inp["b"], inp["h"]
            A, Iy, Iz = b * h, b * h**3 / 12, h * b**3 / 12
            ey, ez = h / 2, b / 2
            self.step("Fläche", "A = b · h", f"A = {mm(b)} · {mm(h)}", fmt_q(A, "cm**2", 2))
            self.step("Trägheitsmoment y", "I_y = b · h³ / 12", f"I_y = {mm(b)} · ({mm(h)})³ / 12",
                      fmt_q(Iy, "cm**4", 2))
            self.step("Trägheitsmoment z", "I_z = h · b³ / 12", f"I_z = {mm(h)} · ({mm(b)})³ / 12",
                      fmt_q(Iz, "cm**4", 2))

        elif form == "rechteckrohr":
            b, h, t = inp["b"], inp["h"], inp["t"]
            if 2 * t >= min(b, h):
                raise ValueError("Wanddicke zu groß: 2·t muss kleiner als b und h sein.")
            bi, hi = b - 2 * t, h - 2 * t
            A = b * h - bi * hi
            Iy = (b * h**3 - bi * hi**3) / 12
            Iz = (h * b**3 - hi * bi**3) / 12
            ey, ez = h / 2, b / 2
            self.step("Fläche", "A = b·h − (b−2t)·(h−2t)",
                      f"A = {mm(b)}·{mm(h)} − {mm(bi)}·{mm(hi)}", fmt_q(A, "cm**2", 2))
            self.step("Trägheitsmoment y", "I_y = [b·h³ − (b−2t)·(h−2t)³] / 12",
                      f"I_y = [{mm(b)}·({mm(h)})³ − {mm(bi)}·({mm(hi)})³] / 12", fmt_q(Iy, "cm**4", 2))
            self.step("Trägheitsmoment z", "I_z = [h·b³ − (h−2t)·(b−2t)³] / 12",
                      f"I_z = [{mm(h)}·({mm(b)})³ − {mm(hi)}·({mm(bi)})³] / 12", fmt_q(Iz, "cm**4", 2))

        elif form == "kreis":
            d = inp["d"]
            A = math.pi * d**2 / 4
            Iy = Iz = math.pi * d**4 / 64
            ey = ez = d / 2
            self.step("Fläche", "A = π · D² / 4", f"A = π · ({mm(d)})² / 4", fmt_q(A, "cm**2", 2))
            self.step("Trägheitsmoment", "I_y = I_z = π · D⁴ / 64", f"I = π · ({mm(d)})⁴ / 64",
                      fmt_q(Iy, "cm**4", 2))

        elif form == "kreisrohr":
            d, t = inp["d"], inp["t"]
            if 2 * t >= d:
                raise ValueError("Wanddicke zu groß: 2·t muss kleiner als D sein.")
            di = d - 2 * t
            A = math.pi * (d**2 - di**2) / 4
            Iy = Iz = math.pi * (d**4 - di**4) / 64
            ey = ez = d / 2
            self.step("Innendurchmesser", "d = D − 2·t", f"d = {mm(d)} − 2 · {mm(t, 2)}", mm(di))
            self.step("Fläche", "A = π · (D² − d²) / 4", f"A = π · (({mm(d)})² − ({mm(di)})²) / 4",
                      fmt_q(A, "cm**2", 2))
            self.step("Trägheitsmoment", "I = π · (D⁴ − d⁴) / 64",
                      f"I = π · (({mm(d)})⁴ − ({mm(di)})⁴) / 64", fmt_q(Iy, "cm**4", 2))

        else:  # i_profil
            b, h, tw, tf = inp["b"], inp["h"], inp["tw"], inp["tf"]
            if tw >= b:
                raise ValueError("Stegdicke t_w muss kleiner als die Breite b sein.")
            if 2 * tf >= h:
                raise ValueError("Flanschdicke zu groß: 2·t_f muss kleiner als h sein.")
            hw = h - 2 * tf
            A = 2 * b * tf + hw * tw
            Iy = (b * h**3 - (b - tw) * hw**3) / 12
            Iz = (2 * tf * b**3 + hw * tw**3) / 12
            ey, ez = h / 2, b / 2
            self.step("Steghöhe", "h_w = h − 2·t_f", f"h_w = {mm(h)} − 2 · {mm(tf, 2)}", mm(hw))
            self.step("Fläche", "A = 2·b·t_f + h_w·t_w",
                      f"A = 2·{mm(b)}·{mm(tf, 2)} + {mm(hw)}·{mm(tw, 2)}", fmt_q(A, "cm**2", 2))
            self.step("Trägheitsmoment y", "I_y = [b·h³ − (b−t_w)·h_w³] / 12",
                      f"I_y = [{mm(b)}·({mm(h)})³ − {mm(b - tw)}·({mm(hw)})³] / 12",
                      fmt_q(Iy, "cm**4", 2))
            self.step("Trägheitsmoment z", "I_z = [2·t_f·b³ + h_w·t_w³] / 12",
                      f"I_z = [2·{mm(tf, 2)}·({mm(b)})³ + {mm(hw)}·({mm(tw, 2)})³] / 12",
                      fmt_q(Iz, "cm**4", 2))
            self.info("Ausrundungsradien zwischen Steg und Flansch sind nicht berücksichtigt – "
                      "Tabellenwerte von Walzprofilen liegen daher etwas höher.")

        Wy, Wz = Iy / ey, Iz / ez
        iy, iz = (Iy / A) ** 0.5, (Iz / A) ** 0.5
        g = (A * inp["rho"]).to("kg/m")
        self.step("Widerstandsmoment y", "W_y = I_y / e_z,max",
                  f"W_y = {fmt_q(Iy, 'cm**4', 2)} / {fmt_q(ey, 'cm', 2)}", fmt_q(Wy, "cm**3", 2))
        self.step("Widerstandsmoment z", "W_z = I_z / e_y,max",
                  f"W_z = {fmt_q(Iz, 'cm**4', 2)} / {fmt_q(ez, 'cm', 2)}", fmt_q(Wz, "cm**3", 2))
        self.step("Trägheitsradius y", "i_y = √(I_y / A)",
                  f"i_y = √({fmt_q(Iy, 'cm**4', 2)} / {fmt_q(A, 'cm**2', 2)})", fmt_q(iy, "cm", 2))
        self.step("Metergewicht", "g = A · ρ",
                  f"g = {fmt_q(A, 'm**2', 6)} · {fmt_q(inp['rho'], 'kg/m**3', 0)}", fmt_q(g, "kg/m", 2))

        self.result("A", "Querschnittsfläche", "A", A, "cm**2", 2, highlight=True)
        self.result("Iy", "Flächenträgheitsmoment y", "I_y", Iy, "cm**4", 2, highlight=True)
        self.result("Iz", "Flächenträgheitsmoment z", "I_z", Iz, "cm**4", 2)
        self.result("Wy", "Widerstandsmoment y", "W_y", Wy, "cm**3", 2, highlight=True)
        self.result("Wz", "Widerstandsmoment z", "W_z", Wz, "cm**3", 2)
        self.result("iy", "Trägheitsradius y", "i_y", iy, "cm", 2)
        self.result("iz", "Trägheitsradius z", "i_z", iz, "cm", 2)
        self.result("g", "Metergewicht", "g", g, "kg/m", 2)

    # ---------------------------------------------------------------- Skizze
    def sketch_svg(self, raw) -> str:
        s = Svg()
        cx, cy = 150, 105
        form = raw.get("form", "rechteck")
        if form in ("kreis", "kreisrohr"):
            half_w = half_h = 70.0
        else:
            try:
                ratio = max(0.25, min(4.0, float(raw.get("b", 1)) / float(raw.get("h", 1))))
            except (TypeError, ValueError, ZeroDivisionError):
                ratio = 0.5
            hh, bb = 150.0, 150.0 * ratio
            if bb > 200:
                bb, hh = 200.0, 200.0 / ratio
            half_w, half_h = bb / 2, hh / 2

        # Schwerachsen (enden knapp außerhalb der Kontur, damit Maße frei bleiben)
        s.line(cx - half_w - 28, cy, cx + half_w + 10, cy, MUTED, 1, "5,4")
        s.text(cx - half_w - 34, cy + 4, "y", 13, MUTED, "end", True)
        s.line(cx, cy - half_h - 14, cx, cy + half_h + 6, MUTED, 1, "5,4")
        s.text(cx + 6, cy - half_h - 6, "z", 13, MUTED, "start", True)

        if form in ("kreis", "kreisrohr"):
            r = half_w
            s.circle(cx, cy, r)
            if form == "kreisrohr":
                s.circle(cx, cy, r - 14, fill="#ffffff")
                s.text(cx + r + 6, cy - r + 20, "t", 12, MUTED, "start", True)
            s.dim_v(cx + r + 26, cy - r, cy + r, "D")
        else:
            x0, y0, bb, hh = cx - half_w, cy - half_h, 2 * half_w, 2 * half_h
            if form == "rechteck":
                s.rect(x0, y0, bb, hh)
            elif form == "rechteckrohr":
                s.rect(x0, y0, bb, hh)
                tt = max(6, min(bb, hh) * 0.12)
                s.rect(x0 + tt, y0 + tt, bb - 2 * tt, hh - 2 * tt, fill="#ffffff")
            else:
                tf = max(6, hh * 0.08)
                tw = max(4, bb * 0.08)
                s.polygon([
                    (x0, y0), (x0 + bb, y0), (x0 + bb, y0 + tf), (cx + tw / 2, y0 + tf),
                    (cx + tw / 2, y0 + hh - tf), (x0 + bb, y0 + hh - tf), (x0 + bb, y0 + hh),
                    (x0, y0 + hh), (x0, y0 + hh - tf), (cx - tw / 2, y0 + hh - tf),
                    (cx - tw / 2, y0 + tf), (x0, y0 + tf),
                ])
            s.dim_h(x0, x0 + bb, y0 + hh + 22, "b")
            s.dim_v(x0 + bb + 26, y0, y0 + hh, "h")
        return s.render()
