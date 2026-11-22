# Ingenieurs-Rechner

Modulare Desktop-App (Python · PySide6) für Ingenieurberechnungen im Team:
Maschinenbau, Bau/Statik, Elektrotechnik und Fluid/Thermo – mit Rechenweg,
Systemskizze, Diagramm, PDF-Rechnungsnachweis und Excel/CSV-Export.

> **Hinweis:** Alle Rechenverfahren sind vereinfachte Ingenieurmodelle. Ergebnisse
> sind vor Verwendung in Nachweisen von fachkundiger Stelle gegen die jeweilige
> Originalnorm zu prüfen.

## Stand: Version 0.9.0

**Rechner (Phase 1 und 4)**

| Fachgebiet      | Rechner                                  | Grundlage                                             |
|-----------------|------------------------------------------|-------------------------------------------------------|
| Maschinenbau    | Biegung Einfeldträger                    | Bernoulli-Balken, Einzel- oder Streckenlast           |
|                 | Schraube: Vorspannkraft & Anziehdrehmoment | VDI 2230 Blatt 1, Gewinde DIN 13, ISO 898-1         |
|                 | Welle auf Torsion                        | Drehmoment, τ_t, Verdrehwinkel, Mindestdurchmesser    |
|                 | Rohr / Behälter unter Innendruck         | Kesselformel, Wanddicke in Anlehnung an AD 2000 B1    |
| Bau / Statik    | Querschnittswerte                        | Rechteck, Rohr, Kreis, I-Profil (ohne Radien)         |
|                 | Biegeknicken Druckstab (Stahl)           | DIN EN 1993-1-1, 6.3.1 (Knicklinien a₀–d)             |
|                 | Kragträger                               | Endlast + Streckenlast, Moment- und Biegelinie        |
| Elektrotechnik  | Spannungsfall Leitung                    | in Anlehnung an DIN VDE 0100-520 Anhang G             |
|                 | Leistung & Blindstromkompensation        | S, P, Q, I; Kompensationsleistung und Kapazität       |
|                 | Abschaltbedingung LS-Schalter            | DIN VDE 0100-410, DIN EN 60898-1, c_min = 0,95        |
| Fluid / Thermo  | Druckverlust Rohrleitung                 | Darcy-Weisbach, Colebrook-White                       |
|                 | U-Wert Bauteil                           | DIN EN ISO 6946, Temperaturverlauf, f_Rsi, GEG-Vergleich |
|                 | Wärmeleistung & Rohrdimension            | ṁ = Q̇/(c·Δθ), Nennweite DIN EN 10255, Druckgefälle    |

Funktionen: Seitenleiste mit Suche (Strg+K) · Eingabeprüfung mit Warnungen ·
Systemskizze · Rechenweg (Formel → eingesetzte Werte → Ergebnis) · Diagramm ·
Projektdatei `.irp` · PDF-Bericht (Strg+P) · Excel-Export (Strg+E) / CSV.

**Positionen und Gesamtbericht (Version 0.6)**

- Jede Berechnung ist eine **Position** im Projekt mit Nummer und Bezeichnung
  (z. B. „Pos. 3 – Träger Achse B“) – beliebig viele, auch mehrere vom selben Rechner.
  Positionsliste oben links: Neu, Duplizieren, Löschen, Verschieben. Ein Klick auf einen
  Rechner öffnet dessen zuletzt benutzte Position oder legt eine neue an.
- **Gesamtbericht** (*Datei › Gesamtbericht*, Strg+Umschalt+P): ein PDF mit Deckblatt
  (Projektdaten, Unterschriftsfelder), Inhaltsverzeichnis mit Seitenzahlen und
  PDF-Lesezeichen, Ergebnisübersicht aller Positionen mit Status (erfüllt / Warnung / Fehler)
  und den vollständigen Nachweisen; Positionen und Bestandteile sind wählbar.
- Projektdateien älterer Versionen werden automatisch übernommen (je Rechner eine Position).

**Heizung / Wärme (Version 0.7–0.8)**

