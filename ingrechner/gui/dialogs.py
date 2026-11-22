"""Dialoge: Projektdaten, Über."""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
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


class _DownloadJob(QThread):
    done = Signal(str)
    failed = Signal(str)

    def __init__(self, key: str, base: str) -> None:
        super().__init__()
        self.key, self.base = key, base

    def run(self) -> None:
        from ingrechner.core import speech

        try:
            self.done.emit(str(speech.download(self.key, self.base)))
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))


class SettingsDialog(QDialog):
    """Einstellungen: Allgemein, Team-Dateien, Diktat (Spracherkennung)."""

    def __init__(self, context, parent=None, tab: str | None = None) -> None:
        from PySide6.QtWidgets import QComboBox, QProgressBar, QPushButton, QTabWidget, QWidget

        from ingrechner.core import speech

        from .context import default_material_path, default_model_base, default_template_path

        super().__init__(parent)
        self.ctx = context
        self._job = None
        self.setWindowTitle("Einstellungen")
        self.setMinimumWidth(680)
        lay = QVBoxLayout(self)
        self.tabs = QTabWidget()
        lay.addWidget(self.tabs)

        # ---------------------------------------------------- Allgemein
        gen = QWidget()
        form = QFormLayout(gen)
        self.author = QLineEdit(context.default_author)
        self.author.setPlaceholderText("wird bei neuen Projekten und Protokollen eingetragen")
        form.addRow("Bearbeiter (Standard)", self.author)
        from PySide6.QtWidgets import QCheckBox

        self.updates = QCheckBox("Beim Start nach neuen Versionen suchen")
        self.updates.setChecked(context.update_check)
        self.updates.setToolTip("Fragt die öffentliche GitHub-Seite des Projekts nach dem neuesten Release. "
                                "Es werden keine Nutzer- oder Projektdaten übertragen.")
        form.addRow("Updates", self.updates)
        self.tabs.addTab(gen, "Allgemein")

        # ------------------------------------------------- Team-Dateien
        team = QWidget()
        tl = QVBoxLayout(team)
        tform = QFormLayout()
        self.mat_path = self._path_row(tform, "Materialdatenbank", str(context.material_path),
                                       default_material_path, "Materialdatenbank (*.json)")
        self.tpl_path = self._path_row(tform, "Protokollvorlagen", str(context.template_path),
                                       default_template_path, "Protokollvorlagen (*.json)")
        tl.addLayout(tform)
        hint = QLabel("Für die gemeinsame Nutzung im Team Dateien auf einem Netzlaufwerk wählen "
                      "(z. B. <code>\\\\server\\technik\\materialien.json</code>). Existiert eine Datei noch "
                      "nicht, wird sie beim ersten eigenen Eintrag angelegt.")
        hint.setWordWrap(True)
        hint.setObjectName("CalcDesc")
        tl.addWidget(hint)
        tl.addStretch(1)
        self.tabs.addTab(team, "Team-Dateien")

        # ------------------------------------------------------- Diktat
        dic = QWidget()
        dl = QVBoxLayout(dic)
        intro = QLabel("Die Spracherkennung (Whisper) läuft <b>offline</b> auf diesem PC. Das Sprachmodell wird "
                       "einmalig heruntergeladen – oder die IT stellt einen Modellordner bereit "
                       "(für PCs ohne Internet).")
        intro.setWordWrap(True)
        dl.addWidget(intro)
        dform = QFormLayout()
        self.model_key = QComboBox()
        for m in speech.MODELS:
            self.model_key.addItem(f"{m.label}  ({m.size}) – {m.hint}", m.key)
        self.model_key.setCurrentIndex(max(0, self.model_key.findData(speech.DEFAULT_MODEL)))
        dl_row = QHBoxLayout()
        dl_row.addWidget(self.model_key, 1)
        self.btn_download = QPushButton("Herunterladen")
        dl_row.addWidget(self.btn_download)
        dform.addRow("Modell laden", dl_row)
        current = context.speech_model_path
        self.model_path = QLineEdit(str(current) if current else "")
        self.model_path.setPlaceholderText("Ordner mit model.bin, config.json, tokenizer.json")
        mrow = QHBoxLayout()
        mrow.addWidget(self.model_path, 1)
        pick = QPushButton("Ordner wählen …")
        mrow.addWidget(pick)
        dform.addRow("Modellordner", mrow)
        self.model_state = QLabel()
        self.model_state.setWordWrap(True)
        dform.addRow("Status", self.model_state)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        dform.addRow("", self.progress)
        self.glossary = QPlainTextEdit(context.speech_glossary)
        self.glossary.setPlaceholderText("Fachbegriffe, Namen, Abkürzungen – durch Komma oder Zeilen getrennt, z. B.\n"
                                         "Betonage, Bewehrung, Prüfstatiker, VDE, Müller Bau GmbH")
        self.glossary.setFixedHeight(90)
        dform.addRow("Fachbegriffe", self.glossary)
        dl.addLayout(dform)
        if not speech.available():
            warn = QLabel("⚠ Das Paket „faster-whisper“ ist nicht installiert – Diktat ist deaktiviert.")
            warn.setStyleSheet("color: #9a5b00;")
            dl.addWidget(warn)
            self.btn_download.setEnabled(False)
        dl.addStretch(1)
        self.tabs.addTab(dic, "Diktat")

        def pick_dir():
            from PySide6.QtWidgets import QFileDialog

            d = QFileDialog.getExistingDirectory(self, "Modellordner wählen", self.model_path.text())
            if d:
                self.model_path.setText(d)

        pick.clicked.connect(pick_dir)
        self.model_path.textChanged.connect(self._update_model_state)
        self.btn_download.clicked.connect(lambda: self._download(str(default_model_base())))
        self._update_model_state()

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("Speichern")
        bb.button(QDialogButtonBox.Cancel).setText("Abbrechen")
        bb.accepted.connect(self._save)
        bb.rejected.connect(self.reject)
        self.buttons = bb
        lay.addWidget(bb)
        if tab:
            names = {"allgemein": 0, "team": 1, "diktat": 2}
            self.tabs.setCurrentIndex(names.get(tab, 0))

    def _path_row(self, form, label, value, default_fn, flt):
        from PySide6.QtWidgets import QFileDialog, QPushButton

        row = QHBoxLayout()
        edit = QLineEdit(value)
        browse = QPushButton("Durchsuchen …")
        reset = QPushButton("Standard")
        row.addWidget(edit, 1)
        row.addWidget(browse)
        row.addWidget(reset)
        form.addRow(label, row)

        def pick():
            path, _ = QFileDialog.getSaveFileName(self, f"{label} wählen", edit.text(), flt,
                                                  options=QFileDialog.DontConfirmOverwrite)
            if path:
                edit.setText(path)

        browse.clicked.connect(pick)
        reset.clicked.connect(lambda: edit.setText(str(default_fn())))
        return edit

    def _update_model_state(self) -> None:
        from ingrechner.core import speech

        p = self.model_path.text().strip()
        if p and speech.is_model_ready(p):
            self.model_state.setText("<span style='color:#2e7d4f'>✔ Modell gefunden – Diktat ist bereit.</span>")
        elif p:
            self.model_state.setText("<span style='color:#b3261e'>✖ In diesem Ordner liegt kein vollständiges "
                                     "Modell.</span>")
        else:
            self.model_state.setText("Noch kein Modell eingerichtet.")

    def _download(self, base: str) -> None:
        key = self.model_key.currentData()
        self.btn_download.setEnabled(False)
        self.buttons.setEnabled(False)
        self.progress.setVisible(True)
        self.model_state.setText(f"Lade Modell „{key}“ herunter – das kann einige Minuten dauern …")
        self._job = _DownloadJob(key, base)

        def done(path: str) -> None:
            self.model_path.setText(path)
            finish()

        def failed(msg: str) -> None:
            self.model_state.setText(f"<span style='color:#b3261e'>✖ {msg}</span>")
            finish()

        def finish() -> None:
            self.progress.setVisible(False)
            self.btn_download.setEnabled(True)
            self.buttons.setEnabled(True)

        self._job.done.connect(done)
        self._job.failed.connect(failed)
        self._job.start()

    def _save(self) -> None:
        self.ctx.default_author = self.author.text().strip()
        self.ctx.update_check = self.updates.isChecked()
        mp = self.mat_path.text().strip()
        if mp and mp != str(self.ctx.material_path):
            self.ctx.material_path = mp
        tp = self.tpl_path.text().strip()
        if tp and tp != str(self.ctx.template_path):
            self.ctx.template_path = tp
        self.ctx.speech_model_path = self.model_path.text().strip() or None
        self.ctx.speech_glossary = self.glossary.toPlainText().strip()
        self.accept()

    def reject(self) -> None:
        if self._job is not None and self._job.isRunning():
            return  # während des Downloads nicht schließen
        super().reject()
