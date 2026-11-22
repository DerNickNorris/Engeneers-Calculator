"""Gemeinsame Test-Einstellungen."""

import gc

import pytest


@pytest.fixture(scope="session", autouse=True)
def _qt_geordnet_beenden():
    """Qt-Objekte am Ende der Testsitzung geordnet abbauen.

    Ohne diesen Schritt räumt der Python-Interpreter beim Beenden Fenster, Widgets und die
    QApplication in zufälliger Reihenfolge ab. Unter Windows führt das gelegentlich dazu, dass
    der Prozess nach erfolgreichen Tests mit Fehlercode endet (CI-Build bricht ab).
    """
    yield
    try:
        from PySide6.QtCore import QCoreApplication, QEvent
        from PySide6.QtWidgets import QApplication
    except ImportError:
        return
    app = QApplication.instance()
    if app is None:
        return
    QApplication.clipboard().clear()
    for w in QApplication.topLevelWidgets():
        w.close()
        w.deleteLater()
    for _ in range(3):
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        app.processEvents()
    gc.collect()
