"""Vorlagen-Editor: Protokollvorlagen aus Bausteinen zusammenstellen (für das Team)."""

from __future__ import annotations

from copy import deepcopy

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QFormLayout, QHBoxLayout, QInputDialog, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QMenu, QMessageBox, QPlainTextEdit,
                               QPushButton, QSplitter, QToolButton, QVBoxLayout, QWidget)

from ingrechner.core.protocols import BLOCK_TYPES, Block, Template

from ..theme import C
from ..widgets import Card, page_header


class TemplateEditorView(QWidget):
    title = "Vorlagen-Editor"

    def __init__(self, context=None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctx = context
        self.current: Template | None = None     # Arbeitskopie
        self.dirty = False
        self._loading = False
        self._build()
        self.refresh()

    @property
    def lib(self):
        return self.ctx.templates

    # ---------------------------------------------------------------- UI
    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 16, 20, 16)
        outer.setSpacing(10)
        page_header(outer, self.title,
                    "Vorlagen bestehen aus Bausteinen (Kopffelder, Teilnehmer, Tagesordnung, Textabschnitte, "
                    "Aufgaben). Mitgelieferte Vorlagen sind schreibgeschützt – zum Anpassen duplizieren. "
                    "Team-Vorlagen (★) liegen in der Datei aus Extras › Einstellungen.")
        split = QSplitter(Qt.Horizontal)
        split.setChildrenCollapsible(False)
        split.setHandleWidth(12)
        outer.addWidget(split, 1)

        # ---- Vorlagenliste
        left = Card("Vorlagen")
        self.tpl_list = QListWidget()
        self.tpl_list.currentRowChanged.connect(self._select_template)
        left.body.addWidget(self.tpl_list, 1)
        row = QHBoxLayout()
        for text, slot in (("Neu", self.new), ("Duplizieren", self.duplicate), ("Löschen", self.delete)):
            b = QPushButton(text)
            b.clicked.connect(slot)
            row.addWidget(b)
            setattr(self, f"btn_{text.lower()}", b)
        left.body.addLayout(row)
        self.footer = QLabel()
        self.footer.setObjectName("CalcDesc")
        self.footer.setWordWrap(True)
        left.body.addWidget(self.footer)
        split.addWidget(left)

        # ---- Vorlage bearbeiten
        right = Card("Vorlage bearbeiten")
        self.readonly_hint = QLabel("Mitgelieferte Vorlage – schreibgeschützt. Zum Anpassen „Duplizieren“.")
        self.readonly_hint.setStyleSheet(f"color: {C['warn']}; background: {C['warn_bg']}; "
                                         f"border: 1px solid {C['warn_border']}; border-radius: 5px; padding: 6px;")
        right.body.addWidget(self.readonly_hint)
        form = QFormLayout()
        self.name = QLineEdit()
        self.titel = QLineEdit()
        self.titel.setPlaceholderText("Überschrift im PDF, z. B. „Protokoll Baubesprechung“")
        self.beschreibung = QPlainTextEdit()
        self.beschreibung.setFixedHeight(54)
        self.schluss = QPlainTextEdit()
        self.schluss.setFixedHeight(54)
        self.schluss.setPlaceholderText("Optional, z. B. Frist für Einwände gegen das Protokoll")
        form.addRow("Name", self.name)
        form.addRow("Überschrift", self.titel)
        form.addRow("Beschreibung", self.beschreibung)
        form.addRow("Schlusstext", self.schluss)
        right.body.addLayout(form)
        for w in (self.name, self.titel):
            w.textEdited.connect(self._meta_changed)
        for w in (self.beschreibung, self.schluss):
            w.textChanged.connect(self._meta_changed)

        blocks_row = QHBoxLayout()
        bl = QVBoxLayout()
        lbl = QLabel("Bausteine")
        lbl.setObjectName("CardTitle")
        bl.addWidget(lbl)
        self.block_list = QListWidget()
        self.block_list.setWordWrap(True)
        self.block_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.block_list.setMinimumWidth(260)
        self.block_list.currentRowChanged.connect(self._select_block)
        bl.addWidget(self.block_list, 1)
        brow = QHBoxLayout()
        self.btn_add = QToolButton()
        self.btn_add.setText("+ Baustein")
        self.btn_add.setPopupMode(QToolButton.InstantPopup)
        menu = QMenu(self)
        for typ, label in BLOCK_TYPES.items():
            menu.addAction(label, lambda t=typ: self.add_block(t))
        self.btn_add.setMenu(menu)
        brow.addWidget(self.btn_add)
        self.btn_up = QToolButton(text="▲")
        self.btn_up.clicked.connect(lambda: self.move_block(-1))
        self.btn_down = QToolButton(text="▼")
        self.btn_down.clicked.connect(lambda: self.move_block(1))
        self.btn_rm = QToolButton(text="✕")
        self.btn_rm.setToolTip("Baustein entfernen")
        self.btn_rm.clicked.connect(self.remove_block)
        for b in (self.btn_up, self.btn_down, self.btn_rm):
            brow.addWidget(b)
        brow.addStretch(1)
        bl.addLayout(brow)
        blocks_row.addLayout(bl, 1)

        detail = QFormLayout()
        self.b_typ = QComboBox()
        for typ, label in BLOCK_TYPES.items():
            self.b_typ.addItem(label, typ)
        self.b_typ.setEnabled(False)
        self.b_titel = QLineEdit()
        self.b_hint = QLineEdit()
        self.b_hint.setPlaceholderText("Hilfetext / Platzhalter für das Feld")
        self.b_vorgaben = QPlainTextEdit()
        self.b_vorgaben.setPlaceholderText("Tagesordnung: ein TOP je Zeile\nTextfeld: Standardwert")
        self.b_vorgaben_label = QLabel("Vorgaben")
        detail.addRow("Typ", self.b_typ)
        detail.addRow("Überschrift", self.b_titel)
        detail.addRow("Hinweis", self.b_hint)
        detail.addRow(self.b_vorgaben_label, self.b_vorgaben)
        self.b_titel.textEdited.connect(self._block_changed)
        self.b_hint.textEdited.connect(self._block_changed)
        self.b_vorgaben.textChanged.connect(self._block_changed)
        blocks_row.addLayout(detail, 2)
        right.body.addLayout(blocks_row, 1)

        save_row = QHBoxLayout()
        self.btn_save = QPushButton("Vorlage speichern")
        self.btn_save.setObjectName("Primary")
        self.btn_save.clicked.connect(self.save)
        self.btn_revert = QPushButton("Änderungen verwerfen")
        self.btn_revert.clicked.connect(lambda: self._select_template(self.tpl_list.currentRow(), force=True))
        self.state = QLabel()
        self.state.setObjectName("Stale")
        save_row.addWidget(self.btn_save)
        save_row.addWidget(self.btn_revert)
        save_row.addWidget(self.state, 1)
        right.body.addLayout(save_row)
        split.addWidget(right)
        split.setSizes([320, 780])

    # ------------------------------------------------------------ Daten
    def refresh(self, select_id: str | None = None) -> None:
        if select_id is None and self.current is not None:
            select_id = self.current.id
        self._templates = self.lib.all()
        self.tpl_list.blockSignals(True)
        self.tpl_list.clear()
        for t in self._templates:
            it = QListWidgetItem(("★ " if not t.builtin else "") + t.name)
            it.setToolTip(t.beschreibung)
            self.tpl_list.addItem(it)
        self.tpl_list.blockSignals(False)
        row = next((i for i, t in enumerate(self._templates) if t.id == select_id), 0)
        self.footer.setText(f"Team-Datei: {self.lib.user_path}" +
                            (f"<br><span style='color:{C['error']}'>{self.lib.user_error}</span>"
                             if self.lib.user_error else ""))
        self.tpl_list.setCurrentRow(row)
        self._select_template(row, force=True)

    def _select_template(self, row: int, force: bool = False) -> None:
        if row < 0 or row >= len(self._templates):
            return
        if not force and self.dirty and not self._confirm_discard():
            self.tpl_list.blockSignals(True)
            prev = next((i for i, t in enumerate(self._templates) if self.current and t.id == self.current.id), 0)
            self.tpl_list.setCurrentRow(prev)
            self.tpl_list.blockSignals(False)
            return
        self.current = deepcopy(self._templates[row])
        self._loading = True
        self.name.setText(self.current.name)
        self.titel.setText(self.current.titel)
        self.beschreibung.setPlainText(self.current.beschreibung)
        self.schluss.setPlainText(self.current.schlusstext)
        self._fill_blocks()
        self._loading = False
        ro = self.current.builtin
        self.readonly_hint.setVisible(ro)
        for w in (self.name, self.titel, self.beschreibung, self.schluss, self.b_titel, self.b_hint,
                  self.b_vorgaben):
            w.setReadOnly(ro)
        for w in (self.btn_add, self.btn_up, self.btn_down, self.btn_rm, self.btn_save, self.btn_revert,
                  self.btn_löschen):
            w.setEnabled(not ro)
        self.dirty = False
        self.state.setText("")

    def _fill_blocks(self, select: int = 0) -> None:
        self.block_list.blockSignals(True)
        self.block_list.clear()
        for b in self.current.blocks:
            it = QListWidgetItem(f"{b.titel or '(ohne Titel)'}\n    {BLOCK_TYPES[b.typ]}")
            self.block_list.addItem(it)
        self.block_list.blockSignals(False)
        if self.current.blocks:
            self.block_list.setCurrentRow(min(select, len(self.current.blocks) - 1))
        self._select_block(self.block_list.currentRow())

    def _select_block(self, row: int) -> None:
        self._loading = True
        b = self.current.blocks[row] if self.current and 0 <= row < len(self.current.blocks) else None
        self.b_titel.setText(b.titel if b else "")
        self.b_hint.setText(b.hinweis if b else "")
        self.b_typ.setCurrentIndex(self.b_typ.findData(b.typ) if b else -1)
        show_v = bool(b and b.typ in ("tagesordnung", "feld"))
        self.b_vorgaben.setVisible(show_v)
        self.b_vorgaben_label.setVisible(show_v)
        if b and b.typ == "feld":
            self.b_vorgaben_label.setText("Standardwert")
            self.b_vorgaben.setFixedHeight(36)
        else:
            self.b_vorgaben_label.setText("TOPs (je Zeile)")
            self.b_vorgaben.setFixedHeight(150)
        self.b_vorgaben.setPlainText("\n".join(b.vorgaben) if b else "")
        self._loading = False

    def _mark(self) -> None:
        if not self._loading:
            self.dirty = True
            self.state.setText("● ungespeicherte Änderungen")

    def _meta_changed(self, *_) -> None:
        if self._loading or self.current is None:
            return
        self.current.name = self.name.text()
        self.current.titel = self.titel.text()
        self.current.beschreibung = self.beschreibung.toPlainText()
        self.current.schlusstext = self.schluss.toPlainText()
        self._mark()

    def _block_changed(self, *_) -> None:
        if self._loading or self.current is None:
            return
        row = self.block_list.currentRow()
        if not 0 <= row < len(self.current.blocks):
            return
        b = self.current.blocks[row]
        b.titel = self.b_titel.text()
        b.hinweis = self.b_hint.text()
        lines = [ln.strip() for ln in self.b_vorgaben.toPlainText().splitlines() if ln.strip()]
        b.vorgaben = lines[:1] if b.typ == "feld" else lines
        it = self.block_list.item(row)
        it.setText(f"{b.titel or '(ohne Titel)'}\n    {BLOCK_TYPES[b.typ]}")
        self._mark()

    # ---------------------------------------------------- Bausteine
    def add_block(self, typ: str) -> None:
        if self.current is None or self.current.builtin:
            return
        default_titles = {"feld": "Neues Feld", "datum": "Datum", "zeit": "Uhrzeit", "teilnehmer": "Teilnehmer",
                          "text": "Abschnitt", "tagesordnung": "Tagesordnung", "aufgaben": "Aufgaben"}
        b = Block(self.current.new_block_key(typ), typ, default_titles[typ])
        row = self.block_list.currentRow() + 1 if self.block_list.currentRow() >= 0 else len(self.current.blocks)
        self.current.blocks.insert(row, b)
        self._fill_blocks(row)
        self.b_titel.setFocus()
        self.b_titel.selectAll()
        self._mark()

    def move_block(self, delta: int) -> None:
        row = self.block_list.currentRow()
        j = row + delta
        if self.current and 0 <= row < len(self.current.blocks) and 0 <= j < len(self.current.blocks):
            bl = self.current.blocks
            bl[row], bl[j] = bl[j], bl[row]
            self._fill_blocks(j)
            self._mark()

    def remove_block(self) -> None:
        row = self.block_list.currentRow()
        if self.current and 0 <= row < len(self.current.blocks):
            del self.current.blocks[row]
            self._fill_blocks(row)
            self._mark()

    # ---------------------------------------------------- Vorlagen
    def _confirm_discard(self) -> bool:
        return QMessageBox.question(self, "Ungespeicherte Änderungen",
                                    "Änderungen an der Vorlage verwerfen?") == QMessageBox.Yes

    def maybe_close(self) -> bool:
        return not self.dirty or self._confirm_discard()

    def _guard(self, fn):
        try:
            return fn()
        except (OSError, ValueError, KeyError, PermissionError) as exc:
            QMessageBox.warning(self, "Vorlagen", str(exc))
            return None

    def new(self) -> None:
        if self.dirty and not self._confirm_discard():
            return
        name, ok = QInputDialog.getText(self, "Neue Vorlage", "Name der Vorlage:")
        if not ok or not name.strip():
            return
        tpl = Template(id="", name=name.strip(), titel=f"Protokoll {name.strip()}", blocks=[
            Block("datum", "datum", "Datum"), Block("teilnehmer", "teilnehmer", "Teilnehmer"),
            Block("top", "tagesordnung", "Tagesordnung", vorgaben=["Begrüßung", "Verschiedenes"]),
            Block("aufgaben", "aufgaben", "Aufgaben")])
        created = self._guard(lambda: self.lib.add(tpl))
        if created:
            self.dirty = False
            self.refresh(created.id)

    def duplicate(self) -> None:
        if self.current is None:
            return
        if self.dirty and not self._confirm_discard():
            return
        src = self.lib.get(self.current.id)
        copy = Template.from_dict({**src.to_dict(), "id": "", "name": f"{src.name} (Team)"})
        created = self._guard(lambda: self.lib.add(copy))
        if created:
            self.dirty = False
            self.refresh(created.id)

    def delete(self) -> None:
        if self.current is None or self.current.builtin:
            return
        if QMessageBox.question(self, "Vorlage löschen", f"Vorlage „{self.current.name}“ für das ganze Team "
                                f"löschen?\nBereits erstellte Protokolle bleiben unverändert.") != QMessageBox.Yes:
            return
        if self._guard(lambda: (self.lib.remove(self.current.id), True)[1]):
            self.dirty = False
            self.current = None
            self.refresh()

    def save(self) -> bool:
        if self.current is None or self.current.builtin:
            return False
        if not self.current.name.strip():
            QMessageBox.warning(self, "Vorlage", "Bitte einen Namen eingeben.")
            return False
        if not self.current.blocks:
            QMessageBox.warning(self, "Vorlage", "Die Vorlage braucht mindestens einen Baustein.")
            return False
        try:
            self.lib.update(self.current)
        except (OSError, ValueError, KeyError, PermissionError) as exc:
            QMessageBox.warning(self, "Vorlagen", str(exc))
            return False
        self.dirty = False
        self.refresh(self.current.id)
        win = self.window()
        if hasattr(win, "statusBar"):
            win.statusBar().showMessage(f"Vorlage „{self.current.name}“ gespeichert", 4000)
        return True
