"""Kleine wiederverwendbare Widgets."""

from __future__ import annotations

from PySide6.QtCore import QByteArray, QRectF, QSize, Qt
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
