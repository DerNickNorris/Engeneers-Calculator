"""Besprechungsprotokoll ausfüllen: Bausteine der Vorlage als Formular, mit Diktat."""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QDate, QStandardPaths, Qt, QTimer, Signal
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDateEdit, QDialog, QDialogButtonBox,
                               QFileDialog, QFormLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QMessageBox, QPlainTextEdit, QPushButton,
                               QScrollArea, QTableWidget, QTableWidgetItem, QTextBrowser, QToolButton,
                               QVBoxLayout, QWidget)

from ingrechner.core.protocol_report import build_protocol_pdf
from ingrechner.core.protocols import (AUFGABE_ART, AUFGABE_STATUS, HEADER_TYPES, PROTOCOL_SUFFIX,
                                       TEILNEHMER_STATUS, Protocol, Template, continue_from)

from ..dictation import DictateButton
from ..theme import C
from ..widgets import Card, page_header

FILE_FILTER = f"Besprechungsprotokoll (*{PROTOCOL_SUFFIX})"


def _initials(name: str) -> str:
    parts = [p for p in name.replace("-", " ").split() if p[:1].isalpha()]
    return "".join(p[0].upper() for p in parts[:3])


class AutoText(QPlainTextEdit):
    """Mehrzeiliges Feld, das mit dem Inhalt wächst (kein Scrollen im Scrollen)."""

    def __init__(self, min_lines: int = 3, parent=None) -> None:
        super().__init__(parent)
        self._min = min_lines
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.document().contentsChanged.connect(self._fit)
        self._fit()

    def _fit(self) -> None:
        lh = self.fontMetrics().lineSpacing()
        lines = max(self._min, int(self.document().size().height()))
        self.setFixedHeight(min(lines, 40) * lh + 14)

    def resizeEvent(self, e) -> None:
        super().resizeEvent(e)
        self._fit()


# ============================================================== Bausteine
class BlockWidget(Card):
    changed = Signal()

    def __init__(self, ctx, block, title: str | None = None) -> None:
        super().__init__(title if title is not None else block.titel)
        self.ctx, self.block = ctx, block
        if block.hinweis and block.typ not in HEADER_TYPES:
            h = QLabel(block.hinweis)
            h.setObjectName("CalcDesc")
            h.setWordWrap(True)
            self.body.addWidget(h)

    def get(self):  # pragma: no cover - abstrakt
        raise NotImplementedError

    def set(self, value) -> None:  # pragma: no cover - abstrakt
        raise NotImplementedError


class HeaderBlock(Card):
    """Alle Kopf-Bausteine (Textfeld, Datum, Zeit) in einem zweispaltigen Formular."""

    changed = Signal()

    def __init__(self, ctx, blocks) -> None:
        super().__init__("Kopfdaten")
        self.blocks = blocks
        self.editors: dict[str, QWidget] = {}
        grid = QHBoxLayout()
        forms = [QFormLayout(), QFormLayout()]
        for f in forms:
            f.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
            grid.addLayout(f, 1)
        for i, b in enumerate(blocks):
            if b.typ == "datum":
                ed = QDateEdit()
                ed.setCalendarPopup(True)
                ed.setDisplayFormat("dd.MM.yyyy")
                ed.dateChanged.connect(self.changed)
            else:
                ed = QLineEdit()
                ed.setPlaceholderText(b.hinweis)
                ed.textEdited.connect(self.changed)
            self.editors[b.key] = ed
            forms[i % 2].addRow(b.titel, ed)
        self.body.addLayout(grid)

    def get(self) -> dict[str, str]:
        out = {}
        for k, ed in self.editors.items():
            out[k] = ed.date().toString("dd.MM.yyyy") if isinstance(ed, QDateEdit) else ed.text()
        return out

    def set(self, values: dict) -> None:
        for k, ed in self.editors.items():
            v = str(values.get(k, ""))
            ed.blockSignals(True)
            if isinstance(ed, QDateEdit):
                d = QDate.fromString(v, "dd.MM.yyyy")
                ed.setDate(d if d.isValid() else QDate.currentDate())
            else:
                ed.setText(v)
            ed.blockSignals(False)