| Rechner | Inhalt |
|---|---|
| Wärmemenge & Wärmeleistung | Q̇ = ṁ·c_p·Δθ – gesucht wahlweise Leistung, Volumenstrom oder Spreizung; Wärmemenge über Betriebsdauer; Wasser oder Luft |
| Wärmetauscher-Auslegung | Energiebilanz beider Seiten, mittlere log. Temperaturdifferenz, erforderliche Fläche A = Q̇/(k·ΔT_m), Gegen-/Gleichstrom, Temperaturverlauf, Prüfung auf Temperaturkreuzung |
| Wärmeverlust Rohrleitung (Luft) | DIN EN ISO 12241 / VDI 2055: Konvektion (Gebäude oder Wind) + Strahlung, Oberflächentemperatur, Vergleich ungedämmt, Verlust über Dämmdicke |
| Temperaturabfall in der Leitung | Austrittstemperatur, Wärmeverlust, Verweilzeit einer durchströmten Leitung |
| Wärmeverlust erdverlegte Leitung | DIN EN 13941: Einzelrohr oder Vor-/Rücklauf, KMR nach EN 253 (DN 20–200, Serie 1–3) oder eigene Dämmung, Erdreich- und Kopplungswiderstand, Jahreswärmeverlust, Vergleich der Dämmserien |
| Heizkörperleistung | DIN EN 442: Umrechnung der Normleistung (75/65/20) über die log. Übertemperatur, erforderliche Normleistung für einen Wärmebedarf, Heizwasserstrom |
| Pufferspeicher | nutzbare Wärmemenge, Lade-/Entladedauer oder erforderliches Volumen für eine Mindestlaufzeit |
| Mischtemperatur | Mischung von bis zu drei Strömen oder Rücklaufbeimischung (Mischventil) für eine Ziel-Vorlauftemperatur |

Temperaturabhängige Stoffwerte für Wasser (0–150 °C) und Luft; Rohrtabellen Stahl (EN 10255/10220)
und Kupfer (EN 1057). **Rohrwerkstoff und Dämmstoff** sind auswählbar – die Werte kommen aus der
Materialdatenbank (neue Gruppen „Rohrwerkstoff“ mit P235GH, P235TR1, 1.4571, Cu-DHP, PE-Xa, PE-RT,
PB-1, PP-R, PE-HD-Mantelrohr und „Dämmstoff“ mit PUR nach EN 253, PIR, Mineralwolle, Elastomer,
PE-Schaum); eigene Werkstoffe über „Werkstoff …“.

**Pumpen (Version 0.9)** – für geschlossene Heiz-/Kältekreise, offene Systeme sowie Abwasser/Industrie
(benutzerdefiniertes Medium mit ρ, ν, p_v; Viskositätshinweis nach ISO/TR 17766)

| Rechner | Inhalt |
|---------|--------|
| Pumpenauslegung (Förderhöhe) | Förderstrom direkt oder aus Leistung/Spreizung; Förderhöhe aus Rohrreibung (Colebrook), Σζ, Komponenten, Regelventil (k_vs), geodätischer Höhe und Behälterdrücken; Anlagenkennlinie |
| Pumpenkennlinie & Betriebspunkt | Kennlinienpunkte aus dem Datenblatt (Tabelle, Einfügen aus Excel), Ausgleichsparabel H(V̇), η formtreu interpoliert, Schnittpunkt mit der Anlagenkennlinie, Drehzahl vorgeben oder auf den Auslegungspunkt regeln (Affinitätsgesetze), Parallel-/Reihenbetrieb, Lage zum Bestpunkt (70–120 %) |
| Pumpenleistung & Motor | Wirkungsgradkette Pumpe – Motor – FU, Verluste je Stufe, Motorgröße nach IEC-Reihe mit Reserve, IE3/IE4-Mindestwirkungsgrade (IEC 60034-30-1), optional Jahresenergie |
| Energiekosten & Regelung | EU-Lastprofil 100/75/50/25 % (6/15/35/44 %) oder eigenes Profil; Vergleich ungeregelt / Δp-c / Δp-v / Anlagenkennlinie; Kosten, CO₂, Amortisation |
| NPSH / Kavitation | NPSH_A aus Behälterdruck, Dampfdruck (IAPWS), Zulauf-/Saughöhe und Saugleitung; Nachweis gegen NPSH_R + Zuschlag, Mindestzulaufhöhe, höchste Wassertemperatur |

Neuer Feldtyp **Tabelle** (`TableField`) im Rechner-Grundgerüst – wird in Eingabemaske, Projektdatei,
PDF-Bericht und Excel-/CSV-Export automatisch unterstützt.

**Werkzeuge (Phase 2)**

