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
