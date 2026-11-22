"""PDF-Rechnungsnachweis mit ReportLab."""

from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

from .. import APP_NAME, __version__
from .model import Calculator, CalcResult, ChoiceField, Level, TableField
from .project import ProjectMeta
from .textfmt import rich
from .units import fmt_num, unit_html

BLUE = colors.HexColor("#1f4e79")
BLUE_LIGHT = colors.HexColor("#e8eff7")
GREY = colors.HexColor("#5b6b7b")
GRID = colors.HexColor("#c9d3de")
WARN = colors.HexColor("#9a5b00")
WARN_BG = colors.HexColor("#fff4e0")

_FONTS_DONE = False


def _register_fonts() -> None:
    """DejaVu Sans kommt mit matplotlib mit und enthält σ, λ, Δ, √ usw."""
    global _FONTS_DONE
    if _FONTS_DONE:
        return
    base = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
    pdfmetrics.registerFont(TTFont("DejaVu", str(base / "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont("DejaVu-Bold", str(base / "DejaVuSans-Bold.ttf")))
    pdfmetrics.registerFont(TTFont("DejaVu-Oblique", str(base / "DejaVuSans-Oblique.ttf")))
    pdfmetrics.registerFont(TTFont("DejaVu-BoldOblique", str(base / "DejaVuSans-BoldOblique.ttf")))
    from reportlab.pdfbase.pdfmetrics import registerFontFamily
    registerFontFamily("DejaVu", normal="DejaVu", bold="DejaVu-Bold",
                       italic="DejaVu-Oblique", boldItalic="DejaVu-BoldOblique")
    _FONTS_DONE = True


def _styles() -> dict[str, ParagraphStyle]:
    base = ParagraphStyle("base", fontName="DejaVu", fontSize=9, leading=12, alignment=TA_LEFT)
    return {
        "base": base,
        "small": ParagraphStyle("small", parent=base, fontSize=7.5, leading=10, textColor=GREY),
        "title": ParagraphStyle("title", parent=base, fontName="DejaVu-Bold", fontSize=15, leading=19,
                                textColor=BLUE, spaceAfter=2),
        "h2": ParagraphStyle("h2", parent=base, fontName="DejaVu-Bold", fontSize=10.5, leading=14,
                             textColor=BLUE, spaceBefore=8, spaceAfter=4),
        "cell": ParagraphStyle("cell", parent=base, fontSize=8.5, leading=11),
        "cellb": ParagraphStyle("cellb", parent=base, fontName="DejaVu-Bold", fontSize=8.5, leading=11),
        "formula": ParagraphStyle("formula", parent=base, fontSize=8.5, leading=11, textColor=BLUE),
    }


def _table(rows, widths, header=True, highlight_rows=()) -> Table:
    t = Table(rows, colWidths=widths, repeatRows=1 if header else 0)
    style = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, GRID),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
    ]
    if header:
        style += [("BACKGROUND", (0, 0), (-1, 0), BLUE_LIGHT), ("LINEBELOW", (0, 0), (-1, 0), 0.8, BLUE)]
    for r in highlight_rows:
        style.append(("BACKGROUND", (0, r), (-1, r), colors.HexColor("#f3f7fb")))
    t.setStyle(TableStyle(style))
    return t


def _image(png: bytes, max_w: float, max_h: float) -> Image:
    img = Image(io.BytesIO(png))
    scale = min(max_w / img.imageWidth, max_h / img.imageHeight, 1.0 * max_w / img.imageWidth)
    img.drawWidth, img.drawHeight = img.imageWidth * scale, img.imageHeight * scale
    return img


def head_table(meta: ProjectMeta, st, page_w: float) -> Table:
    """Kopftabelle mit Projektdaten (Projekt, Nr., Bearbeiter, Datum, Prüfer)."""
    head = [
        [Paragraph("<b>Projekt</b>", st["cell"]), Paragraph(rich(meta.projekt or "–"), st["cell"]),
         Paragraph("<b>Projekt-Nr.</b>", st["cell"]), Paragraph(rich(meta.nummer or "–"), st["cell"])],
        [Paragraph("<b>Bearbeiter</b>", st["cell"]), Paragraph(rich(meta.bearbeiter or "–"), st["cell"]),
         Paragraph("<b>Datum</b>", st["cell"]), Paragraph(rich(meta.datum or "–"), st["cell"])],
        [Paragraph("<b>Geprüft</b>", st["cell"]), Paragraph(rich(meta.pruefer or ""), st["cell"]),
         Paragraph("<b>Unterschrift</b>", st["cell"]), Paragraph("", st["cell"])],
    ]
    ht = Table(head, colWidths=[24 * mm, page_w / 2 - 24 * mm, 26 * mm, page_w / 2 - 26 * mm])
    ht.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.8, BLUE), ("INNERGRID", (0, 0), (-1, -1), 0.4, GRID),
        ("BACKGROUND", (0, 0), (0, -1), BLUE_LIGHT), ("BACKGROUND", (2, 0), (2, -1), BLUE_LIGHT),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return ht


