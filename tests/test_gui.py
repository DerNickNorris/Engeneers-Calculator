"""Rauchtest der Oberfläche (läuft headless mit QT_QPA_PLATFORM=offscreen)."""

import os

import numpy as np

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6.QtWidgets")

import matplotlib  # noqa: E402

matplotlib.use("QtAgg")

from PySide6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="module")
def window(tmp_path_factory):
    from PySide6.QtCore import QSettings, QStandardPaths

    from ingrechner.gui.main_window import MainWindow
    from ingrechner.gui.theme import apply_theme

    QStandardPaths.setTestModeEnabled(True)   # keine echten AppData-Dateien (z. B. Wiederherstellung)
    QSettings.setPath(QSettings.NativeFormat, QSettings.UserScope, str(tmp_path_factory.mktemp("cfg")))
    app = QApplication.instance() or QApplication([])
    apply_theme(app)
    w = MainWindow()
    w.show()
    yield w
    w.project.dirty = False
    for view in w.views.values():   # keine Rückfragen beim Schließen
        if hasattr(view, "dirty"):
            view.dirty = False
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


# ------------------------------------------------------------- Phase 3
def test_protokoll_ansicht(window, tmp_path):
    from ingrechner.core.protocols import Protocol
    from ingrechner.gui.protocols.protocol_view import ParticipantsBlock, TasksBlock

    window.ctx.template_path = tmp_path / "vorlagen.json"
    view = window.open_tool("proto.editor")
    proto = Protocol.new(window.ctx.templates.get("b:baubesprechung"), "7")
    view.load_protocol(proto, dirty=True)
    people = next(w for w in view.widgets.values() if isinstance(w, ParticipantsBlock))
    r = people.add_row({"firma": "Statik"})
    people.table.item(r, 0).setText("Erika Beispiel")      # Eingabe des Namens schlägt Kürzel vor
    assert people.table.item(r, 2).text() == "EB"
    tasks = next(w for w in view.widgets.values() if isinstance(w, TasksBlock))
    tasks._dictated("Bewehrungsplan prüfen")               # wie nach einem Diktat
    view.widgets["top"].tops[0].text.setPlainText("Alle anwesend.")
    view.header.editors["projekt"].setText("Halle 3")
    assert view._save_to(tmp_path / "p.irpk")
    saved = Protocol.load(tmp_path / "p.irpk")
    assert saved.value("projekt") == "Halle 3"
    assert saved.value("aufgaben")[0]["aufgabe"] == "Bewehrungsplan prüfen"
    assert saved.value("aufgaben")[0]["nr"] == "7.1"
    assert saved.value("teilnehmer")[0]["kuerzel"] == "EB"
    assert saved.value("top")[0]["text"] == "Alle anwesend."
    view.follow_up()
    assert view.proto.nummer == "8" and view.dirty
    assert [t["aufgabe"] for t in view.proto.value("aufgaben")] == ["Bewehrungsplan prüfen"]
    view.dirty = False


def test_diktat_text_einfuegen(window):
    from PySide6.QtWidgets import QLineEdit, QPlainTextEdit

    from ingrechner.gui.dictation import insert_text

    pe = QPlainTextEdit()
    pe.setPlainText("Erster Satz.")
    pe.moveCursor(pe.textCursor().MoveOperation.End)
    insert_text(pe, "Zweiter Satz.")
    assert pe.toPlainText() == "Erster Satz. Zweiter Satz."
    le = QLineEdit()
    insert_text(le, "Hallo")
    assert le.text() == "Hallo"


def test_qt_audioformate():
    from PySide6.QtMultimedia import QAudioFormat

    from ingrechner.gui.dictation import qt_samples_to_float

    i16 = (np.array([0, 16384, -32768], dtype="<i2")).tobytes()
    assert list(qt_samples_to_float(i16, QAudioFormat.Int16, 1)) == [0.0, 0.5, -1.0]
    f32 = np.array([0.25, 0.75, -0.5, -0.5], dtype="<f4").tobytes()
    assert list(qt_samples_to_float(f32, QAudioFormat.Float, 2)) == [0.5, -0.5]


def test_diktat_ohne_modell_meldet_status(window, tmp_path):
    window.ctx.speech_model_path = tmp_path
    ok, msg = window.ctx.speech.status()
    assert not ok and ("Sprachmodell" in msg or "nicht installiert" in msg)


def test_vorlagen_editor(window, tmp_path):
    window.ctx.template_path = tmp_path / "v.json"
    view = window.open_tool("proto.templates")
    view.refresh()
    assert not view.btn_save.isEnabled()                    # mitgeliefert = schreibgeschützt
    view.duplicate()
    assert view.current is not None and not view.current.builtin and view.btn_save.isEnabled()
    n = len(view.current.blocks)
    view.add_block("text")
    view.b_titel.setText("Bemerkungen")
    view._block_changed()
    view.move_block(-1)
    assert view.dirty and len(view.current.blocks) == n + 1
    assert view.save()
    reloaded = window.ctx.templates.get(view.current.id)
    assert "Bemerkungen" in [b.titel for b in reloaded.blocks]


# ------------------------------------------------------------- Installer / Updates
def test_datei_oeffnen_per_doppelklick(window, tmp_path):
    from ingrechner.core.protocols import Protocol

    proto = Protocol.new(window.ctx.templates.get("b:gespraechsnotiz"), "42")
    path = proto.save(tmp_path / "notiz")
    window.open_file(str(path))
    view = window.stack.currentWidget()
    assert view.proto is not None and view.proto.nummer == "42"


def test_update_hinweis(window):
    from ingrechner import __version__
    from ingrechner.core.updates import ReleaseInfo

    window._update_result(ReleaseInfo(__version__, "https://example.org", None), "")
    assert window.update_badge is None                         # gleiche Version -> kein Hinweis
    window._update_result(ReleaseInfo("99.0.0", "https://example.org", None), "")
    assert window.update_badge is not None and "99.0.0" in window.update_badge.text()