class TextBlock(BlockWidget):
    def __init__(self, ctx, block) -> None:
        super().__init__(ctx, block)
        self.edit = AutoText(4)
        self.edit.setPlaceholderText("Text eingeben oder diktieren …")
        self.edit.textChanged.connect(self.changed)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(DictateButton(ctx, self.edit))
        self.body.addLayout(row)
        self.body.addWidget(self.edit)

    def get(self) -> str:
        return self.edit.toPlainText()

    def set(self, value) -> None:
        self.edit.blockSignals(True)
        self.edit.setPlainText(str(value or ""))
        self.edit.blockSignals(False)


class _TableBlock(BlockWidget):
    COLUMNS: list[str] = []

    def __init__(self, ctx, block) -> None:
        super().__init__(ctx, block)
        self.table = QTableWidget(0, len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setMinimumSectionSize(34)
        self.table.verticalHeader().setDefaultSectionSize(34)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.AllEditTriggers)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.table.itemChanged.connect(self._item_changed)
        self.body.addWidget(self.table)
        self.buttons = QHBoxLayout()
        add = QPushButton("+ Zeile")
        add.clicked.connect(lambda: (self.add_row({}), self.changed.emit()))
        rem = QPushButton("Zeile entfernen")
        rem.clicked.connect(self.remove_selected)
        self.buttons.addWidget(add)
        self.buttons.addWidget(rem)
        self.buttons.addStretch(1)
        self.body.addLayout(self.buttons)

    def _fit(self) -> None:
        self.table.resizeRowsToContents()
        h = self.table.horizontalHeader().height() + sum(self.table.rowHeight(r) for r in range(self.table.rowCount()))
        self.table.setFixedHeight(h + 6 + (28 if self.table.rowCount() == 0 else 0))

    def _item_changed(self, _item) -> None:
        self.changed.emit()

    def _combo(self, options: list[str], value: str, editable: bool = False) -> QComboBox:
        cb = QComboBox()
        cb.setEditable(editable)
        cb.addItems(options)
        if value and cb.findText(value) < 0:
            cb.addItem(value)
        cb.setCurrentText(value or options[0])
        cb.currentTextChanged.connect(self.changed)
        return cb

    def _text(self, r: int, c: int) -> str:
        w = self.table.cellWidget(r, c)
        if isinstance(w, QComboBox):
            return w.currentText()
        it = self.table.item(r, c)
        return it.text() if it else ""

    def remove_selected(self) -> None:
        rows = sorted({i.row() for i in self.table.selectionModel().selectedRows()}, reverse=True)
        if not rows and self.table.currentRow() >= 0:
            rows = [self.table.currentRow()]
        for r in rows:
            self.table.removeRow(r)
        self._fit()
        self.changed.emit()

    def add_row(self, data: dict) -> int:  # pragma: no cover - abstrakt
        raise NotImplementedError

    def set(self, value) -> None:
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        for row in value or []:
            self.add_row(row)
        self.table.blockSignals(False)
        self._fit()


class ParticipantsBlock(_TableBlock):
    COLUMNS = ["Name", "Firma / Funktion", "Kürzel", "Status"]

    def __init__(self, ctx, block) -> None:
        super().__init__(ctx, block)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(3, QHeaderView.ResizeToContents)

    def add_row(self, data: dict) -> int:
        r = self.table.rowCount()
        self.table.blockSignals(True)
        self.table.insertRow(r)
        for c, key in enumerate(("name", "firma", "kuerzel")):
            self.table.setItem(r, c, QTableWidgetItem(str(data.get(key, ""))))
        self.table.setCellWidget(r, 3, self._combo(TEILNEHMER_STATUS, data.get("status", "anwesend")))
        self.table.blockSignals(False)
        self._fit()
        return r

    def _item_changed(self, item) -> None:
        if item.column() == 0:  # Kürzel automatisch vorschlagen
            k = self.table.item(item.row(), 2)
            if k is not None and not k.text().strip():
                self.table.blockSignals(True)
                k.setText(_initials(item.text()))
                self.table.blockSignals(False)
        super()._item_changed(item)

    def get(self) -> list[dict]:
        out = []
        for r in range(self.table.rowCount()):
            row = {"name": self._text(r, 0), "firma": self._text(r, 1), "kuerzel": self._text(r, 2),
                   "status": self._text(r, 3)}
            if any(row[k].strip() for k in ("name", "firma")):
                out.append(row)
        return out

    def kuerzel(self) -> list[str]:
        return [p["kuerzel"] or p["name"] for p in self.get() if p["kuerzel"] or p["name"]]


