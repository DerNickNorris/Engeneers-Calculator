"""Auswahl der Quelle für ein verknüpftes Eingabefeld."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QDialog, QDialogButtonBox, QHeaderView, QLabel, QLineEdit,
                               QTableWidget, QTableWidgetItem, QVBoxLayout)

from ingrechner.core.links import Kandidat
from ingrechner.core.textfmt import rich


class LinkDialog(QDialog):
    def __init__(self, feld_label: str, kandidaten: list[Kandidat], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Wert aus Position übernehmen")
        self.resize(760, 460)
        self.kandidaten = kandidaten
        self.gewaehlt: Kandidat | None = None
        lay = QVBoxLayout(self)
        head = QLabel(f"Quelle für <b>{rich(feld_label)}</b> wählen. Der Wert wird übernommen und bei Änderungen "
                      "der Quelle automatisch nachgeführt (Feld ist dann gesperrt).")
        head.setWordWrap(True)
        head.setTextFormat(Qt.RichText)
        lay.addWidget(head)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Filtern …")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._filter)
        lay.addWidget(self.search)
        self.table = QTableWidget(len(kandidaten), 3)
        self.table.setHorizontalHeaderLabels(["Position", "Größe", "Aktueller Wert"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        for r, k in enumerate(kandidaten):
            for c, text in enumerate((k.position, k.groesse, k.wert)):
                it = QTableWidgetItem(text)
                if c == 2:
                    it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(r, c, it)
        self.table.doubleClicked.connect(self._accept)
        lay.addWidget(self.table, 1)
        if not kandidaten:
            hint = QLabel("Keine passende Quelle gefunden. Es werden nur Ergebnisse und Eingaben mit passender "
                          "Einheit aus anderen Positionen angeboten (keine Kreisbezüge).")
            hint.setWordWrap(True)
            hint.setObjectName("FieldError")
            lay.addWidget(hint)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("Verknüpfen")
        bb.button(QDialogButtonBox.Cancel).setText("Abbrechen")
        bb.accepted.connect(self._accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        if kandidaten:
            self.table.selectRow(0)

    def _filter(self, text: str) -> None:
        q = text.strip().lower()
        for r, k in enumerate(self.kandidaten):
            self.table.setRowHidden(r, bool(q) and q not in f"{k.position} {k.groesse}".lower())

    def _accept(self, *_args) -> None:
        rows = self.table.selectionModel().selectedRows()
        if not rows or self.table.isRowHidden(rows[0].row()):
            return
        self.gewaehlt = self.kandidaten[rows[0].row()]
        self.accept()
