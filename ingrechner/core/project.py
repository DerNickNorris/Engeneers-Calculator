"""Projektdatei (*.irp, JSON): Kopfdaten + nummerierte Positionen (Berechnungen).

Format-Version 2: beliebig viele Positionen, auch mehrere vom selben Rechner.
Version-1-Dateien (eine Berechnung je Rechner) werden beim Laden übernommen.
"""

from __future__ import annotations

import json
import re
import uuid
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

FORMAT_VERSION = 2
FILE_SUFFIX = ".irp"


@dataclass
class ProjectMeta:
    projekt: str = ""
    nummer: str = ""
    bearbeiter: str = ""
    pruefer: str = ""
    datum: str = field(default_factory=lambda: date.today().strftime("%d.%m.%Y"))
    bemerkung: str = ""


@dataclass
class Position:
    id: str
    calc: str                       # Rechner-ID, z. B. "mb.biegung_einfeldtraeger"
    nr: str = ""                    # Positionsnummer, z. B. "1", "2.1", "A3"
    titel: str = ""                 # Bezeichnung, z. B. "Träger Achse B"
    inputs: dict[str, Any] = field(default_factory=dict)
    notiz: str = ""

    def label(self, calc_title: str = "") -> str:
        name = self.titel.strip() or calc_title
        return f"Pos. {self.nr} – {name}" if self.nr else name


def _new_id() -> str:
    return uuid.uuid4().hex[:10]


def _nr_key(nr: str) -> tuple:
    """Natürliche Sortierung: 2 < 10, 2.1 < 2.10."""
    return tuple(int(p) if p.isdigit() else p for p in re.split(r"(\d+)", nr or "") if p)


@dataclass
class Project:
    meta: ProjectMeta = field(default_factory=ProjectMeta)
    positions: list[Position] = field(default_factory=list)
    path: Path | None = None
    dirty: bool = False

    @property
    def name(self) -> str:
        if self.meta.projekt:
            return self.meta.projekt
        return self.path.stem if self.path else "Unbenanntes Projekt"

    # ----------------------------------------------------------- Positionen
    def get(self, pid: str) -> Position:
        for p in self.positions:
            if p.id == pid:
                return p
        raise KeyError(pid)

    def positions_for(self, calc_id: str) -> list[Position]:
        return [p for p in self.positions if p.calc == calc_id]

    def next_nr(self) -> str:
        """Nächste ganze Positionsnummer (höchste führende Zahl + 1)."""
        nums = []
        for p in self.positions:
            m = re.match(r"\s*(\d+)", p.nr or "")
            if m:
                nums.append(int(m.group(1)))
        return str(max(nums, default=0) + 1)

    def add_position(self, calc_id: str, inputs: dict[str, Any] | None = None, notiz: str = "",
                     nr: str | None = None, titel: str = "", after: str | None = None) -> Position:
        pos = Position(_new_id(), calc_id, self.next_nr() if nr is None else nr, titel, dict(inputs or {}), notiz)
        if after is not None:
            idx = next((i for i, p in enumerate(self.positions) if p.id == after), len(self.positions) - 1)
            self.positions.insert(idx + 1, pos)
        else:
            self.positions.append(pos)
        self.dirty = True
        return pos

    def duplicate(self, pid: str) -> Position:
        src = self.get(pid)
        titel = f"{src.titel} (Kopie)" if src.titel else ""
        return self.add_position(src.calc, deepcopy(src.inputs), src.notiz, titel=titel, after=pid)

    def remove(self, pid: str) -> None:
        self.positions = [p for p in self.positions if p.id != pid]
        self.dirty = True

    def move(self, pid: str, delta: int) -> bool:
        i = next(i for i, p in enumerate(self.positions) if p.id == pid)
        j = i + delta
        if not 0 <= j < len(self.positions):
            return False
        self.positions[i], self.positions[j] = self.positions[j], self.positions[i]
        self.dirty = True
        return True

    def sort_by_nr(self) -> None:
        self.positions.sort(key=lambda p: _nr_key(p.nr))
        self.dirty = True

    def update(self, pid: str, *, inputs: dict[str, Any] | None = None, notiz: str | None = None,
               nr: str | None = None, titel: str | None = None) -> None:
        p = self.get(pid)
        for attr, value in (("inputs", inputs), ("notiz", notiz), ("nr", nr), ("titel", titel)):
            if value is not None and getattr(p, attr) != value:
                setattr(p, attr, dict(value) if attr == "inputs" else value)
                self.dirty = True

    # ------------------------------------------------------------- Datei
    def to_dict(self) -> dict[str, Any]:
        return {"format": "ingrechner-projekt", "version": FORMAT_VERSION,
                "meta": asdict(self.meta), "positionen": [asdict(p) for p in self.positions]}

    def save(self, path: str | Path | None = None) -> Path:
        target = Path(path) if path else self.path
        if target is None:
            raise ValueError("Kein Speicherpfad angegeben.")
        if target.suffix.lower() != FILE_SUFFIX:
            target = target.with_suffix(FILE_SUFFIX)
        tmp = target.with_suffix(target.suffix + ".tmp")
        tmp.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(target)  # atomar, damit bei Absturz keine halbe Datei entsteht
        self.path, self.dirty = target, False
        return target

    @classmethod
    def load(cls, path: str | Path) -> Project:
        p = Path(path)
        data = json.loads(p.read_text(encoding="utf-8"))
        if data.get("format") != "ingrechner-projekt":
            raise ValueError("Die Datei ist keine Ingenieurs-Rechner-Projektdatei.")
        version = int(data.get("version", 0))
        if version > FORMAT_VERSION:
            raise ValueError("Die Projektdatei stammt aus einer neueren Programmversion.")
        known = ProjectMeta.__dataclass_fields__.keys()
        meta = ProjectMeta(**{k: v for k, v in data.get("meta", {}).items() if k in known})
        if version >= 2:
            pos_fields = Position.__dataclass_fields__.keys()
            positions = [Position(**{k: v for k, v in d.items() if k in pos_fields}) for d in data.get("positionen", [])]
        else:  # Version 1: {"calcs": {calc_id: {"inputs", "notiz"}}} -> je Rechner eine Position
            positions = [Position(_new_id(), cid, str(i), "", dict(e.get("inputs", {})), e.get("notiz", ""))
                         for i, (cid, e) in enumerate(data.get("calcs", {}).items(), 1)]
        return cls(meta=meta, positions=positions, path=p)
