"""Firmenvorlage für PDF-Berichte: Briefkopf mit Logo, Akzentfarbe und Fußzeile.

Die Vorlage ist eine JSON-Datei (Logo als Base64 eingebettet), damit sie auf einem Netzlaufwerk für das
ganze Team abgelegt werden kann. Die Berichtsfunktionen lesen die aktuelle Vorlage über :func:`aktuell`;
ohne Vorlage sehen die Berichte aus wie bisher.
"""

from __future__ import annotations

import base64
import io
import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path

FORMAT = "ingrechner-firmenvorlage"
STANDARD_FARBE = "#1f4e79"


@dataclass
class Firmenvorlage:
    firma: str = ""                 # Firmenname (fett im Briefkopf)
    zusatz: str = ""                # Abteilung, Anschrift, Telefon … (mehrzeilig)
    logo_b64: str = ""              # PNG/JPEG als Base64
    logo_pos: str = "rechts"        # "rechts" oder "links"
    farbe: str = STANDARD_FARBE     # Akzentfarbe für Überschriften, Tabellenköpfe, Linien
    fusszeile: str = ""             # z. B. „Vertraulich – nur für den internen Gebrauch“
    programmhinweis: bool = True    # „Ingenieurs-Rechner x.y“ in der Fußzeile

    # --------------------------------------------------------------- Zustand
    @property
    def hat_briefkopf(self) -> bool:
        return bool(self.firma.strip() or self.zusatz.strip() or self.logo_b64)

    @property
    def logo(self) -> bytes | None:
        if not self.logo_b64:
            return None
        try:
            return base64.b64decode(self.logo_b64)
        except (ValueError, TypeError):
            return None

    def set_logo(self, data: bytes | None) -> None:
        self.logo_b64 = base64.b64encode(data).decode("ascii") if data else ""

    def farbe_gueltig(self) -> str:
        f = (self.farbe or "").strip()
        if len(f) == 7 and f.startswith("#"):
            try:
                int(f[1:], 16)
                return f
            except ValueError:
                pass
        return STANDARD_FARBE

    # ----------------------------------------------------------------- Datei
    def to_dict(self) -> dict:
        return {"format": FORMAT, "version": 1, **asdict(self)}

    @classmethod
    def from_dict(cls, data: dict) -> Firmenvorlage:
        if data.get("format") not in (None, FORMAT):
            raise ValueError("Die Datei ist keine Firmenvorlage des Ingenieurs-Rechners.")
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
        return path

    @classmethod
    def load(cls, path: str | Path) -> Firmenvorlage:
        path = Path(path)
        if not path.exists():
            return cls()
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))


def logo_vorbereiten(data: bytes, max_px: int = 1200) -> bytes:
    """Prüft ein Bild und verkleinert es bei Bedarf (PNG), damit die Vorlagendatei klein bleibt."""
    from PIL import Image

    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception as exc:  # noqa: BLE001 - Pillow wirft verschiedene Fehler
        raise ValueError("Die Datei ist kein lesbares Bild (PNG oder JPEG verwenden).") from exc
    if max(img.size) <= max_px and img.format in ("PNG", "JPEG"):
        return data
    img.thumbnail((max_px, max_px))
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGBA")
    out = io.BytesIO()
    img.save(out, "PNG", optimize=True)
    return out.getvalue()


# ------------------------------------------------------- aktuelle Vorlage
_AKTUELL = Firmenvorlage()


def aktuell() -> Firmenvorlage:
    return _AKTUELL


def setzen(vorlage: Firmenvorlage | None) -> None:
    global _AKTUELL
    _AKTUELL = vorlage or Firmenvorlage()
