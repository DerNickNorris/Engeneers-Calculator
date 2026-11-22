"""Abwasser / Klärwerk: Pumpensumpf, Druckleitung, Druckstoß, Faulbehälter, Klärgasleitung."""

import math

import pytest

from ingrechner.calculators.abwasser._aw import rohr_geometrie, rohr_optionen
from ingrechner.calculators.abwasser.druckleitung import Druckleitung
from ingrechner.calculators.abwasser.druckstoss import Druckstoss, wellengeschwindigkeit
from ingrechner.calculators.abwasser.faulbehaelter import Faulbehaelter
from ingrechner.calculators.abwasser.gasleitung import Gasleitung, wasserbeladung
from ingrechner.calculators.abwasser.pumpensumpf import Pumpensumpf
from ingrechner.calculators.fluid.druckverlust_rohr import DruckverlustRohr
from ingrechner.core import links as lk
from ingrechner.core import medien
from ingrechner.core.model import Level
from ingrechner.core.project import Project
from ingrechner.core.registry import by_id
from ingrechner.core.units import Q_

approx = pytest.approx
G = 9.80665


def warned(r, text):
    return any(m.level is Level.WARNUNG and text in m.text for m in r.messages)


class TestPumpensumpf:
    def test_nutzvolumen(self):
        r = Pumpensumpf().run({"QP": 20, "z": 10, "n": 2, "form": "rund", "D": 2.0, "hmin": 0.6, "Vtot": 0})
        V = 0.020 * 3600 / (10 * 2) / 4                       # 0,9 m³
        assert r.value("V") == approx(V)
        assert r.value("dh") == approx(V / (math.pi * 4 / 4))
        assert r.value("hein") == approx(0.6 + V / math.pi)

    def test_spiel_ist_im_ungünstigsten_fall_minimal(self):
        r = Pumpensumpf().run({"QP": 20, "z": 12, "n": 1, "Qzu": 10})
        # bei Q_zu = Q_P/2: t_L + t_S = 4·V/Q_P = 3600/z
        assert (r.value("tlz") + r.value("tsz")) * 60 == approx(3600 / 12)

    def test_zufluss_groesser_als_pumpe(self):
        r = Pumpensumpf().run({"QP": 10, "Qzu": 12})
        assert warned(r, "Spitzenzufluss")

    def test_rechteck_und_totvolumen(self):
        r = Pumpensumpf().run({"QP": 30, "z": 8, "n": 1, "form": "rechteck", "a": 3, "b": 2, "Vtot": 10})
        assert r.value("dh") == approx(0.030 * 3600 / 8 / 4 / 6 * 1.1)


class TestDruckleitung:
    def test_gegen_druckverlustrechner(self):
        r = Druckleitung().run({"QP": 20, "rohr": "pe11:160", "L": 850, "kb": 0.25, "zeta": 0, "hgeo": 8,
                                "medium": "wasser", "theta": 12})
        _, di, _, _ = rohr_geometrie({"rohr": "pe11:160"})
        d = DruckverlustRohr().run({"Q": 72, "d": di * 1000, "L": 850, "k": 0.25, "zeta": 0, "medium": "wasser",
                                    "theta": 12})
        assert r.value("H") == approx(8 + d.value("hv"), rel=1e-6)
        assert r.value("VL") == approx(math.pi * di**2 / 4 * 850)
        assert r.value("p") == approx(r.value("H") * r.value("rho") * G / 1e5)

    def test_aufenthaltszeit_und_vmin(self):
        r = Druckleitung().run({"QP": 5, "Qd": 50, "rohr": "pe11:160", "L": 2000})
        assert warned(r, "v_min") and warned(r, "Aufenthaltszeit")
        assert r.value("tA") == approx(r.value("VL") / 50 * 24)

    def test_rohrauswahl(self):
        assert rohr_geometrie({"rohr": "pe11:110"})[1] == approx((110 - 20) / 1000)
        assert rohr_geometrie({"rohr": "st:DN 150"})[2] == approx(0.1683)
        assert rohr_geometrie({"rohr": "frei", "da": Q_(200, "mm"), "s": Q_(10, "mm")})[1] == approx(0.18)
        assert len(rohr_optionen()) == 2 * 18 + 15 + 1


