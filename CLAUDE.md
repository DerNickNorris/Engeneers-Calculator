# Hinweise für Claude

## Releases und Versionen
- Release-Tags `vX.Y.Z` müssen zu `ingrechner/__init__.__version__` und `pyproject.toml` passen.
- **Die Versionshistorie wird nie geändert:** Wenn ein Release-Build fehlschlägt, werden Tag und Release
  NICHT gelöscht, verschoben oder neu angelegt. Der nächste Versuch ist immer eine neue Version
  (Patch-Stufe erhöhen, z. B. 0.9.1 fehlgeschlagen → 0.9.2). Ausdrücklicher Wunsch des Projektinhabers.
- Versionssprung immer per PR, bevor der Nutzer das Release anlegt.

## Arbeitsweise
- UI und Kommunikation auf Deutsch.
- Tests: `QT_QPA_PLATFORM=offscreen python -m pytest -q`
- Neue Rechner: eine Datei unter `ingrechner/calculators/<fachgebiet>/`; Kategorie ggf. in
  `core/registry.CATEGORY_ORDER` und `tests/test_core.py` ergänzen.
