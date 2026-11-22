"""Generische Ansicht für ein Rechenmodul – wird aus der Feldbeschreibung aufgebaut."""

from __future__ import annotations

from typing import Any

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QFormLayout, QHBoxLayout, QHeaderView,
                               QLabel, QLineEdit, QPlainTextEdit, QPushButton, QScrollArea,
                               QSizePolicy, QSplitter, QTableWidget, QTableWidgetItem, QTabWidget,
                               QTextBrowser, QVBoxLayout, QWidget)

from ingrechner.core.model import Calculator, CalcResult, ChoiceField, NumberField
from ingrechner.core.plotstyle import apply_style
from ingrechner.core.textfmt import rich
from ingrechner.core.units import fmt_num, parse_num, pretty_unit

from .theme import C
from .widgets import Card, MessageBox, SketchWidget


class CalculatorView(QWidget):
    changed = Signal()      # Eingaben geändert
    computed = Signal()     # neu berechnet

    def __init__(self, calc: Calculator, parent: QWidget | None = None, context=None) -> None:
        super().__init__(parent)
        self.calc = calc
        self.ctx = context
        self.result: CalcResult | None = None
        self._stale = True
        self._editors: dict[str, QLineEdit | QComboBox] = {}
        self._errors: dict[str, QLabel] = {}
        self._rows: dict[str, list[QWidget]] = {}
        self._build()
        self.set_values(calc.defaults())

    # ---------------------------------------------------------------- Aufbau
    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 16, 20, 16)
        outer.setSpacing(10)

        title = QLabel(self.calc.title)
        title.setObjectName("CalcTitle")
        norm = QLabel(rich(self.calc.norm))
        norm.setObjectName("NormBadge")
        norm.setTextFormat(Qt.RichText)
        norm.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        head = QHBoxLayout()
        head.addWidget(title)
        head.addSpacing(10)
        head.addWidget(norm, 0, Qt.AlignVCenter)
        head.addStretch(1)
        outer.addLayout(head)
        desc = QLabel(self.calc.description)
        desc.setObjectName("CalcDesc")
        desc.setWordWrap(True)
        outer.addWidget(desc)

        split = QSplitter(Qt.Horizontal)
        split.setChildrenCollapsible(False)
        split.setHandleWidth(12)
        outer.addWidget(split, 1)

        # ---- linke Spalte: Eingaben + Skizze
        left = QWidget()
        lcol = QVBoxLayout(left)
        lcol.setContentsMargins(0, 0, 0, 0)
        lcol.setSpacing(10)

        self.sketch = SketchWidget()
        sk_card = Card("Systemskizze")
        sk_card.body.addWidget(self.sketch)
        lcol.addWidget(sk_card)

        in_card = Card("Eingaben")
        self.form = QFormLayout()
        self.form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.form.setHorizontalSpacing(10)
        self.form.setVerticalSpacing(6)
        self.form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        for f in self.calc.fields:
            self._add_field(f)
        in_card.body.addLayout(self.form)

        self.notiz = QPlainTextEdit()
        self.notiz.setPlaceholderText("Position / Notiz für den Bericht (optional)")
        self.notiz.setFixedHeight(54)
        self.notiz.textChanged.connect(self.changed)
        in_card.body.addWidget(self.notiz)

        btns = QHBoxLayout()
        self.btn_calc = QPushButton("Berechnen")
        self.btn_calc.setObjectName("Primary")
        self.btn_calc.setToolTip("Berechnen (Enter / F5)")
        self.btn_calc.clicked.connect(self.compute)
        reset = QPushButton("Standardwerte")
        reset.clicked.connect(lambda: (self.set_values(self.calc.defaults()), self.changed.emit()))
        btns.addWidget(self.btn_calc)
        btns.addWidget(reset)
        if self.calc.material_map and self.ctx is not None:
            mat_btn = QPushButton("Werkstoff …")
            mat_btn.setToolTip("Kennwerte aus der Materialdatenbank übernehmen")
            mat_btn.clicked.connect(self.pick_material)
            btns.addWidget(mat_btn)
        btns.addStretch(1)
        in_card.body.addLayout(btns)
        lcol.addWidget(in_card)
        lcol.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(left)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setMinimumWidth(440)
        split.addWidget(scroll)

        # ---- rechte Spalte: Ergebnisse + Hinweise | Rechenweg/Diagramm (vertikal teilbar)
        res_card = Card("Ergebnisse")
        self.stale_label = QLabel("Noch nicht berechnet – Eingaben prüfen und „Berechnen“ klicken.")
        self.stale_label.setObjectName("Stale")
        self.stale_label.setWordWrap(True)
        res_card.body.addWidget(self.stale_label)
        res_inner = QWidget()
        res_lay = QVBoxLayout(res_inner)
        res_lay.setContentsMargins(0, 0, 4, 0)
        res_lay.setSpacing(8)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Größe", "Symbol", "Wert"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hh.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        res_lay.addWidget(self.table)
        self.msg_box = QVBoxLayout()
        self.msg_box.setSpacing(4)
        res_lay.addLayout(self.msg_box)
        res_lay.addStretch(1)
        res_scroll = QScrollArea()
        res_scroll.setWidgetResizable(True)
        res_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        res_scroll.setWidget(res_inner)
        res_card.body.addWidget(res_scroll, 1)

        self.tabs = QTabWidget()
        self.steps_view = QTextBrowser()
        self.steps_view.setOpenLinks(False)
        self.tabs.addTab(self.steps_view, "Rechenweg")
        self.figure = Figure(figsize=(6, 4), dpi=100, layout="constrained")
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.setMinimumHeight(220)
        self._plot_index = self.tabs.addTab(self.canvas, "Diagramm")

        right = QSplitter(Qt.Vertical)
        right.setChildrenCollapsible(False)
        right.setHandleWidth(10)
        right.addWidget(res_card)
        right.addWidget(self.tabs)
        right.setSizes([430, 400])
        split.addWidget(right)
        split.setSizes([460, 640])

        for seq in ("F5", "Ctrl+Return"):
            QShortcut(QKeySequence(seq), self, activated=self.compute)

    def _add_field(self, f) -> None:
        label = QLabel(f"{f.label}")
        label.setToolTip(f.tooltip)
        if len(f.label) > 24:              # lange Bezeichnungen umbrechen statt Felder abzuschneiden
            label.setWordWrap(True)
            label.setMinimumWidth(150)
            label.setMaximumWidth(190)
        label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        if isinstance(f, ChoiceField):
            editor = QComboBox()
            editor.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
            editor.setMinimumContentsLength(14)
            for value, text in f.options:
                editor.addItem(text, value)
            editor.currentIndexChanged.connect(self._on_choice)
            editor.setToolTip(f.tooltip)
            field_widget = editor
        else:
            editor = QLineEdit()
            editor.setAlignment(Qt.AlignRight)
            editor.setToolTip(f.tooltip or f.label)
            editor.setMinimumWidth(110)
            editor.textEdited.connect(lambda _t, key=f.key: self._on_edit(key))
            editor.returnPressed.connect(self.compute)
            sym = QLabel(rich(f.symbol))
            sym.setTextFormat(Qt.RichText)
            sym.setFixedWidth(46)
            sym.setStyleSheet(f"color:{C['muted']}; font-style: italic;")
            unit = QLabel(pretty_unit(f.unit))
            unit.setObjectName("Unit")
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.addWidget(sym)
            row.addWidget(editor, 1)
            row.addWidget(unit)
            field_widget = QWidget()
            field_widget.setLayout(row)
        err = QLabel()
        err.setObjectName("FieldError")
        err.setVisible(False)
        holder = QWidget()
        v = QVBoxLayout(holder)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(2)
        v.addWidget(field_widget)
        v.addWidget(err)
        self.form.addRow(label, holder)
        self._editors[f.key] = editor
        self._errors[f.key] = err
        self._rows[f.key] = [label, holder]

    # ------------------------------------------------------- Werkstoff
    def pick_material(self) -> None:
        from .tools.materials_view import MaterialPickerDialog

        dlg = MaterialPickerDialog(self.ctx, tuple(self.calc.material_map.values()), self)
        if dlg.exec() and dlg.material is not None:
            self.apply_material(dlg.material)

    def apply_material(self, mat) -> list[str]:
        """Übernimmt Kennwerte; gibt die Liste der nicht vorhandenen Eigenschaften zurück."""
        from ingrechner.core.materials import PROPERTIES

        values, missing = {}, []
        for key, prop in self.calc.material_map.items():
            v = getattr(mat, prop)
            if v is None:
                missing.append(PROPERTIES[prop][0])
            else:
                values[key] = v
        self.set_values(self.valid_values() | values)
        # Werkstoff in der Notiz vermerken (erscheint im PDF-Bericht)
        line = f"Werkstoff: {mat.display}" + (f", {mat.norm}" if mat.norm else "")
        lines = [ln for ln in self.notiz.toPlainText().splitlines() if not ln.startswith("Werkstoff:")]
        self.notiz.setPlainText("\n".join([line, *lines]).strip())
        win = self.window()
        if hasattr(win, "statusBar"):
            msg = f"Werkstoff {mat.name} übernommen"
            if missing:
                msg += f" – nicht hinterlegt: {', '.join(missing)}"
            win.statusBar().showMessage(msg, 6000)
        self.changed.emit()
        return missing

    # ------------------------------------------------------------ Werte
    def set_values(self, values: dict[str, Any]) -> None:
        merged = self.calc.defaults() | {k: v for k, v in values.items() if k in self._editors}
        for f in self.calc.fields:
            ed = self._editors[f.key]
            ed.blockSignals(True)
            if isinstance(f, ChoiceField):
                idx = ed.findData(merged[f.key])
                ed.setCurrentIndex(max(0, idx))
            else:
                ed.setText(fmt_num(float(merged[f.key]), f.decimals).replace(" ", ""))
            ed.blockSignals(False)
        for key in self._editors:
            self._show_error(key, None)
        self._update_visibility()
        self._mark_stale()

    def raw_values(self) -> dict[str, Any]:
        """Aktuelle Eingaben (Zahlen in Feldeinheit). Ungültige Zahlen werden als Text geliefert."""
        out: dict[str, Any] = {}
        for f in self.calc.fields:
            ed = self._editors[f.key]
            if isinstance(f, ChoiceField):
                out[f.key] = ed.currentData()
            else:
                try:
                    out[f.key] = parse_num(ed.text())
                except ValueError:
                    out[f.key] = ed.text()
        return out

    def valid_values(self) -> dict[str, Any]:
        """Nur gültig lesbare Werte – zum Speichern im Projekt."""
        return {k: v for k, v in self.raw_values().items()
                if not isinstance(v, str) or isinstance(self.calc.field(k), ChoiceField)}

    def set_notiz(self, text: str) -> None:
        self.notiz.blockSignals(True)
        self.notiz.setPlainText(text)
        self.notiz.blockSignals(False)

    # ------------------------------------------------------------ Events
    def _on_choice(self) -> None:
        self._update_visibility()
        self._mark_stale()
        self.changed.emit()

    def _on_edit(self, key: str) -> None:
        f = self.calc.field(key)
        text = self._editors[key].text()
        try:
            msg = f.check(parse_num(text)) if isinstance(f, NumberField) else None
        except ValueError:
            msg = "Bitte eine Zahl eingeben (Komma oder Punkt als Dezimaltrenner)."
        self._show_error(key, msg)
        self._mark_stale()
        self.sketch.set_svg(self.calc.sketch_svg(self.calc.defaults() | self.valid_values()))
        self.changed.emit()

    def _show_error(self, key: str, msg: str | None) -> None:
        ed = self._editors[key]
        ed.setProperty("invalid", bool(msg))
        ed.style().unpolish(ed)
        ed.style().polish(ed)
        lbl = self._errors[key]
        lbl.setText(msg or "")
        lbl.setVisible(bool(msg))

    def _update_visibility(self) -> None:
        raw = self.raw_values()
        for f in self.calc.fields:
            visible = self.calc.is_visible(f, raw)
            for w in self._rows[f.key]:
                w.setVisible(visible)
        self.sketch.set_svg(self.calc.sketch_svg(self.calc.defaults() | self.valid_values()))

    def _mark_stale(self) -> None:
        self._stale = True
        if self.result is not None:
            self.stale_label.setText("Eingaben geändert – Ergebnisse sind veraltet. Bitte neu berechnen.")
        self.stale_label.setVisible(True)
        self.table.setEnabled(self.result is None)
        self.table.setStyleSheet(f"color: {C['muted']};" if self.result is not None else "")

    @property
    def is_current(self) -> bool:
        return self.result is not None and not self._stale and self.result.ok

    # ------------------------------------------------------------ Rechnen
    def compute(self) -> CalcResult:
        raw = self.raw_values()
        res = self.calc.run(raw)
        for key in self._editors:
            self._show_error(key, res.field_errors.get(key))
        self.result = res
        self._stale = False
        self.table.setEnabled(True)
        self.table.setStyleSheet("")
        self._show_result(res, raw)
        self.computed.emit()
        return res

    def _show_result(self, res: CalcResult, raw: dict[str, Any]) -> None:
        # Hinweise
        while self.msg_box.count():
            w = self.msg_box.takeAt(0).widget()
            if w:
                w.deleteLater()

        if res.field_errors:
            self.stale_label.setText("Bitte die rot markierten Eingaben korrigieren.")
            self.stale_label.setVisible(True)
            self.table.setRowCount(0)
            self.table.setFixedHeight(self.table.horizontalHeader().height() + 4)
            self.steps_view.clear()
            self.figure.clear()
            self.canvas.draw_idle()
            return
        self.stale_label.setVisible(False)

        for m in res.messages:
            self.msg_box.addWidget(MessageBox(m))

        # Tabelle
        self.table.setRowCount(len(res.values))
        for r, rv in enumerate(res.values):
            name = QTableWidgetItem(rv.label)
            val = QTableWidgetItem(rv.text)
            val.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            if rv.highlight:
                for it in (name, val):
                    fnt = it.font()
                    fnt.setBold(True)
                    it.setFont(fnt)
            self.table.setItem(r, 0, name)
            sym = QLabel(rich(rv.symbol))
            sym.setTextFormat(Qt.RichText)
            sym.setContentsMargins(6, 0, 6, 0)
            sym.setStyleSheet("font-style: italic; background: transparent;")
            self.table.setCellWidget(r, 1, sym)
            self.table.setItem(r, 1, QTableWidgetItem(rv.symbol))  # für Kopieren
            self.table.item(r, 1).setForeground(Qt.transparent)
            self.table.setItem(r, 2, val)
        self.table.resizeRowsToContents()
        h = self.table.horizontalHeader().height() + sum(self.table.rowHeight(i) for i in range(len(res.values)))
        self.table.setFixedHeight(h + 4)

        # Rechenweg
        parts = [f"<div style='font-family: Segoe UI, DejaVu Sans; font-size: 10pt; color:{C['text']}'>"]
        for i, s in enumerate(res.steps, 1):
            parts.append(
                f"<p style='margin: 0 0 2px 0'><b>{i}. {rich(s.title)}</b></p>"
                f"<p style='margin: 0 0 2px 16px; color:{C['accent']}'>{rich(s.formula)}</p>"
                f"<p style='margin: 0 0 12px 16px'>{rich(s.substitution)} &nbsp;=&nbsp; "
                f"<b>{rich(s.result)}</b></p>"
            )
        parts.append("</div>")
        self.steps_view.setHtml("".join(parts))

        # Diagramm
        self.figure.clear()
        apply_style(self.figure)
        has_plot = self.calc.plot(self.figure, self.calc.defaults() | raw, res)
        self.canvas.draw_idle()
        self.tabs.setTabVisible(self._plot_index, has_plot)
