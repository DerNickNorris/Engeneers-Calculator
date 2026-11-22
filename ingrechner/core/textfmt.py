"""Hilfen, um Symbole wie ``I_y`` als Rich-Text mit Tiefstellung auszugeben."""

from __future__ import annotations

import re
from xml.sax.saxutils import escape

# Tiefgestellt werden Buchstaben/Ziffern (auch griechisch) und z. B. "z,max" – keine Hochzahlen wie ²
_SUB = re.compile(r"_([0-9A-Za-zÄÖÜäöüα-ωΑ-Ω]+(?:,[A-Za-zα-ω]+)?)")


def rich(text: str) -> str:
    """``σ_zul = R_e / S`` -> ``σ<sub>zul</sub> = R<sub>e</sub> / S`` (HTML-escaped)."""
    return _SUB.sub(r"<sub>\1</sub>", escape(text))


def plain(text: str) -> str:
    """Für CSV/Excel: Unterstriche bleiben als Lesehilfe erhalten."""
    return text
