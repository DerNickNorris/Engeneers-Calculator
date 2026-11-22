"""Einheitenumrechnung auf Basis von pint – Kategorien mit kuratierten Einheiten."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .units import Q_, ureg


@dataclass(frozen=True)
class UnitDef:
    expr: str     # pint-Ausdruck
    label: str    # Anzeige
    name: str     # Klartext


def _u(expr: str, label: str, name: str) -> UnitDef:
    return UnitDef(expr, label, name)


CATEGORIES: dict[str, list[UnitDef]] = {
    "Länge": [
        _u("micrometer", "µm", "Mikrometer"), _u("mm", "mm", "Millimeter"), _u("cm", "cm", "Zentimeter"),
        _u("dm", "dm", "Dezimeter"), _u("m", "m", "Meter"), _u("km", "km", "Kilometer"),
        _u("inch", "in", "Zoll"), _u("foot", "ft", "Fuß"), _u("yard", "yd", "Yard"),
        _u("mile", "mi", "Meile"), _u("nautical_mile", "sm", "Seemeile"),
    ],
    "Fläche": [
        _u("mm**2", "mm²", "Quadratmillimeter"), _u("cm**2", "cm²", "Quadratzentimeter"),
        _u("m**2", "m²", "Quadratmeter"), _u("hectare", "ha", "Hektar"), _u("km**2", "km²", "Quadratkilometer"),
        _u("inch**2", "in²", "Quadratzoll"), _u("foot**2", "ft²", "Quadratfuß"),
    ],
    "Volumen": [
        _u("mm**3", "mm³", "Kubikmillimeter"), _u("cm**3", "cm³", "Kubikzentimeter"),
        _u("milliliter", "ml", "Milliliter"), _u("liter", "l", "Liter"), _u("m**3", "m³", "Kubikmeter"),
        _u("inch**3", "in³", "Kubikzoll"), _u("foot**3", "ft³", "Kubikfuß"),
        _u("gallon", "gal (US)", "US-Gallone"), _u("imperial_gallon", "gal (UK)", "Imp. Gallone"),
    ],
    "Masse": [
        _u("mg", "mg", "Milligramm"), _u("g", "g", "Gramm"), _u("kg", "kg", "Kilogramm"),
        _u("metric_ton", "t", "Tonne"), _u("ounce", "oz", "Unze"), _u("pound", "lb", "Pfund (US)"),
    ],
    "Kraft": [
        _u("N", "N", "Newton"), _u("daN", "daN", "Dekanewton"), _u("kN", "kN", "Kilonewton"),
        _u("MN", "MN", "Meganewton"), _u("kilogram_force", "kp", "Kilopond"),
        _u("pound_force", "lbf", "Pound-force"), _u("kip", "kip", "Kilopound-force"),
    ],
    "Druck / Spannung": [
        _u("Pa", "Pa", "Pascal"), _u("hPa", "hPa", "Hektopascal"), _u("kPa", "kPa", "Kilopascal"),
        _u("MPa", "MPa", "Megapascal"), _u("N/mm**2", "N/mm²", "Newton je mm²"),
        _u("kN/m**2", "kN/m²", "Kilonewton je m²"), _u("mbar", "mbar", "Millibar"), _u("bar", "bar", "Bar"),
        _u("atm", "atm", "Phys. Atmosphäre"), _u("psi", "psi", "Pound je in²"),
        _u("mmHg", "mmHg", "Millimeter Quecksilbersäule"), _u("m_H2O", "mWS", "Meter Wassersäule"),
    ],
    "Energie / Arbeit": [
        _u("J", "J", "Joule"), _u("kJ", "kJ", "Kilojoule"), _u("MJ", "MJ", "Megajoule"),
        _u("N*m", "N·m", "Newtonmeter"), _u("W*h", "Wh", "Wattstunde"), _u("kW*h", "kWh", "Kilowattstunde"),
        _u("MW*h", "MWh", "Megawattstunde"), _u("calorie", "cal", "Kalorie"),
        _u("kilocalorie", "kcal", "Kilokalorie"), _u("Btu", "BTU", "British thermal unit"),
    ],
    "Leistung": [
        _u("W", "W", "Watt"), _u("kW", "kW", "Kilowatt"), _u("MW", "MW", "Megawatt"),
        _u("metric_horsepower", "PS", "Pferdestärke"), _u("horsepower", "hp", "Horsepower (mech.)"),
        _u("kilocalorie/hour", "kcal/h", "Kilokalorie je Stunde"), _u("Btu/hour", "BTU/h", "BTU je Stunde"),
    ],
    "Drehmoment": [
        _u("N*mm", "N·mm", "Newtonmillimeter"), _u("N*m", "N·m", "Newtonmeter"),
        _u("kN*m", "kN·m", "Kilonewtonmeter"), _u("pound_force*inch", "lbf·in", "Pound-force-Inch"),
        _u("pound_force*foot", "lbf·ft", "Pound-force-Foot"),
    ],
    "Geschwindigkeit": [
        _u("m/s", "m/s", "Meter je Sekunde"), _u("m/min", "m/min", "Meter je Minute"),
        _u("km/h", "km/h", "Kilometer je Stunde"), _u("foot/s", "ft/s", "Fuß je Sekunde"),
        _u("mile/hour", "mph", "Meilen je Stunde"), _u("knot", "kn", "Knoten"),
    ],
    "Volumenstrom": [
        _u("m**3/s", "m³/s", "Kubikmeter je Sekunde"), _u("m**3/h", "m³/h", "Kubikmeter je Stunde"),
        _u("liter/s", "l/s", "Liter je Sekunde"), _u("liter/min", "l/min", "Liter je Minute"),
        _u("liter/hour", "l/h", "Liter je Stunde"), _u("gallon/min", "gpm (US)", "US-Gallonen je Minute"),
    ],
    "Massenstrom": [
        _u("kg/s", "kg/s", "Kilogramm je Sekunde"), _u("kg/hour", "kg/h", "Kilogramm je Stunde"),
        _u("metric_ton/hour", "t/h", "Tonnen je Stunde"), _u("pound/hour", "lb/h", "Pfund je Stunde"),
    ],
    "Dichte": [
        _u("kg/m**3", "kg/m³", "Kilogramm je m³"), _u("g/cm**3", "g/cm³", "Gramm je cm³"),
        _u("kg/dm**3", "kg/dm³", "Kilogramm je dm³"), _u("metric_ton/m**3", "t/m³", "Tonnen je m³"),
        _u("pound/foot**3", "lb/ft³", "Pfund je ft³"),
    ],
    "Temperatur": [
        _u("degC", "°C", "Grad Celsius"), _u("K", "K", "Kelvin"), _u("degF", "°F", "Grad Fahrenheit"),
        _u("degR", "°R", "Grad Rankine"),
    ],
    "Temperaturdifferenz": [
        _u("K", "K", "Kelvin"), _u("delta_degC", "Δ°C", "Grad Celsius (Differenz)"),
        _u("delta_degF", "Δ°F", "Grad Fahrenheit (Differenz)"),
    ],
    "Winkel": [
        _u("degree", "°", "Grad"), _u("radian", "rad", "Radiant"), _u("gradian", "gon", "Gon"),
        _u("arcminute", "′", "Winkelminute"), _u("arcsecond", "″", "Winkelsekunde"),
        _u("turn", "U", "Umdrehung"),
    ],
    "Drehzahl / Frequenz": [
        _u("revolution/minute", "1/min", "Umdrehungen je Minute"), _u("revolution/second", "1/s", "Umdrehungen je Sekunde"),
        _u("Hz", "Hz", "Hertz"), _u("radian/second", "rad/s", "Winkelgeschwindigkeit"),
    ],
    "Zeit": [
        _u("ms", "ms", "Millisekunde"), _u("s", "s", "Sekunde"), _u("minute", "min", "Minute"),
        _u("hour", "h", "Stunde"), _u("day", "d", "Tag"), _u("week", "Wo", "Woche"),
        _u("year", "a", "Jahr (365,25 d)"),
    ],
    "Dyn. Viskosität": [
        _u("Pa*s", "Pa·s", "Pascalsekunde"), _u("mPa*s", "mPa·s", "Millipascalsekunde"),
        _u("poise", "P", "Poise"), _u("centipoise", "cP", "Centipoise"),
    ],
    "Kin. Viskosität": [
        _u("m**2/s", "m²/s", "Quadratmeter je Sekunde"), _u("mm**2/s", "mm²/s", "Quadratmillimeter je Sekunde"),
        _u("stokes", "St", "Stokes"), _u("centistokes", "cSt", "Centistokes"),
    ],
    "Flächenmoment 2. Grades": [
        _u("mm**4", "mm⁴", "Millimeter hoch 4"), _u("cm**4", "cm⁴", "Zentimeter hoch 4"),
        _u("m**4", "m⁴", "Meter hoch 4"), _u("inch**4", "in⁴", "Zoll hoch 4"),
    ],
    "Widerstandsmoment": [
        _u("mm**3", "mm³", "Millimeter hoch 3"), _u("cm**3", "cm³", "Zentimeter hoch 3"),
        _u("m**3", "m³", "Meter hoch 3"), _u("inch**3", "in³", "Zoll hoch 3"),
    ],
    "Wärmeleitfähigkeit": [
        _u("W/(m*K)", "W/(m·K)", "Watt je Meter und Kelvin"),
        _u("Btu/(hour*foot*delta_degF)", "BTU/(h·ft·°F)", "BTU je Stunde, Fuß und °F"),
    ],
}


class ConversionError(ValueError):
    pass


def convert(value: float, src: str, dst: str) -> float:
    """Rechnet ``value`` von ``src`` nach ``dst`` um (pint-Ausdrücke)."""
    try:
        return float(Q_(value, src).to(dst).magnitude)
    except Exception as exc:  # pint wirft verschiedene Fehlertypen
        raise ConversionError(f"Umrechnung {src} → {dst} nicht möglich: {exc}") from None


def convert_all(value: float, category: str, src: str) -> list[tuple[UnitDef, float]]:
    return [(u, convert(value, src, u.expr)) for u in CATEGORIES[category]]


# ------------------------------------------------------------- Freitext
_LABEL_TO_EXPR = {}
for _units in CATEGORIES.values():
    for _ud in _units:
        _LABEL_TO_EXPR.setdefault(_ud.label, _ud.expr)
# Zusätzliche, gebräuchliche Schreibweisen
_LABEL_TO_EXPR.update({"°C": "degC", "°F": "degF", "°": "degree", "PS": "metric_horsepower",
                       "kp": "kilogram_force", "mWS": "m_H2O", "U/min": "revolution/minute",
                       "1/min": "revolution/minute", "rpm": "revolution/minute", "t": "metric_ton",
                       "l": "liter", "kWh": "kW*h", "Wh": "W*h", "h": "hour", "min": "minute",
                       "N/mm²": "N/mm**2", "gal": "gallon"})

_FREE_RE = re.compile(
    r"^\s*([-+]?\d[\d\s]*(?:[.,]\d+)?(?:[eE][-+]?\d+)?)\s*(.+?)\s+(?:in|nach|zu|->|→|to)\s+(.+?)\s*$")


def _unit_expr(text: str) -> str:
    t = text.strip()
    if t in _LABEL_TO_EXPR:
        return _LABEL_TO_EXPR[t]
    t = t.replace("²", "**2").replace("³", "**3").replace("⁴", "**4").replace("·", "*").replace("^", "**")
    return _LABEL_TO_EXPR.get(t, t)


def parse_free(text: str) -> tuple[float, str, float, str]:
    """Freitext wie ``3,5 bar in psi`` oder ``100 °C nach °F``.

    Rückgabe: (Wert, Quell-Einheit, Ergebnis, Ziel-Einheit) – Einheiten wie eingegeben.
    """
    m = _FREE_RE.match(text)
    if not m:
        raise ConversionError("Format: „<Zahl> <Einheit> in <Einheit>“, z. B. „3,5 bar in psi“.")
    num_txt, src, dst = m.groups()
    num = float(num_txt.replace(" ", "").replace(",", "."))
    try:
        result = convert(num, _unit_expr(src), _unit_expr(dst))
    except ConversionError:
        try:
            ureg.parse_units(_unit_expr(src))
        except Exception:
            raise ConversionError(f"Unbekannte Einheit „{src}“.") from None
        try:
            ureg.parse_units(_unit_expr(dst))
        except Exception:
            raise ConversionError(f"Unbekannte Einheit „{dst}“.") from None
        raise ConversionError(f"„{src}“ und „{dst}“ sind nicht ineinander umrechenbar.") from None
    return num, src, result, dst
