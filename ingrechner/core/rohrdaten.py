"""Rohrabmessungen für die Wärmeverlustrechner (Außendurchmesser × Wanddicke in mm)."""

from __future__ import annotations

# Stahlrohre: DN 10–100 Gewinderohr mittelschwer DIN EN 10255, darüber DIN EN 10220
STAHL = {
    "DN 10": (17.2, 2.3), "DN 15": (21.3, 2.6), "DN 20": (26.9, 2.6), "DN 25": (33.7, 3.2),
    "DN 32": (42.4, 3.2), "DN 40": (48.3, 3.2), "DN 50": (60.3, 3.6), "DN 65": (76.1, 3.6),
    "DN 80": (88.9, 4.0), "DN 100": (114.3, 4.5), "DN 125": (139.7, 4.0), "DN 150": (168.3, 4.5),
    "DN 200": (219.1, 6.3), "DN 250": (273.0, 6.3), "DN 300": (323.9, 7.1),
}
# Kupferrohre DIN EN 1057
KUPFER = {
    "Cu 12×1": (12.0, 1.0), "Cu 15×1": (15.0, 1.0), "Cu 18×1": (18.0, 1.0), "Cu 22×1": (22.0, 1.0),
    "Cu 28×1,5": (28.0, 1.5), "Cu 35×1,5": (35.0, 1.5), "Cu 42×1,5": (42.0, 1.5), "Cu 54×2": (54.0, 2.0),
    "Cu 64×2": (64.0, 2.0), "Cu 76,1×2": (76.1, 2.0), "Cu 88,9×2": (88.9, 2.0), "Cu 108×2,5": (108.0, 2.5),
}
# PE 100 Druckrohre DIN EN 12201-2: Außendurchmesser -> Wanddicke je SDR
_PE_DA = (32, 40, 50, 63, 75, 90, 110, 125, 140, 160, 180, 200, 225, 250, 280, 315, 355, 400)
PE100 = {
    11: dict(zip(_PE_DA, (2.9, 3.7, 4.6, 5.8, 6.8, 8.2, 10.0, 11.4, 12.7, 14.6, 16.4, 18.2, 20.5, 22.7, 25.4,
                          28.6, 32.2, 36.3))),
    17: dict(zip(_PE_DA, (2.0, 2.4, 3.0, 3.8, 4.5, 5.4, 6.6, 7.4, 8.3, 9.5, 10.7, 11.9, 13.4, 14.8, 16.6,
                          18.7, 21.1, 23.7))),
}

LAMBDA_ROHR = {"stahl": 50.0, "kupfer": 380.0, "edelstahl": 15.0, "pe": 0.4}

def _fmt(d: float, s: float) -> str:
    return f"{d:g} × {s:g} mm".replace(".", ",")


def rohr_optionen() -> list[tuple[str, str]]:
    opts = [(f"st:{k}", f"Stahl {k}  ({_fmt(*v)})") for k, v in STAHL.items()]
    opts += [(f"cu:{k}", f"Kupfer {k.replace('Cu ', '')} mm") for k in KUPFER]
    opts.append(("frei", "Benutzerdefiniert"))
    return opts


def rohr(key: str) -> tuple[float, float, str]:
    """(Außendurchmesser mm, Wanddicke mm, Werkstoff) für einen Auswahlschlüssel."""
    kind, _, name = key.partition(":")
    if kind == "st":
        d, s = STAHL[name]
        return d, s, "stahl"
    if kind == "cu":
        d, s = KUPFER[name]
        return d, s, "kupfer"
    raise KeyError(key)


# Emissionsgrade der Außenoberfläche (DIN EN ISO 12241, Tab. 1 / VDI 2055, gerundet)
EMISSION = {
    "blech_alu": (0.05, "Aluminium blank"),
    "blech_alu_ox": (0.13, "Aluminium oxidiert"),
    "verzinkt": (0.26, "Stahlblech verzinkt, blank"),
    "verzinkt_staub": (0.44, "Stahlblech verzinkt, verstaubt"),
    "edelstahl": (0.15, "Edelstahl"),
    "stahl_ox": (0.80, "Stahl oxidiert / ungestrichen"),
    "anstrich": (0.93, "Anstrich, Kunststoffmantel, Dämmstoff-Oberfläche"),
}


# ------------------------------------------------- Werkstoffe aus der Datenbank
def _db_group(gruppe: str):
    from .materials import MaterialLibrary

    return [m for m in MaterialLibrary(None).builtin if m.gruppe == gruppe and m.lam]


def werkstoff_optionen() -> list[tuple[str, str]]:
    opts = [("auto", "nach Rohrauswahl (Stahl P235GH / Kupfer Cu-DHP)")]
    opts += [(m.id, f"{m.name}  (λ = {m.lam:g} W/(m·K))".replace(".", ",")) for m in _db_group("Rohrwerkstoff")]
    opts.append(("frei", "λ eingeben / aus Materialdatenbank"))
    return opts


def daemmstoff_optionen() -> list[tuple[str, str]]:
    opts = [(m.id, f"{m.name}  (λ = {m.lam:g} W/(m·K))".replace(".", ",")) for m in _db_group("Dämmstoff")]
    opts.append(("frei", "λ eingeben"))
    return opts


def werkstoff(mat_id: str):
    for m in _db_group("Rohrwerkstoff") + _db_group("Dämmstoff"):
        if m.id == mat_id:
            return m
    raise KeyError(mat_id)


# Fernwärme-Kunststoffmantelrohre (KMR) nach DIN EN 253 – typische Abmessungen:
# DN: (Stahlrohr d_a, Wanddicke, {Dämmserie: (Mantelrohr-Außendurchmesser, Mantelwanddicke)}) in mm.
# Herstellerangaben haben Vorrang.
KMR = {
    "DN 20": (26.9, 2.6, {1: (90, 2.2), 2: (110, 2.5), 3: (125, 2.5)}),
    "DN 25": (33.7, 2.6, {1: (90, 2.2), 2: (110, 2.5), 3: (125, 2.5)}),
    "DN 32": (42.4, 2.6, {1: (110, 2.5), 2: (125, 2.5), 3: (140, 3.0)}),
    "DN 40": (48.3, 2.6, {1: (110, 2.5), 2: (125, 2.5), 3: (140, 3.0)}),
    "DN 50": (60.3, 2.9, {1: (125, 2.5), 2: (140, 3.0), 3: (160, 3.0)}),
    "DN 65": (76.1, 2.9, {1: (140, 3.0), 2: (160, 3.0), 3: (180, 3.0)}),
    "DN 80": (88.9, 3.2, {1: (160, 3.0), 2: (180, 3.0), 3: (200, 3.2)}),
    "DN 100": (114.3, 3.6, {1: (200, 3.2), 2: (225, 3.4), 3: (250, 3.6)}),
    "DN 125": (139.7, 3.6, {1: (225, 3.4), 2: (250, 3.6), 3: (280, 3.9)}),
    "DN 150": (168.3, 4.0, {1: (250, 3.6), 2: (280, 3.9), 3: (315, 4.1)}),
    "DN 200": (219.1, 4.5, {1: (315, 4.1), 2: (355, 4.5), 3: (400, 4.8)}),
}