| Werkzeug                     | Kurzbeschreibung |
|------------------------------|------------------|
| Einheitenumrechner           | 24 Kategorien (Länge … Druck, Energie, Drehmoment, Viskosität, Flächenmoment); ein Wert → alle Einheiten; Freitext „3,5 bar in psi“ |
| Wissenschaftlicher Rechner   | Tastenfeld, DEG/RAD, Variablen (`a = 5`), `ans`, Verlauf (↑/↓), Live-Vorschau; Zustand bleibt erhalten |
| Materialdatenbank            | 21 mitgelieferte Werkstoffe (Stahl, Edelstahl, Guss, Aluminium, Kupfer, Beton, Holz, Kunststoffe) + eigene Werkstoffe in einer Team-Datei; Übernahme in Rechner über „Werkstoff …“ |
| Funktionsplotter             | bis zu 6 Funktionen f(x), Messwerte aus Excel einfügen, Polstellen-Erkennung, Zoom, Wert an einer Stelle, Wertetabelle als CSV |

Schreibweise im Rechner und Plotter: Dezimalkomma oder -punkt, Argumente mit
Semikolon (`max(1; 2,5)`), Potenz `^`, implizite Multiplikation (`2pi`, `3(x+1)`).
Der Auswerter prüft jeden Ausdruck gegen eine Positivliste – es wird kein
beliebiger Python-Code ausgeführt.

**Team-Materialdatei:** Unter *Extras › Einstellungen* einen Pfad auf einem
Netzlaufwerk wählen (z. B. `\\server\technik\materialien.json`). Alle Kollegen,
die denselben Pfad eintragen, teilen sich die eigenen Werkstoffe. Vor jeder
Änderung wird die Datei neu gelesen, damit Änderungen anderer nicht verloren gehen.

> Die mitgelieferten Werkstoffwerte sind Richtwerte (Mindestwerte der genannten
> Norm für den angegebenen Lieferzustand bzw. typische physikalische Werte).
> Vor Verwendung gegen Norm oder Werkstoffzeugnis prüfen.

**Besprechungsprotokolle (Phase 3)**

- **Vorlagen aus Bausteinen:** Kopffelder (Text, Datum, Uhrzeit), Teilnehmerliste,
  Tagesordnung mit TOPs, Textabschnitte, Aufgaben/Beschlüsse. Drei Vorlagen werden
  mitgeliefert (Baubesprechung, Jour fixe, Gesprächsnotiz); eigene Vorlagen entstehen
  im **Vorlagen-Editor** und liegen in einer Team-Datei (*Extras › Einstellungen › Team-Dateien*).
- **Diktat:** „🎤 Diktat“ an jedem TOP und Textabschnitt, „Aufgabe diktieren“ in der
  Aufgabentabelle; über den Pfeil daneben lassen sich auch Audiodateien (wav, mp3, m4a …)
  transkribieren. Die Erkennung (Whisper über faster-whisper) läuft **offline** auf dem PC.
  Eine Fachbegriffsliste in den Einstellungen verbessert die Schreibweise von Fachwörtern.
- **Folgeprotokoll:** übernimmt Kopfdaten, Teilnehmer und offene Aufgaben/Festlegungen
  (mit Herkunft „aus Prot. Nr.“), die Nummer zählt automatisch weiter (z. B. BB-07 → BB-08).
- Aufgaben werden automatisch nummeriert (`<Protokoll-Nr>.<lfd>`), Kürzel aus Namen vorgeschlagen.
- Ausgabe als **PDF**; gespeichert wird als `.irpk` (JSON). Ungespeicherte Protokolle werden
  alle 30 s gesichert und nach einem Absturz zur Wiederherstellung angeboten.

**Sprachmodell einrichten** (*Extras › Einstellungen › Diktat*):

| Modell          | Größe     | Hinweis |
|-----------------|-----------|---------|
| Base            | ≈ 150 MB  | sehr schnell, kurze Diktate |
| Small           | ≈ 480 MB  | Empfehlung für Büro-PCs |
| Medium          | ≈ 1,5 GB  | genauer, langsamer |
| Large v3 Turbo  | ≈ 1,6 GB  | beste Erkennung, leistungsstarke PCs |

„Herunterladen“ lädt das Modell einmalig von Hugging Face. **PCs ohne Internet:** Die IT
lädt das Modell einmal herunter (Ordner mit `model.bin`, `config.json`, `tokenizer.json`,
`vocabulary.*`) und legt ihn z. B. auf ein Netzlaufwerk; in den Einstellungen dann
„Ordner wählen“. Audiodaten verlassen den PC nie.

**Weitere Rechner:** siehe „Neuen Rechner hinzufügen“ – jeder Rechner ist eine einzelne Datei.

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

Mit einem heruntergeladenen Whisper-Modell und `espeak-ng` läuft zusätzlich ein
End-to-End-Test der Spracherkennung:
`INGRECHNER_TEST_MODEL=<Modellordner> python -m pytest -q`

