"""Zentrale Einheiten-Registry (pint) und deutsche Zahlen-/Einheitenformatierung."""

from __future__ import annotations

import math

import pint

ureg = pint.UnitRegistry()
ureg.define("var = volt_ampere")      # Blindleistung (Voltampere reaktiv)
Q_ = ureg.Quantity

_SUPERSCRIPT = {"2": "²", "3": "³", "4": "⁴", "-1": "⁻¹", "-2": "⁻²"}


def pretty_unit(unit: str) -> str:
    """Wandelt eine pint-Einheit wie ``N/mm**2`` in Anzeigeform ``N/mm²`` um."""
    if not unit:
        return ""
    text = unit
    for exp, sup in sorted(_SUPERSCRIPT.items(), key=lambda kv: -len(kv[0])):
        text = text.replace(f"**{exp}", sup)
    text = text.replace(" * ", "·").replace("*", "·")
    text = text.replace("milliohm", "mΩ").replace("ohm", "Ω").replace("degC", "°C").replace("percent", "%").replace("degree", "°").replace("microfarad", "µF").replace("hour", "h").replace("liter", "l").replace("minute", "min")
    return text


def unit_html(unit: str) -> str:
    """Einheit als ReportLab/Qt-Markup mit <super>-Hochstellung (für PDFs)."""
    if not unit:
        return ""
    text = unit
    for exp in ("-2", "-1", "4", "3", "2"):
        text = text.replace(f"**{exp}", f"<super>{exp.replace('-', '−')}</super>")
    text = text.replace(" * ", "·").replace("*", "·")
    text = text.replace("milliohm", "mΩ").replace("ohm", "Ω").replace("degC", "°C").replace("percent", "%").replace("degree", "°").replace("microfarad", "µF").replace("hour", "h").replace("liter", "l").replace("minute", "min")
    return text


def fmt_num(value: float, decimals: int = 3) -> str:
    """Formatiert eine Zahl deutsch: Dezimalkomma, Leerzeichen als Tausendertrenner.

    Sehr große/kleine Beträge werden in wissenschaftlicher Schreibweise ausgegeben.
    """
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "–"
    if math.isinf(value):
        return "∞"
    mag = abs(value)
    if mag != 0 and (mag >= 1e9 or mag < 10 ** (-decimals - 1)):
        mant, exp = f"{value:.{max(decimals, 2)}e}".split("e")
        return f"{mant.replace('.', ',')}·10^{int(exp)}"
    text = f"{value:,.{decimals}f}"
    text = text.replace(",", " ").replace(".", ",")
    # Tausendertrennung erst ab 10 000 (DIN 1333 Empfehlung)
    int_part = text.split(",")[0].replace("-", "").replace(" ", "")
    if len(int_part) <= 4:
        text = text.replace(" ", "")
    return text


def fmt_q(quantity, unit: str, decimals: int = 3) -> str:
    """Formatiert eine pint-Größe in der gewünschten Einheit, z. B. ``5,000 kN·m``."""
    value = quantity.to(unit).magnitude if unit else float(quantity)
    suffix = pretty_unit(unit)
    return f"{fmt_num(value, decimals)} {suffix}".strip()


def parse_num(text: str) -> float:
    """Liest eine Zahl mit Komma oder Punkt als Dezimaltrenner."""
    cleaned = text.strip().replace(" ", "").replace(" ", "")
    if "," in cleaned and "." in cleaned:
        cleaned = cleaned.replace(".", "")  # 1.234,5 -> 1234,5
    cleaned = cleaned.replace(",", ".")
    return float(cleaned)
