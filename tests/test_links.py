"""Verknüpfung von Positionen."""

import pytest

from ingrechner.core import links as lk
from ingrechner.core.project import Project
from ingrechner.core.project_report import ReportOptions, build_project_report, evaluate
from ingrechner.core.registry import by_id

def approx(x):
    """Verknüpfte Werte sind auf Anzeigegenauigkeit (≥ 4 gültige Ziffern) gerundet."""
    return pytest.approx(x, rel=1e-3)
CALCS = by_id()


def kette():
    p = Project()
    ids = lk.kette_anlegen(p, lk.KETTEN[0])
    return p, ids


def test_pumpenkette_reicht_werte_weiter():
    p, (a, b, c, d, e) = kette()
    res = lk.aufloesen(p, CALCS)
    assert not res.fehler and all(res.results[x].ok for x in (a, b, c, d, e))
    ra, rb = res.results[a], res.results[b]
    assert res.inputs[b]["Va"] == approx(ra.value("V"))         # m³/h -> m³/h
    assert res.inputs[b]["Ha"] == approx(ra.value("H"))
    assert res.inputs[c]["V"] == approx(rb.value("Qb")) and res.inputs[c]["etaP"] == approx(rb.value("eta"))
    assert res.inputs[d]["eta"] == approx(res.results[c].value("eta"))
    assert res.inputs[e]["medium"] == "wasser" and res.inputs[e]["theta"] == 60


def test_einheiten_werden_umgerechnet():
    p = Project()
    q = p.add_position("hz.waermemenge", {"modus": "volumenstrom", "Q": 100, "dt": 20})
    z = p.add_position("fl.druckverlust_rohr")
    z.links = {"Q": {"pos": q.id, "art": lk.ERGEBNIS, "key": "Vl"}}     # l/h -> m³/h
    res = lk.aufloesen(p, CALCS)
    assert res.inputs[z.id]["Q"] == approx(res.results[q.id].value("Vl") / 1000)


def test_aenderung_der_quelle_wird_uebernommen():
    p, (a, b, *_rest) = kette()
    lk.uebernehmen(p, CALCS)
    alt = p.get(b).inputs["Va"]
    p.update(a, inputs=p.get(a).inputs | {"P": 160})
    changed = lk.uebernehmen(p, CALCS)
    assert b in changed and p.get(b).inputs["Va"] == approx(2 * alt)


def test_kreis_und_reihenfolge():
    p, (a, b, c, d, e) = kette()
    assert lk.erzeugt_kreis(p, a, b) and lk.erzeugt_kreis(p, a, a) and not lk.erzeugt_kreis(p, c, a)
    order = lk.reihenfolge(p)
    assert order.index(a) < order.index(b) < order.index(c) < order.index(d)
    assert set(lk.abhaengige(p, b)) == {c, d, e}
    # Kandidaten für die Auslegung enthalten keine abhängigen Positionen (kein Kreis)
    assert all(k.link["pos"] not in (b, c, d, e) for k in lk.kandidaten(p, CALCS, a, "V"))


def test_kandidaten_passen_zur_einheit():
    p, (a, b, c, *_r) = kette()
    kand = lk.kandidaten(p, CALCS, c, "H")                     # Förderhöhe in m
    keys = {(k.link["pos"], k.link["key"]) for k in kand}
    assert (a, "H") in keys and (b, "Hb") in keys
    assert all(k.link["key"] not in ("V", "Phyd") for k in kand)  # m³/h, W passen nicht
    medium = lk.kandidaten(p, CALCS, c, "rho")
    assert any(k.link["key"] == "rho" for k in medium)


def test_fehler_bei_ungueltiger_quelle():
    p, (a, b, *_r) = kette()
    p.update(a, inputs={"L": -5})
    res = lk.aufloesen(p, CALCS)
    assert "Va" in res.fehler[b] and "kein gültiges Ergebnis" in res.fehler[b]["Va"]


def test_loesen_beim_loeschen_und_duplizieren():
    p, (a, b, *_r) = kette()
    dup = p.duplicate(b)
    assert dup.links == p.get(b).links and dup.links is not p.get(b).links
    p.remove(a)
    weg = lk.loesen_fuer_quelle(p, a)
    assert (b, "Va") in weg and "Va" not in p.get(b).links


def test_speichern_und_laden(tmp_path):
    p, ids = kette()
    lk.uebernehmen(p, CALCS)
    p.save(tmp_path / "k.irp")
    q = Project.load(tmp_path / "k.irp")
    assert [x.links for x in q.positions] == [x.links for x in p.positions]
    assert q.get(ids[1]).inputs["Va"] == approx(p.get(ids[1]).inputs["Va"])


def test_beschreibung_und_bericht(tmp_path):
    p, (a, b, *_r) = kette()
    assert lk.beschreibung(p, CALCS, p.get(b).links["Va"]) == "Pos. 1 · V̇_A"
    rs = evaluate(p, CALCS)
    assert all(r.result.ok for r in rs)
    pdf = build_project_report(tmp_path / "g.pdf", p, CALCS, ReportOptions())
    assert pdf.read_bytes().startswith(b"%PDF")
