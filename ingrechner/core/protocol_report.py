"""PDF-Ausgabe eines Besprechungsprotokolls (ReportLab)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import (KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

from .. import APP_NAME, __version__
from .protocols import AUFGABE_ART, HEADER_TYPES, Protocol
from .report import GREY, GRID, _register_fonts, _styles, akzent, akzent_hell, fusszeile_text, rand_oben, seitenrahmen
from .textfmt import rich

DONE = colors.HexColor("#2e7d4f")
OPEN = colors.HexColor("#9a5b00")


def _para_text(text: str) -> str:
    """Mehrzeiligen Text als Paragraph-Markup (Zeilenumbrüche erhalten)."""
    from xml.sax.saxutils import escape

    return "<br/>".join(escape(line) for line in str(text).splitlines()) or "–"


def build_protocol_pdf(path: str | Path, proto: Protocol) -> Path:
    _register_fonts()
    st = _styles()
    path = Path(path)
    page_w = A4[0] - 36 * mm
    story: list = []
    tpl = proto.template

    story.append(Paragraph(rich(proto.title), st["title"]))
    if proto.subject:
        story.append(Paragraph(_para_text(proto.subject), st["small"]))
    story.append(Spacer(1, 4 * mm))

    # ---- Kopfdaten (zweispaltig)
    head = [b for b in tpl.blocks if b.typ in HEADER_TYPES]
    if head:
        cells = []
        for b in head:
            cells += [Paragraph(f"<b>{rich(b.titel)}</b>", st["cell"]),
                      Paragraph(_para_text(proto.value(b.key)), st["cell"])]
        rows = [cells[i:i + 4] for i in range(0, len(cells), 4)]
        if len(rows[-1]) < 4:
            rows[-1] += [""] * (4 - len(rows[-1]))
        lw = 40 * mm
        t = Table(rows, colWidths=[lw, page_w / 2 - lw, lw, page_w / 2 - lw])
        style = [("BOX", (0, 0), (-1, -1), 0.8, akzent()), ("INNERGRID", (0, 0), (-1, -1), 0.4, GRID),
                 ("BACKGROUND", (0, 0), (0, -1), akzent_hell()), ("BACKGROUND", (2, 0), (2, -1), akzent_hell()),
                 ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 3),
                 ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
        t.setStyle(TableStyle(style))
        story.append(t)

    section = 0
    for b in tpl.blocks:
        if b.typ in HEADER_TYPES:
            continue
        section += 1
        heading = Paragraph(f"{section}  {rich(b.titel)}", st["h2"])
        val = proto.value(b.key)

        if b.typ == "teilnehmer":
            rows = [[Paragraph(f"<b>{h}</b>", st["cell"]) for h in ("Name", "Firma / Funktion", "Kürzel", "Status")]]
            for p in val:
                rows.append([Paragraph(_para_text(p.get(k, "")), st["cell"])
                             for k in ("name", "firma", "kuerzel", "status")])
            if len(rows) == 1:
                rows.append([Paragraph("–", st["cell"]), "", "", ""])
            t = Table(rows, colWidths=[page_w * 0.3, page_w * 0.42, page_w * 0.1, page_w * 0.18], repeatRows=1)
            t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), akzent_hell()),
                                   ("LINEBELOW", (0, 0), (-1, 0), 0.8, akzent()),
                                   ("LINEBELOW", (0, 1), (-1, -1), 0.4, GRID),
                                   ("VALIGN", (0, 0), (-1, -1), "TOP")]))
            story += [heading, t]

        elif b.typ == "text":
            story += [heading, Paragraph(_para_text(val), st["base"])]

        elif b.typ == "tagesordnung":
            story.append(heading)
            for i, top in enumerate(val, 1):
                block = Table([
                    [Paragraph(f"<b>TOP {i}</b>", st["cell"]), Paragraph(f"<b>{_para_text(top.get('titel', ''))}</b>", st["cell"])],
                    ["", Paragraph(_para_text(top.get("text", "")) if top.get("text", "").strip() else
                                   "<font color='#5b6b7b'>–</font>", st["base"])],
                ], colWidths=[18 * mm, page_w - 18 * mm])
                block.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                                           ("LINEABOVE", (0, 0), (-1, 0), 0.4, GRID),
                                           ("TOPPADDING", (0, 0), (-1, -1), 2),
                                           ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
                story.append(KeepTogether(block))

        elif b.typ == "aufgaben":
            heads = ("Nr.", "Art", "Gegenstand", "Verantw.", "Termin", "Status")
            rows = [[Paragraph(f"<b>{h}</b>", st["cell"]) for h in heads]]
            for task in val:
                txt = _para_text(task.get("aufgabe", ""))
                if task.get("herkunft"):
                    txt += f"<br/><font size='7' color='#5b6b7b'>aus {_para_text(task['herkunft'])}</font>"
                rows.append([Paragraph(_para_text(task.get("nr", "")), st["cell"]),
                             Paragraph(task.get("art", "A"), st["cell"]),
                             Paragraph(txt, st["cell"]),
                             Paragraph(_para_text(task.get("verantwortlich", "")), st["cell"]),
                             Paragraph(_para_text(task.get("termin", "")), st["cell"]),
                             Paragraph(_para_text(task.get("status", "")), st["cell"])])
            if len(rows) == 1:
                rows.append([Paragraph("–", st["cell"]), "", "", "", "", ""])
            t = Table(rows, colWidths=[19 * mm, 9 * mm, page_w - 87 * mm, 18 * mm, 22 * mm, 19 * mm],
                      repeatRows=1)
            style = [("BACKGROUND", (0, 0), (-1, 0), akzent_hell()), ("LINEBELOW", (0, 0), (-1, 0), 0.8, akzent()),
                     ("LINEBELOW", (0, 1), (-1, -1), 0.4, GRID), ("VALIGN", (0, 0), (-1, -1), "TOP")]
            for i, task in enumerate(val, 1):
                color = DONE if task.get("status") == "erledigt" else OPEN if task.get("art", "A") in ("A", "F") else GREY
                style.append(("TEXTCOLOR", (5, i), (5, i), color))
            t.setStyle(TableStyle(style))
            legend = " · ".join(f"{k} = {v}" for k, v in AUFGABE_ART.items())
            story += [heading, t, Paragraph(legend, st["small"])]

    if tpl.schlusstext.strip():
        story += [Spacer(1, 6 * mm), Paragraph(_para_text(tpl.schlusstext), st["small"])]

    # Unterschrift Protokollführung
    pf = ""
    for b in tpl.blocks:
        if b.typ == "feld" and "protokoll" in b.titel.lower():
            pf = str(proto.value(b.key))
    story += [Spacer(1, 10 * mm),
              Table([["", ""], [Paragraph(f"Aufgestellt: {_para_text(pf) if pf else ''}", st["small"]), ""]],
                    colWidths=[70 * mm, page_w - 70 * mm],
                    style=TableStyle([("LINEABOVE", (0, 1), (0, 1), 0.6, GREY)]))]

    stamp = datetime.now().strftime("%d.%m.%Y %H:%M")
    title = proto.title

    def on_page(canvas, doc):
        seitenrahmen(canvas, fusszeile_text(title, stamp), f"Seite {doc.page}")

    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=rand_oben(), bottomMargin=20 * mm, title=title, subject=proto.subject)
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    return path
