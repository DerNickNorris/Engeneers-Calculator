"""Wissenschaftlicher Rechner mit Tastenfeld, Verlauf und Variablen."""

from __future__ import annotations

import json

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import (QAbstractItemView, QButtonGroup, QGridLayout, QHBoxLayout, QHeaderView,
                               QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton, QRadioButton,
                               QSizePolicy, QSplitter, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from ingrechner.core.expr import FUNCTION_HELP, Evaluator, ExprError, format_result

from ..theme import C
from ..widgets import Card, page_header

KEYS = [
    [("sin", "sin("), ("cos", "cos("), ("tan", "tan("), ("√", "sqrt("), ("x²", "^2"), ("xʸ", "^")],
    [("asin", "asin("), ("acos", "acos("), ("atan", "atan("), ("ln", "ln("), ("log", "log("), ("eˣ", "exp(")],
    [("7", "7"), ("8", "8"), ("9", "9"), ("÷", "/"), ("(", "("), (")", ")")],
    [("4", "4"), ("5", "5"), ("6", "6"), ("×", "*"), ("π", "pi"), ("ans", "ans")],
    [("1", "1"), ("2", "2"), ("3", "3"), ("−", "-"), (";", "; "), ("C", "<clear>")],
    [("0", "0"), (",", ","), ("EXP", "e"), ("+", "+"), ("⌫", "<back>"), ("=", "<eval>")],
]


class SciCalcView(QWidget):
    title = "Wissenschaftlicher Rechner"

    def __init__(self, context=None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctx = context
        self.ev = Evaluator(angle="deg")
        self._history_pos = -1
        self._build()
        self._restore()

    # ---------------------------------------------------------------- UI
    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 16, 20, 16)
        outer.setSpacing(10)
        page_header(outer, self.title,
                    "Komma oder Punkt als Dezimaltrenner, Argumente mit Semikolon: max(1; 2,5). "
                    "Variablen anlegen mit  a = 5 ; das letzte Ergebnis heißt ans. "
                    "↑/↓ blättert im Verlauf, Klick auf einen Eintrag übernimmt ihn.")
        split = QSplitter(Qt.Horizontal)
        split.setChildrenCollapsible(False)
        split.setHandleWidth(12)
        outer.addWidget(split, 1)

        # ---- links: Verlauf, Eingabe, Tastenfeld
        left = Card()
        self.history = QListWidget()
        self.history.setStyleSheet(f"QListWidget {{ border: 1px solid {C['border']}; border-radius: 6px; "
                                   f"font-family: Consolas, 'DejaVu Sans Mono'; font-size: 11pt; }}"
                                   f"QListWidget::item {{ padding: 4px 6px; }}")
        self.history.itemClicked.connect(self._history_clicked)
        left.body.addWidget(self.history, 1)

        self.input = QLineEdit()
        self.input.setPlaceholderText("Ausdruck eingeben, z. B.  sqrt(3^2 + 4^2)  und Enter")
        self.input.setStyleSheet("font-family: Consolas, 'DejaVu Sans Mono'; font-size: 13pt; padding: 8px;")
        self.input.returnPressed.connect(self.evaluate)
        self.input.textChanged.connect(self._preview)
        self.input.installEventFilter(self)
        left.body.addWidget(self.input)
        self.preview = QLabel(" ")
        self.preview.setStyleSheet(f"color: {C['muted']}; font-size: 11pt;")
        self.preview.setAlignment(Qt.AlignRight)
        left.body.addWidget(self.preview)

        mode_row = QHBoxLayout()
        self.deg = QRadioButton("DEG (Grad)")
        self.rad = QRadioButton("RAD (Bogenmaß)")
        self.deg.setChecked(True)
        grp = QButtonGroup(self)
        grp.addButton(self.deg)
        grp.addButton(self.rad)
        self.deg.toggled.connect(self._mode_changed)
        mode_row.addWidget(QLabel("Winkel:"))
        mode_row.addWidget(self.deg)
        mode_row.addWidget(self.rad)
        mode_row.addStretch(1)
        left.body.addLayout(mode_row)

        pad = QGridLayout()
        pad.setSpacing(6)
        for r, row in enumerate(KEYS):
            for c, (label, action) in enumerate(row):
                b = QPushButton(label)
                b.setFocusPolicy(Qt.NoFocus)
                b.setMinimumHeight(38)
                b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                if action == "<eval>":
                    b.setObjectName("Primary")
                elif label.isdigit() or label == ",":
                    b.setStyleSheet(f"background: {C['accent_softer']}; font-weight: 600;")
                b.clicked.connect(lambda _=False, a=action: self._key(a))
                pad.addWidget(b, r, c)
        left.body.addLayout(pad)
        split.addWidget(left)

        # ---- rechts: Variablen + Funktionsübersicht
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(10)
        vc = Card("Variablen")
        self.vars = QTableWidget(0, 2)
        self.vars.setHorizontalHeaderLabels(["Name", "Wert"])
        self.vars.verticalHeader().setVisible(False)
        self.vars.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.vars.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.vars.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.vars.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.vars.cellDoubleClicked.connect(lambda r, _c: self._insert(self.vars.item(r, 0).text()))
        vc.body.addWidget(self.vars)
        btns = QHBoxLayout()
        clear_vars = QPushButton("Variablen löschen")
        clear_vars.clicked.connect(self._clear_vars)
        clear_hist = QPushButton("Verlauf löschen")
        clear_hist.clicked.connect(self._clear_history)
        btns.addWidget(clear_vars)
        btns.addWidget(clear_hist)
        btns.addStretch(1)
        vc.body.addLayout(btns)
        rl.addWidget(vc, 2)

        fc = Card("Funktionen (Doppelklick fügt ein)")
        self.funcs = QListWidget()
        self.funcs.setStyleSheet("QListWidget { border: none; } QListWidget::item { padding: 3px; }")
        for syntax, desc in FUNCTION_HELP.items():
            it = QListWidgetItem(f"{syntax}\n    {desc}")
            it.setData(Qt.UserRole, syntax.split("(")[0].split(" ")[0].split("·")[0].strip())
            self.funcs.addItem(it)
        self.funcs.itemDoubleClicked.connect(self._insert_function)
        fc.body.addWidget(self.funcs)
        rl.addWidget(fc, 3)
        split.addWidget(right)
        split.setSizes([620, 360])

    # ------------------------------------------------------------ Aktionen
    def _insert(self, text: str) -> None:
        self.input.insert(text)
        self.input.setFocus()

    def _insert_function(self, item: QListWidgetItem) -> None:
        name = item.data(Qt.UserRole)
        if name in ("pi", "x^n"):
            self._insert("pi" if name == "pi" else "^")
        else:
            self._insert(f"{name}(")

    def _key(self, action: str) -> None:
        if action == "<eval>":
            self.evaluate()
        elif action == "<clear>":
            self.input.clear()
        elif action == "<back>":
            self.input.backspace()
        else:
            self._insert(action)
        self.input.setFocus()

    def _mode_changed(self) -> None:
        self.ev.angle = "deg" if self.deg.isChecked() else "rad"
        self._preview(self.input.text())
        self._persist()

    def _preview(self, text: str) -> None:
        if not text.strip():
            self.preview.setText(" ")
            return
        probe = Evaluator(self.ev.angle)
        probe.variables = dict(self.ev.variables)
        probe.ans = self.ev.ans
        try:
            _, val = probe.evaluate(text)
            self.preview.setStyleSheet(f"color: {C['muted']}; font-size: 11pt;")
            self.preview.setText(f"= {format_result(val)}")
        except ExprError:
            self.preview.setText(" ")

    def evaluate(self) -> None:
        text = self.input.text().strip()
        if not text:
            return
        try:
            name, val = self.ev.evaluate(text)
        except ExprError as exc:
            self.preview.setStyleSheet(f"color: {C['error']}; font-size: 10.5pt;")
            self.preview.setText(str(exc))
            return
        line = f"{text}   =   {format_result(val)}"
        item = QListWidgetItem(line)
        item.setData(Qt.UserRole, text)
        item.setTextAlignment(Qt.AlignRight)
        self.history.addItem(item)
        self.history.scrollToBottom()
        self._history_pos = -1
        self.input.clear()
        self.preview.setText(f"= {format_result(val)}" + (f"   (gespeichert in {name})" if name else ""))
        self._refresh_vars()
        self._persist()

    def _history_clicked(self, item: QListWidgetItem) -> None:
        self.input.setText(item.data(Qt.UserRole))
        self.input.setFocus()

    def eventFilter(self, obj, event) -> bool:
        if obj is self.input and event.type() == QEvent.KeyPress and event.key() in (Qt.Key_Up, Qt.Key_Down):
            n = self.history.count()
            if n:
                if event.key() == Qt.Key_Up:
                    self._history_pos = n - 1 if self._history_pos < 0 else max(0, self._history_pos - 1)
                else:
                    self._history_pos = -1 if self._history_pos in (-1, n - 1) else self._history_pos + 1
                self.input.setText("" if self._history_pos < 0 else self.history.item(self._history_pos).data(Qt.UserRole))
            return True
        return super().eventFilter(obj, event)

    def _refresh_vars(self) -> None:
        items = [("ans", self.ev.ans), *sorted(self.ev.variables.items())]
        self.vars.setRowCount(len(items))
        for r, (k, v) in enumerate(items):
            self.vars.setItem(r, 0, QTableWidgetItem(k))
            val = QTableWidgetItem(format_result(v))
            val.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.vars.setItem(r, 1, val)

    def _clear_vars(self) -> None:
        self.ev.variables.clear()
        self.ev.ans = 0.0
        self._refresh_vars()
        self._persist()

    def _clear_history(self) -> None:
        self.history.clear()
        self._persist()

    # ----------------------------------------------- Zustand merken
    def _persist(self) -> None:
        if not self.ctx or getattr(self, "_restoring", False):
            return
        hist = [self.history.item(i).data(Qt.UserRole) for i in range(self.history.count())][-200:]
        lines = [self.history.item(i).text() for i in range(self.history.count())][-200:]
        state = {"angle": self.ev.angle, "vars": self.ev.variables, "ans": self.ev.ans,
                 "history": hist, "lines": lines}
        self.ctx.settings.setValue("scicalc/state", json.dumps(state))

    def _restore(self) -> None:
        self._restoring = True
        if self.ctx:
            try:
                state = json.loads(self.ctx.settings.value("scicalc/state", "{}"))
            except (TypeError, ValueError):
                state = {}
            self.ev.variables = {k: float(v) for k, v in state.get("vars", {}).items()}
            self.ev.ans = float(state.get("ans", 0.0))
            (self.rad if state.get("angle") == "rad" else self.deg).setChecked(True)
            for expr, line in zip(state.get("history", []), state.get("lines", [])):
                it = QListWidgetItem(line)
                it.setData(Qt.UserRole, expr)
                it.setTextAlignment(Qt.AlignRight)
                self.history.addItem(it)
            self.history.scrollToBottom()
        self._restoring = False
        self._refresh_vars()