class TasksBlock(_TableBlock):
    COLUMNS = ["Nr.", "Art", "Gegenstand", "Verantw.", "Termin", "Status"]

    def __init__(self, ctx, block, people_source=None) -> None:
        super().__init__(ctx, block)
        self.people_source = people_source or (lambda: [])
        hh = self.table.horizontalHeader()
        for c in (0, 1, 3, 4, 5):
            hh.setSectionResizeMode(c, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.setWordWrap(True)
        dict_btn = DictateButton(ctx, on_text=self._dictated)
        dict_btn.setText("🎤 Aufgabe diktieren")
        dict_btn._idle_look = lambda b=dict_btn: (DictateButton._idle_look(b), b.setText("🎤 Aufgabe diktieren"))
        self.buttons.insertWidget(2, dict_btn)
        legend = QLabel(" · ".join(f"{k} = {v}" for k, v in AUFGABE_ART.items()))
        legend.setObjectName("CalcDesc")
        self.buttons.addWidget(legend)

    def _dictated(self, text: str) -> None:
        r = self.add_row({"aufgabe": text})
        self.table.setCurrentCell(r, 3)
        self.changed.emit()

    def add_row(self, data: dict) -> int:
        r = self.table.rowCount()
        self.table.blockSignals(True)
        self.table.insertRow(r)
        nr = QTableWidgetItem(str(data.get("nr", "")))
        nr.setToolTip("Leer lassen – wird beim Speichern automatisch vergeben")
        self.table.setItem(r, 0, nr)
        art = self._combo(list(AUFGABE_ART), data.get("art", "A"))
        art.setToolTip("\n".join(f"{k} = {v}" for k, v in AUFGABE_ART.items()))
        self.table.setCellWidget(r, 1, art)
        task = QTableWidgetItem(str(data.get("aufgabe", "")))
        if data.get("herkunft"):
            task.setToolTip(f"Übernommen aus {data['herkunft']}")
            task.setData(Qt.UserRole, data["herkunft"])
        self.table.setItem(r, 2, task)
        people = self.people_source()
        self.table.setCellWidget(r, 3, self._combo(["", *people], str(data.get("verantwortlich", "")), editable=True))
        self.table.setItem(r, 4, QTableWidgetItem(str(data.get("termin", ""))))
        self.table.setCellWidget(r, 5, self._combo(AUFGABE_STATUS, data.get("status", "offen")))
        self.table.blockSignals(False)
        self._fit()
        return r

    def get(self) -> list[dict]:
        out = []
        for r in range(self.table.rowCount()):
            task_item = self.table.item(r, 2)
            row = {"nr": self._text(r, 0), "art": self._text(r, 1), "aufgabe": self._text(r, 2),
                   "verantwortlich": self._text(r, 3), "termin": self._text(r, 4), "status": self._text(r, 5)}
            if task_item is not None and task_item.data(Qt.UserRole):
                row["herkunft"] = task_item.data(Qt.UserRole)
            if row["aufgabe"].strip():
                out.append(row)
        return out


class TopWidget(QWidget):
    changed = Signal()
    remove = Signal(object)
    move = Signal(object, int)

    def __init__(self, ctx, number: int, data: dict) -> None:
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 6, 0, 6)
        lay.setSpacing(4)
        head = QHBoxLayout()
        self.num = QLabel()
        self.num.setStyleSheet(f"font-weight: 600; color: {C['heading']}; min-width: 54px;")
        self.title = QLineEdit(data.get("titel", ""))
        self.title.setPlaceholderText("Thema")
        self.title.setStyleSheet("font-weight: 600;")
        self.title.textEdited.connect(self.changed)
        self.text = AutoText(2)
        self.text.setPlaceholderText("Besprechungsinhalt eingeben oder diktieren …")
        self.text.setPlainText(data.get("text", ""))
        self.text.textChanged.connect(self.changed)
        head.addWidget(self.num)
        head.addWidget(self.title, 1)
        head.addWidget(DictateButton(ctx, self.text))
        for sym, tip, slot in (("▲", "nach oben", lambda: self.move.emit(self, -1)),
                               ("▼", "nach unten", lambda: self.move.emit(self, 1)),
                               ("✕", "TOP entfernen", lambda: self.remove.emit(self))):
            b = QToolButton()
            b.setText(sym)
            b.setToolTip(tip)
            b.clicked.connect(slot)
            head.addWidget(b)
        lay.addLayout(head)
        lay.addWidget(self.text)
        self.set_number(number)

    def set_number(self, n: int) -> None:
        self.num.setText(f"TOP {n}")

    def get(self) -> dict:
        return {"titel": self.title.text(), "text": self.text.toPlainText()}


