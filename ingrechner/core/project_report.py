"""Gesamtbericht eines Projekts: Deckblatt, Inhaltsverzeichnis, Ergebnisübersicht, alle Positionen."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import (BaseDocTemplate, Frame, NextPageTemplate, PageBreak, PageTemplate,
                                Paragraph, Spacer, Table, TableStyle)
from reportlab.platypus.tableofcontents import TableOfContents

from .. import APP_NAME, __version__
from .model import Calculator, CalcResult, Level
from .project import Position, Project
from .links import beschreibung
from .report import (GREY, GRID, WARN, _register_fonts, _styles, calc_body,
                     plot_png, akzent, akzent_hell, briefkopf_zeichnen, fusszeile_text, rand_oben, seitenrahmen)
from .textfmt import rich
from .units import fmt_num, unit_html

OK_GREEN = "#2e7d4f"
ERR_RED = "#b3261e"


@dataclass
class ReportOptions:
    titel: str = "Berechnungsnachweise"
    deckblatt: bool = True
    inhaltsverzeichnis: bool = True
    uebersicht: bool = True
    skizzen: bool = True
    diagramme: bool = True
    position_ids: list[str] | None = None   # None = alle Positionen
    extra: dict = field(default_factory=dict)


@dataclass
class PositionResult:
    position: Position
    calc: Calculator | None
    result: CalcResult | None
    inputs: dict | None = None      # Eingaben mit übernommenen (verknüpften) Werten

    @property
    def status(self) -> tuple[str, str]:
        """(Text, Farbe) für die Übersicht."""
        if self.calc is None or self.result is None:
            return "Rechner unbekannt", ERR_RED
        r = self.result
        if r.field_errors or any(m.level is Level.FEHLER for m in r.messages):
            return "Fehler", ERR_RED
        warnings = sum(1 for m in r.messages if m.level is Level.WARNUNG)
        if warnings:
            return f"{warnings} Warnung{'en' if warnings > 1 else ''}", WARN.hexval().replace("0x", "#")
        return "erfüllt", OK_GREEN


def evaluate(project: Project, calcs: dict[str, type[Calculator]],
             position_ids: list[str] | None = None) -> list[PositionResult]:
    """Rechnet alle (bzw. die gewählten) Positionen aus den gespeicherten Eingaben neu.

    Verknüpfte Felder erhalten den aktuellen Wert ihrer Quellposition.
    """
    from .links import aufloesen

    res = aufloesen(project, calcs)
    out = []
    for pos in project.positions:
        if position_ids is not None and pos.id not in position_ids:
            continue
        cls = calcs.get(pos.calc)
        if cls is None:
            out.append(PositionResult(pos, None, None))
            continue
        calc = cls()
        inputs = res.inputs.get(pos.id, pos.inputs)
        out.append(PositionResult(pos, calc, res.results.get(pos.id) or calc.run(inputs), inputs))
    return out


class _NumberedCanvas(rl_canvas.Canvas):
    """Canvas, der „Seite x von y“ schreibt (Seitenzahl erst am Ende bekannt)."""

    footer_left = ""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved = []

    def showPage(self):
        self._saved.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved)
        for state in self._saved:
            self.__dict__.update(state)
            if self._pageNumber > 1 or not getattr(self, "_has_cover", False):
                seitenrahmen(self, self.footer_left, f"Seite {self._pageNumber} von {total}")
            else:
                self.saveState()
                briefkopf_zeichnen(self, gross=True)
                self.restoreState()
            super().showPage()
        super().save()


class _Doc(BaseDocTemplate):
    def __init__(self, filename, **kw):
        super().__init__(filename, **kw)
        frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="f")
        self.addPageTemplates([PageTemplate(id="cover", frames=[frame]),
                               PageTemplate(id="normal", frames=[frame])])

    def afterFlowable(self, flowable):
        """Überschriften ins Inhaltsverzeichnis und als PDF-Lesezeichen eintragen."""
        if isinstance(flowable, Paragraph) and flowable.style.name in ("toc0", "toc1"):
            level = 0 if flowable.style.name == "toc0" else 1
            text = flowable.getPlainText()
            key = f"h{id(flowable)}"
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(text, key, level=level, closed=level > 0)
            self.notify("TOCEntry", (level, text, self.page, key))


def _cover(project: Project, opts: ReportOptions, results: list[PositionResult], st, page_w) -> list:
    m = project.meta
    big = ParagraphStyle("big", parent=st["title"], fontSize=24, leading=30, spaceAfter=6)
    sub = ParagraphStyle("sub", parent=st["base"], fontSize=13, leading=18, textColor=GREY)
    story: list = [Spacer(1, 45 * mm), Paragraph(rich(opts.titel), big)]
    if m.projekt:
        story.append(Paragraph(rich(m.projekt), sub))
    story.append(Spacer(1, 16 * mm))
    rows = [("Projekt-Nr.", m.nummer), ("Aufgestellt von", m.bearbeiter), ("Geprüft von", m.pruefer),
            ("Datum", m.datum), ("Umfang", f"{len(results)} Position{'en' if len(results) != 1 else ''}"),
            ("Bemerkung", m.bemerkung)]
    data = [[Paragraph(f"<b>{k}</b>", st["cell"]), Paragraph(rich(v or "–").replace("\n", "<br/>"), st["cell"])]
            for k, v in rows if v or k in ("Projekt-Nr.", "Datum", "Umfang")]
    t = Table(data, colWidths=[40 * mm, page_w - 40 * mm])
    t.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.4, GRID), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    story += [t, Spacer(1, 30 * mm)]
    sig = Table([["Aufgestellt:", "", "Geprüft:", ""],
                 ["Ort, Datum", "Unterschrift", "Ort, Datum", "Unterschrift"]],
                colWidths=[page_w / 4] * 4, rowHeights=[16 * mm, 6 * mm])
    sig.setStyle(TableStyle([("FONT", (0, 0), (-1, -1), "DejaVu", 8), ("TEXTCOLOR", (0, 1), (-1, 1), GREY),
                             ("LINEBELOW", (0, 0), (-1, 0), 0.6, GREY), ("VALIGN", (0, 0), (-1, 0), "TOP"),
                             ("LEFTPADDING", (0, 0), (-1, -1), 2), ("RIGHTPADDING", (0, 0), (-1, -1), 8)]))
    story += [sig, Spacer(1, 20 * mm),
              Paragraph(f"Erstellt mit {APP_NAME} {__version__} am {datetime.now().strftime('%d.%m.%Y')}. "
                        "Vereinfachte Rechenverfahren – vor Verwendung fachkundig gegen die "
                        "Originalnormen prüfen.", st["small"])]
    return story


def _key_values(result: CalcResult, limit: int = 3) -> str:
    vals = [v for v in result.values if v.highlight][:limit] or result.values[:limit]
    return "<br/>".join(f"{rich(v.symbol)} = {fmt_num(v.value, v.decimals)} {unit_html(v.unit)}" for v in vals)


def _overview(results: list[PositionResult], st, page_w) -> list:
    vals_style = ParagraphStyle("vals", parent=st["cell"], leading=14)   # Platz für Tief-/Hochstellungen
    head = ["Pos.", "Bezeichnung / Rechner", "Maßgebende Ergebnisse", "Status"]
    rows = [[Paragraph(f"<b>{h}</b>", st["cell"]) for h in head]]
    style = [("BACKGROUND", (0, 0), (-1, 0), akzent_hell()), ("LINEBELOW", (0, 0), (-1, 0), 0.8, akzent()),
             ("LINEBELOW", (0, 1), (-1, -1), 0.4, GRID), ("VALIGN", (0, 0), (-1, -1), "TOP")]
    for pr in results:
        p = pr.position
        calc_title = pr.calc.title if pr.calc else p.calc
        name = rich(p.titel.strip() or calc_title)
        sub = f"<br/><font size='7' color='#5b6b7b'>{rich(calc_title)}</font>" if p.titel.strip() else ""
        vals = _key_values(pr.result) if pr.result and pr.result.ok and pr.result.values else "–"
        text, color = pr.status
        rows.append([Paragraph(rich(p.nr or "–"), st["cell"]), Paragraph(name + sub, st["cell"]),
                     Paragraph(vals, vals_style),
                     Paragraph(f"<font color='{color}'><b>{'✔ ' if text == 'erfüllt' else '⚠ '}{text}</b></font>",
                               st["cell"])])
    t = Table(rows, colWidths=[16 * mm, page_w * 0.34, page_w - 16 * mm - page_w * 0.34 - 36 * mm, 36 * mm],
              repeatRows=1)
    t.setStyle(TableStyle(style))
    return [t]


def build_project_report(path: str | Path, project: Project, calcs: dict[str, type[Calculator]],
                         opts: ReportOptions | None = None,
                         sketch_png_fn: Callable[[str], bytes] | None = None,
                         progress: Callable[[int, int], None] | None = None) -> Path:
    """Erzeugt den Gesamtbericht als PDF.

    ``sketch_png_fn`` wandelt die SVG-Skizze in PNG um (in der GUI über Qt); ohne
    Funktion werden keine Skizzen eingebunden.
    """
    _register_fonts()
    opts = opts or ReportOptions()
    st = _styles()
    st["toc0"] = ParagraphStyle("toc0", parent=st["title"], fontSize=14, leading=18, spaceAfter=1)
    st["toc1"] = ParagraphStyle("toc1", parent=st["h2"], fontSize=12, leading=16, spaceBefore=0)
    path = Path(path)
    page_w = A4[0] - 36 * mm
    results = evaluate(project, calcs, opts.position_ids)
    if not results:
        raise ValueError("Keine Positionen für den Bericht ausgewählt.")

    story: list = []
    if opts.deckblatt:
        story += _cover(project, opts, results, st, page_w)
        story += [NextPageTemplate("normal"), PageBreak()]
    if opts.inhaltsverzeichnis:
        toc = TableOfContents()
        toc.levelStyles = [
            ParagraphStyle("t0", fontName="DejaVu-Bold", fontSize=9.5, leading=14, leftIndent=0,
                           textColor=akzent()),
            ParagraphStyle("t1", fontName="DejaVu", fontSize=9, leading=13, leftIndent=8 * mm),
        ]
        toc.dotsMinLevel = 0
        story += [Paragraph("Inhaltsverzeichnis", st["title"]), Spacer(1, 4 * mm), toc, PageBreak()]
    if opts.uebersicht:
        story += [Paragraph("Zusammenstellung der Ergebnisse", st["toc0"]), Spacer(1, 3 * mm)]
        story += _overview(results, st, page_w)
        story.append(PageBreak())

    for i, pr in enumerate(results, 1):
        if progress:
            progress(i, len(results))
        p = pr.position
        calc_title = pr.calc.title if pr.calc else p.calc
        story.append(Paragraph(rich(p.label(calc_title)), st["toc0"]))
        if pr.calc is None:
            story += [Paragraph(f"Unbekannter Rechner „{rich(p.calc)}“ – die Position kann mit dieser "
                                "Programmversion nicht berechnet werden.", st["base"]), PageBreak()]
            continue
        calc = pr.calc
        story.append(Paragraph(f"{rich(calc.title)} · {calc.category} · {rich(calc.norm)}", st["small"]))
        if p.notiz.strip():
            story += [Spacer(1, 2 * mm), Paragraph(f"<b>Notiz:</b> {rich(p.notiz)}", st["base"])]
        inputs = pr.inputs if pr.inputs is not None else p.inputs
        raw = calc.defaults() | inputs
        quellen = {k: beschreibung(project, calcs, lk) for k, lk in p.links.items()}
        sketch = None
        if opts.skizzen and sketch_png_fn is not None:
            svg = calc.sketch_svg(raw)
            sketch = sketch_png_fn(svg) if svg else None
        plot = plot_png(calc, raw, pr.result) if opts.diagramme and pr.result.ok else None
        prefix = f"{p.nr}." if p.nr else f"{i}."
        story += calc_body(calc, inputs, pr.result, st, page_w, sketch, plot, prefix=prefix, quellen=quellen)
        if i < len(results):
            story.append(PageBreak())

    footer = fusszeile_text(" · ".join(x for x in (project.meta.projekt, project.meta.nummer, opts.titel) if x),
                            datetime.now().strftime("%d.%m.%Y %H:%M"))

    class Canvas(_NumberedCanvas):
        footer_left = footer
        _has_cover = opts.deckblatt

    doc = _Doc(str(path), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=rand_oben(),
               bottomMargin=20 * mm, title=f"{opts.titel} – {project.name}", author=project.meta.bearbeiter or APP_NAME,
               subject=project.meta.projekt)
    if not opts.deckblatt:
        story.insert(0, NextPageTemplate("normal"))
    doc.multiBuild(story, canvasmaker=Canvas)
    return path
