"""Kleine wiederverwendbare Widgets."""

from __future__ import annotations

from PySide6.QtCore import QByteArray, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from ingrechner.core.model import Message
from ingrechner.core.textfmt import rich


class Card(QFrame):
    """Weiße Karte mit optionalem Titel."""

    def __init__(self, title: str | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(14, 12, 14, 14)
        self.body.setSpacing(8)
        if title:
            t = QLabel(title)
            t.setObjectName("CardTitle")
            self.body.addWidget(t)


class SketchWidget(QWidget):
    """Zeigt ein SVG unter Beibehaltung des Seitenverhältnisses."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._renderer = QSvgRenderer(self)
        self.setMinimumHeight(170)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

    def set_svg(self, svg: str | None) -> None:
        self._renderer.load(QByteArray((svg or "").encode("utf-8")))
        self.setVisible(bool(svg))
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(360, 220)

    def paintEvent(self, _event) -> None:
        if not self._renderer.isValid():
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        size = self._renderer.defaultSize().scaled(self.size(), Qt.KeepAspectRatio)
        x = (self.width() - size.width()) / 2
        y = (self.height() - size.height()) / 2
        self._renderer.render(p, QRectF(x, y, size.width(), size.height()))
        p.end()


def svg_to_png(svg: str, scale: float = 3.0) -> bytes:
    """SVG headless zu PNG rendern (für den PDF-Bericht)."""
    from PySide6.QtCore import QBuffer, QIODevice

    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    size = renderer.defaultSize() * scale
    img = QImage(size, QImage.Format_ARGB32)
    img.fill(Qt.white)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    renderer.render(p)
    p.end()
    buf = QBuffer()
    buf.open(QIODevice.WriteOnly)
    img.save(buf, "PNG")
    return bytes(buf.data())


ICONS = {"info": "ℹ", "warnung": "⚠", "fehler": "✖"}
COLORS = {"info": "#1f4e79", "warnung": "#9a5b00", "fehler": "#b3261e"}


class MessageBox(QFrame):
    """Farbige Hinweiszeile (Info / Warnung / Fehler)."""

    def __init__(self, msg: Message, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        lvl = msg.level.value
        self.setObjectName(f"Msg_{lvl}")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 6, 10, 6)
        icon = QLabel(ICONS[lvl])
        icon.setStyleSheet(f"color:{COLORS[lvl]}; font-size: 12pt; background: transparent; border: none;")
        icon.setFixedWidth(20)
        icon.setAlignment(Qt.AlignTop)
        text = QLabel(rich(msg.text))
        text.setTextFormat(Qt.RichText)
        text.setWordWrap(True)
        text.setStyleSheet("background: transparent; border: none;")
        text.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(icon)
        lay.addWidget(text, 1)


def page_header(layout: QVBoxLayout, title: str, description: str, badge: str | None = None) -> None:
    """Einheitlicher Seitenkopf (Titel, optional Badge, Beschreibung)."""
    t = QLabel(title)
    t.setObjectName("CalcTitle")
    head = QHBoxLayout()
    head.addWidget(t)
    if badge:
        b = QLabel(badge)
        b.setObjectName("NormBadge")
        b.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        head.addSpacing(10)
        head.addWidget(b, 0, Qt.AlignVCenter)
    head.addStretch(1)
    layout.addLayout(head)
    d = QLabel(description)
    d.setObjectName("CalcDesc")
    d.setWordWrap(True)
    layout.addWidget(d)


class TableEditor(QWidget):
    """Tabelleneditor für ein :class:`TableField` (z. B. Kennlinienpunkte aus dem Datenblatt).

    Zellen akzeptieren Komma oder Punkt; leere Zeilen werden ignoriert. Werte können auch per
    Strg+V aus Excel (Tabulator-getrennt) eingefügt werden.
    """

    edited = Signal()

    def __init__(self, field, parent: QWidget | None = None) -> None:
        from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QPushButton, QTableWidget

        from ingrechner.core.units import pretty_unit

        super().__init__(parent)
        self.field = field
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        self.table = QTableWidget(0, len(field.columns))
        self.table.setObjectName("FieldTable")
        self.table.setHorizontalHeaderLabels(
            [f"{c.label} [{pretty_unit(c.unit)}]" + (" (opt.)" if c.optional else "") if c.unit
             else c.label + (" (opt.)" if c.optional else "") for c in field.columns])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setDefaultSectionSize(24)
        self.table.setSelectionMode(QAbstractItemView.ContiguousSelection)
        self.table.setToolTip(field.tooltip)
        self.table.itemChanged.connect(self._changed)
        lay.addWidget(self.table)
        btns = QHBoxLayout()
        btns.setContentsMargins(0, 0, 0, 0)
        self.btn_add = QPushButton("+ Zeile")
        self.btn_del = QPushButton("− Zeile")
        for b in (self.btn_add, self.btn_del):
            b.setObjectName("Small")
            b.setCursor(Qt.PointingHandCursor)
        self.btn_add.clicked.connect(self.add_row)
        self.btn_del.clicked.connect(self.remove_row)
        hint = QLabel("Strg+V: aus Excel einfügen")
        hint.setToolTip("Tabulator-getrennte Werte aus Excel einfügen; ab Zeile 1, Spalte 1 wird die Tabelle ersetzt.")
        hint.setObjectName("Unit")
        btns.addWidget(self.btn_add)
        btns.addWidget(self.btn_del)
        btns.addStretch(1)
        btns.addWidget(hint)
        lay.addLayout(btns)
        from PySide6.QtGui import QKeySequence, QShortcut
        QShortcut(QKeySequence.Paste, self.table, activated=self.paste, context=Qt.WidgetShortcut)

    # ------------------------------------------------------------ API
    def set_rows(self, rows) -> None:
        from ingrechner.core.units import fmt_num

        self.table.blockSignals(True)
        rows = list(rows or [])
        self.table.setRowCount(max(len(rows), self.field.min_rows))
        for r in range(self.table.rowCount()):
            row = rows[r] if r < len(rows) else []
            for c, col in enumerate(self.field.columns):
                v = row[c] if c < len(row) else None
                if v is None or v == "":
                    text = ""
                elif isinstance(v, (int, float)):
                    text = fmt_num(float(v), col.decimals).replace(" ", "")
                else:
                    text = str(v)
                self.table.setItem(r, c, self._item(text))
        self.table.blockSignals(False)
        self._fit()

    def rows(self) -> list[list]:
        from ingrechner.core.units import parse_num

        out = []
        for r in range(self.table.rowCount()):
            row = []
            for c in range(self.table.columnCount()):
                it = self.table.item(r, c)
                text = it.text().strip() if it else ""
                if not text:
                    row.append(None)
                    continue
                try:
                    row.append(parse_num(text))
                except ValueError:
                    row.append(text)
            if any(v is not None for v in row):
                out.append(row)
        return out

    def add_row(self) -> None:
        if self.table.rowCount() >= self.field.max_rows:
            return
        r = self.table.currentRow() + 1 if self.table.currentRow() >= 0 else self.table.rowCount()
        self.table.blockSignals(True)
        self.table.insertRow(r)
        for c in range(self.table.columnCount()):
            self.table.setItem(r, c, self._item(""))
        self.table.blockSignals(False)
        self._fit()
        self.edited.emit()

    def remove_row(self) -> None:
        if self.table.rowCount() <= 1:
            return
        r = self.table.currentRow() if self.table.currentRow() >= 0 else self.table.rowCount() - 1
        self.table.removeRow(r)
        self._fit()
        self.edited.emit()

    def paste(self) -> None:
        from PySide6.QtWidgets import QApplication

        text = QApplication.clipboard().text()
        lines = [ln for ln in text.replace("\r", "").split("\n") if ln.strip()]
        if not lines:
            return
        r0 = max(self.table.currentRow(), 0)
        c0 = max(self.table.currentColumn(), 0)
        need = min(r0 + len(lines), self.field.max_rows)
        self.table.blockSignals(True)
        if r0 == 0 and c0 == 0:        # ganze Kennlinie eingefügt → Tabelle ersetzen
            self.table.setRowCount(max(need, self.field.min_rows))
            for r in range(self.table.rowCount()):
                for c in range(self.table.columnCount()):
                    self.table.setItem(r, c, self._item(""))
        while self.table.rowCount() < need:
            self.table.insertRow(self.table.rowCount())
        for i, ln in enumerate(lines[: need - r0]):
            cells = ln.split("\t") if "\t" in ln else ln.split(";")
            for j, cell in enumerate(cells):
                c = c0 + j
                if c < self.table.columnCount():
                    self.table.setItem(r0 + i, c, self._item(cell.strip()))
        self.table.blockSignals(False)
        self._fit()
        self.edited.emit()

    # --------------------------------------------------------- intern
    def _item(self, text: str):
        from PySide6.QtWidgets import QTableWidgetItem

        it = QTableWidgetItem(text)
        it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        return it

    def _changed(self, _item) -> None:
        self.edited.emit()

    def _fit(self) -> None:
        h = self.table.horizontalHeader().height() or 26
        self.table.setFixedHeight(h + 24 * min(self.table.rowCount(), 9) + 4)
        self.btn_add.setEnabled(self.table.rowCount() < self.field.max_rows)
        self.btn_del.setEnabled(self.table.rowCount() > 1)

    # Kompatibilität mit der Fehleranzeige der Eingabemaske
    def setProperty(self, name, value):  # noqa: N802 - Qt-API
        if name == "invalid":
            self.table.setProperty(name, value)
            self.table.style().unpolish(self.table)
            self.table.style().polish(self.table)
        return super().setProperty(name, value)


_LINK_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="2.2" '
    'stroke-linecap="round" stroke-linejoin="round"><path d="M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7l-1.7 1.7"/>'
    '<path d="M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7l1.7-1.7"/></svg>')
_ICON_CACHE: dict = {}


def link_icon(color: str = "#6b7b8c"):
    """Kettensymbol für verknüpfte Felder (als QIcon, aus SVG gerendert)."""
    from PySide6.QtGui import QIcon, QPixmap

    if color not in _ICON_CACHE:
        icon = QIcon()
        for size in (16, 32):
            img = QImage(size, size, QImage.Format_ARGB32)
            img.fill(0)
            r = QSvgRenderer(QByteArray(_LINK_SVG.format(c=color).encode()))
            painter = QPainter(img)
            painter.setRenderHint(QPainter.Antialiasing)
            r.render(painter)
            painter.end()
            icon.addPixmap(QPixmap.fromImage(img))
        _ICON_CACHE[color] = icon
    return _ICON_CACHE[color]
