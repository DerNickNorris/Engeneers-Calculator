"""Rauchtest der Oberfläche (läuft headless mit QT_QPA_PLATFORM=offscreen)."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6.QtWidgets")

import matplotlib  # noqa: E402

matplotlib.use("QtAgg")

from PySide6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="module")
def window(tmp_path_factory):
    from PySide6.QtCore import QSettings

    from ingrechner.gui.main_window import MainWindow
    from ingrechner.gui.theme import apply_theme

    QSettings.setPath(QSettings.NativeFormat, QSettings.UserScope, str(tmp_path_factory.mktemp("cfg")))
    app = QApplication.instance() or QApplication([])
    apply_theme(app)
    w = MainWindow()
    w.show()
    yield w
    w.project.dirty = False
    w.close()


def test_alle_rechner_oeffnen_und_rechnen(window):
    for cls in window.calc_classes:
        view = window.open_calculator(cls.id)
        res = view.compute()
        assert res.ok
        assert view.table.rowCount() == len(res.values)
        assert view.is_current


def test_ungueltige_eingabe_wird_markiert(window):
    view = window.open_calculator("mb.biegung_einfeldtraeger")
    ed = view._editors["L"]
    ed.setText("abc")
    view._on_edit("L")
    assert ed.property("invalid") is True
    assert not view.compute().ok
    view.set_values({"L": 2000})
    assert view.compute().ok


def test_feldsichtbarkeit(window):
    view = window.open_calculator("mb.biegung_einfeldtraeger")
    combo = view._editors["lastfall"]
    combo.setCurrentIndex(combo.findData("streckenlast"))
    assert view._rows["q"][0].isHidden() is False
    assert view._rows["F"][0].isHidden() is True
    combo.setCurrentIndex(combo.findData("einzellast"))


def test_suche_filtert(window):
    window.search.setText("rohr")
    visible = []
    for i in range(window.tree.topLevelItemCount()):
        cat = window.tree.topLevelItem(i)
        visible += [cat.child(j).text(0) for j in range(cat.childCount()) if not cat.child(j).isHidden()]
    assert "Druckverlust Rohrleitung" in visible
    assert "Spannungsfall Leitung" not in visible
    window.search.clear()


def test_projekt_speichern_und_laden(window, tmp_path):
    view = window.open_calculator("et.spannungsfall")
    view.set_values({"L": 123.0})
    view.changed.emit()
    assert window.project.dirty
    assert window._save_to(tmp_path / "p.irp")
    window.open_project(str(tmp_path / "p.irp"))
    assert window.project.inputs("et.spannungsfall")["L"] == 123.0


# ------------------------------------------------------------- Phase 2
def test_werkzeuge_oeffnen(window):
    for spec in window.tool_specs:
        view = window.open_calculator(spec.id)
        assert window.stack.currentWidget() is view
    # PDF/Export sind nur bei Rechnern aktiv
    assert not window.a_pdf.isEnabled()


def test_einheitenumrechner_tabelle(window):
    view = window.open_tool("tool.units")
    view.set_input("Länge", "2*25,4", "mm")
    values = {view.table.item(r, 1).text(): view.table.item(r, 0).text() for r in range(view.table.rowCount())}
    assert values["in"] == "2"
    assert values["m"] == "0,0508"
    view.free.setText("3,5 bar in psi")
    assert "50,76" in view.free_result.text()


def test_wiss_rechner(window):
    view = window.open_tool("tool.sci")
    view.input.setText("r = 3")
    view.evaluate()
    view.input.setText("pi*r^2")
    view.evaluate()
    assert view.history.item(view.history.count() - 1).text().endswith("28,2743338823")
    view.input.setText("1/0")
    view.evaluate()
    assert "Division" in view.preview.text()


def test_werkstoff_in_rechner_uebernehmen(window, tmp_path):
    window.ctx.material_path = tmp_path / "team.json"
    view = window.open_calculator("mb.biegung_einfeldtraeger")
    mat = next(m for m in window.ctx.materials.all() if m.name == "EN AW-6082 T6")
    assert view.apply_material(mat) == []
    raw = view.raw_values()
    assert (raw["E"], raw["Re"]) == (70000, 250)
    assert view.notiz.toPlainText().startswith("Werkstoff: EN AW-6082 T6")
    # Erneute Übernahme ersetzt die Werkstoffzeile, statt sie zu doppeln
    view.apply_material(next(m for m in window.ctx.materials.all() if m.name == "S235JR"))
    assert view.notiz.toPlainText().count("Werkstoff:") == 1
    # Fehlende Kennwerte werden gemeldet und nicht überschrieben
    cu = next(m for m in window.ctx.materials.all() if m.name == "Cu-ETP R220")
    assert view.apply_material(cu) == ["Streck-/Dehngrenze"]
    assert view.raw_values()["Re"] == 235


def test_materialansicht_eigener_werkstoff(window, tmp_path):
    from ingrechner.core.materials import Material

    window.ctx.material_path = tmp_path / "team2.json"
    view = window.open_tool("tool.materials")
    n = view.table.rowCount()
    window.ctx.materials.add(Material(id="", name="Testwerkstoff", gruppe="Baustahl", E=1))
    view.refresh()
    assert view.table.rowCount() == n + 1
    view.search.setText("Testwerkstoff")
    assert view.table.rowCount() == 1
    assert view.btn_bearbeiten.isEnabled()


def test_plotter(window, tmp_path):
    view = window.open_tool("tool.plotter")
    view.f_txt[0].setText("x^2")
    view.f_on[1].setChecked(False)
    view.draw()
    assert len(view._curves) == 1
    view.at_x.setText("3")
    assert "9" in view.at_out.text()
    view.write_csv(tmp_path / "w.csv")
    lines = (tmp_path / "w.csv").read_text(encoding="utf-8-sig").splitlines()
    assert lines[0] == "x;f1(x) = x^2" and len(lines) == view.npts.value() + 1
    view.f_txt[0].setText("foo(x)")
    view.draw()
    assert view.f_err[0].isVisibleTo(view)
