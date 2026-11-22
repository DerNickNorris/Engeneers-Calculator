"""Materialdatenbank: mitgelieferte Richtwerte + vom Team erweiterbare Datei.

* Die mitgelieferten Werkstoffe (``resources/materials.json``) sind schreibgeschützt.
* Eigene Werkstoffe liegen in einer JSON-Datei, deren Pfad in den Einstellungen
  festgelegt wird – z. B. auf einem Netzlaufwerk, damit das ganze Team sie nutzt.
  Vor jeder Änderung wird die Datei neu eingelesen, damit gleichzeitige Änderungen
  von Kollegen nicht verloren gehen.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, fields
from pathlib import Path

BUILTIN_PATH = Path(__file__).resolve().parent.parent / "resources" / "materials.json"
FORMAT = "ingrechner-materialien"


@dataclass
class Material:
    id: str
    name: str
    gruppe: str = ""
    norm: str = ""
    werkstoffnr: str = ""
    rho: float | None = None     # Dichte kg/m³
    E: float | None = None       # E-Modul N/mm²
    nu: float | None = None      # Querkontraktionszahl
    Re: float | None = None      # Streck-/Dehngrenze N/mm²
    Rm: float | None = None      # Zugfestigkeit N/mm²
    fc: float | None = None      # Druckfestigkeit (charakteristisch) N/mm²
    alpha: float | None = None   # Wärmeausdehnung 10⁻⁶/K
    lam: float | None = None     # Wärmeleitfähigkeit W/(m·K)
    c: float | None = None       # spez. Wärmekapazität J/(kg·K)
    bemerkung: str = ""

    @property
    def builtin(self) -> bool:
        return self.id.startswith("b:")

    @property
    def display(self) -> str:
        nr = f" ({self.werkstoffnr})" if self.werkstoffnr else ""
        return f"{self.name}{nr}"

    @classmethod
    def from_dict(cls, data: dict) -> Material:
        known = {f.name for f in fields(cls)}
        clean = {k: v for k, v in data.items() if k in known}
        for key in NUMERIC:
            if clean.get(key) in ("", None):
                clean[key] = None
            elif key in clean:
                clean[key] = float(clean[key])
        return cls(**clean)


# Anzeige-Metadaten: Schlüssel -> (Bezeichnung, Symbol, Einheit, Nachkommastellen)
PROPERTIES: dict[str, tuple[str, str, str, int]] = {
    "rho": ("Dichte", "ρ", "kg/m³", 0),
    "E": ("Elastizitätsmodul", "E", "N/mm²", 0),
    "nu": ("Querkontraktionszahl", "ν", "–", 3),
    "Re": ("Streck-/Dehngrenze", "R_e / R_p0,2", "N/mm²", 0),
    "Rm": ("Zugfestigkeit", "R_m", "N/mm²", 0),
    "fc": ("Druckfestigkeit (charakt.)", "f_c,k", "N/mm²", 1),
    "alpha": ("Wärmeausdehnung", "α", "10⁻⁶/K", 1),
    "lam": ("Wärmeleitfähigkeit", "λ", "W/(m·K)", 2),
    "c": ("Spez. Wärmekapazität", "c", "J/(kg·K)", 0),
}
NUMERIC = tuple(PROPERTIES)


def _read(path: Path) -> list[Material]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("format") != FORMAT:
        raise ValueError(f"{path.name} ist keine Materialdatenbank-Datei.")
    return [Material.from_dict(m) for m in data.get("materialien", [])]


class MaterialLibrary:
    def __init__(self, user_path: str | Path | None = None, builtin_path: Path = BUILTIN_PATH) -> None:
        self.builtin: list[Material] = _read(builtin_path)
        self.user_path = Path(user_path) if user_path else None
        self.user: list[Material] = []
        self.user_error: str | None = None
        self.reload()

    # ------------------------------------------------------------ Lesen
    def reload(self) -> None:
        self.user, self.user_error = [], None
        if self.user_path and self.user_path.exists():
            try:
                self.user = _read(self.user_path)
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                self.user_error = f"Eigene Materialdatei konnte nicht gelesen werden: {exc}"

    def all(self) -> list[Material]:
        return [*self.builtin, *self.user]

    def get(self, mat_id: str) -> Material:
        for m in self.all():
            if m.id == mat_id:
                return m
        raise KeyError(mat_id)

    def groups(self) -> list[str]:
        return sorted({m.gruppe for m in self.all() if m.gruppe})

    def search(self, text: str = "", gruppe: str | None = None) -> list[Material]:
        tokens = text.lower().split()
        out = []
        for m in self.all():
            if gruppe and m.gruppe != gruppe:
                continue
            hay = " ".join((m.name, m.gruppe, m.norm, m.werkstoffnr, m.bemerkung)).lower()
            if all(t in hay for t in tokens):
                out.append(m)
        return out

    # ------------------------------------------------------- Schreiben
    def _require_path(self) -> Path:
        if not self.user_path:
            raise ValueError("Kein Speicherort für eigene Werkstoffe festgelegt (Einstellungen).")
        return self.user_path

    def _save(self) -> None:
        path = self._require_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"format": FORMAT, "version": 1,
                   "materialien": [asdict(m) for m in self.user]}
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)

    def add(self, mat: Material) -> Material:
        self._require_path()
        self.reload()
        new = Material.from_dict({**asdict(mat), "id": f"u:{uuid.uuid4().hex[:10]}"})
        self.user.append(new)
        self._save()
        return new

    def update(self, mat: Material) -> None:
        if mat.builtin:
            raise PermissionError("Mitgelieferte Werkstoffe sind schreibgeschützt – bitte duplizieren.")
        self.reload()
        for i, m in enumerate(self.user):
            if m.id == mat.id:
                self.user[i] = mat
                self._save()
                return
        raise KeyError(f"Werkstoff wurde inzwischen gelöscht: {mat.name}")

    def remove(self, mat_id: str) -> None:
        if mat_id.startswith("b:"):
            raise PermissionError("Mitgelieferte Werkstoffe können nicht gelöscht werden.")
        self.reload()
        self.user = [m for m in self.user if m.id != mat_id]
        self._save()
