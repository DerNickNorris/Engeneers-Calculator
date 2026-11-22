"""Hilfsfunktionen für den Funktionsplotter (ohne GUI, testbar)."""

from __future__ import annotations

import math
import re
from collections.abc import Callable
from dataclasses import dataclass

_SPLIT = re.compile(r"[;\t]+|\s+")


@dataclass
class XYData:
    x: list[float]
    y: list[float]
    skipped: int = 0          # nicht lesbare Zeilen (z. B. Überschriften)
    header: list[str] | None = None


def _num(text: str) -> float:
    t = text.strip().replace(" ", "")
    if "," in t and "." in t:
        t = t.replace(".", "")
    return float(t.replace(",", "."))


def parse_xy(text: str) -> XYData:
    """Liest zwei Spalten (x, y) – z. B. aus Excel kopiert.

    Trennzeichen: Tabulator, Semikolon oder Leerzeichen; Dezimalkomma erlaubt.
    Zeilen, die sich nicht lesen lassen (Überschriften), werden übersprungen.
    """
    xs: list[float] = []
    ys: list[float] = []
    skipped = 0
    header = None
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [p for p in _SPLIT.split(line) if p]
        if len(parts) < 2:
            skipped += 1
            continue
        try:
            x, y = _num(parts[0]), _num(parts[1])
        except ValueError:
            if not xs and header is None:
                header = parts[:2]
            skipped += 1
            continue
        xs.append(x)
        ys.append(y)
    return XYData(xs, ys, skipped, header)


def _percentile(sorted_vals: list[float], q: float) -> float:
    if not sorted_vals:
        return 0.0
    idx = min(len(sorted_vals) - 1, max(0, int(round(q * (len(sorted_vals) - 1)))))
    return sorted_vals[idx]


def sample(f: Callable[[float], float], xmin: float, xmax: float, n: int = 400) -> tuple[list[float], list[float]]:
    """Tastet ``f`` gleichmäßig ab.

    Polstellen (z. B. tan bei π/2) werden erkannt – Vorzeichenwechsel mit einem Sprung,
    der weit über den üblichen Schrittweiten liegt – und als Lücke (nan) dargestellt,
    damit keine senkrechten Verbindungslinien entstehen.
    """
    if n < 2:
        raise ValueError("Mindestens 2 Punkte.")
    if not xmax > xmin:
        raise ValueError("x max muss größer als x min sein.")
    step = (xmax - xmin) / (n - 1)
    xs = [xmin + i * step for i in range(n)]
    ys = [f(x) for x in xs]
    diffs = sorted(abs(b - a) for a, b in zip(ys, ys[1:]) if math.isfinite(a) and math.isfinite(b))
    if len(diffs) > 10:
        typical = _percentile(diffs, 0.5) or _percentile(diffs, 0.9) or 1e-12
        for i in range(1, n):
            a, b = ys[i - 1], ys[i]
            if math.isfinite(a) and math.isfinite(b) and (a > 0) != (b > 0) and abs(b - a) > 25 * typical:
                # Der betragsmäßig größere Punkt liegt an der Polstelle -> Lücke
                if abs(a) > abs(b):
                    ys[i - 1] = math.nan
                else:
                    ys[i] = math.nan
    return xs, ys


def robust_ylim(curves: list[list[float]]) -> tuple[float, float] | None:
    """Sinnvoller y-Bereich, wenn einzelne Ausreißer (Polstellen) die Skalierung zerstören würden.

    Gibt ``None`` zurück, wenn die automatische Skalierung passt.
    """
    vals = sorted(v for ys in curves for v in ys if math.isfinite(v))
    if len(vals) < 20:
        return None
    lo, hi = _percentile(vals, 0.02), _percentile(vals, 0.98)
    full = vals[-1] - vals[0]
    core = hi - lo
    if core <= 0 or full <= 4 * core:
        return None
    pad = 0.15 * core
    return lo - pad, hi + pad
