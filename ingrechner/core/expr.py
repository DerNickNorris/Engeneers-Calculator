"""Sicherer Formel-Auswerter für den wissenschaftlichen Rechner und den Funktionsplotter.

Es wird kein beliebiger Python-Code ausgeführt: Der Ausdruck wird geparst, der
Syntaxbaum gegen eine Positivliste geprüft (Zahlen, Grundrechenarten, erlaubte
Funktionen/Konstanten, Variablen) und erst dann ausgewertet.

Schreibweise (deutsch):
* Dezimaltrennzeichen Komma oder Punkt:            ``3,5 * 2``  oder  ``3.5 * 2``
* Argumente mit Semikolon (oder „Komma + Leerzeichen“): ``max(1; 2,5)`` / ``max(1, 2.5)``
* Potenz ``^`` oder ``**``, Wurzel ``sqrt(x)`` oder ``√(x)``, ``²`` ``³``
* Implizite Multiplikation: ``2pi``, ``3(4+1)``, ``(1+2)(3+4)``
* Variablen: ``a = 5``; das letzte Ergebnis heißt ``ans``
"""

from __future__ import annotations

import ast
import math
import re
from collections.abc import Callable

G_N = 9.80665


class ExprError(ValueError):
    """Verständliche Fehlermeldung für den Nutzer."""


def _fact(n: float) -> float:
    if n < 0 or n != int(n):
        raise ExprError("fact() ist nur für natürliche Zahlen definiert.")
    if n > 170:
        raise ExprError("fact(): Ergebnis zu groß (n ≤ 170).")
    return float(math.factorial(int(n)))


def _log(x: float, base: float = 10.0) -> float:
    return math.log(x, base)


def _round(x: float, n: float = 0) -> float:
    return float(round(x, int(n)))


def _sign(x: float) -> float:
    return math.copysign(1.0, x) if x != 0 else 0.0


def _functions(angle: str) -> dict[str, Callable]:
    deg = angle == "deg"
    to_rad = math.radians if deg else (lambda v: v)
    from_rad = math.degrees if deg else (lambda v: v)
    return {
        "sin": lambda v: math.sin(to_rad(v)),
        "cos": lambda v: math.cos(to_rad(v)),
        "tan": lambda v: math.tan(to_rad(v)),
        "asin": lambda v: from_rad(math.asin(v)),
        "acos": lambda v: from_rad(math.acos(v)),
        "atan": lambda v: from_rad(math.atan(v)),
        "atan2": lambda y, x: from_rad(math.atan2(y, x)),
        "sinh": math.sinh, "cosh": math.cosh, "tanh": math.tanh,
        "asinh": math.asinh, "acosh": math.acosh, "atanh": math.atanh,
        "sqrt": math.sqrt, "cbrt": lambda v: math.copysign(abs(v) ** (1 / 3), v),
        "exp": math.exp, "ln": math.log, "log": _log, "log2": math.log2,
        "abs": abs, "round": _round, "floor": lambda v: float(math.floor(v)),
        "ceil": lambda v: float(math.ceil(v)), "fact": _fact, "sign": _sign,
        "min": min, "max": max, "hypot": math.hypot, "mod": math.fmod,
        "deg": math.degrees, "rad": math.radians,
    }


CONSTANTS = {"pi": math.pi, "e": math.e, "g": G_N}
FUNCTION_NAMES = tuple(_functions("rad"))

