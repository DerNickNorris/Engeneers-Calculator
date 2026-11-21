"""Materialdatenbank: Suchen, Anzeigen, eigene Werkstoffe pflegen, in Rechner übernehmen."""

from __future__ import annotations

from dataclasses import asdict, replace

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
                               QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox, QPlainTextEdit,
                               QPushButton, QSplitter, QTableWidget, QTableWidgetItem, QTextBrowser,
                               QVBoxLayout, QWidget)

from ingrechner.core.materials import PROPERTIES, Material, MaterialLibrary
from ingrechner.core.textfmt import rich
from ingrechner.core.units import fmt_num, parse_num

from ..theme import C
from ..widgets import Card, page_header

TABLE_COLS = [("name", "Werkstoff"), ("werkstoffnr", "Nr."), ("gruppe", "Gruppe"), ("rho", "ρ [kg/m³]"),
              ("E", "E [N/mm²]"), ("Re", "R_e [N/mm²]"), ("Rm", "R_m [N/mm²]")]


def _fmt(mat: Material, key: str) -> str:
    v = getattr(mat, key)
    if v is None:
        return "–"
    if key in PROPERTIES:
        return fmt_num(v, PROPERTIES[key][3])
    return str(v)


class MaterialEditDialog(QDialog):
    def __init__(self, mat: Material, groups: list[str], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Werkstoff bearbeiten" if mat.id else "Neuer Werkstoff")
        self.setMinimumWidth(520)
        self._mat = mat
        lay = QVBoxLayout(self)
        form = QFormLayout()
        self.name = QLineEdit(mat.name)
        self.gruppe = QComboBox()
        self.gruppe.setEditable(True)
        self.gruppe.addItems(groups)
        self.gruppe.setCurrentText(mat.gruppe)
        self.norm = QLineEdit(mat.norm)
        self.nr = QLineEdit(mat.werkstoffnr)
        form.addRow("Bezeichnung *", self.name)
        form.addRow("Gruppe", self.gruppe)
        form.addRow("Norm / Quelle", self.norm)
        form.addRow("Werkstoff-Nr.", self.nr)
        self.num: dict[str, QLineEdit] = {}
        for key, (label, sym, unit, dec) in PROPERTIES.items():
            v = getattr(mat, key)
            e = QLineEdit("" if v is None else fmt_num(v, max(dec, 3)).rstrip("0").rstrip(","))
            e.setPlaceholderText("leer = unbekannt")
            e.setAlignment(Qt.AlignRight)
            row = QHBoxLayout()
            row.addWidget(e, 1)
            u = QLabel(unit)
            u.setMinimumWidth(70)
            u.setStyleSheet(f"color: {C['muted']}")
            row.addWidget(u)
            form.addRow(f"{label} ({sym.replace('_', '')})", row)
            self.num[key] = e
        self.bem = QPlainTextEdit(mat.bemerkung)
        self.bem.setFixedHeight(64)
        form.addRow("Bemerkung", self.bem)
        lay.addLayout(form)
        self.err = QLabel()
        self.err.setObjectName("FieldError")
        lay.addWidget(self.err)
        bb = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Save).setText("Speichern")
        bb.button(QDialogButtonBox.Cancel).setText("Abbrechen")
        bb.accepted.connect(self._accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def _accept(self) -> None:
        if not self.name.text().strip():
            self.err.setText("Bitte eine Bezeichnung eingeben.")
            return
        values = {}
        for key, e in self.num.items():
            t = e.text().strip()
            if not t:
                values[key] = None
                continue
            try:
                values[key] = parse_num(t)
            except ValueError:
                self.err.setText(f"„{PROPERTIES[key][0]}“: keine gültige Zahl.")
                return
            if values[key] < 0:
                self.err.setText(f"„{PROPERTIES[key][0]}“ darf nicht negativ sein.")
                return
        self.result_material = replace(
            self._mat, name=self.name.text().strip(), gruppe=self.gruppe.currentText().strip(),
            norm=self.norm.text().strip(), werkstoffnr=self.nr.text().strip(),
            bemerkung=self.bem.toPlainText().strip(), **values)
        self.accept()


class MaterialsView(QWidget):
    title = "Materialdatenbank"
    chosen = Signal(object)   # Material (nur im Auswahlmodus)

    def __init__(self, context=None, parent: QWidget | None = None, pick_mode: bool = False,
                 required: tuple[str, ...] = ()) -> None:
        super().__init__(parent)
        self.ctx = context
        self.pick_mode = pick_mode
        self.required = required
        self._rows: list[Material] = []
        self._build()
        self.refresh()

    @property
    def lib(self) -> MaterialLibrary:
        return self.ctx.materials

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0 if self.pick_mode else 20, 0 if self.pick_mode else 16,
                                 0 if self.pick_mode else 20, 0 if self.pick_mode else 16)
        outer.setSpacing(10)
        if not self.pick_mode:
            page_header(outer, self.title,
                        "Mitgelieferte Richtwerte (schreibgeschützt) und eigene Werkstoffe des Teams. "
                        "Festigkeiten gelten für den angegebenen Lieferzustand und die Erzeugnisdicke – "
                        "vor Verwendung gegen Norm bzw. Werkstoffzeugnis prüfen.")
        bar = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Suchen: Name, Werkstoff-Nr., Norm …")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.refresh)
        self.group = QComboBox()
        self.group.currentIndexChanged.connect(self.refresh)
        bar.addWidget(self.search, 1)
        bar.addWidget(self.group)
        if not self.pick_mode:
            for text, slot in (("Neu", self.new), ("Duplizieren", self.duplicate), ("Bearbeiten", self.edit),
                               ("Löschen", self.delete), ("Neu laden", self.reload)):
                b = QPushButton(text)
                b.clicked.connect(slot)
                bar.addWidget(b)
                setattr(self, f"btn_{text.split()[0].lower()}", b)
        outer.addLayout(bar)

        split = QSplitter(Qt.Horizontal)
        split.setChildrenCollapsible(False)
        split.setHandleWidth(12)
        tcard = Card()
        self.table = QTableWidget(0, len(TABLE_COLS))
        self.table.setHorizontalHeaderLabels([c[1].replace("_", "") for c in TABLE_COLS])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setSortingEnabled(False)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        hh.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.table.itemSelectionChanged.connect(self._show_detail)
        self.table.cellDoubleClicked.connect(self._double_click)
        tcard.body.addWidget(self.table)
        split.addWidget(tcard)
        dcard = Card("Kennwerte")
        self.detail = QTextBrowser()
        self.detail.setMinimumWidth(300)
        dcard.body.addWidget(self.detail)
        split.addWidget(dcard)
        split.setSizes([700, 360])
        outer.addWidget(split, 1)

        self.footer = QLabel()
        self.footer.setWordWrap(True)
        self.footer.setObjectName("CalcDesc")
        self.footer.setTextInteractionFlags(Qt.TextSelectableByMouse)
        outer.addWidget(self.footer)

    # ------------------------------------------------------------ Daten
    def refresh(self) -> None:
        current_group = self.group.currentData()
        self.group.blockSignals(True)
        self.group.clear()
        self.group.addItem("Alle Gruppen", None)
        for g in self.lib.groups():
            self.group.addItem(g, g)
        idx = self.group.findData(current_group)
        self.group.setCurrentIndex(max(0, idx))
        self.group.blockSignals(False)

        selected = self.selected()
        self._rows = self.lib.search(self.search.text(), self.group.currentData())
        self.table.setRowCount(len(self._rows))
        for r, m in enumerate(self._rows):
            for c, (key, _) in enumerate(TABLE_COLS):
                it = QTableWidgetItem(_fmt(m, key))
                if key in PROPERTIES:
                    it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if not m.builtin:
                    it.setForeground(Qt.darkBlue)
                    if c == 0:
                        it.setText(f"{m.name}  ★")
                        it.setToolTip("Eigener Werkstoff (Team-Datei)")
                self.table.setItem(r, c, it)
        if selected:
            for r, m in enumerate(self._rows):
                if m.id == selected.id:
                    self.table.selectRow(r)
                    break
        if not self.table.selectedItems() and self._rows:
            self.table.selectRow(0)
        self._update_footer()
        self._show_detail()

    def _update_footer(self) -> None:
        path = self.lib.user_path
        txt = (f"Mitgeliefert: {len(self.lib.builtin)} · Eigene (★): {len(self.lib.user)} · "
               f"Team-Datei: {path}  (änderbar unter Extras › Einstellungen)")
        if self.lib.user_error:
            txt += f"<br><span style='color:{C['error']}'>{self.lib.user_error}</span>"
        self.footer.setText(txt)

    def selected(self) -> Material | None:
        rows = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        if rows and rows[0].row() < len(self._rows):
            return self._rows[rows[0].row()]
        return None

    def _show_detail(self) -> None:
        m = self.selected()
        if m is None:
            self.detail.setHtml(f"<p style='color:{C['muted']}'>Kein Werkstoff ausgewählt.</p>")
            for name in ("btn_bearbeiten", "btn_löschen", "btn_duplizieren"):
                if hasattr(self, name):
                    getattr(self, name).setEnabled(False)
            return
        rows = "".join(
            f"<tr><td style='padding:3px 10px 3px 0; white-space:nowrap'>{label}</td>"
            f"<td style='padding:3px 8px; color:{C['muted']}'><i>{rich(sym)}</i></td>"
            f"<td align='right' style='padding:3px 0'><b>{_fmt(m, key)}</b></td>"
            f"<td style='padding:3px 0 3px 6px; color:{C['muted']}'>{unit}</td></tr>"
            for key, (label, sym, unit, _) in PROPERTIES.items())
        src = "Mitgeliefert (schreibgeschützt)" if m.builtin else "Eigener Werkstoff (Team-Datei)"
        self.detail.setHtml(
            f"<h3 style='color:{C['heading']}; margin-bottom:2px'>{rich(m.name)}</h3>"
            f"<p style='color:{C['muted']}; margin-top:0'>{rich(m.gruppe)} · {rich(m.norm)}"
            f"{' · ' + rich(m.werkstoffnr) if m.werkstoffnr else ''}</p>"
            f"<table cellspacing='0'>{rows}</table>"
            f"<p>{rich(m.bemerkung)}</p><p style='color:{C['muted']}; font-size:9pt'>{src}</p>")
        if hasattr(self, "btn_bearbeiten"):
            self.btn_bearbeiten.setEnabled(not m.builtin)
            self.btn_löschen.setEnabled(not m.builtin)
            self.btn_duplizieren.setEnabled(True)

    def _double_click(self, *_):
        m = self.selected()
        if m is None:
            return
        if self.pick_mode:
            self.chosen.emit(m)
        elif not m.builtin:
            self.edit()
        else:
            self.duplicate()

    # ------------------------------------------------------- Bearbeiten
    def _run_dialog(self, mat: Material) -> Material | None:
        dlg = MaterialEditDialog(mat, self.lib.groups(), self)
        return dlg.result_material if dlg.exec() else None

    def _guard(self, fn) -> None:
        try:
            fn()
        except (OSError, ValueError, KeyError, PermissionError) as exc:
            QMessageBox.warning(self, "Materialdatenbank", str(exc))
        self.refresh()

    def new(self) -> None:
        mat = self._run_dialog(Material(id="", name="", gruppe=self.group.currentData() or ""))
        if mat:
            self._guard(lambda: self._select(self.lib.add(mat)))

    def duplicate(self) -> None:
        src = self.selected()
        if src is None:
            return
        mat = self._run_dialog(Material.from_dict({**asdict(src), "id": "", "name": f"{src.name} (Kopie)"}))
        if mat:
            self._guard(lambda: self._select(self.lib.add(mat)))

    def edit(self) -> None:
        src = self.selected()
        if src is None or src.builtin:
            return
        mat = self._run_dialog(src)
        if mat:
            self._guard(lambda: self.lib.update(mat))

    def delete(self) -> None:
        m = self.selected()
        if m is None or m.builtin:
            return
        if QMessageBox.question(self, "Werkstoff löschen",
                                f"„{m.name}“ aus der Team-Datei löschen?\nDas betrifft alle Kollegen, "
                                f"die diese Datei nutzen.") == QMessageBox.Yes:
            self._guard(lambda: self.lib.remove(m.id))

    def reload(self) -> None:
        self._guard(self.lib.reload)

    def _select(self, mat: Material) -> None:
        self.search.clear()
        self.group.setCurrentIndex(0)
        self.refresh()
        for r, m in enumerate(self._rows):
            if m.id == mat.id:
                self.table.selectRow(r)


