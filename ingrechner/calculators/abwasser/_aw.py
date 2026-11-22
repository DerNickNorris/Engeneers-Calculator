"""Gemeinsame Felder der Abwasser-Rechner: Rohrauswahl (Stahl, PE 100, frei)."""

from __future__ import annotations

from ingrechner.core.model import ChoiceField, NumberField
from ingrechner.core.rohrdaten import PE100, STAHL

FREI = {"rohr": ["frei"]}


def rohr_optionen() -> list[tuple[str, str]]:
    opts = [(f"pe{sdr}:{d}", f"PE 100 SDR {sdr}  d {d} × {str(s).replace('.', ',')} mm")
            for sdr in (11, 17) for d, s in PE100[sdr].items()]
    opts += [(f"st:{k}", f"Stahl {k}  ({str(d).replace('.', ',')} × {str(s).replace('.', ',')} mm)")
             for k, (d, s) in STAHL.items()]
    opts.append(("frei", "Benutzerdefiniert (d_a, s)"))
    return opts


def rohr_felder(default: str = "pe11:160", vis: dict | None = None) -> list:
    v = dict(vis or {})
    return [
        ChoiceField("rohr", "Rohr", rohr_optionen(), default, visible_if=v or None,
                    tooltip="PE 100 nach DIN EN 12201 (SDR 11 ≙ PN 16, SDR 17 ≙ PN 10), Stahl nach EN 10255/10220"),
        NumberField("da", "Außendurchmesser", "d_a", "mm", 160, min=0, decimals=1, visible_if={**v, **FREI}),
        NumberField("s", "Wanddicke", "s", "mm", 9.5, min=0, decimals=2, visible_if={**v, **FREI}),
    ]


def rohr_geometrie(inp) -> tuple[str, float, float, float]:
    """(Bezeichnung, d_i m, d_a m, s m) aus der Rohrauswahl."""
    key = inp["rohr"]
    if key == "frei":
        da, s = inp["da"].to("mm").magnitude, inp["s"].to("mm").magnitude
        if 2 * s >= da:
            raise ValueError("Die Wanddicke muss kleiner als der halbe Außendurchmesser sein.")
        name = f"d {da:g} × {s:g} mm".replace(".", ",")
    elif key.startswith("st:"):
        name = key[3:]
        da, s = STAHL[name]
    else:
        kind, d = key.split(":")
        sdr = int(kind[2:])
        da, s = float(d), PE100[sdr][int(d)]
        name = f"PE {d}×{s:g} SDR {sdr}".replace(".", ",")
    return name, (da - 2 * s) / 1000, da / 1000, s / 1000
