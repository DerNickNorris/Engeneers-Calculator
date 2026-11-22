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
    cats = list(dict.fromkeys(c.category for c in ALL))   # Reihenfolge des ersten Auftretens
    assert cats == ["Maschinenbau", "Bau / Statik", "Elektrotechnik", "Fluid / Thermo"]


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


# ------------------------------------------------------------- Updates
class _FakeResp:
    def __init__(self, payload):
        self.payload = payload

    def read(self):
        import json as _j

        return _j.dumps(self.payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_versionsvergleich():
    from ingrechner.core.updates import is_newer, parse_version

    assert parse_version("v1.2") == (1, 2, 0)
    assert parse_version("0.10.1-beta") == (0, 10, 1)
    assert is_newer("v0.10.0", "0.9.5") and not is_newer("0.5.0", "0.5.0")
    assert not is_newer("unsinn", "0.5.0")


def test_release_abfrage():
    from ingrechner.core.updates import API_URL, fetch_latest

    seen = {}

    def opener(req, timeout):
        seen["url"], seen["ua"] = req.full_url, req.get_header("User-agent")
        return _FakeResp({"tag_name": "v9.9.9", "html_url": "https://example.org/rel", "body": "Neu",
                          "assets": [{"name": "Ingenieurs-Rechner-Setup-9.9.9.exe",
                                      "browser_download_url": "https://example.org/setup.exe"},
                                     {"name": "portable.zip", "browser_download_url": "https://example.org/p.zip"}]})

    info = fetch_latest(opener=opener)
    assert seen["url"] == API_URL and seen["ua"].startswith("Ingenieurs-Rechner/")
    assert (info.version, info.installer_url) == ("9.9.9", "https://example.org/setup.exe")


def test_noch_kein_release():
    import urllib.error

    from ingrechner.core.updates import fetch_latest

    def opener(req, timeout):
        raise urllib.error.HTTPError(req.full_url, 404, "Not Found", {}, None)

    assert fetch_latest(opener=opener) is None


def test_versionen_konsistent():
    import pathlib
    import re

    import ingrechner

    root = pathlib.Path(__file__).resolve().parent.parent
    toml = (root / "pyproject.toml").read_text(encoding="utf-8")
    assert re.search(r'^version = "([^"]+)"', toml, re.M).group(1) == ingrechner.__version__


def test_installer_skript():
    import pathlib

    iss = (pathlib.Path(__file__).resolve().parent.parent / "installer" / "ingrechner.iss").read_text(encoding="utf-8")
    assert "AppId={{CED6D8DE-0288-46B4-874B-8DE5693DA2F7}" in iss   # darf sich nie ändern
    for needed in (".irp", ".irpk", "German.isl", "PrivilegesRequired=lowest", "ingrechner\\resources\\icon.ico"):
        assert needed in iss