FUNCTION_HELP = {
    "sin / cos / tan": "Winkelfunktionen (Modus DEG oder RAD)",
    "asin / acos / atan": "Umkehrfunktionen",
    "atan2(y; x)": "Winkel aus Koordinaten",
    "sinh / cosh / tanh": "Hyperbelfunktionen",
    "sqrt(x) · √x · cbrt(x)": "Quadrat- / Kubikwurzel",
    "x^n · x² · x³": "Potenz",
    "exp(x) · ln(x)": "e-Funktion, natürlicher Logarithmus",
    "log(x) · log(x; b) · log2(x)": "Logarithmus zur Basis 10 / b / 2",
    "abs · sign · floor · ceil": "Betrag, Vorzeichen, Ab-/Aufrunden",
    "round(x; n)": "Runden auf n Stellen",
    "fact(n)": "Fakultät n!",
    "min(…) · max(…) · hypot(a; b)": "Minimum, Maximum, √(a²+b²)",
    "mod(a; b)": "Divisionsrest",
    "deg(x) · rad(x)": "Bogenmaß ↔ Grad",
    "pi · e · g": "Konstanten (g = 9,80665 m/s²)",
}

_BINOPS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.Mod, ast.FloorDiv)
_UNOPS = (ast.UAdd, ast.USub)
_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_ASSIGN_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=(?!=)(.*)$", re.S)
_NUM_BEFORE = re.compile(r"\b(\d+(?:\.\d*)?(?:[eE][+-]?\d+)?)(?![\d.]|[eE][+-]?\d)(?=\s*[A-Za-z_(])")
_PAREN_BEFORE = re.compile(r"\)(?=\s*[\w(])")


def preprocess(text: str) -> str:
    s = text.strip()
    for a, b in (("×", "*"), ("·", "*"), ("÷", "/"), ("−", "-"), ("π", "pi"), ("²", "^2"), ("³", "^3")):
        s = s.replace(a, b)
    s = re.sub(r"√\s*(\d+(?:[.,]\d+)?|[A-Za-z_]\w*)", r"sqrt(\1)", s)   # √2, √x
    s = s.replace("√", "sqrt")                                           # √(…)
    s = re.sub(r",\s+", ";", s)           # "Komma + Leerzeichen" = Argumenttrenner
    s = s.replace(",", ".").replace(";", ",")
    s = s.replace("^", "**")
    s = _NUM_BEFORE.sub(r"\1*", s)        # 2pi -> 2*pi, 3(…) -> 3*(…)
    s = _PAREN_BEFORE.sub(")*", s)        # (…)(…) -> (…)*(…)
    return s


class _FloatConstants(ast.NodeTransformer):
    """Ganzzahl-Literale als float auswerten: verhindert riesige Ganzzahlen (9**9**9)."""

    def visit_Constant(self, node: ast.Constant) -> ast.AST:
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise ExprError("Nur Zahlen sind als Werte erlaubt.")
        return ast.copy_location(ast.Constant(float(node.value)), node)


