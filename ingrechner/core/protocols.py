"""Besprechungsprotokolle: Vorlagen (Bausteine), Protokolldokumente, Fortschreibung.

Eine **Vorlage** besteht aus Bausteinen (Blöcken). Ein **Protokoll** enthält eine
Kopie der Vorlage (damit spätere Vorlagenänderungen alte Protokolle nicht verändern)
und die Werte je Baustein.
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

BUILTIN_TEMPLATES = Path(__file__).resolve().parent.parent / "resources" / "protocol_templates.json"
TEMPLATE_FORMAT = "ingrechner-protokollvorlagen"
PROTOCOL_FORMAT = "ingrechner-protokoll"
PROTOCOL_SUFFIX = ".irpk"

BLOCK_TYPES: dict[str, str] = {
    "feld": "Textfeld (einzeilig)",
    "datum": "Datum",
    "zeit": "Uhrzeit / Zeitraum",
    "teilnehmer": "Teilnehmerliste",
    "text": "Textabschnitt (diktierbar)",
    "tagesordnung": "Tagesordnung mit TOPs (diktierbar)",
    "aufgaben": "Aufgaben / Beschlüsse",
}
TEILNEHMER_STATUS = ["anwesend", "entschuldigt", "Verteiler"]
AUFGABE_ART = {"A": "Aufgabe", "B": "Beschluss", "F": "Festlegung", "I": "Information"}
AUFGABE_STATUS = ["offen", "in Arbeit", "erledigt"]
HEADER_TYPES = ("feld", "datum", "zeit")


@dataclass
class Block:
    key: str
    typ: str
    titel: str
    hinweis: str = ""
    vorgaben: list[str] = field(default_factory=list)  # Feld: Standardwert; Tagesordnung: TOP-Titel

    @classmethod
    def from_dict(cls, d: dict) -> Block:
        if d.get("typ") not in BLOCK_TYPES:
            raise ValueError(f"Unbekannter Bausteintyp: {d.get('typ')}")
        return cls(key=str(d["key"]), typ=d["typ"], titel=str(d.get("titel", "")),
                   hinweis=str(d.get("hinweis", "")), vorgaben=[str(v) for v in d.get("vorgaben", [])])


@dataclass
class Template:
    id: str
    name: str
    beschreibung: str = ""
    titel: str = "Besprechungsprotokoll"
    schlusstext: str = ""
    blocks: list[Block] = field(default_factory=list)

    @property
    def builtin(self) -> bool:
        return self.id.startswith("b:")

    @classmethod
    def from_dict(cls, d: dict) -> Template:
        blocks = [Block.from_dict(b) for b in d.get("blocks", [])]
        keys = [b.key for b in blocks]
        if len(keys) != len(set(keys)):
            raise ValueError(f"Vorlage „{d.get('name')}“: doppelte Baustein-Schlüssel.")
        return cls(id=str(d["id"]), name=str(d["name"]), beschreibung=str(d.get("beschreibung", "")),
                   titel=str(d.get("titel", "Besprechungsprotokoll")),
                   schlusstext=str(d.get("schlusstext", "")), blocks=blocks)

    def to_dict(self) -> dict:
        return asdict(self)

    def block(self, key: str) -> Block:
        for b in self.blocks:
            if b.key == key:
                return b
        raise KeyError(key)

    def new_block_key(self, typ: str) -> str:
        existing = {b.key for b in self.blocks}
        i = 1
        while f"{typ}{i}" in existing:
            i += 1
        return f"{typ}{i}"


def empty_value(block: Block) -> Any:
    if block.typ == "teilnehmer":
        return []
    if block.typ == "tagesordnung":
        return [{"titel": t, "text": ""} for t in block.vorgaben]
    if block.typ == "aufgaben":
        return []
    if block.typ == "datum":
        return date.today().strftime("%d.%m.%Y")
    if block.typ == "feld":
        return block.vorgaben[0] if block.vorgaben else ""
    return ""


@dataclass
class Protocol:
    template: Template
    nummer: str = "1"
    values: dict[str, Any] = field(default_factory=dict)
    path: Path | None = None

    @classmethod
    def new(cls, template: Template, nummer: str = "1") -> Protocol:
        tpl = deepcopy(template)
        return cls(tpl, nummer, {b.key: empty_value(b) for b in tpl.blocks})

    def value(self, key: str) -> Any:
        if key not in self.values:
            self.values[key] = empty_value(self.template.block(key))
        return self.values[key]

    # ------------------------------------------------------- Ableitungen
    @property
    def title(self) -> str:
        return f"{self.template.titel} Nr. {self.nummer}".strip()

    def first_value(self, typ: str) -> str:
        for b in self.template.blocks:
            if b.typ == typ and str(self.value(b.key)).strip():
                return str(self.value(b.key))
        return ""

    @property
    def subject(self) -> str:
        """Projekt/Thema: erstes ausgefülltes Textfeld."""
        return self.first_value("feld")

    def suggested_filename(self) -> str:
        datum = self.first_value("datum")
        m = re.match(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", datum)
        iso = f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}" if m else ""
        base = " ".join(p for p in (iso, self.template.titel, f"Nr {self.nummer}", self.subject) if p)
        return "".join(ch if ch.isalnum() or ch in " -_." else "_" for ch in base).strip()[:120]

    def open_tasks(self) -> list[dict]:
        out = []
        for b in self.template.blocks:
            if b.typ == "aufgaben":
                out += [t for t in self.value(b.key) if t.get("status") != "erledigt"
                        and t.get("art", "A") in ("A", "F")]
        return out

    def renumber_tasks(self) -> None:
        """Aufgaben ohne Nummer erhalten „<Protokoll-Nr>.<lfd>“."""
        for b in self.template.blocks:
            if b.typ != "aufgaben":
                continue
            used = {t.get("nr") for t in self.value(b.key)}
            i = 1
            for t in self.value(b.key):
                if not str(t.get("nr", "")).strip():
                    while f"{self.nummer}.{i}" in used:
                        i += 1
                    t["nr"] = f"{self.nummer}.{i}"
                    used.add(t["nr"])

    # ----------------------------------------------------------- Datei
    def to_dict(self) -> dict:
        return {"format": PROTOCOL_FORMAT, "version": 1, "nummer": self.nummer,
                "vorlage": self.template.to_dict(), "werte": self.values}

    def save(self, path: str | Path | None = None) -> Path:
        target = Path(path) if path else self.path
        if target is None:
            raise ValueError("Kein Speicherpfad angegeben.")
        if target.suffix.lower() != PROTOCOL_SUFFIX:
            target = target.with_name(target.name + PROTOCOL_SUFFIX)
        tmp = target.with_name(target.name + ".tmp")
        tmp.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(target)
        self.path = target
        return target

    @classmethod
    def load(cls, path: str | Path) -> Protocol:
        p = Path(path)
        data = json.loads(p.read_text(encoding="utf-8"))
        if data.get("format") != PROTOCOL_FORMAT:
            raise ValueError("Die Datei ist keine Protokolldatei des Ingenieurs-Rechners.")
        tpl = Template.from_dict(data["vorlage"])
        proto = cls(tpl, str(data.get("nummer", "1")), dict(data.get("werte", {})), p)
        for b in tpl.blocks:  # fehlende Werte ergänzen
            proto.value(b.key)
        return proto


def next_number(nummer: str) -> str:
    """„3“ → „4“, „BB-07“ → „BB-08“, „2026/1“ → „2026/2“; ohne Zahl: „<nr>-2“."""
    m = re.search(r"(\d+)(?!.*\d)", nummer)
    if not m:
        return f"{nummer}-2" if nummer else "1"
    digits = m.group(1)
    nxt = str(int(digits) + 1).zfill(len(digits))
    return nummer[:m.start()] + nxt + nummer[m.end():]


def continue_from(prev: Protocol) -> Protocol:
    """Folgeprotokoll: Kopfdaten, Teilnehmer und offene Aufgaben werden übernommen."""
    new = Protocol.new(prev.template, next_number(prev.nummer))
    for b in new.template.blocks:
        old = deepcopy(prev.value(b.key))
        if b.typ == "feld":
            new.values[b.key] = old
        elif b.typ == "teilnehmer":
            new.values[b.key] = [{**p, "status": "anwesend" if p.get("status") != "Verteiler" else "Verteiler"}
                                 for p in old]
        elif b.typ == "aufgaben":
            new.values[b.key] = [
                {**t, "herkunft": t.get("herkunft") or f"Prot. {prev.nummer}"}
                for t in old if t.get("status") != "erledigt" and t.get("art", "A") in ("A", "F")
            ]
    return new


# ------------------------------------------------------------ Vorlagen
def _read_templates(path: Path) -> list[Template]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("format") != TEMPLATE_FORMAT:
        raise ValueError(f"{path.name} ist keine Vorlagendatei.")
    return [Template.from_dict(t) for t in data.get("vorlagen", [])]


class TemplateLibrary:
    """Mitgelieferte Vorlagen (schreibgeschützt) + Team-Vorlagen in einer JSON-Datei."""

    def __init__(self, user_path: str | Path | None = None, builtin_path: Path = BUILTIN_TEMPLATES) -> None:
        self.builtin = _read_templates(builtin_path)
        self.user_path = Path(user_path) if user_path else None
        self.user: list[Template] = []
        self.user_error: str | None = None
        self.reload()

    def reload(self) -> None:
        self.user, self.user_error = [], None
        if self.user_path and self.user_path.exists():
            try:
                self.user = _read_templates(self.user_path)
            except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
                self.user_error = f"Team-Vorlagen konnten nicht gelesen werden: {exc}"

    def all(self) -> list[Template]:
        return [*self.builtin, *self.user]

    def get(self, tpl_id: str) -> Template:
        for t in self.all():
            if t.id == tpl_id:
                return t
        raise KeyError(tpl_id)

    def _save(self) -> None:
        if not self.user_path:
            raise ValueError("Kein Speicherort für Team-Vorlagen festgelegt (Einstellungen).")
        self.user_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"format": TEMPLATE_FORMAT, "version": 1, "vorlagen": [t.to_dict() for t in self.user]}
        tmp = self.user_path.with_name(self.user_path.name + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.user_path)

    def add(self, tpl: Template) -> Template:
        if not self.user_path:
            raise ValueError("Kein Speicherort für Team-Vorlagen festgelegt (Einstellungen).")
        self.reload()
        new = Template.from_dict({**tpl.to_dict(), "id": f"u:{uuid.uuid4().hex[:10]}"})
        self.user.append(new)
        self._save()
        return new

    def update(self, tpl: Template) -> None:
        if tpl.builtin:
            raise PermissionError("Mitgelieferte Vorlagen sind schreibgeschützt – bitte duplizieren.")
        Template.from_dict(tpl.to_dict())  # validieren
        self.reload()
        for i, t in enumerate(self.user):
            if t.id == tpl.id:
                self.user[i] = deepcopy(tpl)
                self._save()
                return
        raise KeyError(f"Vorlage wurde inzwischen gelöscht: {tpl.name}")

    def remove(self, tpl_id: str) -> None:
        if tpl_id.startswith("b:"):
            raise PermissionError("Mitgelieferte Vorlagen können nicht gelöscht werden.")
        self.reload()
        self.user = [t for t in self.user if t.id != tpl_id]
        self._save()