class MaterialPickerDialog(QDialog):
    """Werkstoff auswählen, um Kennwerte in einen Rechner zu übernehmen."""

    def __init__(self, context, required: tuple[str, ...], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Werkstoff aus Datenbank übernehmen")
        self.resize(980, 560)
        self.required = required
        self.material: Material | None = None
        lay = QVBoxLayout(self)
        names = ", ".join(PROPERTIES[k][0] for k in required)
        hint = QLabel(f"Übernommen werden: <b>{names}</b>. Doppelklick oder „Übernehmen“.")
        lay.addWidget(hint)
        self.view = MaterialsView(context, self, pick_mode=True, required=required)
        self.view.chosen.connect(self._choose)
        lay.addWidget(self.view, 1)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("Übernehmen")
        bb.button(QDialogButtonBox.Cancel).setText("Abbrechen")
        bb.accepted.connect(lambda: self._choose(self.view.selected()))
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def _choose(self, mat: Material | None) -> None:
        if mat is None:
            return
        missing = [PROPERTIES[k][0] for k in self.required if getattr(mat, k) is None]
        if missing and len(missing) == len(self.required):
            QMessageBox.information(self, "Keine Werte", f"Für „{mat.name}“ sind keine passenden Kennwerte "
                                                         f"hinterlegt ({', '.join(missing)}).")
            return
        self.material = mat
        self.accept()
