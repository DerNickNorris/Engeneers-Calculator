"""Gemeinsame Eingabefelder und Auflösung für Rechner mit gedämmten Rohrleitungen."""

from __future__ import annotations

from ingrechner.core.model import ChoiceField, NumberField
from ingrechner.core.rohrdaten import (EMISSION, LAMBDA_ROHR, daemmstoff_optionen, rohr, rohr_optionen,
                                       werkstoff, werkstoff_optionen)
from ingrechner.core.svg import INK, MUTED, Svg

FREI = {"rohr": ["frei"]}


def rohr_felder(default_rohr: str = "st:DN 50", daemm: float = 50) -> list:
    return [
        ChoiceField("rohr", "Rohr", rohr_optionen(), default_rohr),
        NumberField("da", "Außendurchmesser Rohr", "d_a", "mm", 60.3, min=0, decimals=1, visible_if=FREI),
        NumberField("s", "Wanddicke Rohr", "s", "mm", 3.6, min=0, decimals=2, visible_if=FREI),
        ChoiceField("werkstoff", "Rohrwerkstoff", werkstoff_optionen(), "auto",
                    tooltip="Werte aus der Materialdatenbank (Gruppe „Rohrwerkstoff“). Über „Werkstoff …“ "
                            "lassen sich auch eigene Werkstoffe des Teams übernehmen."),
        NumberField("lam_rohr", "λ Rohrwerkstoff", "λ_R", "W/(m*K)", 50, min=0, decimals=3,
                    visible_if={"werkstoff": ["frei"]}),
        NumberField("daemm", "Dämmdicke", "s_D", "mm", daemm, min=0, min_inclusive=True, decimals=1,
                    tooltip="0 = ungedämmt"),
        ChoiceField("daemmstoff", "Dämmstoff", daemmstoff_optionen(), "b:mw-rohrschale",
                    tooltip="λ-Werte als Richtwerte bei typischer Mitteltemperatur – Herstellerkurve beachten"),
        NumberField("lam_d", "λ Dämmstoff", "λ_D", "W/(m*K)", 0.040, min=0, decimals=4,
                    visible_if={"daemmstoff": ["frei"]}),
    ]


def emission_feld() -> ChoiceField:
    return ChoiceField("oberflaeche", "Außenoberfläche", [(k, f"{v[1]} (ε = {v[0]:g})".replace(".", ","))
                                                          for k, v in EMISSION.items()], "anstrich",
                       tooltip="Emissionsgrad für den Strahlungsanteil (DIN EN ISO 12241)")


def aufloesen(inp) -> dict:
    """Rohrgeometrie und λ-Werte aus den Eingaben (Längen in m)."""
    if inp["rohr"] == "frei":
        da, s = inp["da"].to("m").magnitude, inp["s"].to("m").magnitude
        auto_mat, rohr_name = "stahl", f"d_a = {inp['da'].to('mm').magnitude:g} mm".replace(".", ",")
    else:
        da_mm, s_mm, auto_mat = rohr(inp["rohr"])
        da, s = da_mm / 1000, s_mm / 1000
        rohr_name = inp["rohr"].split(":", 1)[1]
    if inp["werkstoff"] == "auto":
        mat = werkstoff("b:p235gh" if auto_mat == "stahl" else "b:cu-dhp")
        lam_r, w_name = mat.lam, mat.name
    elif inp["werkstoff"] == "frei":
        lam_r, w_name = inp["lam_rohr"].to("W/(m*K)").magnitude, "λ vorgegeben"
    else:
        mat = werkstoff(inp["werkstoff"])
        lam_r, w_name = mat.lam, mat.name
    if inp["daemmstoff"] == "frei":
        lam_d, d_name = inp["lam_d"].to("W/(m*K)").magnitude, "λ vorgegeben"
    else:
        mat = werkstoff(inp["daemmstoff"])
        lam_d, d_name = mat.lam, mat.name
    return {"da": da, "s": s, "lam_r": lam_r, "werkstoff": w_name, "lam_d": lam_d, "daemmstoff": d_name,
            "daemm": inp["daemm"].to("m").magnitude, "rohr": rohr_name, "kunststoff": lam_r < 1.0}


def querschnitt_svg(daemm_mm: float, label: str = "") -> str:
    s = Svg()
    cx, cy = 150, 110
    r_rohr = 34
    r_d = r_rohr + (min(60.0, daemm_mm) if daemm_mm > 0 else 0) * 0.9
    if daemm_mm > 0:
        s.circle(cx, cy, r_d, fill="#eef3f8")
        s.text(cx + r_d + 8, cy - r_d + 12, "Dämmung", 11, MUTED, "start")
    s.circle(cx, cy, r_rohr, fill="#9aa7b4")
    s.circle(cx, cy, r_rohr - 5, fill="#dce6f1")
    s.text(cx, cy + 4, "θ_m", 13, INK, italic=True)
    s.text(cx + r_d + 8, cy + 30, "θ_a", 13, INK, "start", True)
    if label:
        s.text(cx, 210, label, 11, MUTED)
    return s.render()
