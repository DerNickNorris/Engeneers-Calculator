"""Export der Eingaben und Ergebnisse als CSV (Excel-kompatibel, ;) oder XLSX."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from .model import Calculator, CalcResult, ChoiceField
from .project import ProjectMeta
from .units import fmt_num, pretty_unit


def _input_rows(calc: Calculator, raw: dict[str, Any]):
    merged = calc.defaults() | raw
    for f in calc.fields:
        if not calc.is_visible(f, merged):
            continue
        if isinstance(f, ChoiceField):
            yield f.label, "", f.label_for(merged[f.key]), ""
        else:
            yield f.label, f.symbol, float(merged[f.key]), pretty_unit(f.unit)


def export_csv(path: str | Path, calc: Calculator, raw: dict[str, Any], result: CalcResult,
               meta: ProjectMeta) -> Path:
    path = Path(path)
    with path.open("w", newline="", encoding="utf-8-sig") as fh:  # BOM -> Excel erkennt UTF-8
        w = csv.writer(fh, delimiter=";")
        w.writerow(["Rechner", calc.title])
        w.writerow(["Projekt", meta.projekt])
        w.writerow(["Projekt-Nr.", meta.nummer])
        w.writerow(["Bearbeiter", meta.bearbeiter])
        w.writerow(["Datum", meta.datum])
        w.writerow([])
        w.writerow(["Abschnitt", "Größe", "Symbol", "Wert", "Einheit"])
        for label, sym, val, unit in _input_rows(calc, raw):
            w.writerow(["Eingabe", label, sym, fmt_num(val, 6) if isinstance(val, float) else val, unit])
        for rv in result.values:
            w.writerow(["Ergebnis", rv.label, rv.symbol, fmt_num(rv.value, max(rv.decimals, 4)),
                        pretty_unit(rv.unit)])
        for m in result.messages:
            w.writerow(["Hinweis", m.level.value, "", m.text, ""])
    return path


def export_xlsx(path: str | Path, calc: Calculator, raw: dict[str, Any], result: CalcResult,
                meta: ProjectMeta) -> Path:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    path = Path(path)
    wb = Workbook()
    head_font = Font(bold=True, color="FFFFFF")
    head_fill = PatternFill("solid", fgColor="1F4E79")

    def header(ws, cols):
        ws.append(cols)
        for cell in ws[ws.max_row]:
            cell.font, cell.fill = head_font, head_fill

    ws = wb.active
    ws.title = "Übersicht"
    ws.append([calc.title])
    ws["A1"].font = Font(bold=True, size=14, color="1F4E79")
    for k, v in [("Fachgebiet", calc.category), ("Normbezug", calc.norm), ("Projekt", meta.projekt),
                 ("Projekt-Nr.", meta.nummer), ("Bearbeiter", meta.bearbeiter), ("Datum", meta.datum)]:
        ws.append([k, v])
    ws.append([])
    header(ws, ["Abschnitt", "Größe", "Symbol", "Wert", "Einheit"])
    for label, sym, val, unit in _input_rows(calc, raw):
        ws.append(["Eingabe", label, sym, val, unit])
    for rv in result.values:
        ws.append(["Ergebnis", rv.label, rv.symbol, round(rv.value, 10), pretty_unit(rv.unit)])
        if rv.highlight:
            for cell in ws[ws.max_row]:
                cell.font = Font(bold=True)

    ws2 = wb.create_sheet("Rechenweg")
    header(ws2, ["Nr.", "Schritt", "Formel", "Eingesetzt", "Ergebnis"])
    for i, s in enumerate(result.steps, 1):
        ws2.append([i, s.title, s.formula, s.substitution, s.result])

    ws3 = wb.create_sheet("Hinweise")
    header(ws3, ["Stufe", "Text"])
    for m in result.messages:
        ws3.append([m.level.value, m.text])

    for sheet, widths in ((ws, [14, 34, 10, 16, 12]), (ws2, [5, 30, 40, 60, 18]), (ws3, [10, 100])):
        for i, wdt in enumerate(widths):
            sheet.column_dimensions[chr(65 + i)].width = wdt
        for row in sheet.iter_rows():
            for cell in row:
                cell.alignment = Alignment(vertical="top", wrap_text=sheet is not ws)
    wb.save(path)
    return path