class AgendaBlock(BlockWidget):
    def __init__(self, ctx, block) -> None:
        super().__init__(ctx, block)
        self.tops: list[TopWidget] = []
        self.list = QVBoxLayout()
        self.list.setSpacing(0)
        self.body.addLayout(self.list)
        add = QPushButton("+ TOP hinzufügen")
        add.clicked.connect(lambda: (self._add({}), self.changed.emit()))
        row = QHBoxLayout()
        row.addWidget(add)
        row.addStretch(1)
        self.body.addLayout(row)

    def _add(self, data: dict) -> TopWidget:
        w = TopWidget(self.ctx, len(self.tops) + 1, data)
        w.changed.connect(self.changed)
        w.remove.connect(self._remove)
        w.move.connect(self._move)
        self.tops.append(w)
        self.list.addWidget(w)
        return w

    def _renumber(self) -> None:
        for i, w in enumerate(self.tops, 1):
            w.set_number(i)
            self.list.removeWidget(w)
            self.list.addWidget(w)

    def _remove(self, w: TopWidget) -> None:
        if (w.title.text().strip() or w.text.toPlainText().strip()) and QMessageBox.question(
                self, "TOP entfernen", f"„{w.title.text() or 'TOP'}“ mit Inhalt entfernen?") != QMessageBox.Yes:
            return
        self.tops.remove(w)
        self.list.removeWidget(w)
        w.deleteLater()
        self._renumber()
        self.changed.emit()

    def _move(self, w: TopWidget, delta: int) -> None:
        i = self.tops.index(w)
        j = i + delta
        if 0 <= j < len(self.tops):
            self.tops[i], self.tops[j] = self.tops[j], self.tops[i]
            self._renumber()
            self.changed.emit()

    def get(self) -> list[dict]:
        return [w.get() for w in self.tops]

    def set(self, value) -> None:
        for w in self.tops:
            self.list.removeWidget(w)
            w.deleteLater()
        self.tops = []
        for d in value or []:
            self._add(d)


