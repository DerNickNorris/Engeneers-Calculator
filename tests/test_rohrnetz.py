"""Rohrnetz – Strangberechnung."""

import pytest

from ingrechner.calculators.fluid.druckverlust_rohr import DruckverlustRohr
from ingrechner.calculators.fluid.rohrnetz import Rohrnetz, nachschlagen, reihe
from ingrechner.calculators.pumpen._pumpe import rohr_dp
from ingrechner.core import links as lk
from ingrechner.core import medien
from ingrechner.core.model import Level
from ingrechner.core.project import Project
from ingrechner.core.registry import by_id

approx = pytest.approx
G = 9.80665
BASIS = {"last": "volumen", "medium": "wasser", "theta": 20, "laenge": "gesamt", "rauheit": "frei", "k": 0.05,
         "dp_e": 0, "res": 0}


def test_einzelstrecke_wie_druckverlustrechner():
    r = Rohrnetz().run(BASIS | {"reihe": "frei", "strecken_v": [[10, 50, 100, 4, None]]})
    d = DruckverlustRohr().run({"Q": 10, "d": 50, "L": 100, "k": 0.05, "zeta": 4, "medium": "wasser",
                                "theta": 20})
    assert r.ok and d.ok
    assert r.value("dp") == approx(d.value("dp") * 100, rel=1e-6)      # kPa vs bar
    assert r.value("H") == approx(d.value("hv"), rel=1e-6)


def test_summe_zuschlag_und_trasse():
    rows = [[6, 65, 40, 3, None], [3, 50, 30, 2, 15]]
    a = Rohrnetz().run(BASIS | {"strecken_v": rows, "dp_e": 20, "res": 10})
    z = medien.medium("wasser").zustand(20)
    soll = 0.0
    for V, dn, L, zeta, dpk in rows:
        _, di = nachschlagen("stahl", dn)
        r = rohr_dp(V / 3600, di, L, 5e-5, zeta, z.rho, z.nu)
        soll += r.dp_r + r.dp_z + (dpk or 0) * 1000
    assert a.value("dp_netz") == approx(soll / 1000)
    assert a.value("dp") == approx((soll + 20e3) * 1.1 / 1000)
    assert a.value("H") == approx((soll + 20e3) * 1.1 / (z.rho * G))
    assert a.value("V") == approx(6)
    b = Rohrnetz().run(BASIS | {"strecken_v": [[6, 65, 20, 1.5, None], [3, 50, 15, 1, 15]], "laenge": "trasse"})
    assert b.value("dp_netz") == approx(soll / 1000) and b.value("L") == approx(70)


def test_volumenstrom_aus_leistung():
    r = Rohrnetz().run(BASIS | {"last": "waerme", "dT": 20, "theta": 70,
                                "strecken_q": [[100, None, 10, None, None]]})
    z = medien.medium("wasser").zustand(70)
    assert r.value("V") == approx(100 / (z.rho * z.cp * 20) * 3600)


def test_automatische_dimensionierung():
    r = Rohrnetz().run(BASIS | {"strecken_v": [[5, None, 50, None, None]], "Rmax": 150, "vmax": 1.5})
    assert r.ok and r.value("Rmax") <= 150 and r.value("vmax") <= 1.5
    # die nächstkleinere Nennweite hätte R_max oder v_max überschritten
    z = medien.medium("wasser").zustand(20)
    ds = reihe("stahl")
    i = next(i for i, (_, _, di) in enumerate(ds) if rohr_dp(5 / 3600, di, 1, 5e-5, 0, z.rho, z.nu).r <= 150
             and rohr_dp(5 / 3600, di, 1, 5e-5, 0, z.rho, z.nu).v <= 1.5)
    kleiner = rohr_dp(5 / 3600, ds[i - 1][2], 1, 5e-5, 0, z.rho, z.nu)
    assert kleiner.r > 150 or kleiner.v > 1.5
    assert any(f"TS 1: {ds[i][1]}" in s.result for s in r.steps)


def test_rohrreihen():
    assert nachschlagen("pe11", 110)[1] == approx((110 - 20) / 1000)
    assert nachschlagen("kupfer", 22)[1] == approx(0.020)
    assert nachschlagen("stahl", 300)[0] == "DN 300"
    with pytest.raises(ValueError, match="verfügbar"):
        nachschlagen("stahl", 33)
    r = Rohrnetz().run(BASIS | {"reihe": "frei", "strecken_v": [[5, None, 10, None, None]], "Rmax": 150})
    assert r.ok and r.value("Rmax") <= 150
    erf = next(s.result for s in r.steps if "d_i,erf" in s.result)
    di = float(erf.split("d_i,erf ")[1].split(" mm")[0]) / 1000
    z = medien.medium("wasser").zustand(20)
    assert rohr_dp(5 / 3600, di - 0.001, 1, 5e-5, 0, z.rho, z.nu).r > 150    # 1 mm kleiner reicht nicht


def test_warnung_grenzwerte():
    r = Rohrnetz().run(BASIS | {"strecken_v": [[20, 32, 10, None, None]]})
    assert any(m.level is Level.WARNUNG and "Grenzwerte" in m.text for m in r.messages)


def test_kette_rohrnetz_pumpe():
    p = Project()
    ids = lk.kette_anlegen(p, lk.KETTEN[1])
    res = lk.aufloesen(p, by_id())
    assert not res.fehler and all(res.results[i].ok for i in ids)
    assert res.inputs[ids[1]]["Ha"] == approx(res.results[ids[0]].value("H"), rel=1e-3)
