"""Firmenvorlage für PDF-Berichte."""

import io

import pytest
from PIL import Image

from ingrechner.core import briefkopf
from ingrechner.core.briefkopf import Firmenvorlage, logo_vorbereiten
from ingrechner.core.project import Project, ProjectMeta
from ingrechner.core.registry import by_id
from ingrechner.core import report


def png(w=300, h=100) -> bytes:
    b = io.BytesIO()
    Image.new("RGB", (w, h), (200, 40, 40)).save(b, "PNG")
    return b.getvalue()


@pytest.fixture(autouse=True)
def zuruecksetzen():
    yield
    briefkopf.setzen(None)


def test_speichern_und_laden(tmp_path):
    v = Firmenvorlage(firma="Muster GmbH", zusatz="Zeile 1\nZeile 2", farbe="#2e7d4f", fusszeile="Vertraulich",
                      programmhinweis=False, logo_pos="links")
    v.set_logo(png())
    w = Firmenvorlage.load(v.save(tmp_path / "team" / "vorlage.json"))
    assert w == v and w.logo == png() and w.hat_briefkopf
    assert Firmenvorlage.load(tmp_path / "fehlt.json") == Firmenvorlage()


def test_ungueltige_daten(tmp_path):
    with pytest.raises(ValueError):
        Firmenvorlage.from_dict({"format": "etwas-anderes"})
    assert Firmenvorlage(farbe="blau").farbe_gueltig() == briefkopf.STANDARD_FARBE
    assert Firmenvorlage(farbe="#12ab3Z").farbe_gueltig() == briefkopf.STANDARD_FARBE
    assert not Firmenvorlage().hat_briefkopf


def test_logo_wird_verkleinert():
    klein = png(300, 100)
    assert logo_vorbereiten(klein) == klein
    gross = logo_vorbereiten(png(4000, 1000))
    assert max(Image.open(io.BytesIO(gross)).size) == 1200
    with pytest.raises(ValueError, match="Bild"):
        logo_vorbereiten(b"kein bild")


def test_akzentfarbe_und_fusszeile():
    assert report.akzent().hexval() == "0x1f4e79"
    briefkopf.setzen(Firmenvorlage(farbe="#ff0000", fusszeile="Vertraulich", programmhinweis=False))
    assert report.akzent().hexval() == "0xff0000"
    hell = report.akzent_hell()
    assert (hell.red, hell.green, hell.blue) == pytest.approx((1.0, 0.9, 0.9))
    text = report.fusszeile_text("Pos. 1", "01.01.2026 10:00")
    assert "Vertraulich" in text and "Ingenieurs-Rechner" not in text
    assert report.rand_oben() == report.mm * 16          # ohne Briefkopf
    briefkopf.setzen(Firmenvorlage(firma="X"))
    assert report.rand_oben() > report.mm * 30


class _Canvas:
    def __init__(self):
        self.texte, self.bilder = [], []

    def __getattr__(self, name):
        return lambda *a, **k: None

    def drawString(self, x, y, text):
        self.texte.append(text)

    def drawImage(self, img, x, y, w, h, **k):
        self.bilder.append((x, y, w, h))


def test_briefkopf_wird_gezeichnet():
    v = Firmenvorlage(firma="Muster GmbH", zusatz="A\nB\nC\nD\nE")
    v.set_logo(png(300, 100))
    briefkopf.setzen(v)
    c = _Canvas()
    report.briefkopf_zeichnen(c)
    assert c.texte == ["Muster GmbH", "A", "B", "C", "D"]          # höchstens 4 Zusatzzeilen
    (x, y, w, h), = c.bilder
    assert h == pytest.approx(16 * report.mm) and w == pytest.approx(48 * report.mm)
    assert x + w == pytest.approx(report.A4[0] - 18 * report.mm)   # rechtsbündig


def test_alle_berichte_mit_vorlage(tmp_path):
    from ingrechner.core import links
    from ingrechner.core.project_report import ReportOptions, build_project_report
    from ingrechner.core.protocol_report import build_protocol_pdf
    from ingrechner.core.protocols import Protocol

    v = Firmenvorlage(firma="Muster GmbH", zusatz="Abteilung TGA", farbe="#2e7d4f", fusszeile="intern")
    v.set_logo(png())
    briefkopf.setzen(v)
    calc = by_id()["fl.druckverlust_rohr"]()
    raw = calc.defaults()
    res = calc.run(raw)
    assert report.build_pdf(tmp_path / "e.pdf", calc, raw, res, ProjectMeta()).read_bytes().startswith(b"%PDF")
    p = Project()
    links.kette_anlegen(p, links.KETTEN[0])
    assert build_project_report(tmp_path / "g.pdf", p, by_id(), ReportOptions()).stat().st_size > 10000
    from ingrechner.core.protocols import TemplateLibrary
    tpl = TemplateLibrary(tmp_path / "t.json").all()[0]
    assert build_protocol_pdf(tmp_path / "p.pdf", Protocol.new(tpl)).read_bytes().startswith(b"%PDF")
