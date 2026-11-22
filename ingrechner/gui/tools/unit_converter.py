"""Einheitenumrechner: ein Wert → alle Einheiten der Kategorie auf einen Blick."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QGridLayout, QHBoxLayout, QHeaderView,
                               QLabel, QLineEdit, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from ingrechner.core.expr import Evaluator, ExprError, format_result
from ingrechner.core.unitconv import CATEGORIES, ConversionError, convert_all, parse_free

from ..theme import C
from ..widgets import Card, page_header


class UnitConverterView(QWidget):
    title = "Einheitenumrechner"

    def __init__(self, context=None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._eval = Evaluator()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 16, 20, 16)
        outer.setSpacing(10)
        page_header(outer, self.title,
                    "Wert und Einheit eingeben – alle Einheiten der Kategorie werden sofort angezeigt. "
                    "Im Wertfeld sind auch Rechenausdrücke erlaubt, z. B. 2*25,4. "
                    "Doppelklick auf eine Zeile kopiert den Wert.", "pint-Einheitensystem")

        # ---- Eingabe
        card = Card("Umrechnen")
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        self.category = QComboBox()
        self.category.addItems(list(CATEGORIES))
        self.value = QLineEdit("1")
        self.value.setAlignment(Qt.AlignRight)
        self.value.setMinimumWidth(160)
        self.unit = QComboBox()
        self.unit.setMinimumWidth(220)
        for col, (lbl, w) in enumerate((("Kategorie", self.category), ("Wert", self.value), ("Einheit", self.unit))):
            grid.addWidget(QLabel(lbl), 0, col)
            grid.addWidget(w, 1, col)
        grid.setColumnStretch(3, 1)
        card.body.addLayout(grid)
        self.error = QLabel()
        self.error.setObjectName("FieldError")
        card.body.addWidget(self.error)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Wert", "Einheit", "Bezeichnung"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.Stretch)
        hh.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.table.cellDoubleClicked.connect(self._copy_row)
        card.body.addWidget(self.table, 1)
        outer.addWidget(card, 1)

        # ---- Freitext
        free = Card("Schnellumrechnung")
        row = QHBoxLayout()
        self.free = QLineEdit()
        self.free.setPlaceholderText("z. B.  3,5 bar in psi   ·   100 °C nach °F   ·   2000 U/min in rad/s")
        self.free_result = QLabel()
        self.free_result.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.free_result.setMinimumWidth(260)
        row.addWidget(self.free, 1)
        row.addWidget(self.free_result)
        free.body.addLayout(row)
        outer.addWidget(free)

        self.category.currentTextChanged.connect(self._fill_units)
        self.value.textChanged.connect(self._update)
        self.unit.currentIndexChanged.connect(self._update)
        self.free.textChanged.connect(self._update_free)
        self._fill_units(self.category.currentText())

    def _fill_units(self, category: str) -> None:
        self.unit.blockSignals(True)
        self.unit.clear()
        for u in CATEGORIES[category]:
            self.unit.addItem(f"{u.label}  –  {u.name}", u.expr)
        self.unit.blockSignals(False)
        self._update()

    def set_input(self, category: str, value: str, unit_expr: str) -> None:
        self.category.setCurrentText(category)
        self.unit.setCurrentIndex(max(0, self.unit.findData(unit_expr)))
        self.value.setText(value)

    def _update(self) -> None:
        self.table.setRowCount(0)
        text = self.value.text().strip()
        if not text:
            self.error.setText("")
            return
        try:
            _, val = self._eval.evaluate(text)
            rows = convert_all(val, self.category.currentText(), self.unit.currentData())
        except (ExprError, ConversionError) as exc:
            self.error.setText(str(exc))
            return
        self.error.setText("")
        self.table.setRowCount(len(rows))
        current = self.unit.currentData()
        for r, (u, v) in enumerate(rows):
            items = [QTableWidgetItem(format_result(v, 10)), QTableWidgetItem(u.label), QTableWidgetItem(u.name)]
            items[0].setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            if u.expr == current:
                for it in items:
                    f = it.font()
                    f.setBold(True)
                    it.setFont(f)
            for c, it in enumerate(items):
                self.table.setItem(r, c, it)

    def _copy_row(self, row: int, _col: int) -> None:
        item = self.table.item(row, 0)
        if item:
            QGuiApplication.clipboard().setText(item.text())
            win = self.window()
            if hasattr(win, "statusBar"):
                win.statusBar().showMessage(f"Kopiert: {item.text()} {self.table.item(row, 1).text()}", 3000)

    def _update_free(self, text: str) -> None:
        if not text.strip():
            self.free_result.setText("")
            return
        try:
            num, src, res, dst = parse_free(text)
        except ConversionError as exc:
            self.free_result.setText(f"<span style='color:{C['muted']}'>{exc}</span>")
            return
        self.free_result.setText(f"<b style='color:{C['heading']}; font-size: 12pt'>= {format_result(res, 10)} {dst}</b>")
