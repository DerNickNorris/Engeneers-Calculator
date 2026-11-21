"""Dialoge: Projektdaten, Über."""

from __future__ import annotations

from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit,
                               QPlainTextEdit, QVBoxLayout)

from ingrechner import APP_NAME, __version__
from ingrechner.core.project import ProjectMeta


class ProjectMetaDialog(QDialog):
    def __init__(self, meta: ProjectMeta, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Projektdaten")
        self.setMinimumWidth(460)
        lay = QVBoxLayout(self)
        info = QLabel("Diese Angaben erscheinen im Kopf jedes PDF-Berichts und Exports.")
        info.setObjectName("CalcDesc")
        info.setWordWrap(True)
        lay.addWidget(info)
        form = QFormLayout()
        self.ed: dict[str, QLineEdit] = {}
        for key, label in [("projekt", "Projekt"), ("nummer", "Projekt-Nr."), ("bearbeiter", "Bearbeiter"),
                           ("pruefer", "Geprüft von"), ("datum", "Datum")]:
            e = QLineEdit(getattr(meta, key))
            form.addRow(label, e)
            self.ed[key] = e
        self.bem = QPlainTextEdit(meta.bemerkung)
        self.bem.setFixedHeight(70)
        form.addRow("Bemerkung", self.bem)
        lay.addLayout(form)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("Übernehmen")
        bb.button(QDialogButtonBox.Cancel).setText("Abbrechen")
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def meta(self) -> ProjectMeta:
        return ProjectMeta(**{k: e.text().strip() for k, e in self.ed.items()},
                           bemerkung=self.bem.toPlainText().strip())


ABOUT_HTML = f"""
<h3 style="color:#1f4e79">{APP_NAME} {__version__}</h3>
<p>Modularer Ingenieurs-Rechner für Maschinenbau, Bau/Statik, Elektrotechnik und Fluid/Thermo.</p>
<p><b>Wichtiger Hinweis:</b> Alle Rechenverfahren sind vereinfachte Ingenieurmodelle.
Ergebnisse sind vor Verwendung in Nachweisen von fachkundiger Stelle gegen die
jeweilige Originalnorm zu prüfen. Es wird keine Haftung für die Richtigkeit übernommen.</p>
<p style="color:#5f6f7f">Python · PySide6 (Qt) · pint · matplotlib · ReportLab · openpyxl</p>
"""
