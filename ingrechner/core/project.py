"""Projektdatei (*.irp, JSON): Kopfdaten + Eingaben je Rechner."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

FORMAT_VERSION = 1
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
class Project:
    meta: ProjectMeta = field(default_factory=ProjectMeta)
    # Rechner-ID -> {"inputs": {...}, "notiz": "..."}
    calcs: dict[str, dict[str, Any]] = field(default_factory=dict)
    path: Path | None = None
    dirty: bool = False

    @property
    def name(self) -> str:
        if self.meta.projekt:
            return self.meta.projekt
        return self.path.stem if self.path else "Unbenanntes Projekt"

    def set_inputs(self, calc_id: str, inputs: dict[str, Any], notiz: str | None = None) -> None:
        entry = self.calcs.setdefault(calc_id, {"inputs": {}, "notiz": ""})
        if entry["inputs"] != inputs:
            entry["inputs"] = dict(inputs)
            self.dirty = True
        if notiz is not None and entry.get("notiz", "") != notiz:
            entry["notiz"] = notiz
            self.dirty = True

    def inputs(self, calc_id: str) -> dict[str, Any] | None:
        entry = self.calcs.get(calc_id)
        return dict(entry["inputs"]) if entry else None

    def notiz(self, calc_id: str) -> str:
        return self.calcs.get(calc_id, {}).get("notiz", "")

    # ------------------------------------------------------------ Datei
    def to_dict(self) -> dict[str, Any]:
        return {"format": "ingrechner-projekt", "version": FORMAT_VERSION,
                "meta": asdict(self.meta), "calcs": self.calcs}

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
        if int(data.get("version", 0)) > FORMAT_VERSION:
            raise ValueError("Die Projektdatei stammt aus einer neueren Programmversion.")
        known = ProjectMeta.__dataclass_fields__.keys()
        meta = ProjectMeta(**{k: v for k, v in data.get("meta", {}).items() if k in known})
        return cls(meta=meta, calcs=data.get("calcs", {}), path=p)