Die Tests prüfen die Formeln gegen unabhängige Referenzwerte (Handrechnung,
Moody-Diagramm, Tabellenwerte), außerdem alle Auswahlkombinationen, Projektdatei,
Exporte, PDF-Erzeugung und einen Rauchtest der Oberfläche (headless).

## Installation (für Anwender)

Unter **Releases** auf GitHub die Datei `Ingenieurs-Rechner-Setup-<Version>.exe` herunterladen
und starten.

- Ohne Administratorrechte wird nur für den angemeldeten Benutzer installiert; im ersten Dialog
  lässt sich „für alle Benutzer“ wählen (dann sind Administratorrechte nötig).
- Startmenü-Eintrag, optional Desktop-Verknüpfung, Doppelklick auf `.irp` (Projekte) und
  `.irpk` (Protokolle) öffnet die App.
- **Update:** neues Setup einfach darüber installieren – Einstellungen, Projekte, Materialien
  und Vorlagen bleiben erhalten. Die App weist beim Start auf neue Versionen hin
  (abschaltbar unter *Extras › Einstellungen › Allgemein*; dabei wird nur die öffentliche
  GitHub-Seite abgefragt, es werden keine Daten übertragen). Manuell: *Hilfe › Nach Updates suchen*.
- **Deinstallation:** Windows-Einstellungen › Apps › „Ingenieurs-Rechner“.
- **Fehler:** Unerwartete Fehler erscheinen in einem Dialog und werden in
  `%APPDATA%\Ingenieurs-Rechner\Ingenieurs-Rechner\fehlerprotokoll.log` protokolliert
  (*Hilfe › Fehlerprotokoll öffnen*) – diese Datei bei Problemen mitschicken.
- Stille Installation für die IT/Softwareverteilung:
  `Ingenieurs-Rechner-Setup-x.y.z.exe /VERYSILENT /SUPPRESSMSGBOXES /ALLUSERS`
- Das Setup ist nicht signiert: Windows SmartScreen zeigt beim ersten Start eine Warnung
  („Weitere Informationen“ › „Trotzdem ausführen“).

## Windows-EXE und Installer bauen

**Automatisch (GitHub Actions, `.github/workflows/build-windows.yml`)** – bei jedem Push und
Pull Request: Tests → EXE → Selbsttest → Installer → Testinstallation (still installieren,
installierte App starten, Dateizuordnung und Startmenü prüfen, deinstallieren). Downloads
unter *Actions › Lauf › Artifacts*: `Ingenieurs-Rechner-Setup` und die portable Version.

**Neue Version veröffentlichen:**
1. Version in `ingrechner/__init__.py` **und** `pyproject.toml` erhöhen (ein Test prüft, dass beide gleich sind).
2. Nach dem Merge in `main` einen Tag setzen, z. B. `git tag v0.5.0` und `git push origin v0.5.0`
   (oder auf GitHub: *Releases › Draft a new release › Tag v0.5.0*).
3. Der Workflow baut alles und hängt Setup und portable ZIP-Datei an das Release an (etwa
   5 Minuten). Wurde das Release vorher auf GitHub angelegt, werden die Dateien ergänzt.
   Der Tag muss zur Programmversion passen, sonst bricht der Build ab.

**Lokal unter Windows:** `build.bat` doppelklicken. Ergebnis
`dist\Ingenieurs-Rechner\Ingenieurs-Rechner.exe`; ist [Inno Setup 6](https://jrsoftware.org/isdl.php)
installiert, zusätzlich `dist\installer\Ingenieurs-Rechner-Setup-<Version>.exe`.

Selbsttest einer fertigen EXE: `Ingenieurs-Rechner.exe --selftest --selftest-out=st.txt`
(optional mit echter Spracherkennung: `--selftest-model=<Modellordner> --selftest-audio=<datei.wav>`).
Durch die Spracherkennung (CTranslate2, ONNX Runtime, FFmpeg) ist der Programmordner
mehrere hundert MB groß; das Sprachmodell selbst wird nicht mitgeliefert.

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
    tools/         Werkzeuge: Einheitenumrechner, Rechner, Materialien, Plotter
    protocols/     Protokollansicht und Vorlagen-Editor
    dictation.py   Mikrofonaufnahme und Diktat-Schaltfläche
  resources/       Icon, materials.json, protocol_templates.json
installer/         Inno-Setup-Skript für den Windows-Installer
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

Optional: `sketch_svg()` für die Systemskizze, `plot()` für ein Diagramm und
`material_map = {"E": "E", "Re": "Re"}`, um Werkstoffwerte aus der Datenbank
übernehmen zu können (Feldschlüssel → Materialeigenschaft).
Danach einen Test mit Referenzwerten in `tests/` ergänzen.
