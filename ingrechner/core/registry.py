"""Findet alle Rechenmodule im Paket ``ingrechner.calculators`` automatisch.

Neues Modul anlegen: Datei in einem Fachgebiets-Unterordner erstellen, die eine
:class:`~ingrechner.core.model.Calculator`-Unterklasse enthält. Fertig.
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil

from .model import Calculator

CATEGORY_ORDER = ["Maschinenbau", "Bau / Statik", "Elektrotechnik", "Fluid / Thermo", "Heizung / Wärme", "Lüftung / RLT",
                  "Pumpen", "Abwasser / Klärwerk"]


def discover() -> list[type[Calculator]]:
    import ingrechner.calculators as pkg

    found: dict[str, type[Calculator]] = {}
    for info in pkgutil.walk_packages(pkg.__path__, prefix=pkg.__name__ + "."):
        module = importlib.import_module(info.name)
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if issubclass(obj, Calculator) and obj is not Calculator and obj.id:
                if obj.id in found and found[obj.id] is not obj:
                    raise RuntimeError(f"Doppelte Rechner-ID: {obj.id}")
                found[obj.id] = obj

    def sort_key(cls: type[Calculator]):
        cat = CATEGORY_ORDER.index(cls.category) if cls.category in CATEGORY_ORDER else 99
        return (cat, cls.category, cls.title)

    return sorted(found.values(), key=sort_key)


def by_id() -> dict[str, type[Calculator]]:
    return {cls.id: cls for cls in discover()}
