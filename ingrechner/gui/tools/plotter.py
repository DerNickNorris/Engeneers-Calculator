"""Funktionsplotter: bis zu sechs Funktionen f(x) und eingefügte Messwerte."""

from __future__ import annotations

import csv
import math
from pathlib import Path

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QFileDialog, QFormLayout, QGridLayout,
                               QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QPushButton,
                               QRadioButton, QScrollArea, QSpinBox, QSplitter, QVBoxLayout, QWidget)

from ingrechner.core.expr import Evaluator, ExprError, format_result
from ingrechner.core.plotstyle import apply_style
from ingrechner.core.plotting import parse_xy, robust_ylim, sample

from ..theme import C
from ..widgets import Card, page_header

COLORS = ["#1f6fb2", "#c0392b", "#2e7d4f", "#8e44ad", "#d68910", "#2b3a4a"]
EXAMPLES = ["sin(x)", "0,5x^2 - 1", "", "", "", ""]


class PlotterView(QWidget):
    title = "Funktionsplotter"

    def __init__(self, context=None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctx = context
        self._curves: list[tuple[str, list[float], list[float]]] = []
        self._build()
        self.draw()

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 16, 20, 16)
        outer.setSpacing(10)
        page_header(outer, self.title,
                    "Funktionen in x eingeben (Schreibweise wie im wissenschaftlichen Rechner, z. B. 3x^2 - sin(x)) "
                    "und/oder Messwerte aus Excel einfügen. Mit der Werkzeugleiste über dem Diagramm "
                    "lässt sich zoomen, verschieben und als Bild speichern.")
        split = QSplitter(Qt.Horizontal)
        split.setChildrenCollapsible(False)
        split.setHandleWidth(12)
        outer.addWidget(split, 1)

        # ---------------- linke Spalte
        left = QWidget()
        lcol = QVBoxLayout(left)
        lcol.setContentsMargins(0, 0, 0, 0)
        lcol.setSpacing(10)

        fcard = Card("Funktionen")
        grid = QGridLayout()
        grid.setHorizontalSpacing(6)
        self.f_on: list[QCheckBox] = []
        self.f_txt: list[QLineEdit] = []
        self.f_err: list[QLabel] = []
        for i in range(6):
            cb = QCheckBox()
            cb.setChecked(bool(EXAMPLES[i]))
            swatch = QLabel("■")
            swatch.setStyleSheet(f"color: {COLORS[i]}; font-size: 14pt;")
            ed = QLineEdit(EXAMPLES[i])
            ed.setPlaceholderText(f"f{i + 1}(x) = …")
            ed.returnPressed.connect(self.draw)
            ed.textEdited.connect(lambda _t, c=cb: c.setChecked(True))
            err = QLabel()
            err.setObjectName("FieldError")
            err.setVisible(False)
            grid.addWidget(cb, 2 * i, 0)
            grid.addWidget(swatch, 2 * i, 1)
            grid.addWidget(QLabel(f"f{i + 1}(x) ="), 2 * i, 2)
            grid.addWidget(ed, 2 * i, 3)
            grid.addWidget(err, 2 * i + 1, 3)
            self.f_on.append(cb)
            self.f_txt.append(ed)
            self.f_err.append(err)
        grid.setColumnStretch(3, 1)
        fcard.body.addLayout(grid)

        form = QFormLayout()
        rng = QHBoxLayout()
        self.xmin = QLineEdit("-5")
        self.xmax = QLineEdit("5")
        for e in (self.xmin, self.xmax):
            e.setAlignment(Qt.AlignRight)
            e.setMaximumWidth(90)
            e.returnPressed.connect(self.draw)
        rng.addWidget(self.xmin)
        rng.addWidget(QLabel("bis"))
        rng.addWidget(self.xmax)
        rng.addStretch(1)
        form.addRow("x-Bereich", rng)
        self.npts = QSpinBox()
        self.npts.setRange(20, 5000)
        self.npts.setValue(500)
        form.addRow("Stützstellen", self.npts)
        mode = QHBoxLayout()
        self.rad = QRadioButton("RAD")
        self.deg = QRadioButton("DEG")
        self.rad.setChecked(True)
        g = QButtonGroup(self)
        g.addButton(self.rad)
        g.addButton(self.deg)
        mode.addWidget(self.rad)
        mode.addWidget(self.deg)
        mode.addStretch(1)
        form.addRow("Winkel", mode)
        self.title_ed = QLineEdit()
        self.xlabel = QLineEdit("x")
        self.ylabel = QLineEdit("y")
        form.addRow("Titel", self.title_ed)
        form.addRow("Achse x", self.xlabel)
        form.addRow("Achse y", self.ylabel)
        fcard.body.addLayout(form)
        btns = QHBoxLayout()
        draw = QPushButton("Zeichnen")
        draw.setObjectName("Primary")
        draw.clicked.connect(self.draw)
        csv_btn = QPushButton("Wertetabelle (CSV) …")
        csv_btn.clicked.connect(self.export_csv)
        btns.addWidget(draw)
        btns.addWidget(csv_btn)
        btns.addStretch(1)
        fcard.body.addLayout(btns)
        lcol.addWidget(fcard)

        vcard = Card("Wert an einer Stelle")
        vrow = QHBoxLayout()
        vrow.addWidget(QLabel("x ="))
        self.at_x = QLineEdit("1")
        self.at_x.setMaximumWidth(110)
        self.at_x.setAlignment(Qt.AlignRight)
        self.at_x.textChanged.connect(self._values_at)
        vrow.addWidget(self.at_x)
        vrow.addStretch(1)
        vcard.body.addLayout(vrow)
        self.at_out = QLabel()
        self.at_out.setTextInteractionFlags(Qt.TextSelectableByMouse)
        vcard.body.addWidget(self.at_out)
        lcol.addWidget(vcard)

        dcard = Card("Messwerte (zwei Spalten x / y, z. B. aus Excel)")
        self.data_on = QCheckBox("Messwerte anzeigen")
        self.data_on.setChecked(True)
        self.data = QPlainTextEdit()
        self.data.setPlaceholderText("x\ty\n0\t0,1\n1\t0,9\n2\t3,8")
        self.data.setFixedHeight(120)
        self.data_info = QLabel()
        self.data_info.setObjectName("CalcDesc")
        dcard.body.addWidget(self.data_on)
        dcard.body.addWidget(self.data)
        dcard.body.addWidget(self.data_info)
        lcol.addWidget(dcard)
        lcol.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(left)
        scroll.setMinimumWidth(420)
        split.addWidget(scroll)

        # ---------------- rechte Spalte: Diagramm
        pcard = Card()
        self.figure = Figure(figsize=(7, 5), dpi=100, layout="constrained")
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)
        pcard.body.addWidget(self.toolbar)
        pcard.body.addWidget(self.canvas, 1)
        split.addWidget(pcard)
        split.setSizes([440, 700])

    # ------------------------------------------------------------ Logik
    def _evaluator(self) -> Evaluator:
        return Evaluator("deg" if self.deg.isChecked() else "rad")

    def _range(self) -> tuple[float, float]:
        ev = self._evaluator()
        return ev.evaluate(self.xmin.text())[1], ev.evaluate(self.xmax.text())[1]

    def draw(self) -> None:
        self.figure.clear()
        apply_style(self.figure)
        ax = self.figure.subplots()
        self._curves = []
        try:
            x0, x1 = self._range()
            if not x1 > x0:
                raise ExprError("x max muss größer als x min sein.")
        except ExprError as exc:
            self.f_err[0].setText(f"x-Bereich: {exc}")
            self.f_err[0].setVisible(True)
            self.canvas.draw_idle()
            return
        ev = self._evaluator()
        for i, (on, ed, err) in enumerate(zip(self.f_on, self.f_txt, self.f_err)):
            err.setVisible(False)
            text = ed.text().strip()
            if not (on.isChecked() and text):
                continue
            try:
                f = ev.function(text)
            except ExprError as exc:
                err.setText(str(exc))
                err.setVisible(True)
                continue
            xs, ys = sample(f, x0, x1, self.npts.value())
            if all(math.isnan(y) for y in ys):
                err.setText("Im gewählten Bereich nicht definiert.")
                err.setVisible(True)
                continue
            ax.plot(xs, ys, color=COLORS[i], lw=2, label=f"f{i + 1}(x) = {text}")
            self._curves.append((f"f{i + 1}(x) = {text}", xs, ys))

        self.data_info.setText("")
        d = parse_xy(self.data.toPlainText())
        if self.data_on.isChecked() and self.data.toPlainText().strip():
            if d.x:
                label = f"Messwerte ({d.header[1]})" if d.header else "Messwerte"
                ax.plot(d.x, d.y, "o-", color="#2b3a4a", ms=4, lw=1, alpha=0.85, label=label)
            info = f"{len(d.x)} Wertepaare gelesen"
            if d.skipped:
                info += f", {d.skipped} Zeile(n) übersprungen"
            self.data_info.setText(info)

        ylim = robust_ylim([c[2] for c in self._curves] + ([d.y] if self.data_on.isChecked()
                                                          and self.data.toPlainText().strip() else []))
        if ylim:
            ax.set_ylim(*ylim)
        ax.axhline(0, color="#9aa7b4", lw=0.8)
        ax.axvline(0, color="#9aa7b4", lw=0.8)
        ax.grid(True, alpha=0.35)
        ax.set_xlabel(self.xlabel.text())
        ax.set_ylabel(self.ylabel.text())
        if self.title_ed.text().strip():
            ax.set_title(self.title_ed.text().strip())
        if ax.get_legend_handles_labels()[0]:
            ax.legend(loc="best")
        self.canvas.draw_idle()
        self._values_at()

    def _values_at(self) -> None:
        try:
            x = self._evaluator().evaluate(self.at_x.text())[1]
        except ExprError:
            self.at_out.setText("")
            return
        ev = self._evaluator()
        lines = []
        for i, (on, ed) in enumerate(zip(self.f_on, self.f_txt)):
            if on.isChecked() and ed.text().strip():
                try:
                    y = ev.function(ed.text())(x)
                except ExprError:
                    continue
                val = "nicht definiert" if math.isnan(y) else format_result(y, 10)
                lines.append(f"<span style='color:{COLORS[i]}'>■</span> f{i + 1}({format_result(x)}) = <b>{val}</b>")
        self.at_out.setText("<br>".join(lines) or f"<span style='color:{C['muted']}'>Keine Funktion aktiv.</span>")

    def export_csv(self) -> None:
        if not self._curves:
            QMessageBox.information(self, "Wertetabelle", "Bitte zuerst mindestens eine Funktion zeichnen.")
            return
        start = str(Path(self.ctx.settings.value("lastDir", "")) / "Wertetabelle.csv") if self.ctx else "Wertetabelle.csv"
        path, _ = QFileDialog.getSaveFileName(self, "Wertetabelle speichern", start, "CSV-Datei (*.csv)")
        if not path:
            return
        self.write_csv(path)

    def write_csv(self, path: str | Path) -> None:
        xs = self._curves[0][1]
        with open(path, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.writer(fh, delimiter=";")
            w.writerow(["x", *[c[0] for c in self._curves]])
            for j, x in enumerate(xs):
                row = [format_result(x, 10)]
                for _, _, ys in self._curves:
                    row.append("" if math.isnan(ys[j]) else format_result(ys[j], 10))
                w.writerow(row)
