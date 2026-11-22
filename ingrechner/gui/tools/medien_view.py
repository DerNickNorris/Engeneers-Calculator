"""Mediendatenbank: Stoffwerte von Flüssigkeiten und Gasen über der Temperatur anzeigen."""

from __future__ import annotations

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QSplitter,
                               QTableWidget, QTableWidgetItem, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from ingrechner.core import medien
from ingrechner.core.plotstyle import apply_style
from ingrechner.core.units import fmt_num, parse_num

from ..widgets import Card, page_header

ART = {"fluessig": "Flüssigkeit", "gas": "Gas", "pastoes": "pastös (keine Strömungsrechnung)"}


class MedienView(QWidget):
    title = "Mediendatenbank"

    def __init__(self, context=None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctx = context
        self.current: medien.Medium | None = None
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 16, 20, 16)
        outer.setSpacing(10)
        page_header(outer, self.title,
                    "Stoffwerte für Rohrleitungs-, Pumpen- und Wärmerechner – Richtwerte für überschlägige "
                    "Berechnungen. Die Medien stehen in den Rechnern als Auswahl „Medium“ zur Verfügung.")
        split = QSplitter(Qt.Horizontal)
        outer.addWidget(split, 1)

        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Suchen: Name, z. B. Glykol, Klärschlamm, Erdgas …")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._fill)
        lv.addWidget(self.search)
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.currentItemChanged.connect(self._select)
        lv.addWidget(self.tree, 1)
        split.addWidget(left)

        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(0, 0, 0, 0)
        info = Card()
        self.name = QLabel()
        self.name.setObjectName("CardTitle")
        self.meta = QLabel()
        self.meta.setWordWrap(True)
        self.meta.setTextFormat(Qt.RichText)
        info.body.addWidget(self.name)
        info.body.addWidget(self.meta)
        bar = QHBoxLayout()
        bar.addWidget(QLabel("Druck (absolut) für Gase:"))
        self.p = QLineEdit("1,01325")
        self.p.setFixedWidth(90)
        self.p.setAlignment(Qt.AlignRight)
        self.p.editingFinished.connect(self._show)
        bar.addWidget(self.p)
        bar.addWidget(QLabel("bar"))
        bar.addStretch(1)
        self.p_row = QWidget()
        self.p_row.setLayout(bar)
        info.body.addWidget(self.p_row)
        rv.addWidget(info)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["θ [°C]", "ρ [kg/m³]", "ν [mm²/s]", "η [mPa·s]", "c_p [kJ/(kg·K)]",
                                              "p_v [kPa] / Z"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setMinimumHeight(200)
        rv.addWidget(self.table, 1)
        self.figure = Figure(figsize=(6, 3), dpi=100, layout="constrained")
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.setMinimumHeight(240)
        rv.addWidget(self.canvas, 1)
        split.addWidget(right)
        split.setSizes([320, 780])
        self._fill()

    # ---------------------------------------------------------------- Liste
    def _fill(self) -> None:
        q = self.search.text().strip().lower()
        self.tree.blockSignals(True)
        self.tree.clear()
        first = None
        for gruppe in medien.GRUPPEN:
            items = [m for m in medien.MEDIEN if m.gruppe == gruppe and (not q or q in m.name.lower()
                                                                          or q in gruppe.lower())]
            if not items:
                continue
            g = QTreeWidgetItem([gruppe])
            g.setFlags(Qt.ItemIsEnabled)
            f = g.font(0)
            f.setBold(True)
            g.setFont(0, f)
            self.tree.addTopLevelItem(g)
            for m in items:
                it = QTreeWidgetItem([m.name])
                it.setData(0, Qt.UserRole, m.id)
                g.addChild(it)
                first = first or it
            g.setExpanded(True)
        self.tree.blockSignals(False)
        if first is not None and (self.current is None or q):
            self.tree.setCurrentItem(first)

    def select(self, mid: str) -> None:
        for i in range(self.tree.topLevelItemCount()):
            g = self.tree.topLevelItem(i)
            for j in range(g.childCount()):
                if g.child(j).data(0, Qt.UserRole) == mid:
                    self.tree.setCurrentItem(g.child(j))
                    return

    def _select(self, item, _prev=None) -> None:
        if item is None or item.data(0, Qt.UserRole) is None:
            return
        self.current = medien.medium(item.data(0, Qt.UserRole))
        self._show()

    # -------------------------------------------------------------- Anzeige
    def _temps(self, m: medien.Medium) -> list[float]:
        lo, hi = m.t_min, m.t_max
        step = 10 if hi - lo <= 120 else 20 if hi - lo <= 250 else 50
        ts = [lo] + [t for t in range(int(np.ceil(lo / step) * step), int(hi) + 1, step) if lo < t < hi] + [hi]
        return list(dict.fromkeys(float(t) for t in ts))

    def _druck(self) -> float:
        try:
            return max(parse_num(self.p.text()), 1e-3) * 1e5
        except ValueError:
            self.p.setText("1,01325")
            return medien.P_NORM

    def _show(self) -> None:
        m = self.current
        if m is None:
            return
        self.name.setText(m.name)
        lines = [f"<b>Gruppe:</b> {m.gruppe} &nbsp; <b>Art:</b> {ART[m.art]} &nbsp; "
                 f"<b>Bereich:</b> {fmt_num(m.t_min, 0)} … {fmt_num(m.t_max, 0)} °C"]
        if isinstance(m, medien.Gas):
            lines.append(f"<b>Molmasse:</b> {fmt_num(m.M, 2)} g/mol &nbsp; <b>Normdichte:</b> "
                         f"{fmt_num(m.normdichte(), 4)} kg/m³ (0 °C, 1,01325 bar)")
        for k, v in m.kennwerte.items():
            lines.append(f"<b>{k}:</b> {v}")
        lines.append(f"<span style='color:#5b6b7b'>{m.hinweis}</span>")
        self.meta.setText("<br>".join(lines))
        self.p_row.setVisible(m.art == "gas")
        self.table.setRowCount(0)
        self.figure.clear()
        if not m.fliessfaehig:
            self.table.setVisible(False)
            self.canvas.setVisible(False)
            return
        self.table.setVisible(True)
        self.canvas.setVisible(True)
        p = self._druck()
        ts = self._temps(m)
        zs = [m.zustand(t, p) for t in ts]
        self.table.setRowCount(len(zs))
        for r, z in enumerate(zs):
            last = fmt_num(z.Z, 4) if m.art == "gas" else ("–" if z.pv <= 0 else fmt_num(z.pv / 1000, 3))
            vals = [fmt_num(z.theta, 0), fmt_num(z.rho, 3 if m.art == "gas" else 1), fmt_num(z.nu * 1e6, 3),
                    fmt_num(z.mu * 1000, 4 if m.art == "gas" else 3), fmt_num(z.cp, 3), last]
            for c, v in enumerate(vals):
                it = QTableWidgetItem(v)
                it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(r, c, it)
        self.table.setHorizontalHeaderItem(5, QTableWidgetItem("Z [–]" if m.art == "gas" else "p_v [kPa]"))

        apply_style(self.figure)
        tf = np.linspace(m.t_min, m.t_max, 120)
        zf = [m.zustand(float(t), p) for t in tf]
        ax1, ax2 = self.figure.subplots(1, 2)
        ax1.plot(tf, [z.rho for z in zf], color="#1f6fb2", lw=2)
        ax1.set_ylabel("Dichte ρ  [kg/m³]")
        ax2.plot(tf, [z.nu * 1e6 for z in zf], color="#c0392b", lw=2)
        if m.art == "fluessig" and max(z.nu for z in zf) / min(z.nu for z in zf) > 8:
            ax2.set_yscale("log")
        ax2.set_ylabel("kin. Viskosität ν  [mm²/s]")
        for ax in (ax1, ax2):
            ax.set_xlabel("θ  [°C]")
            ax.grid(True, alpha=0.3, which="both")
        self.canvas.draw_idle()
