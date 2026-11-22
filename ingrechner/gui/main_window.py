"""Hauptfenster: Seitenleiste mit Suche, Arbeitsbereich, Menüs und Projektverwaltung."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, QStandardPaths, Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (QFileDialog, QHBoxLayout, QLabel, QLineEdit, QMainWindow,
                               QMessageBox, QProgressDialog, QSplitter, QStackedWidget, QToolBar,
                               QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from ingrechner import APP_NAME, __version__
from ingrechner.core import registry
from ingrechner.core.export import export_csv, export_xlsx
from ingrechner.core.project import FILE_SUFFIX, Project
from ingrechner.core.project_report import build_project_report
from ingrechner.core.report import build_pdf, plot_png

from .calc_view import CalculatorView
from .context import AppContext
from .dialogs import ABOUT_HTML, ProjectMetaDialog, SettingsDialog
from .positions import PositionsPanel, ReportDialog
from .tools import tools
from .theme import C
from .widgets import Card, svg_to_png

ROLE_ID = Qt.UserRole
ROLE_KEYWORDS = Qt.UserRole + 1

# Bereiche späterer Ausbaustufen – sichtbar, aber noch deaktiviert
PLANNED: dict[str, list[str]] = {}


class MainWindow(QMainWindow):
    def __init__(self, context: AppContext | None = None, check_updates: bool = False) -> None:
        super().__init__()
        self.ctx = context or AppContext()
        self.settings: QSettings = self.ctx.settings
        self.calc_classes = registry.discover()
        self.tool_specs = tools()
        self.views: dict[str, QWidget] = {}
        self.calc_by_id = {c.id: c for c in self.calc_classes}
        self._last_pos: dict[str, str] = {}      # Rechner-ID -> zuletzt geöffnete Position
        self.project = Project()
        self.project.meta.bearbeiter = self.ctx.default_author
        self.resize(1360, 860)
        self._build_ui()
        self._build_actions()
        self._update_title()
        geo = self.settings.value("geometry")
        if geo is not None:
            self.restoreGeometry(geo)
        from .updates import UpdateChecker

        self.update_badge = None
        self._manual_update_check = False
        self.updater = UpdateChecker(self)
        self.updater.finished.connect(self._update_result)
        if check_updates and self.ctx.update_check:
            from PySide6.QtCore import QTimer

            QTimer.singleShot(3000, self.updater.check)

    # ---------------------------------------------------------------- UI
    def _build_ui(self) -> None:
        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        side = QWidget()
        side.setObjectName("Sidebar")
        side.setFixedWidth(290)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(12, 14, 12, 12)
        sl.setSpacing(8)
        t = QLabel(APP_NAME)
        t.setObjectName("AppTitle")
        sub = QLabel(f"Version {__version__}")
        sub.setObjectName("AppSub")
        sl.addWidget(t)
        sl.addWidget(sub)
        self.search = QLineEdit()
        self.search.setObjectName("SearchBox")
        self.search.setPlaceholderText("Suchen …  (Strg+K)")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._filter_tree)
        self.search.returnPressed.connect(self._open_first_match)
        sl.addWidget(self.search)

        self.positions = PositionsPanel(self.calc_classes)
        self.positions.open_requested.connect(self.open_position)
        self.positions.add_requested.connect(lambda cid: self.open_position(self.new_position(cid)))
        self.positions.duplicate_requested.connect(self.duplicate_position)
        self.positions.delete_requested.connect(self.delete_position)
        self.positions.move_requested.connect(self.move_position)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(14)
        self.tree.itemClicked.connect(self._on_tree_item)
        self.tree.itemActivated.connect(self._on_tree_item)
        self._fill_tree()
        split = QSplitter(Qt.Vertical)
        split.setChildrenCollapsible(False)
        split.setHandleWidth(10)
        split.addWidget(self.positions)
        split.addWidget(self.tree)
        split.setSizes([260, 420])
        sl.addWidget(split, 1)
        self.positions.refresh(self.project)
        root.addWidget(side)

        self.stack = QStackedWidget()
        self.welcome = self._build_welcome()
        self.stack.addWidget(self.welcome)
        root.addWidget(self.stack, 1)
        self.setCentralWidget(central)
        self.statusBar().showMessage("Bereit")

    def _fill_tree(self) -> None:
        cats: dict[str, QTreeWidgetItem] = {}
        bold = self.tree.font()
        bold.setBold(True)
        for cls in self.calc_classes:
            if cls.category not in cats:
                item = QTreeWidgetItem([cls.category])
                item.setFont(0, bold)
                item.setFlags(Qt.ItemIsEnabled)
                self.tree.addTopLevelItem(item)
                cats[cls.category] = item
            child = QTreeWidgetItem([cls.title])
            child.setData(0, ROLE_ID, cls.id)
            child.setData(0, ROLE_KEYWORDS, " ".join((cls.title, cls.category, *cls.keywords)).lower())
            child.setToolTip(0, cls.description)
            cats[cls.category].addChild(child)
        tool_cats: dict[str, QTreeWidgetItem] = {}
        for spec in self.tool_specs:
            if spec.category not in tool_cats:
                item = QTreeWidgetItem([spec.category])
                item.setFont(0, bold)
                item.setFlags(Qt.ItemIsEnabled)
                self.tree.addTopLevelItem(item)
                tool_cats[spec.category] = item
            child = QTreeWidgetItem([spec.title])
            child.setData(0, ROLE_ID, spec.id)
            child.setData(0, ROLE_KEYWORDS, " ".join((spec.title, spec.category, *spec.keywords)).lower())
            child.setToolTip(0, spec.description)
            tool_cats[spec.category].addChild(child)
        for cat, names in PLANNED.items():
            item = QTreeWidgetItem([f"{cat}  (geplant)"])
            item.setFont(0, bold)
            item.setFlags(Qt.ItemIsEnabled)
            item.setForeground(0, Qt.gray)
            self.tree.addTopLevelItem(item)
            for n in names:
                child = QTreeWidgetItem([n])
                child.setFlags(Qt.NoItemFlags)
                child.setToolTip(0, "Geplant für eine spätere Ausbaustufe")
                fnt = child.font(0)
                fnt.setItalic(True)
                child.setFont(0, fnt)
                child.setForeground(0, Qt.gray)
                child.setData(0, ROLE_KEYWORDS, n.lower())
                item.addChild(child)
        self.tree.expandAll()

    def _build_welcome(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(40, 36, 40, 36)
        h = QLabel("Willkommen")
        h.setObjectName("CalcTitle")
        lay.addWidget(h)
        card = Card()
        txt = QLabel(
            f"<p>Wählen Sie links einen Rechner aus oder drücken Sie <b>Strg+K</b>, um zu suchen.</p>"
            f"<ul style='margin-left:-20px'>"
            f"<li><b>Berechnen:</b> Enter, F5 oder Schaltfläche „Berechnen“</li>"
            f"<li><b>Positionen:</b> Jede Berechnung ist eine Position im Projekt (z. B. „Pos. 3 – Träger "
            f"Achse B“) – beliebig viele, auch vom selben Rechner (Liste oben links)</li>"
            f"<li><b>Projekt:</b> Speichert alle Positionen in einer <code>{FILE_SUFFIX}</code>-Datei</li>"
            f"<li><b>Bericht:</b> PDF einer Position (Strg+P) oder <b>Gesamtbericht</b> aller Positionen mit "
            f"Deckblatt, Inhaltsverzeichnis und Ergebnisübersicht (Strg+Umschalt+P)</li>"
            f"<li><b>Export:</b> Ergebnisse als Excel- oder CSV-Datei</li>"
            f"<li><b>Werkzeuge:</b> Einheitenumrechner, wissenschaftlicher Rechner, Materialdatenbank "
            f"(Werkstoffwerte per „Werkstoff …“ in Rechner übernehmen) und Funktionsplotter</li>"
            f"<li><b>Protokolle:</b> Besprechungsprotokolle nach Team-Vorlagen, Diktat per Mikrofon "
            f"(offline, Whisper), Folgeprotokoll mit offenen Aufgaben, PDF-Ausgabe</li></ul>"
            f"<p style='color:{C['muted']}'>Hinweis: Vereinfachte Rechenverfahren. Ergebnisse vor Verwendung in "
            f"Nachweisen fachkundig gegen die Originalnorm prüfen.</p>"
        )
        txt.setWordWrap(True)
        txt.setTextFormat(Qt.RichText)
        card.body.addWidget(txt)
        lay.addWidget(card)
        lay.addStretch(1)
        return w

    def _build_actions(self) -> None:
        def act(text, slot, shortcut=None, tip=None):
            a = QAction(text, self)
            a.triggered.connect(slot)
            if shortcut:
                a.setShortcut(QKeySequence(shortcut))
            a.setToolTip(tip or text)
            return a

        self.a_new = act("Neues Projekt", self.new_project, QKeySequence.New)
        self.a_open = act("Öffnen …", self.open_project, QKeySequence.Open)
        self.a_save = act("Speichern", self.save_project, QKeySequence.Save)
        self.a_save_as = act("Speichern unter …", self.save_project_as, QKeySequence.SaveAs)
        self.a_meta = act("Projektdaten …", self.edit_meta, "Ctrl+I")
        self.a_pdf = act("PDF-Bericht …", self.export_pdf, QKeySequence.Print,
                         "PDF-Bericht der aktuellen Position")
        self.a_report = act("Gesamtbericht …", self.export_report, "Ctrl+Shift+P",
                            "Alle Positionen in einem PDF mit Deckblatt und Inhaltsverzeichnis")
        self.a_xlsx = act("Export Excel …", lambda: self.export_table("xlsx"), "Ctrl+E")
        self.a_csv = act("Export CSV …", lambda: self.export_table("csv"))
        self.a_quit = act("Beenden", self.close, QKeySequence.Quit)
        self.a_search = act("Suchen", self._focus_search, "Ctrl+K")
        self.addAction(self.a_search)

        m = self.menuBar().addMenu("&Datei")
        for a in (self.a_new, self.a_open, None, self.a_save, self.a_save_as, None, self.a_meta, None,
                  self.a_pdf, self.a_report, self.a_xlsx, self.a_csv, None, self.a_quit):
            m.addSeparator() if a is None else m.addAction(a)
        x = self.menuBar().addMenu("E&xtras")
        x.addAction(act("Einstellungen …", self.edit_settings, QKeySequence.Preferences))
        h = self.menuBar().addMenu("&Hilfe")
        h.addAction(act("Nach Updates suchen …", self.check_updates_now))
        h.addAction(act("Fehlerprotokoll öffnen …", self.open_error_log))
        h.addAction(act("Über …", self.about))

        tb = QToolBar("Werkzeugleiste")
        tb.setMovable(False)
        tb.setToolButtonStyle(Qt.ToolButtonTextOnly)
        for a in (self.a_new, self.a_open, self.a_save, None, self.a_meta, None, self.a_pdf, self.a_report,
                  self.a_xlsx):
            tb.addSeparator() if a is None else tb.addAction(a)
        self.addToolBar(tb)
        self._update_actions()

    # ------------------------------------------------------- Navigation
    def _focus_search(self) -> None:
        self.search.setFocus()
        self.search.selectAll()

    def _filter_tree(self, text: str) -> None:
        q = text.strip().lower()
        for i in range(self.tree.topLevelItemCount()):
            cat = self.tree.topLevelItem(i)
            any_visible = False
            for j in range(cat.childCount()):
                child = cat.child(j)
                hit = not q or all(tok in (child.data(0, ROLE_KEYWORDS) or "") for tok in q.split())
                child.setHidden(not hit)
                any_visible |= hit
            cat.setHidden(not any_visible)

    def _open_first_match(self) -> None:
        for i in range(self.tree.topLevelItemCount()):
            cat = self.tree.topLevelItem(i)
            for j in range(cat.childCount()):
                child = cat.child(j)
                if not child.isHidden() and child.data(0, ROLE_ID):
                    self.tree.setCurrentItem(child)
                    self._on_tree_item(child)
                    return

    def _on_tree_item(self, item: QTreeWidgetItem, _col: int = 0) -> None:
        calc_id = item.data(0, ROLE_ID)
        if calc_id:
            self.open_calculator(calc_id)

    def open_calculator(self, calc_id: str) -> QWidget:
        """Rechner aus der Liste öffnen: zuletzt benutzte Position dieses Rechners oder eine neue."""
        if calc_id.startswith(("tool.", "proto.")):
            return self.open_tool(calc_id)
        existing = self.project.positions_for(calc_id)
        pid = self._last_pos.get(calc_id)
        if not any(p.id == pid for p in existing):
            pid = existing[-1].id if existing else self.new_position(calc_id)
        return self.open_position(pid)

    # ------------------------------------------------------- Positionen
    def new_position(self, calc_id: str, inputs: dict | None = None) -> str:
        pos = self.project.add_position(calc_id, inputs)
        self.positions.refresh(self.project, pos.id)
        self._update_title()
        return pos.id

    def open_position(self, pid: str) -> QWidget | None:
        key = f"pos:{pid}"
        view = self.views.get(key)
        if view is None:
            pos = self.project.get(pid)
            cls = self.calc_by_id.get(pos.calc)
            if cls is None:
                QMessageBox.warning(self, "Unbekannter Rechner",
                                    f"Die Position verwendet den Rechner „{pos.calc}“, den diese Programmversion "
                                    "nicht kennt. Die Daten bleiben beim Speichern erhalten.")
                return None
            view = CalculatorView(cls(), context=self.ctx)
            view.position_id = pid
            if pos.inputs:
                view.set_values(pos.inputs)
            view.set_notiz(pos.notiz)
            view.set_position(pos.nr, pos.titel)
            view.changed.connect(lambda v=view: self._on_view_changed(v))
            view.computed.connect(lambda v=view: self._on_view_changed(v))
            view.meta_changed.connect(lambda v=view: self._on_meta_changed(v))
            self.views[key] = view
            self.stack.addWidget(view)
        self.stack.setCurrentWidget(view)
        self._last_pos[view.calc.id] = pid
        self.positions.select(pid)
        pos = self.project.get(pid)
        self.statusBar().showMessage(f"{pos.label(view.calc.title)} · {view.calc.category} › {view.calc.title}")
        self._update_actions()
        return view

    def _sync_view(self, view: CalculatorView) -> None:
        if view.position_id is not None:
            self.project.update(view.position_id, inputs=view.valid_values(), notiz=view.notiz.toPlainText())

    def _sync_views(self) -> None:
        for v in self.views.values():
            if isinstance(v, CalculatorView):
                self._sync_view(v)

    def duplicate_position(self, pid: str) -> None:
        self._sync_views()
        new = self.project.duplicate(pid)
        self.positions.refresh(self.project, new.id)
        self.open_position(new.id)
        self._update_title()

    def delete_position(self, pid: str) -> None:
        pos = self.project.get(pid)
        cls = self.calc_by_id.get(pos.calc)
        label = pos.label(cls.title if cls else pos.calc)
        if QMessageBox.question(self, "Position löschen", f"„{label}“ aus dem Projekt löschen?") != QMessageBox.Yes:
            return
        idx = next(i for i, p in enumerate(self.project.positions) if p.id == pid)
        view = self.views.pop(f"pos:{pid}", None)
        if view is not None:
            self.stack.removeWidget(view)
            view.deleteLater()
        self.project.remove(pid)
        remaining = self.project.positions
        nxt = remaining[min(idx, len(remaining) - 1)].id if remaining else None
        self.positions.refresh(self.project, nxt)
        if nxt:
            self.open_position(nxt)
        else:
            self.stack.setCurrentWidget(self.welcome)
            self._update_actions()
        self._update_title()

    def move_position(self, pid: str, delta: int) -> None:
        if self.project.move(pid, delta):
            self.positions.refresh(self.project, pid)
            self._update_title()

    def open_tool(self, tool_id: str) -> QWidget:
        view = self.views.get(tool_id)
        spec = next(t for t in self.tool_specs if t.id == tool_id)
        if view is None:
            view = spec.factory(self.ctx)
            self.views[tool_id] = view
            self.stack.addWidget(view)
        elif hasattr(view, "refresh"):
            view.refresh()
        self.stack.setCurrentWidget(view)
        self.statusBar().showMessage(f"{spec.category} › {spec.title}")
        self._update_actions()
        return view

    def current_view(self) -> CalculatorView | None:
        w = self.stack.currentWidget()
        return w if isinstance(w, CalculatorView) else None

    def _on_view_changed(self, view: CalculatorView) -> None:
        self._sync_view(view)
        self._update_title()

    def _on_meta_changed(self, view: CalculatorView) -> None:
        if view.position_id is None:
            return
        self.project.update(view.position_id, nr=view.pos_nr.text().strip(), titel=view.pos_title.text().strip())
        self.positions.refresh(self.project, view.position_id)
        self._update_title()

    def _update_actions(self) -> None:
        has_view = self.current_view() is not None
        for a in (self.a_pdf, self.a_xlsx, self.a_csv):
            a.setEnabled(has_view)
        if hasattr(self, "a_report"):
            self.a_report.setEnabled(bool(self.project.positions))

    def _update_title(self) -> None:
        self._update_actions()
        star = " *" if self.project.dirty else ""
        self.setWindowTitle(f"{self.project.name}{star} – {APP_NAME}")

    # ---------------------------------------------------------- Projekt
    def _last_dir(self) -> str:
        default = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)
        return str(self.settings.value("lastDir", default))

    def _remember_dir(self, path: str | Path) -> None:
        self.settings.setValue("lastDir", str(Path(path).parent))

    def _confirm_discard(self) -> bool:
        if not self.project.dirty:
            return True
        r = QMessageBox.question(
            self, "Ungespeicherte Änderungen",
            f"Das Projekt „{self.project.name}“ enthält ungespeicherte Änderungen. Jetzt speichern?",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel, QMessageBox.Save)
        if r == QMessageBox.Save:
            return self.save_project()
        return r == QMessageBox.Discard

    def _reset_views(self) -> None:
        """Rechneransichten schließen (Projektwechsel). Werkzeuge bleiben erhalten."""
        for key in [k for k, v in self.views.items() if isinstance(v, CalculatorView)]:
            view = self.views.pop(key)
            self.stack.removeWidget(view)
            view.deleteLater()
        self.stack.setCurrentWidget(self.welcome)
        self.tree.clearSelection()
        self._last_pos.clear()
        self.positions.refresh(self.project)
        self._update_actions()

    def new_project(self) -> None:
        if not self._confirm_discard():
            return
        self.project = Project()
        self.project.meta.bearbeiter = self.ctx.default_author
        self._reset_views()
        self._update_title()
        self.edit_meta()

    def open_project(self, path: str | None = None) -> None:
        if not self._confirm_discard():
            return
        if not path:
            path, _ = QFileDialog.getOpenFileName(self, "Projekt öffnen", self._last_dir(),
                                                  f"Ingenieurs-Rechner-Projekt (*{FILE_SUFFIX})")
            if not path:
                return
        try:
            self.project = Project.load(path)
        except Exception as exc:  # noqa: BLE001 - dem Nutzer jeden Fehler zeigen
            QMessageBox.critical(self, "Fehler beim Öffnen", f"Die Datei konnte nicht geöffnet werden:\n{exc}")
            return
        self._remember_dir(path)
        self._reset_views()
        self._update_title()
        first = next((p.id for p in self.project.positions if p.calc in self.calc_by_id), None)
        if first:
            self.open_position(first)
        self.statusBar().showMessage(f"Projekt geladen: {path}", 5000)

    def save_project(self) -> bool:
        if self.project.path is None:
            return self.save_project_as()
        return self._save_to(self.project.path)

    def save_project_as(self) -> bool:
        suggestion = str(Path(self._last_dir()) / f"{self.project.name}{FILE_SUFFIX}")
        path, _ = QFileDialog.getSaveFileName(self, "Projekt speichern", suggestion,
                                              f"Ingenieurs-Rechner-Projekt (*{FILE_SUFFIX})")
        if not path:
            return False
        return self._save_to(Path(path))

    def _save_to(self, path: Path) -> bool:
        self._sync_views()
        try:
            saved = self.project.save(path)
        except OSError as exc:
            QMessageBox.critical(self, "Fehler beim Speichern", str(exc))
            return False
        self._remember_dir(saved)
        self._update_title()
        self.statusBar().showMessage(f"Gespeichert: {saved}", 5000)
        return True

    def edit_meta(self) -> None:
        dlg = ProjectMetaDialog(self.project.meta, self)
        if dlg.exec():
            new = dlg.meta()
            if new != self.project.meta:
                self.project.meta = new
                self.project.dirty = True
            self._update_title()

    # ----------------------------------------------------------- Export
    def _ready_view(self) -> CalculatorView | None:
        view = self.current_view()
        if view is None:
            return None
        res = view.result if view.is_current else view.compute()
        if not res.ok:
            QMessageBox.warning(self, "Export nicht möglich",
                                "Die Berechnung enthält Fehler. Bitte zuerst die Eingaben korrigieren.")
            return None
        return view

    def _position_label(self, view: CalculatorView) -> str:
        if view.position_id is None:
            return ""
        return self.project.get(view.position_id).label(view.calc.title)

    def _export_name(self, view: CalculatorView, suffix: str) -> str:
        label = self._position_label(view) or view.calc.title
        base = f"{self.project.meta.nummer + '_' if self.project.meta.nummer else ''}{label}"
        safe = "".join(ch if ch.isalnum() or ch in " -_." else "_" for ch in base).strip()
        return str(Path(self._last_dir()) / f"{safe}.{suffix}")

    def export_pdf(self) -> None:
        view = self._ready_view()
        if view is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "PDF-Bericht speichern", self._export_name(view, "pdf"),
                                              "PDF-Datei (*.pdf)")
        if not path:
            return
        raw = view.raw_values()
        svg = view.calc.sketch_svg(view.calc.defaults() | raw)
        try:
            build_pdf(path, view.calc, raw, view.result, self.project.meta, view.notiz.toPlainText(),
                      svg_to_png(svg) if svg else None, plot_png(view.calc, raw, view.result),
                      position=self._position_label(view))
        except OSError as exc:
            QMessageBox.critical(self, "Fehler", f"PDF konnte nicht geschrieben werden:\n{exc}")
            return
        self._remember_dir(path)
        self.statusBar().showMessage(f"PDF-Bericht erstellt: {path}", 6000)

    def export_report(self) -> None:
        """Gesamtbericht: alle (gewählten) Positionen in einem PDF."""
        self._sync_views()
        if not self.project.positions:
            QMessageBox.information(self, "Gesamtbericht", "Das Projekt enthält noch keine Positionen.")
            return
        dlg = ReportDialog(self.project, {c.id: c.title for c in self.calc_classes}, self.settings, self)
        if not dlg.exec():
            return
        opts = dlg.options()
        name = "".join(ch if ch.isalnum() or ch in " -_." else "_"
                       for ch in f"{self.project.meta.nummer + '_' if self.project.meta.nummer else ''}"
                                 f"{opts.titel} {self.project.name}").strip()
        path, _ = QFileDialog.getSaveFileName(self, "Gesamtbericht speichern", str(Path(self._last_dir()) / f"{name}.pdf"),
                                              "PDF-Datei (*.pdf)")
        if not path:
            return
        n = len(opts.position_ids or self.project.positions)
        prog = QProgressDialog("Gesamtbericht wird erstellt …", None, 0, n, self)
        prog.setWindowTitle("Gesamtbericht")
        prog.setMinimumDuration(300)
        prog.setWindowModality(Qt.WindowModal)

        def step(i: int, total: int) -> None:
            prog.setValue(i)
            prog.setLabelText(f"Position {i} von {total} …")

        try:
            build_project_report(path, self.project, self.calc_by_id, opts, sketch_png_fn=svg_to_png, progress=step)
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, "Fehler", f"Der Gesamtbericht konnte nicht erstellt werden:\n{exc}")
            return
        finally:
            prog.close()
        self._remember_dir(path)
        self.statusBar().showMessage(f"Gesamtbericht erstellt: {path}", 8000)
        box = QMessageBox(QMessageBox.Information, "Gesamtbericht", f"Der Gesamtbericht wurde erstellt:\n{path}",
                          parent=self)
        open_btn = box.addButton("Öffnen", QMessageBox.AcceptRole)
        box.addButton("Schließen", QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() is open_btn:
            from PySide6.QtCore import QUrl
            from PySide6.QtGui import QDesktopServices

            QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def export_table(self, kind: str) -> None:
        view = self._ready_view()
        if view is None:
            return
        flt = "Excel-Arbeitsmappe (*.xlsx)" if kind == "xlsx" else "CSV-Datei (*.csv)"
        path, _ = QFileDialog.getSaveFileName(self, "Exportieren", self._export_name(view, kind), flt)
        if not path:
            return
        fn = export_xlsx if kind == "xlsx" else export_csv
        try:
            fn(path, view.calc, view.raw_values(), view.result, self.project.meta)
        except OSError as exc:
            QMessageBox.critical(self, "Fehler", f"Export fehlgeschlagen:\n{exc}")
            return
        self._remember_dir(path)
        self.statusBar().showMessage(f"Exportiert: {path}", 6000)

    # ------------------------------------------------------------ Sonstiges
    def edit_settings(self, tab: str | None = None) -> None:
        dlg = SettingsDialog(self.ctx, self, tab=tab)
        if dlg.exec():
            for key in ("tool.materials", "proto.templates", "proto.editor"):
                view = self.views.get(key)
                if view is not None and hasattr(view, "refresh"):
                    view.refresh()
            self.statusBar().showMessage("Einstellungen gespeichert", 4000)

    def open_file(self, path: str) -> None:
        """Datei per Doppelklick/Kommandozeile öffnen (.irp Projekt, .irpk Protokoll)."""
        from ingrechner.core.protocols import PROTOCOL_SUFFIX

        if path.lower().endswith(PROTOCOL_SUFFIX):
            self.open_tool("proto.editor").open(path)
        elif path.lower().endswith(FILE_SUFFIX):
            self.open_project(path)

    def open_error_log(self) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        from .errors import log_path

        path = log_path()
        if path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        else:
            QMessageBox.information(self, "Fehlerprotokoll", f"Bisher wurden keine Fehler protokolliert.\n({path})")

    def check_updates_now(self) -> None:
        self._manual_update_check = True
        self.statusBar().showMessage("Suche nach Updates …", 3000)
        self.updater.check()

    def _update_result(self, info, error: str) -> None:
        from ingrechner import __version__
        from ingrechner.core.updates import is_newer

        from .updates import UpdateBadge, show_update_dialog

        manual, self._manual_update_check = self._manual_update_check, False
        if info is not None and is_newer(info.version):
            if self.update_badge is None:
                self.update_badge = UpdateBadge(info, self)
                self.statusBar().addPermanentWidget(self.update_badge)
            if manual:
                show_update_dialog(self, info)
        elif manual:
            if error:
                QMessageBox.warning(self, "Update-Prüfung",
                                    f"Die Update-Prüfung ist fehlgeschlagen (Internetverbindung?):\n{error}")
            else:
                QMessageBox.information(self, "Update-Prüfung",
                                        f"Sie verwenden die aktuelle Version ({__version__}).")

    def about(self) -> None:
        QMessageBox.about(self, f"Über {APP_NAME}", ABOUT_HTML)

    def closeEvent(self, event) -> None:
        for view in self.views.values():
            if hasattr(view, "maybe_close") and not view.maybe_close():
                event.ignore()
                return
        if self._confirm_discard():
            self.settings.setValue("geometry", self.saveGeometry())
            event.accept()
        else:
            event.ignore()