class Evaluator:
    def __init__(self, angle: str = "rad") -> None:
        self.variables: dict[str, float] = {}
        self.ans: float = 0.0
        self.angle = angle

    @property
    def angle(self) -> str:
        return self._angle

    @angle.setter
    def angle(self, mode: str) -> None:
        if mode not in ("deg", "rad"):
            raise ValueError(mode)
        self._angle = mode
        self._funcs = _functions(mode)

    # ------------------------------------------------------------ Prüfung
    def _check(self, tree: ast.AST, names: set[str]) -> None:
        for node in ast.walk(tree):
            if isinstance(node, (ast.Expression, ast.Load, *_BINOPS, *_UNOPS)):
                continue
            if isinstance(node, ast.BinOp):
                if not isinstance(node.op, _BINOPS):
                    raise ExprError("Operator nicht erlaubt.")
            elif isinstance(node, ast.UnaryOp):
                if not isinstance(node.op, _UNOPS):
                    raise ExprError("Operator nicht erlaubt.")
            elif isinstance(node, ast.Constant):
                pass
            elif isinstance(node, ast.Call):
                if not isinstance(node.func, ast.Name) or node.func.id not in self._funcs:
                    name = getattr(node.func, "id", "?")
                    raise ExprError(f"Unbekannte Funktion „{name}“.")
                if node.keywords:
                    raise ExprError("Benannte Argumente sind nicht erlaubt.")
                if any(isinstance(a, ast.Starred) for a in node.args):
                    raise ExprError("Ungültiges Argument.")
            elif isinstance(node, ast.Name):
                if node.id not in names and node.id not in self._funcs:
                    raise ExprError(f"Unbekannter Name „{node.id}“.")
            else:
                raise ExprError("Ungültiger Ausdruck.")

    def _compile(self, text: str, extra: set[str]) -> object:
        src = preprocess(text)
        if not src:
            raise ExprError("Leerer Ausdruck.")
        if len(src) > 2000:
            raise ExprError("Ausdruck zu lang.")
        try:
            tree = ast.parse(src, mode="eval")
        except SyntaxError:
            raise ExprError("Syntaxfehler – Klammern und Operatoren prüfen.") from None
        tree = ast.fix_missing_locations(_FloatConstants().visit(tree))
        names = set(CONSTANTS) | set(self.variables) | {"ans"} | extra
        self._check(tree, names)
        return compile(tree, "<ausdruck>", "eval")

    def _env(self) -> dict[str, object]:
        return {"__builtins__": {}, **self._funcs, **CONSTANTS, **self.variables, "ans": self.ans}

    @staticmethod
    def _run(code, env) -> float:
        try:
            value = eval(code, env)  # noqa: S307 - Syntaxbaum wurde gegen Positivliste geprüft
        except ZeroDivisionError:
            raise ExprError("Division durch null.") from None
        except OverflowError:
            raise ExprError("Zahl zu groß.") from None
        except ExprError:
            raise
        except ValueError:
            raise ExprError("Außerhalb des Definitionsbereichs (z. B. Wurzel oder Logarithmus "
                            "einer negativen Zahl).") from None
        except TypeError:
            raise ExprError("Falsche Anzahl von Argumenten – Argumente mit „;“ trennen.") from None
        if isinstance(value, complex) or not isinstance(value, (int, float)):
            raise ExprError("Ergebnis ist keine reelle Zahl.")
        value = float(value)
        if math.isinf(value):
            raise ExprError("Zahl zu groß.")
        return value

    # --------------------------------------------------------------- API
    def evaluate(self, text: str) -> tuple[str | None, float]:
        """Wertet ``text`` aus. Bei ``name = ausdruck`` wird die Variable gesetzt.

        Rückgabe: (Variablenname oder None, Ergebnis). Das Ergebnis wird zu ``ans``.
        """
        target = None
        m = _ASSIGN_RE.match(text)
        if m:
            target, text = m.group(1), m.group(2)
            if target in self._funcs or target in CONSTANTS or target == "ans":
                raise ExprError(f"„{target}“ ist reserviert und kann nicht belegt werden.")
        value = self._run(self._compile(text, set()), self._env())
        if target:
            self.variables[target] = value
        self.ans = value
        return target, value

    def function(self, text: str, var: str = "x") -> Callable[[float], float]:
        """Kompiliert einen Ausdruck in ``var`` zu einer Funktion (für Plots).

        Außerhalb des Definitionsbereichs liefert die Funktion ``nan``.
        """
        code = self._compile(text, {var})
        env = self._env()

        def f(x: float) -> float:
            env[var] = float(x)
            try:
                return self._run(code, env)
            except ExprError:
                return math.nan

        f(1.0)  # Früh erkennen, ob z. B. Argumentanzahl falsch ist (TypeError -> nan ok)
        return f


def format_result(value: float, digits: int = 12) -> str:
    """Ergebnis deutsch formatieren: ``1234,5`` / ``1,5E-07``."""
    if value == 0:
        return "0"
    if abs(value) < 1e15 and value == int(value):
        return str(int(value))
    text = f"{value:.{digits}g}"
    if "e" in text:
        mant, exp = text.split("e")
        return f"{mant.replace('.', ',')}E{int(exp):+d}"
    return text.replace(".", ",")
