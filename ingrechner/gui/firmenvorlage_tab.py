"""Einstellungsseite „Firmenvorlage“: Briefkopf, Logo, Akzentfarbe und Fußzeile der PDF-Berichte."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel,
                               QLineEdit, QMessageBox, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget)

from ingrechner.core import briefkopf
from ingrechner.core.briefkopf import Firmenvorlage


class FirmenvorlageTab(QWidget):
    def __init__(self, context, path_row, parent=None) -> None:
        super().__init__(parent)
        from .context import default_vorlage_path

        self.ctx = context
        self._logo: bytes | None = None
        self._farbe = briefkopf.STANDARD_FARBE
        lay = QVBoxLayout(self)
        intro = QLabel("Briefkopf, Logo und Farbe für <b>alle PDF-Berichte</b> (Einzelnachweis, Gesamtbericht, "
                       "Besprechungsprotokoll). Für das ganze Team die Vorlagendatei auf einem Netzlaufwerk ablegen – "
                       "das Logo ist in der Datei enthalten.")
        intro.setWordWrap(True)
        intro.setObjectName("CalcDesc")
        lay.addWidget(intro)
        form = QFormLayout()
        self.path = path_row(form, "Vorlagendatei", str(context.vorlage_path), default_vorlage_path,
                             "Firmenvorlage (*.json)")
        self.btn_load = QPushButton("Aus Datei laden")
        self.btn_load.setToolTip("Vorlage aus der angegebenen Datei (z. B. Teamvorlage) in die Felder übernehmen")
        self.btn_load.clicked.connect(self._laden_klick)
        lrow = QHBoxLayout()
        lrow.addWidget(self.btn_load)
        lrow.addStretch(1)
        form.addRow("", lrow)

        self.firma = QLineEdit()
        self.firma.setPlaceholderText("z. B. Muster Ingenieure GmbH")
        form.addRow("Firmenname", self.firma)
        self.zusatz = QPlainTextEdit()
        self.zusatz.setPlaceholderText("Abteilung, Anschrift, Telefon … (bis zu 4 Zeilen)")
        self.zusatz.setFixedHeight(76)
        form.addRow("Zusatzzeilen", self.zusatz)

        logo_row = QHBoxLayout()
        self.logo_preview = QLabel("kein Logo")
        self.logo_preview.setFixedSize(180, 60)
        self.logo_preview.setAlignment(Qt.AlignCenter)
        self.logo_preview.setStyleSheet("border: 1px dashed #9aa7b4; background: white;")
        b_logo = QPushButton("Logo wählen …")
        b_logo.clicked.connect(self._logo_waehlen)
        self.b_logo_weg = QPushButton("Entfernen")
        self.b_logo_weg.clicked.connect(lambda: self._set_logo(None))
        self.logo_pos = QComboBox()
        self.logo_pos.addItem("Logo rechts", "rechts")
        self.logo_pos.addItem("Logo links", "links")
        logo_row.addWidget(self.logo_preview)
        col = QVBoxLayout()
        col.addWidget(b_logo)
        col.addWidget(self.b_logo_weg)
        col.addWidget(self.logo_pos)
        logo_row.addLayout(col)
        logo_row.addStretch(1)
        form.addRow("Logo", logo_row)

        farbe_row = QHBoxLayout()
        self.b_farbe = QPushButton()
        self.b_farbe.setFixedWidth(120)
        self.b_farbe.clicked.connect(self._farbe_waehlen)
        b_std = QPushButton("Standard")
        b_std.clicked.connect(lambda: self._set_farbe(briefkopf.STANDARD_FARBE))
        farbe_row.addWidget(self.b_farbe)
        farbe_row.addWidget(b_std)
        farbe_row.addStretch(1)
        form.addRow("Akzentfarbe", farbe_row)
        self.fuss = QLineEdit()
        self.fuss.setPlaceholderText("z. B. Vertraulich – nur für den internen Gebrauch")
        form.addRow("Fußzeile (Zusatz)", self.fuss)
        self.prog = QCheckBox("Programmname und Version in der Fußzeile")
        form.addRow("", self.prog)
        lay.addLayout(form)
        row = QHBoxLayout()
        self.b_vorschau = QPushButton("Vorschau-PDF öffnen")
        self.b_vorschau.clicked.connect(self.vorschau)
        row.addWidget(self.b_vorschau)
        row.addStretch(1)
        lay.addLayout(row)
        lay.addStretch(1)
        self.set_vorlage(briefkopf.aktuell())

    # ---------------------------------------------------------------- Werte
    def set_vorlage(self, v: Firmenvorlage) -> None:
        self.firma.setText(v.firma)
        self.zusatz.setPlainText(v.zusatz)
        self._set_logo(v.logo)
        self.logo_pos.setCurrentIndex(max(0, self.logo_pos.findData(v.logo_pos)))
        self._set_farbe(v.farbe_gueltig())
        self.fuss.setText(v.fusszeile)
        self.prog.setChecked(v.programmhinweis)

    def vorlage(self) -> Firmenvorlage:
        v = Firmenvorlage(firma=self.firma.text().strip(),
                          zusatz="\n".join(self.zusatz.toPlainText().splitlines()[:4]).strip(),
                          logo_pos=self.logo_pos.currentData(), farbe=self._farbe,
                          fusszeile=self.fuss.text().strip(), programmhinweis=self.prog.isChecked())
        v.set_logo(self._logo)
        return v

    def _set_logo(self, data: bytes | None) -> None:
        self._logo = data
        self.b_logo_weg.setEnabled(bool(data))
        if not data:
            self.logo_preview.setPixmap(QPixmap())
            self.logo_preview.setText("kein Logo")
            return
        pm = QPixmap()
        pm.loadFromData(QByteArray(data))
        self.logo_preview.setPixmap(pm.scaled(176, 56, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def _set_farbe(self, hexcode: str) -> None:
        self._farbe = hexcode
        text = "#ffffff" if QColor(hexcode).lightness() < 140 else "#000000"
        self.b_farbe.setText(hexcode)
        self.b_farbe.setStyleSheet(f"background: {hexcode}; color: {text}; border: 1px solid #6b7b8c;")

    # -------------------------------------------------------------- Aktionen
    def _logo_waehlen(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Logo wählen", "", "Bilder (*.png *.jpg *.jpeg)")
        if not path:
            return
        try:
            self._set_logo(briefkopf.logo_vorbereiten(Path(path).read_bytes()))
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Logo", str(exc))

    def _farbe_waehlen(self) -> None:
        c = QColorDialog.getColor(QColor(self._farbe), self, "Akzentfarbe wählen")
        if c.isValid():
            self._set_farbe(c.name())

    def _laden_klick(self) -> None:
        p = Path(self.path.text().strip())
        if not p.exists():
            QMessageBox.information(self, "Firmenvorlage", f"Die Datei existiert (noch) nicht:\n{p}")
            return
        try:
            self.set_vorlage(Firmenvorlage.load(p))
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Firmenvorlage", f"Die Datei konnte nicht gelesen werden:\n{exc}")

    def vorschau(self, oeffnen: bool = True) -> Path:
        """Erzeugt einen Beispielbericht mit der Vorlage aus den Feldern (ohne sie zu speichern)."""
        import tempfile

        from ingrechner.core.project import ProjectMeta
        from ingrechner.core.registry import by_id
        from ingrechner.core.report import build_pdf, plot_png

        alt = briefkopf.aktuell()
        briefkopf.setzen(self.vorlage())
        try:
            calc = by_id()["fl.druckverlust_rohr"]()
            raw = calc.defaults()
            res = calc.run(raw)
            path = Path(tempfile.gettempdir()) / "Ingenieurs-Rechner_Vorschau_Firmenvorlage.pdf"
            build_pdf(path, calc, raw, res, ProjectMeta(projekt="Vorschau Firmenvorlage", nummer="2026-001",
                                                         bearbeiter=self.ctx.default_author or "Bearbeiter"),
                      "Beispielbericht zur Kontrolle der Firmenvorlage.", None, plot_png(calc, raw, res),
                      position="Pos. 1 – Beispiel")
        finally:
            briefkopf.setzen(alt)
        if oeffnen:
            from PySide6.QtCore import QUrl
            from PySide6.QtGui import QDesktopServices

            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        return path

    def speichern(self) -> str | None:
        """Speichert die Vorlage in die Datei und aktiviert sie; liefert eine Fehlermeldung oder None."""
        v = self.vorlage()
        path = Path(self.path.text().strip() or str(self.ctx.vorlage_path))
        try:
            if v.hat_briefkopf or v.fusszeile or v.farbe != briefkopf.STANDARD_FARBE or not v.programmhinweis \
                    or path.exists():
                v.save(path)
        except OSError as exc:
            return f"Die Firmenvorlage konnte nicht gespeichert werden:\n{exc}"
        self.ctx.vorlage_path = path
        briefkopf.setzen(v)
        return None
