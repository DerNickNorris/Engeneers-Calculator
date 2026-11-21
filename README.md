# Ingenieurs-Rechner

Modulare Desktop-App (Python · PySide6) für Ingenieurberechnungen im Team:
Maschinenbau, Bau/Statik, Elektrotechnik und Fluid/Thermo – mit Rechenweg,
Systemskizze, Diagramm, PDF-Rechnungsnachweis und Excel/CSV-Export.

> **Hinweis:** Alle Rechenverfahren sind vereinfachte Ingenieurmodelle. Ergebnisse
> sind vor Verwendung in Nachweisen von fachkundiger Stelle gegen die jeweilige
> Originalnorm zu prüfen.

## Stand: Phase 1

| Fachgebiet      | Rechner                    | Grundlage                                        |
|-----------------|----------------------------|--------------------------------------------------|
| Maschinenbau    | Biegung Einfeldträger      | Bernoulli-Balken, Einzel- oder Streckenlast      |
| Bau / Statik    | Querschnittswerte          | Rechteck, Rohr, Kreis, I-Profil (ohne Radien)    |
| Elektrotechnik  | Spannungsfall Leitung      | in Anlehnung an DIN VDE 0100-520 Anhang G        |
| Fluid / Thermo  | Druckverlust Rohrleitung   | Darcy-Weisbach, Colebrook-White                  |

Funktionen: Seitenleiste mit Suche (Strg+K) · Eingabeprüfung mit Warnungen ·
Systemskizze · Rechenweg (Formel → eingesetzte Werte → Ergebnis) · Diagramm ·
Projektdatei `.irp` · PDF-Bericht (Strg+P) · Excel-Export (Strg+E) / CSV.

Geplant: Phase 2 Werkzeuge (Einheitenumrechner, wissenschaftlicher Rechner,
Materialdatenbank) · Phase 3 Besprechungsprotokolle mit Vorlagen-Editor und
Offline-Diktat (Whisper) · Phase 4 weitere Fachrechner.

## Starten (Entwicklung)

```bash
python -m venv .venv
.venv\Scripts\activate          # Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt
python run.py
```

## Tests

```bash
python -m pytest -q
```

Die Tests prüfen die Formeln gegen unabhängige Referenzwerte (Handrechnung,
Moody-Diagramm, Tabellenwerte), außerdem alle Auswahlkombinationen, Projektdatei,
Exporte, PDF-Erzeugung und einen Rauchtest der Oberfläche (headless).

## Windows-EXE bauen

Lokal unter Windows: `build.bat` doppelklicken. Ergebnis:
`dist\Ingenieurs-Rechner\Ingenieurs-Rechner.exe` – zum Weitergeben den ganzen
Ordner `dist\Ingenieurs-Rechner` zippen (kein Python auf dem Zielrechner nötig).

Alternativ automatisch über GitHub Actions (`.github/workflows/build-windows.yml`):
Tests → EXE → Selbsttest der EXE → Download als Artefakt.

Selbsttest einer fertigen EXE: `Ingenieurs-Rechner.exe --selftest --selftest-out=st.txt`

## Projektstruktur

```
ingrechner/
  core/            Rechenkern ohne GUI (testbar)
    model.py       Basisklasse Calculator, Felder, Ergebnisse, Rechenweg
    units.py       pint-Einheiten, deutsche Zahlenformatierung
    registry.py    findet Rechenmodule automatisch
    project.py     Projektdatei (.irp, JSON)
    report.py      PDF-Bericht (ReportLab)
    export.py      CSV / Excel
    svg.py         Baukasten für Systemskizzen
  calculators/     ein Unterordner je Fachgebiet, eine Datei je Rechner
  gui/             PySide6-Oberfläche (generisch, kein Code je Rechner nötig)
tests/
```

## Neuen Rechner hinzufügen

Eine Datei in `ingrechner/calculators/<fachgebiet>/` anlegen – mehr nicht.
Seitenleiste, Suche, Eingabemaske, Validierung, Speichern, PDF und Export
entstehen automatisch.

```python
from ingrechner.core.model import Calculator, NumberField
from ingrechner.core.units import fmt_num, fmt_q


class Leistung(Calculator):
    id = "et.leistung"                     # eindeutig, wird in Projektdateien gespeichert
    title = "Wirkleistung Wechselstrom"
    category = "Elektrotechnik"
    description = "P = U · I · cos φ"
    norm = "Grundlagen Elektrotechnik"
    keywords = ("leistung", "watt")
    fields = [
        NumberField("U", "Spannung", "U", "V", 230, min=0),
        NumberField("I", "Strom", "I", "A", 10, min=0),
        NumberField("cos", "Leistungsfaktor", "cos φ", "", 1.0, min=0, max=1),
    ]

    def compute(self, inp):
        P = inp["U"] * inp["I"] * inp["cos"]      # pint rechnet die Einheiten mit
        self.step("Wirkleistung", "P = U · I · cos φ",
                  f"P = {fmt_q(inp['U'], 'V', 0)} · {fmt_q(inp['I'], 'A', 1)} · {fmt_num(inp['cos'], 2)}",
                  fmt_q(P, "kW"))
        self.result("P", "Wirkleistung", "P", P, "kW", highlight=True)
        if P.to("kW").magnitude > 3.7:
            self.warn("Über 3,7 kW – Schieflastgrenze beachten.")
```

Optional: `sketch_svg()` für die Systemskizze und `plot()` für ein Diagramm.
Danach einen Test mit Referenzwerten in `tests/` ergänzen.
