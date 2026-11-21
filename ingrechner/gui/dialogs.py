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


class SettingsDialog(QDialog):
    """Einstellungen: Team-Materialdatei und Standard-Bearbeiter."""

    def __init__(self, context, parent=None) -> None:
        from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QPushButton

        from .context import default_material_path

        super().__init__(parent)
        self.ctx = context
        self.setWindowTitle("Einstellungen")
        self.setMinimumWidth(620)
        lay = QVBoxLayout(self)
        form = QFormLayout()
        self.author = QLineEdit(context.default_author)
        self.author.setPlaceholderText("wird bei neuen Projekten als Bearbeiter eingetragen")
        form.addRow("Bearbeiter (Standard)", self.author)

        row = QHBoxLayout()
        self.mat_path = QLineEdit(str(context.material_path))
        browse = QPushButton("Durchsuchen …")
        reset = QPushButton("Standard")
        row.addWidget(self.mat_path, 1)
        row.addWidget(browse)
        row.addWidget(reset)
        form.addRow("Team-Materialdatei", row)
        lay.addLayout(form)
        hint = QLabel("Für die gemeinsame Nutzung im Team eine Datei auf einem Netzlaufwerk wählen "
                      "(z. B. <code>\\\\server\\technik\\materialien.json</code>). Existiert die Datei noch "
                      "nicht, wird sie beim ersten eigenen Werkstoff angelegt.")
        hint.setWordWrap(True)
        hint.setObjectName("CalcDesc")
        lay.addWidget(hint)

        def pick():
            path, _ = QFileDialog.getSaveFileName(self, "Materialdatei wählen", self.mat_path.text(),
                                                  "Materialdatenbank (*.json)",
                                                  options=QFileDialog.DontConfirmOverwrite)
            if path:
                self.mat_path.setText(path)

        browse.clicked.connect(pick)
        reset.clicked.connect(lambda: self.mat_path.setText(str(default_material_path())))
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("Speichern")
        bb.button(QDialogButtonBox.Cancel).setText("Abbrechen")
        bb.accepted.connect(self._save)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def _save(self) -> None:
        self.ctx.default_author = self.author.text().strip()
        new_path = self.mat_path.text().strip()
        if new_path and new_path != str(self.ctx.material_path):
            self.ctx.material_path = new_path
        self.accept()