class TestDruckstoss:
    def test_wellengeschwindigkeit_stahl(self):
        # Stahl DN 150: a ≈ 1300 m/s (Literatur 1200–1400 m/s)
        a = wellengeschwindigkeit(2.1e9, 1000, 2.1e11, 0.1593, 0.0045)
        assert 1200 < a < 1400

    def test_joukowsky_und_michaud(self):
        base = {"v0": 1.0, "L": 500, "da": 168.3, "s": 4.5, "werkstoff": "stahl", "rho": 1000, "K": 2100,
                "p0": 3, "PN": 10}
        r = Druckstoss().run(base | {"Ts": 0})
        a = r.value("a")
        assert r.value("dp") == approx(1000 * a * 1.0 / 1e5)
        assert r.value("Tr") == approx(1000 / a)
        r2 = Druckstoss().run(base | {"Ts": 10})
        assert r2.value("dp") == approx(2 * 1000 * 500 * 1.0 / 10 / 1e5)
        assert r.value("pmax") == approx(3 + r.value("dp"))
        assert warned(r, "Nenndruck") and warned(r, "Dampfdruck")

    def test_pe_weich(self):
        r = Druckstoss().run({})
        assert 250 < r.value("a") < 450          # PE 100 SDR 11


class TestFaulbehaelter:
    def test_waermebedarf(self):
        inp = {"QS": 40, "schlamm": "klaerschlamm_5", "tRS": 12, "tF": 37, "D": 14, "H": 13, "Uw": 0.4,
               "Ud": 0.4, "Ub": 0.6, "ta": -12, "tE": 10, "zus": 0, "gas": "nein"}
        r = Faulbehaelter().run(inp)
        z = medien.medium("klaerschlamm_5").zustand(24.5)
        qa = 40 / 86400 * z.rho * z.cp * 1000 * 25
        A_w, A_d = math.pi * 14 * 13, math.pi * 49
        qt = 0.4 * A_w * 49 + 0.4 * A_d * 49 + 0.6 * A_d * 27
        assert r.value("Qa") == approx(qa / 1000) and r.value("Qt") == approx(qt / 1000)
        assert r.value("tF") == approx(math.pi * 49 * 13 / 40)

    def test_klaergas(self):
        r = Faulbehaelter().run({"Vg": 900, "ch4": 63, "eta": 45})
        assert r.value("Qg") == approx(900 * 0.63 * 9.97 * 0.45 / 24)
        r = Faulbehaelter().run({"Vg": 200})
        assert warned(r, "nur")


class TestGasleitung:
    def test_wasserbeladung(self):
        # p_s(35 °C) = 5,627 kPa: x = 5,627/(101,325 − 5,627) · 18,015/22,414 = 47,3 g je m³ (Norm, trocken)
        assert wasserbeladung(35, 101325) * 1000 == approx(47.3, rel=0.005)

    def test_druckverlust_und_kondensat(self):
        r = Gasleitung().run({"Vn": 60, "gas": "klaergas_65", "pue": 30, "pamb": 1013.25, "tg": 15,
                              "rohr": "pe11:110", "L": 120, "rauheit": "kunststoff", "zeta": 6, "tsat": 35})
        g = medien.medium("klaergas_65")
        p = 101325 + 3000
        z, zn = g.zustand(15, p), g.zustand(0, 101325)
        assert r.value("rho") == approx(z.rho)
        assert r.value("Vb") == approx(60 * zn.rho / z.rho)
        kond = 60 * 24 * (wasserbeladung(35, p) - wasserbeladung(15, p))
        assert r.value("kond") == approx(kond)

    def test_zu_klein(self):
        r = Gasleitung().run({"Vn": 300, "rohr": "pe11:63"})
        assert warned(r, "zulässigen") and warned(r, "Gasgeschwindigkeit")


def test_kette_abwasserpumpwerk():
    p = Project()
    ids = lk.kette_anlegen(p, lk.KETTEN[2])
    res = lk.aufloesen(p, by_id())
    assert not res.fehler and all(res.results[i].ok for i in ids)
    assert res.inputs[ids[2]]["QP"] == approx(res.results[ids[1]].value("Qb") / 3.6, rel=1e-3)   # m³/h -> l/s
    assert res.inputs[ids[3]]["p0"] == approx(res.results[ids[0]].value("p"), rel=1e-3)
    assert res.inputs[ids[4]]["medium"] == "abwasser_zulauf"