def _quelle(quellen: dict[str, str] | None, key: str) -> str:
    if not quellen or key not in quellen:
        return ""
    return f"<br/><font size='7' color='#1f6fb2'>← aus {rich(quellen[key])}</font>"


def calc_body(calc: Calculator, raw: dict[str, Any], result: CalcResult, st, page_w: float,
              sketch_png: bytes | None = None, plot_png: bytes | None = None, prefix: str = "",
              quellen: dict[str, str] | None = None) -> list:
    """Inhalt eines Rechnungsnachweises: Eingaben, Ergebnisse, Hinweise, Rechenweg, Diagramm.

    ``prefix`` nummeriert die Abschnitte (z. B. „3.“ → „3.1 Eingangswerte“ im Gesamtbericht).
    """
    story: list = []
    sec = iter(range(1, 20))

    def h(title: str) -> Paragraph:
        return Paragraph(f"{prefix}{next(sec)}  {title}", st["h2"])

    # ---- Eingaben (+ Skizze daneben)
    story.append(h("Eingangswerte"))
    rows = [[Paragraph("<b>Größe</b>", st["cell"]), Paragraph("<b>Symbol</b>", st["cell"]),
             Paragraph("<b>Wert</b>", st["cell"])]]
    merged = calc.defaults() | raw
    for f in calc.fields:
        if not calc.is_visible(f, merged):
            continue
        if isinstance(f, ChoiceField):
            rows.append([Paragraph(rich(f.label), st["cell"]), Paragraph("", st["cell"]),
                         Paragraph(rich(f.label_for(merged[f.key])) + _quelle(quellen, f.key), st["cell"])])
        elif isinstance(f, TableField):
            trows, _ = f.parse(merged[f.key])
            head = " · ".join(f"{rich(c.label)} [{unit_html(c.unit)}]" if c.unit else rich(c.label) for c in f.columns)
            body = "<br/>".join(" · ".join("–" if v is None else fmt_num(v, c.decimals) for v, c in zip(r, f.columns))
                                for r in trows)
            rows.append([Paragraph(rich(f.label), st["cell"]), Paragraph("", st["cell"]),
                         Paragraph(f"<font color='#5b6b7b'>{head}</font><br/>{body}", st["cell"])])
        else:
            try:
                val = f"{fmt_num(float(merged[f.key]), f.decimals)} {unit_html(f.unit)}"
            except (TypeError, ValueError):
                val = f"<font color='#b3261e'>{rich(str(merged[f.key]))}</font>"
            rows.append([Paragraph(rich(f.label), st["cell"]), Paragraph(rich(f.symbol), st["cell"]),
                         Paragraph(val + _quelle(quellen, f.key), st["cell"])])
    if sketch_png:
        left_w = page_w * 0.58
        inputs_tbl = _table(rows, [left_w * 0.5, left_w * 0.18, left_w * 0.32])
        sketch = _image(sketch_png, page_w - left_w - 6 * mm, 60 * mm)
        wrap = Table([[inputs_tbl, sketch]], colWidths=[left_w + 6 * mm, page_w - left_w - 6 * mm])
        wrap.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                  ("ALIGN", (1, 0), (1, 0), "CENTER")]))
        story.append(wrap)
    else:
        story.append(_table(rows, [page_w * 0.5, page_w * 0.18, page_w * 0.32]))

    if result.field_errors:
        story.append(h("Eingaben ungültig"))
        for msg in result.field_errors.values():
            story.append(Paragraph(f"<font color='#b3261e'>✖ {rich(msg)}</font>", st["base"]))
        return story

    # ---- Ergebnisse
    story.append(h("Ergebnisse"))
    rows = [[Paragraph("<b>Größe</b>", st["cell"]), Paragraph("<b>Symbol</b>", st["cell"]),
             Paragraph("<b>Wert</b>", st["cell"])]]
    hl = []
    for i, rv in enumerate(result.values, start=1):
        sty = st["cellb"] if rv.highlight else st["cell"]
        rows.append([Paragraph(rich(rv.label), sty), Paragraph(rich(rv.symbol), sty),
                     Paragraph(f"{fmt_num(rv.value, rv.decimals)} {unit_html(rv.unit)}", sty)])
        if rv.highlight:
            hl.append(i)
    story.append(_table(rows, [page_w * 0.5, page_w * 0.18, page_w * 0.32], highlight_rows=hl))

    # ---- Hinweise
    if result.messages:
        story.append(h("Bewertung und Hinweise"))
        mrows = []
        for m in result.messages:
            tag = {"info": "Info", "warnung": "Warnung", "fehler": "Fehler"}[m.level.value]
            mrows.append([Paragraph(f"<b>{tag}</b>", st["cell"]), Paragraph(rich(m.text), st["cell"])])
        mt = Table(mrows, colWidths=[22 * mm, page_w - 22 * mm])
        style = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), 0.4, GRID)]
        for i, m in enumerate(result.messages):
            if m.level is not Level.INFO:
                style += [("BACKGROUND", (0, i), (-1, i), WARN_BG), ("TEXTCOLOR", (0, i), (0, i), WARN)]
        mt.setStyle(TableStyle(style))
        story.append(mt)

    # ---- Rechenweg
    story.append(h("Rechenweg"))
    for i, s in enumerate(result.steps, start=1):
        block = Table([
            [Paragraph(f"<b>{i}.</b>", st["cell"]), Paragraph(f"<b>{rich(s.title)}</b>", st["cell"])],
            ["", Paragraph(rich(s.formula), st["formula"])],
            ["", Paragraph(f"{rich(s.substitution)}  =  <b>{rich(s.result)}</b>", st["cell"])],
        ], colWidths=[8 * mm, page_w - 8 * mm])
        block.setStyle(TableStyle([("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                                   ("LEFTPADDING", (0, 0), (-1, -1), 2), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        story.append(KeepTogether([block, Spacer(1, 1.5 * mm)]))

    # ---- Diagramm
    if plot_png:
        story.append(KeepTogether([h("Diagramm"), _image(plot_png, page_w, 110 * mm)]))

    story.append(Spacer(1, 5 * mm))
    story.append(Paragraph(rich(calc.disclaimer), st["small"]))
    return story


def build_pdf(path: str | Path, calc: Calculator, raw: dict[str, Any], result: CalcResult,
              meta: ProjectMeta, notiz: str = "", sketch_png: bytes | None = None,
              plot_png: bytes | None = None, position: str = "", quellen: dict[str, str] | None = None) -> Path:
    """Einzelner Rechnungsnachweis. ``position``: z. B. „Pos. 3 – Träger Achse B“."""
    _register_fonts()
    st = _styles()
    path = Path(path)
    page_w = A4[0] - 36 * mm
    story: list = []

    # ---- Kopf
    if position:
        story.append(Paragraph(rich(position), st["title"]))
        story.append(Paragraph(f"{rich(calc.title)} · {calc.category} · {rich(calc.norm)}", st["small"]))
    else:
        story.append(Paragraph(rich(calc.title), st["title"]))
        story.append(Paragraph(f"{calc.category} · {rich(calc.norm)}", st["small"]))
    story.append(Spacer(1, 4 * mm))
    story.append(head_table(meta, st, page_w))
    if notiz.strip():
        story.append(Spacer(1, 2 * mm))
        story.append(Paragraph(f"<b>Notiz:</b> {rich(notiz)}", st["base"]))
    story += calc_body(calc, raw, result, st, page_w, sketch_png, plot_png, quellen=quellen)

    stamp = datetime.now().strftime("%d.%m.%Y %H:%M")
    footer_title = position or calc.title

    def on_page(canvas, doc):
        canvas.saveState()
        canvas.setFont("DejaVu", 7.5)
        canvas.setFillColor(GREY)
        canvas.setStrokeColor(GRID)
        canvas.line(18 * mm, 14 * mm, A4[0] - 18 * mm, 14 * mm)
        canvas.drawString(18 * mm, 10 * mm, f"{APP_NAME} {__version__} · {footer_title} · erstellt {stamp}")
        canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Seite {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=16 * mm, bottomMargin=20 * mm, title=footer_title,
                            author=meta.bearbeiter or APP_NAME, subject=meta.projekt)
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    return path


def plot_png(calc: Calculator, raw: dict[str, Any], result: CalcResult, dpi: int = 160) -> bytes | None:
    """Rendert das Diagramm des Rechners headless (Agg) als PNG für den Bericht."""
    from matplotlib.figure import Figure

    from .plotstyle import apply_style

    fig = Figure(figsize=(7.2, 4.6), dpi=dpi)
    apply_style(fig)
    if not calc.plot(fig, calc.defaults() | raw, result):
        return None
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, facecolor="white")
    return buf.getvalue()