# ============================================================ Dialoge
class TemplateChooser(QDialog):
    def __init__(self, ctx, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Neues Protokoll – Vorlage wählen")
        self.resize(720, 420)
        self.templates: list[Template] = ctx.templates.all()
        lay = QHBoxLayout(self)
        self.list = QListWidget()
        for t in self.templates:
            it = QListWidgetItem(("★ " if not t.builtin else "") + t.name)
            self.list.addItem(it)
        self.list.currentRowChanged.connect(self._show)
        self.list.itemDoubleClicked.connect(self.accept)
        lay.addWidget(self.list, 2)
        right = QVBoxLayout()
        self.info = QTextBrowser()
        right.addWidget(self.info, 1)
        form = QFormLayout()
        self.nummer = QLineEdit("1")
        self.nummer.setToolTip("z. B. 1, BB-01 oder 2026/1 – Folgeprotokolle zählen automatisch weiter")
        form.addRow("Protokoll-Nr.", self.nummer)
        right.addLayout(form)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("Protokoll anlegen")
        bb.button(QDialogButtonBox.Cancel).setText("Abbrechen")
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        right.addWidget(bb)
        lay.addLayout(right, 3)
        self.list.setCurrentRow(0)

    def _show(self, row: int) -> None:
        if row < 0:
            return
        t = self.templates[row]
        from ingrechner.core.protocols import BLOCK_TYPES
        items = "".join(f"<li>{b.titel} <span style='color:{C['muted']}'>({BLOCK_TYPES[b.typ]})</span></li>"
                        for b in t.blocks)
        self.info.setHtml(f"<h3 style='color:{C['heading']}'>{t.name}</h3><p>{t.beschreibung}</p>"
                          f"<p><b>Bausteine:</b></p><ul>{items}</ul>")

    def selected(self) -> Template:
        return self.templates[max(0, self.list.currentRow())]


# ============================================================== Ansicht
class ProtocolView(QWidget):
    title = "Besprechungsprotokoll"

    def __init__(self, context=None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctx = context
        self.proto: Protocol | None = None
        self.dirty = False
        self.widgets: dict[str, QWidget] = {}
        self.header: HeaderBlock | None = None
        self._build()
        self._autosave = QTimer(self)
        self._autosave.setInterval(30_000)
        self._autosave.timeout.connect(self._write_recovery)
        self._autosave.start()
        QTimer.singleShot(0, self._offer_recovery)

    # ---------------------------------------------------------------- UI
    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 16, 20, 16)
        outer.setSpacing(10)
        page_header(outer, self.title,
                    "Protokoll nach Vorlage ausfüllen. „🎤 Diktat“ nimmt über das Mikrofon auf und erkennt die "
                    "Sprache offline auf diesem PC – es werden keine Daten übertragen.", "Offline-Diktat")
        bar = QHBoxLayout()
        self.btns = {}
        for key, text, slot in (("new", "Neu …", self.new), ("open", "Öffnen …", self.open),
                                ("save", "Speichern", self.save), ("saveas", "Speichern unter …", self.save_as),
                                ("cont", "Folgeprotokoll …", self.follow_up), ("pdf", "PDF …", self.export_pdf)):
            b = QPushButton(text)
            b.clicked.connect(slot)
            bar.addWidget(b)
            self.btns[key] = b
        self.btns["pdf"].setObjectName("Primary")
        self.btns["cont"].setToolTip("Neues Protokoll aus einem vorhandenen fortschreiben: Kopfdaten, Teilnehmer "
                                     "und offene Aufgaben werden übernommen, die Nummer zählt weiter.")
        bar.addStretch(1)
        bar.addWidget(QLabel("Nr."))
        self.nummer = QLineEdit()
        self.nummer.setMaximumWidth(110)
        self.nummer.textEdited.connect(self._mark_dirty)
        bar.addWidget(self.nummer)
        outer.addLayout(bar)
        self.file_label = QLabel()
        self.file_label.setObjectName("CalcDesc")
        outer.addWidget(self.file_label)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        outer.addWidget(self.scroll, 1)
        self._show_empty()

    def _show_empty(self) -> None:
        w = QWidget()
        lay = QVBoxLayout(w)
        card = Card("Kein Protokoll geöffnet")
        txt = QLabel("Legen Sie ein neues Protokoll nach Vorlage an, öffnen Sie ein vorhandenes oder schreiben Sie "
                     "ein Protokoll fort („Folgeprotokoll“) – offene Aufgaben werden dabei übernommen.")
        txt.setWordWrap(True)
        card.body.addWidget(txt)
        ok, msg = self.ctx.speech.status() if self.ctx else (False, "")
        state = QLabel(("✔ " if ok else "ℹ ") + msg)
        state.setStyleSheet(f"color: {C['ok'] if ok else C['muted']};")
        state.setWordWrap(True)
        card.body.addWidget(state)
        lay.addWidget(card)
        lay.addStretch(1)
        self.scroll.setWidget(w)
        for k in ("save", "saveas", "pdf"):
            self.btns[k].setEnabled(False)
        self.nummer.setEnabled(False)
        self.file_label.setText("")

    def _render(self) -> None:
        """Formular aus der Vorlage des aktuellen Protokolls aufbauen."""
        p = self.proto
        container = QWidget()
        lay = QVBoxLayout(container)
        lay.setContentsMargins(0, 0, 8, 0)
        lay.setSpacing(10)
        self.widgets = {}
        head_blocks = [b for b in p.template.blocks if b.typ in HEADER_TYPES]
        self.header = None
        participants = None
        if head_blocks:
            self.header = HeaderBlock(self.ctx, head_blocks)
            self.header.set({b.key: p.value(b.key) for b in head_blocks})
            self.header.changed.connect(self._mark_dirty)
            lay.addWidget(self.header)
        for b in p.template.blocks:
            if b.typ in HEADER_TYPES:
                continue
            if b.typ == "teilnehmer":
                w = ParticipantsBlock(self.ctx, b)
                participants = w
            elif b.typ == "text":
                w = TextBlock(self.ctx, b)
            elif b.typ == "tagesordnung":
                w = AgendaBlock(self.ctx, b)
            elif b.typ == "aufgaben":
                src = participants
                w = TasksBlock(self.ctx, b, people_source=(lambda s=src: s.kuerzel() if s else []))
            else:
                continue
            w.set(p.value(b.key))
            w.changed.connect(self._mark_dirty)
            self.widgets[b.key] = w
            lay.addWidget(w)
        lay.addStretch(1)
        self.scroll.setWidget(container)
        for k in ("save", "saveas", "pdf"):
            self.btns[k].setEnabled(True)
        self.nummer.setEnabled(True)
        self.nummer.setText(p.nummer)
        self.dirty = False
        self._update_label()

    def _mark_dirty(self, *_) -> None:
        if self.proto is not None:
            self.dirty = True
            self._update_label()

    def _update_label(self) -> None:
        if self.proto is None:
            return
        where = str(self.proto.path) if self.proto.path else "noch nicht gespeichert"
        self.file_label.setText(f"{self.proto.template.titel} · Vorlage „{self.proto.template.name}“ · "
                                f"{where}{'  ●  ungespeicherte Änderungen' if self.dirty else ''}")

    def refresh(self) -> None:
        if self.proto is None:
            self._show_empty()

    # ------------------------------------------------------------ Daten
    def collect(self) -> Protocol:
        p = self.proto
        p.nummer = self.nummer.text().strip() or p.nummer
        if self.header:
            p.values.update(self.header.get())
        for key, w in self.widgets.items():
            p.values[key] = w.get()
        p.renumber_tasks()
        return p

    def load_protocol(self, proto: Protocol, dirty: bool = False) -> None:
        self.proto = proto
        self._render()
        self.dirty = dirty
        self._update_label()

    # ---------------------------------------------------------- Aktionen
    def maybe_close(self) -> bool:
        if not (self.proto and self.dirty):
            return True
        r = QMessageBox.question(self, "Ungespeichertes Protokoll",
                                 "Das Protokoll enthält ungespeicherte Änderungen. Jetzt speichern?",
                                 QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel, QMessageBox.Save)
        if r == QMessageBox.Save:
            return self.save()
        if r == QMessageBox.Discard:
            self._clear_recovery()
            self.dirty = False
            return True
        return False

    def _start_dir(self) -> str:
        return str(self.ctx.settings.value("protocols/lastDir",
                                           QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)))

    def new(self) -> None:
        if not self.maybe_close():
            return
        dlg = TemplateChooser(self.ctx, self)
        if dlg.exec():
            proto = Protocol.new(dlg.selected(), dlg.nummer.text().strip() or "1")
            self._prefill_author(proto)
            self.load_protocol(proto, dirty=True)

    def _prefill_author(self, proto: Protocol) -> None:
        author = self.ctx.default_author
        if not author:
            return
        for b in proto.template.blocks:
            if b.typ == "feld" and "protokoll" in b.titel.lower() and not proto.value(b.key):
                proto.values[b.key] = author

    def open(self, path: str | None = None) -> None:
        if not self.maybe_close():
            return
        if not path:
            path, _ = QFileDialog.getOpenFileName(self, "Protokoll öffnen", self._start_dir(), FILE_FILTER)
            if not path:
                return
        try:
            proto = Protocol.load(path)
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
            QMessageBox.critical(self, "Fehler beim Öffnen", f"Das Protokoll konnte nicht geöffnet werden:\n{exc}")
            return
        self.ctx.settings.setValue("protocols/lastDir", str(Path(path).parent))
        self.load_protocol(proto)

    def follow_up(self) -> None:
        if not self.maybe_close():
            return
        if self.proto is not None and self.proto.path is not None:
            prev = self.collect()
        else:
            path, _ = QFileDialog.getOpenFileName(self, "Vorheriges Protokoll wählen", self._start_dir(), FILE_FILTER)
            if not path:
                return
            try:
                prev = Protocol.load(path)
            except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
                QMessageBox.critical(self, "Fehler", str(exc))
                return
        new = continue_from(prev)
        self.load_protocol(new, dirty=True)
        n = len(new.open_tasks())
        win = self.window()
        if hasattr(win, "statusBar"):
            win.statusBar().showMessage(f"Folgeprotokoll Nr. {new.nummer} angelegt – {n} offene Aufgabe(n) übernommen.",
                                        6000)

    def save(self) -> bool:
        if self.proto is None:
            return False
        if self.proto.path is None:
            return self.save_as()
        return self._save_to(self.proto.path)

    def save_as(self) -> bool:
        if self.proto is None:
            return False
        p = self.collect()
        start = str(Path(self._start_dir()) / (p.suggested_filename() + PROTOCOL_SUFFIX))
        path, _ = QFileDialog.getSaveFileName(self, "Protokoll speichern", start, FILE_FILTER)
        if not path:
            return False
        return self._save_to(Path(path))

    def _save_to(self, path: Path) -> bool:
        try:
            saved = self.collect().save(path)
        except OSError as exc:
            QMessageBox.critical(self, "Fehler beim Speichern", str(exc))
            return False
        self.ctx.settings.setValue("protocols/lastDir", str(saved.parent))
        self._refresh_numbers()
        self.dirty = False
        self._clear_recovery()
        self._update_label()
        win = self.window()
        if hasattr(win, "statusBar"):
            win.statusBar().showMessage(f"Protokoll gespeichert: {saved}", 5000)
        return True

    def _refresh_numbers(self) -> None:
        """Automatisch vergebene Aufgabennummern in der Tabelle anzeigen."""
        for key, w in self.widgets.items():
            if isinstance(w, TasksBlock):
                w.set(self.proto.value(key))

    def export_pdf(self) -> None:
        if self.proto is None:
            return
        p = self.collect()
        self._refresh_numbers()
        base = Path(str(p.path.parent)) if p.path else Path(self._start_dir())
        start = str(base / (p.suggested_filename() + ".pdf"))
        path, _ = QFileDialog.getSaveFileName(self, "Protokoll als PDF", start, "PDF-Datei (*.pdf)")
        if not path:
            return
        try:
            build_protocol_pdf(path, p)
        except OSError as exc:
            QMessageBox.critical(self, "Fehler", f"PDF konnte nicht geschrieben werden:\n{exc}")
            return
        win = self.window()
        if hasattr(win, "statusBar"):
            win.statusBar().showMessage(f"PDF erstellt: {path}", 6000)

    # ------------------------------------------- Wiederherstellung
    def _recovery_path(self) -> Path:
        from ..context import app_data_dir

        return app_data_dir() / f"wiederherstellung{PROTOCOL_SUFFIX}"

    def _write_recovery(self) -> None:
        if self.proto is None or not self.dirty:
            return
        try:
            rp = self._recovery_path()
            rp.parent.mkdir(parents=True, exist_ok=True)
            p = self.collect()
            data = p.to_dict()
            data["original_pfad"] = str(p.path) if p.path else ""
            rp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass

    def _clear_recovery(self) -> None:
        try:
            self._recovery_path().unlink(missing_ok=True)
        except OSError:
            pass

    def _offer_recovery(self) -> None:
        rp = self._recovery_path()
        if not rp.exists():
            return
        try:
            data = json.loads(rp.read_text(encoding="utf-8"))
            proto = Protocol.load(rp)
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            self._clear_recovery()
            return
        r = QMessageBox.question(self, "Protokoll wiederherstellen",
                                 f"Es wurde ein nicht gespeichertes Protokoll gefunden:\n„{proto.title}“\n\n"
                                 f"Wiederherstellen?")
        if r == QMessageBox.Yes:
            proto.path = Path(data["original_pfad"]) if data.get("original_pfad") else None
            self.load_protocol(proto, dirty=True)
        else:
            self._clear_recovery()
