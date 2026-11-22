"""Helles, ruhiges Farbschema in Grau- und Blautönen."""

from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication

C = {
    "bg": "#f3f5f8",          # Fensterhintergrund
    "panel": "#ffffff",       # Karten / Eingabeflächen
    "sidebar": "#e8edf3",
    "border": "#d3dbe4",
    "border_strong": "#b7c3cf",
    "text": "#1f2d3a",
    "muted": "#5f6f7f",
    "accent": "#1f6fb2",      # Primärblau
    "accent_hover": "#185d96",
    "accent_soft": "#d6e5f4", # Auswahl
    "accent_softer": "#edf3fa",
    "heading": "#1f4e79",
    "warn": "#9a5b00",
    "warn_bg": "#fff4e0",
    "warn_border": "#f0c987",
    "error": "#b3261e",
    "error_bg": "#fdecea",
    "error_border": "#efb1ab",
    "info_bg": "#edf3fa",
    "info_border": "#c4d7ec",
    "ok": "#2e7d4f",
}

QSS = f"""
QWidget {{ color: {C['text']}; }}
QMainWindow, QDialog {{ background: {C['bg']}; }}
QToolTip {{ background: {C['panel']}; color: {C['text']}; border: 1px solid {C['border_strong']}; padding: 4px; }}

/* Seitenleiste */
#Sidebar {{ background: {C['sidebar']}; border-right: 1px solid {C['border']}; }}
#Sidebar QTreeWidget {{ background: transparent; border: none; font-size: 10pt; outline: 0; }}
#Sidebar QTreeWidget::item {{ padding: 5px 4px; border-radius: 4px; }}
#Sidebar QTreeWidget::item:hover {{ background: {C['accent_softer']}; }}
#Sidebar QTreeWidget::item:selected {{ background: {C['accent_soft']}; color: {C['heading']}; }}
#SearchBox {{ background: {C['panel']}; border: 1px solid {C['border']}; border-radius: 6px; padding: 6px 8px; }}
#SearchBox:focus {{ border: 1px solid {C['accent']}; }}
#AppTitle {{ font-size: 12pt; font-weight: 600; color: {C['heading']}; }}
#AppSub {{ color: {C['muted']}; font-size: 8.5pt; }}

/* Karten */
#Card {{ background: {C['panel']}; border: 1px solid {C['border']}; border-radius: 8px; }}
#CardTitle {{ font-size: 10.5pt; font-weight: 600; color: {C['heading']}; }}
#CalcTitle {{ font-size: 16pt; font-weight: 600; color: {C['heading']}; }}
#CalcDesc {{ color: {C['muted']}; }}
#NormBadge {{ background: {C['accent_softer']}; color: {C['heading']}; border: 1px solid {C['info_border']};
              border-radius: 10px; padding: 2px 10px; font-size: 8.5pt; }}
#Stale {{ color: {C['warn']}; font-style: italic; }}
#FieldError {{ color: {C['error']}; font-size: 8.5pt; }}
#Unit {{ color: {C['muted']}; min-width: 58px; }}

QLineEdit, QComboBox, QPlainTextEdit, QTextEdit, QDateEdit {{
    background: {C['panel']}; border: 1px solid {C['border_strong']}; border-radius: 5px; padding: 4px 6px;
    selection-background-color: {C['accent_soft']}; selection-color: {C['text']};
}}
QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus {{ border: 1px solid {C['accent']}; }}
QLineEdit[invalid="true"] {{ border: 1px solid {C['error']}; background: {C['error_bg']}; }}
QTableWidget#FieldTable {{ background: {C['panel']}; border: 1px solid {C['border_strong']}; border-radius: 5px;
    gridline-color: {C['border']}; selection-background-color: {C['accent_soft']}; selection-color: {C['text']}; }}
QTableWidget#FieldTable[invalid="true"] {{ border: 1px solid {C['error']}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{ background: {C['panel']}; border: 1px solid {C['border_strong']};
    selection-background-color: {C['accent_soft']}; selection-color: {C['text']}; }}

QPushButton {{ background: {C['panel']}; border: 1px solid {C['border_strong']}; border-radius: 5px;
               padding: 6px 14px; }}
QPushButton:hover {{ background: {C['accent_softer']}; border-color: {C['accent']}; }}
QPushButton:pressed {{ background: {C['accent_soft']}; }}
QPushButton#Primary {{ background: {C['accent']}; color: white; border: 1px solid {C['accent']}; font-weight: 600; }}
QPushButton#Primary:hover {{ background: {C['accent_hover']}; }}
QPushButton#Small {{ padding: 2px 10px; font-size: 8.5pt; }}

QTableWidget {{ background: {C['panel']}; border: none; gridline-color: {C['border']};
                selection-background-color: {C['accent_soft']}; selection-color: {C['text']}; }}
QHeaderView::section {{ background: {C['accent_softer']}; color: {C['heading']}; border: none;
                        border-bottom: 1px solid {C['border_strong']}; padding: 5px; font-weight: 600; }}

QTabWidget::pane {{ border: 1px solid {C['border']}; border-radius: 6px; background: {C['panel']}; top: -1px; }}
QTabBar::tab {{ background: transparent; color: {C['muted']}; padding: 7px 16px; border: none;
                border-bottom: 2px solid transparent; }}
QTabBar::tab:selected {{ color: {C['heading']}; border-bottom: 2px solid {C['accent']}; font-weight: 600; }}
QTabBar::tab:hover {{ color: {C['text']}; }}
QTextBrowser {{ border: none; background: {C['panel']}; }}

QToolBar {{ background: {C['panel']}; border: none; border-bottom: 1px solid {C['border']}; spacing: 4px; padding: 3px; }}
QToolBar QToolButton {{ padding: 5px 9px; border-radius: 5px; }}
QToolBar QToolButton:hover {{ background: {C['accent_softer']}; }}
QMenuBar {{ background: {C['panel']}; }}
QMenuBar::item:selected {{ background: {C['accent_softer']}; }}
QMenu {{ background: {C['panel']}; border: 1px solid {C['border_strong']}; }}
QMenu::item {{ padding: 5px 22px; }}
QMenu::item:selected {{ background: {C['accent_soft']}; color: {C['text']}; }}
QStatusBar {{ background: {C['panel']}; border-top: 1px solid {C['border']}; color: {C['muted']}; }}
QScrollArea {{ border: none; background: transparent; }}
QSplitter::handle {{ background: {C['bg']}; }}
QScrollBar:vertical {{ background: transparent; width: 10px; }}
QScrollBar::handle:vertical {{ background: {C['border_strong']}; border-radius: 4px; min-height: 24px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}

#Msg_info {{ background: {C['info_bg']}; border: 1px solid {C['info_border']}; border-radius: 5px; }}
#Msg_warnung {{ background: {C['warn_bg']}; border: 1px solid {C['warn_border']}; border-radius: 5px; }}
#Msg_fehler {{ background: {C['error_bg']}; border: 1px solid {C['error_border']}; border-radius: 5px; }}
"""


def apply_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    pal = QPalette()
    pal.setColor(QPalette.Window, QColor(C["bg"]))
    pal.setColor(QPalette.WindowText, QColor(C["text"]))
    pal.setColor(QPalette.Base, QColor(C["panel"]))
    pal.setColor(QPalette.AlternateBase, QColor(C["accent_softer"]))
    pal.setColor(QPalette.Text, QColor(C["text"]))
    pal.setColor(QPalette.Button, QColor(C["panel"]))
    pal.setColor(QPalette.ButtonText, QColor(C["text"]))
    pal.setColor(QPalette.Highlight, QColor(C["accent_soft"]))
    pal.setColor(QPalette.HighlightedText, QColor(C["text"]))
    pal.setColor(QPalette.ToolTipBase, QColor(C["panel"]))
    pal.setColor(QPalette.ToolTipText, QColor(C["text"]))
    pal.setColor(QPalette.PlaceholderText, QColor(C["muted"]))
    pal.setColor(QPalette.Link, QColor(C["accent"]))
    app.setPalette(pal)
    font = QFont("Segoe UI", 10)
    font.setStyleHint(QFont.SansSerif)
    app.setFont(font)
    app.setStyleSheet(QSS)
