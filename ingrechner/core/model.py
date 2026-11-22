"""Basisklassen für Rechenmodule.

Ein Rechenmodul ist eine Unterklasse von :class:`Calculator`. Es beschreibt seine
Eingabefelder deklarativ und implementiert :meth:`Calculator.compute`. Die
Oberfläche, Validierung, Speicherung und der PDF-Bericht werden generisch aus
dieser Beschreibung erzeugt – ein neues Modul braucht keinen GUI-Code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .units import Q_, fmt_num, pretty_unit


class Level(Enum):
    INFO = "info"
    WARNUNG = "warnung"
    FEHLER = "fehler"


@dataclass
class NumberField:
    key: str
    label: str
    symbol: str
    unit: str
    default: float
    min: float | None = None
    max: float | None = None
    min_inclusive: bool = False
    decimals: int = 3
    tooltip: str = ""
    visible_if: dict[str, list[str]] | None = None

    def check(self, value: float) -> str | None:
        """Gibt eine Fehlermeldung zurück, wenn ``value`` außerhalb des Bereichs liegt."""
        unit = pretty_unit(self.unit)
        if self.min is not None:
            if self.min_inclusive and value < self.min:
                return f"{self.symbol} muss ≥ {fmt_num(self.min, 3)} {unit} sein."
            if not self.min_inclusive and value <= self.min:
                return f"{self.symbol} muss > {fmt_num(self.min, 3)} {unit} sein."
        if self.max is not None and value > self.max:
            return f"{self.symbol} darf höchstens {fmt_num(self.max, 3)} {unit} sein."
        return None


@dataclass
class ChoiceField:
    key: str
    label: str
    options: list[tuple[str, str]]  # (Wert, Anzeigetext)
    default: str
    tooltip: str = ""
    visible_if: dict[str, list[str]] | None = None

    def label_for(self, value: str) -> str:
        return dict(self.options).get(value, value)


Field = NumberField | ChoiceField


@dataclass
class Step:
    """Ein Schritt des Rechenwegs: Formel → eingesetzte Werte → Ergebnis."""

    title: str
    formula: str
    substitution: str
    result: str


@dataclass
class ResultValue:
    key: str
    label: str
    symbol: str
    value: float
    unit: str
    decimals: int = 3
    highlight: bool = False

    @property
    def text(self) -> str:
        return f"{fmt_num(self.value, self.decimals)} {pretty_unit(self.unit)}".strip()


@dataclass
class Message:
    level: Level
    text: str


@dataclass
class CalcResult:
    values: list[ResultValue] = field(default_factory=list)
    steps: list[Step] = field(default_factory=list)
    messages: list[Message] = field(default_factory=list)
    field_errors: dict[str, str] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.field_errors and not any(m.level is Level.FEHLER for m in self.messages)

    def value(self, key: str) -> float:
        for rv in self.values:
            if rv.key == key:
                return rv.value
        raise KeyError(key)


class Calculator:
    """Basisklasse aller Rechenmodule."""

    id: str = ""
    title: str = ""
    category: str = ""          # Fachgebiet, z. B. "Maschinenbau"
    description: str = ""
    norm: str = ""              # Normbezug / Quelle
    keywords: tuple[str, ...] = ()
    fields: list[Field] = []
    # Feldschlüssel -> Materialeigenschaft (siehe core.materials.PROPERTIES); aktiviert
    # die Schaltfläche „Werkstoff aus Datenbank“ in der Oberfläche.
    material_map: dict[str, str] = {}
    # Optional (Auswahlfeld, Wert): wird beim Übernehmen eines Werkstoffs gesetzt, z. B. ("werkstoff", "frei"),
    # damit der übernommene Wert statt einer Voreinstellung verwendet wird.
    material_select: tuple[str, str] | None = None
    disclaimer: str = (
        "Vereinfachtes Rechenverfahren. Ergebnisse sind vor Verwendung in "
        "Nachweisen von fachkundiger Stelle gegen die Originalnorm zu prüfen."
    )

    def __init__(self) -> None:
        self._steps: list[Step] = []
        self._values: list[ResultValue] = []
        self._messages: list[Message] = []

    # ------------------------------------------------------------------ API
    def defaults(self) -> dict[str, Any]:
        return {f.key: f.default for f in self.fields}

    def field(self, key: str) -> Field:
        for f in self.fields:
            if f.key == key:
                return f
        raise KeyError(key)

    def is_visible(self, f: Field, raw: dict[str, Any]) -> bool:
        if not f.visible_if:
            return True
        return all(raw.get(k) in allowed for k, allowed in f.visible_if.items())

    def run(self, raw: dict[str, Any]) -> CalcResult:
        """Validiert die Rohwerte (Zahlen in Feldeinheit), rechnet und liefert das Ergebnis."""
        values = self.defaults() | dict(raw)
        errors: dict[str, str] = {}
        inp: dict[str, Any] = {}
        for f in self.fields:
            v = values[f.key]
            if isinstance(f, ChoiceField):
                if v not in dict(f.options):
                    errors[f.key] = f"Ungültige Auswahl für {f.label}."
                inp[f.key] = v
                continue
            if not self.is_visible(f, values):
                inp[f.key] = Q_(float(f.default), f.unit) if f.unit else float(f.default)
                continue
            try:
                num = float(v)
            except (TypeError, ValueError):
                errors[f.key] = f"{f.label}: keine gültige Zahl."
                continue
            msg = f.check(num)
            if msg:
                errors[f.key] = msg
            inp[f.key] = Q_(num, f.unit) if f.unit else num

        if errors:
            return CalcResult(field_errors=errors)

        self._steps, self._values, self._messages = [], [], []
        try:
            self.compute(inp)
        except ZeroDivisionError:
            self.error("Division durch null – bitte Eingaben prüfen.")
        except ValueError as exc:
            self.error(str(exc))
        return CalcResult(list(self._values), list(self._steps), list(self._messages))

    # ------------------------------------------------ zu überschreiben
    def compute(self, inp: dict[str, Any]) -> None:  # pragma: no cover - abstrakt
        raise NotImplementedError

    def sketch_svg(self, raw: dict[str, Any]) -> str | None:
        """Optionale Systemskizze als SVG-Text (Größe 360×220)."""
        return None

    def plot(self, fig, raw: dict[str, Any], result: CalcResult) -> bool:
        """Optional: Diagramm in eine matplotlib-Figure zeichnen. True, wenn gezeichnet."""
        return False

    # ------------------------------------------------ Hilfen für compute()
    def step(self, title: str, formula: str, substitution: str, result: str) -> None:
        self._steps.append(Step(title, formula, substitution, result))

    def result(self, key: str, label: str, symbol: str, quantity, unit: str,
               decimals: int = 3, highlight: bool = False) -> float:
        value = quantity.to(unit).magnitude if unit else float(quantity)
        self._values.append(ResultValue(key, label, symbol, float(value), unit, decimals, highlight))
        return float(value)

    def info(self, text: str) -> None:
        self._messages.append(Message(Level.INFO, text))

    def warn(self, text: str) -> None:
        self._messages.append(Message(Level.WARNUNG, text))

    def error(self, text: str) -> None:
        self._messages.append(Message(Level.FEHLER, text))
