"""Positionsliste des Projekts (Seitenleiste) und Dialog für den Gesamtbericht."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QDialog, QDialogButtonBox, QFormLayout,
                               QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMenu,
                               QPushButton, QToolButton, QVBoxLayout, QWidget)

from ingrechner.core.project import Project
from ingrechner.core.project_report import ReportOptions

from .theme import C

ROLE_PID = Qt.UserRole


class PositionsPanel(QWidget):
    """Liste der Positionen eines Projekts mit Neu/Duplizieren/Löschen/Verschieben."""

    open_requested = Signal(str)          # Positions-ID
    add_requested = Signal(str)           # Rechner-ID
    duplicate_requested = Signal(str)
    delete_requested = Signal(str)
    move_requested = Signal(str, int)

    def __init__(self, calc_classes, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.calc_titles = {c.id: c.title for c in calc_classes}
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        head = QHBoxLayout()
        title = QLabel("Positionen")
        title.setStyleSheet(f"font-weight: 600; color: {C['heading']};")
        self.count = QLabel()
        self.count.setObjectName("AppSub")
        head.addWidget(title)
        head.addStretch(1)
        head.addWidget(self.count)
        lay.addLayout(head)

        self.list = QListWidget()
        self.list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list.setStyleSheet(
            f"QListWidget {{ background: {C['panel']}; border: 1px solid {C['border']}; border-radius: 6px; }}"
            f"QListWidget::item {{ padding: 4px 6px; border-bottom: 1px solid {C['accent_softer']}; }}"
            f"QListWidget::item:selected {{ background: {C['accent_soft']}; color: {C['heading']}; }}")
        self.list.itemClicked.connect(lambda it: self.open_requested.emit(it.data(ROLE_PID)))
        self.list.itemActivated.connect(lambda it: self.open_requested.emit(it.data(ROLE_PID)))
        lay.addWidget(self.list, 1)
        self.empty = QLabel("Noch keine Positionen. Unten einen Rechner wählen – die Berechnung wird "
                            "automatisch als Position angelegt.")
        self.empty.setWordWrap(True)
        self.empty.setObjectName("AppSub")
        lay.addWidget(self.empty)

        row = QHBoxLayout()
        row.setSpacing(3)
        self.btn_add = QToolButton()
        self.btn_add.setText("＋ Neu")
        self.btn_add.setToolTip("Neue Position mit einem Rechner anlegen")
        self.btn_add.setPopupMode(QToolButton.InstantPopup)
        menu = QMenu(self)
        cats: dict[str, QMenu] = {}
        for cls in calc_classes:
            sub = cats.get(cls.category) or menu.addMenu(cls.category)
            cats[cls.category] = sub
            sub.addAction(cls.title, lambda cid=cls.id: self.add_requested.emit(cid))
        self.btn_add.setMenu(menu)
        row.addWidget(self.btn_add)
        for attr, text, tip, slot in (
                ("btn_dup", "⧉", "Position duplizieren", lambda: self._emit(self.duplicate_requested)),
                ("btn_del", "✕", "Position löschen", lambda: self._emit(self.delete_requested)),
                ("btn_up", "▲", "nach oben", lambda: self._emit_move(-1)),
                ("btn_down", "▼", "nach unten", lambda: self._emit_move(1))):
            b = QToolButton()
            b.setText(text)
            b.setToolTip(tip)
            b.clicked.connect(slot)
            setattr(self, attr, b)
            row.addWidget(b)
        row.addStretch(1)
        lay.addLayout(row)

    def _selected(self) -> str | None:
        it = self.list.currentItem()
        return it.data(ROLE_PID) if it else None

    def _emit(self, signal) -> None:
        pid = self._selected()
        if pid:
            signal.emit(pid)

    def _emit_move(self, delta: int) -> None:
        pid = self._selected()
        if pid:
            self.move_requested.emit(pid, delta)

    def refresh(self, project: Project, current: str | None = None) -> None:
        self.list.blockSignals(True)
        self.list.clear()
        for p in project.positions:
            calc_title = self.calc_titles.get(p.calc, f"unbekannter Rechner ({p.calc})")
            name = p.titel.strip() or calc_title
            text = f"{p.nr + '  ' if p.nr else ''}{name}"
            if p.titel.strip():
                text += f"\n      {calc_title}"
            it = QListWidgetItem(text)
            it.setData(ROLE_PID, p.id)
            it.setToolTip(f"{p.label(calc_title)}\n{calc_title}" + (f"\n{p.notiz}" if p.notiz else ""))
            if p.calc not in self.calc_titles:
                it.setForeground(Qt.red)
            self.list.addItem(it)
            if p.id == current:
                self.list.setCurrentItem(it)
        self.list.blockSignals(False)
        n = len(project.positions)
        self.count.setText(f"{n}" if n else "")
        self.empty.setVisible(n == 0)
        self.list.setVisible(n > 0)
        for b in (self.btn_dup, self.btn_del, self.btn_up, self.btn_down):
            b.setEnabled(n > 0)

    def select(self, pid: str | None) -> None:
        for i in range(self.list.count()):
            if self.list.item(i).data(ROLE_PID) == pid:
                self.list.setCurrentRow(i)
                return
        self.list.clearSelection()


class ReportDialog(QDialog):
    """Auswahl der Positionen und Optionen für den Gesamtbericht."""

    def __init__(self, project: Project, calc_titles: dict[str, str], settings=None, parent=None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Gesamtbericht erstellen")
        self.resize(560, 560)
        lay = QVBoxLayout(self)
        form = QFormLayout()
        default_title = str(settings.value("report/title", "Berechnungsnachweise")) if settings else \
            "Berechnungsnachweise"
        self.titel = QLineEdit(default_title)
        form.addRow("Titel (Deckblatt)", self.titel)
        lay.addLayout(form)

        opts = QHBoxLayout()
        self.cb = {}
        for key, text in (("deckblatt", "Deckblatt"), ("inhaltsverzeichnis", "Inhaltsverzeichnis"),
                          ("uebersicht", "Ergebnisübersicht"), ("skizzen", "Skizzen"), ("diagramme", "Diagramme")):
            c = QCheckBox(text)
            c.setChecked(True)
            self.cb[key] = c
            opts.addWidget(c)
        opts.addStretch(1)
        lay.addLayout(opts)

        lbl = QLabel("Positionen im Bericht:")
        lbl.setStyleSheet("font-weight: 600;")
        lay.addWidget(lbl)
        self.list = QListWidget()
        for p in project.positions:
            calc_title = calc_titles.get(p.calc, p.calc)
            it = QListWidgetItem(p.label(calc_title) + (f"   ({calc_title})" if p.titel.strip() else ""))
            it.setData(ROLE_PID, p.id)
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked)
            self.list.addItem(it)
        lay.addWidget(self.list, 1)
        sel = QHBoxLayout()
        for text, state in (("Alle", Qt.Checked), ("Keine", Qt.Unchecked)):
            b = QPushButton(text)
            b.clicked.connect(lambda _=False, s=state: self._set_all(s))
            sel.addWidget(b)
        sel.addStretch(1)
        lay.addLayout(sel)
        hint = QLabel("Alle Positionen werden mit ihren gespeicherten Eingaben neu berechnet.")
        hint.setObjectName("CalcDesc")
        lay.addWidget(hint)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("PDF erstellen …")
        bb.button(QDialogButtonBox.Cancel).setText("Abbrechen")
        bb.accepted.connect(self._accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def _set_all(self, state) -> None:
        for i in range(self.list.count()):
            self.list.item(i).setCheckState(state)

    def selected_ids(self) -> list[str]:
        return [self.list.item(i).data(ROLE_PID) for i in range(self.list.count())
                if self.list.item(i).checkState() == Qt.Checked]

    def _accept(self) -> None:
        if not self.selected_ids():
            return
        if self.settings is not None:
            self.settings.setValue("report/title", self.titel.text().strip())
        self.accept()

    def options(self) -> ReportOptions:
        return ReportOptions(titel=self.titel.text().strip() or "Berechnungsnachweise",
                             position_ids=self.selected_ids(), **{k: c.isChecked() for k, c in self.cb.items()})
