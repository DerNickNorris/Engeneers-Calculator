"""Einheitlicher, ruhiger Diagrammstil (Grau/Blau) für App und Bericht."""

from __future__ import annotations

import matplotlib as mpl

RC = {
    "font.family": "DejaVu Sans",
    "font.size": 9,
    "axes.edgecolor": "#9aa7b4",
    "axes.labelcolor": "#2b3a4a",
    "axes.titlesize": 10,
    "axes.titleweight": "bold",
    "axes.titlecolor": "#1f4e79",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "xtick.color": "#4a5a6a",
    "ytick.color": "#4a5a6a",
    "grid.color": "#c9d3de",
    "legend.frameon": False,
    "axes.formatter.use_locale": False,
}


def apply_style(fig) -> None:
    mpl.rcParams.update(RC)
    fig.set_facecolor("white")
