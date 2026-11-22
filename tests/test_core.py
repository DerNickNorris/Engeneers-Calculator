"""Einheiten, Registry, Projektdatei, Export und PDF-Bericht."""

import csv

import pytest

from ingrechner.core import registry
from ingrechner.core.export import export_csv, export_xlsx
from ingrechner.core.model import ChoiceField, NumberField
from ingrechner.core.project import Project, ProjectMeta
from ingrechner.core.report import build_pdf, plot_png
from ingrechner.core.textfmt import rich
from ingrechner.core.units import fmt_num, parse_num, pretty_unit

ALL = registry.discover()


def test_registry_findet_alle_beispielrechner():
    ids = {c.id for c in ALL}
    assert {"mb.biegung_einfeldtraeger", "st.querschnittswerte", "et.spannungsfall",
            "fl.druckverlust_rohr"} <= ids
    assert [c.category for c in ALL][:4] == ["Maschinenbau", "Bau / Statik", "Elektrotechnik", "Fluid / Thermo"]


@pytest.mark.parametrize("cls", ALL, ids=lambda c: c.id)
def test_jeder_rechner_ist_vollstaendig(cls):
    calc = cls()
    assert calc.title and calc.category and calc.description and calc.norm
    keys = [f.key for f in calc.fields]
    assert len(keys) == len(set(keys)), "doppelte Feldschlüssel"
    for f in calc.fields:
        if isinstance(f, NumberField):
            assert f.check(f.default) is None, f"Standardwert von {f.key} ist ungültig"
        if isinstance(f, ChoiceField):
            assert f.default in dict(f.options)
        for dep in (f.visible_if or {}):
            assert dep in keys
    r = calc.run({})
    assert r.ok and r.values and r.steps
    assert calc.sketch_svg(calc.defaults()).startswith("<svg")


@pytest.mark.parametrize("cls", ALL, ids=lambda c: c.id)
def test_alle_auswahlkombinationen_rechnen(cls):
    calc = cls()
    choices = [f for f in calc.fields if isinstance(f, ChoiceField)]
    for f in choices:
        for value, _ in f.options:
            r = calc.run({f.key: value})
            assert r.ok, (f.key, value, r.field_errors, [m.text for m in r.messages])


def test_zahlenformat_deutsch():
    assert fmt_num(1234.5, 1) == "1234,5"
    assert fmt_num(70454.2, 0) == "70 454"
    assert fmt_num(-0.5, 2) == "-0,50"
    assert parse_num("1,5") == 1.5
    assert parse_num("1.5") == 1.5
    assert parse_num("1.234,5") == 1234.5
    assert parse_num(" 2 000 ") == 2000
    with pytest.raises(ValueError):
        parse_num("abc")


def test_einheiten_anzeige():
    assert pretty_unit("N/mm**2") == "N/mm²"
    assert pretty_unit("cm**4") == "cm⁴"
    assert pretty_unit("kN*m") == "kN·m"
    assert pretty_unit("milliohm/m") == "mΩ/m"
    assert pretty_unit("percent") == "%"


def test_rich_text_tiefstellung_und_escaping():
    assert rich("σ_zul = R_e / S") == "σ<sub>zul</sub> = R<sub>e</sub> / S"
    assert rich("a < b & c") == "a &lt; b &amp; c"
    assert rich("P_v = n · I_b² · R_L") == "P<sub>v</sub> = n · I<sub>b</sub>² · R<sub>L</sub>"
    assert rich("W_y = I_y / e_z,max") == "W<sub>y</sub> = I<sub>y</sub> / e<sub>z,max</sub>"
    assert rich("ρ_θ = ρ_20") == "ρ<sub>θ</sub> = ρ<sub>20</sub>"


def test_projekt_roundtrip(tmp_path):
    p = Project(meta=ProjectMeta(projekt="Halle 3", nummer="P-042", bearbeiter="Test"))
    p.set_inputs("mb.biegung_einfeldtraeger", {"L": 3000.0, "lastfall": "streckenlast"}, "Pos. 1")
    assert p.dirty
    path = p.save(tmp_path / "test")          # Endung wird ergänzt
    assert path.suffix == ".irp" and not p.dirty
    q = Project.load(path)
    assert q.meta.projekt == "Halle 3"
    assert q.inputs("mb.biegung_einfeldtraeger") == {"L": 3000.0, "lastfall": "streckenlast"}
    assert q.notiz("mb.biegung_einfeldtraeger") == "Pos. 1"


def test_projekt_fremde_datei_abgelehnt(tmp_path):
    f = tmp_path / "x.irp"
    f.write_text('{"foo": 1}', encoding="utf-8")
    with pytest.raises(ValueError):
        Project.load(f)


@pytest.mark.parametrize("cls", ALL, ids=lambda c: c.id)
def test_exporte_und_pdf(cls, tmp_path):
    calc = cls()
    raw = calc.defaults()
    res = calc.run(raw)
    meta = ProjectMeta(projekt="Test <&> Projekt", bearbeiter="Prüfer")

    csv_path = export_csv(tmp_path / "e.csv", calc, raw, res, meta)
    rows = list(csv.reader(csv_path.open(encoding="utf-8-sig"), delimiter=";"))
    assert rows[0] == ["Rechner", calc.title]
    assert sum(1 for r in rows if r and r[0] == "Ergebnis") == len(res.values)

    from openpyxl import load_workbook
    wb = load_workbook(export_xlsx(tmp_path / "e.xlsx", calc, raw, res, meta))
    assert wb.sheetnames == ["Übersicht", "Rechenweg", "Hinweise"]
    assert wb["Rechenweg"].max_row == len(res.steps) + 1

    png = plot_png(calc, raw, res)
    pdf = build_pdf(tmp_path / "b.pdf", calc, raw, res, meta, "Pos. 1", None, png)
    data = pdf.read_bytes()
    assert data.startswith(b"%PDF") and len(data) > 5000
