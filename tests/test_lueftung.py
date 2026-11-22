"""Lüftung / RLT: feuchte Luft, Luftmenge, Kanal, Kanalnetz, Ventilator, WRG."""

import math

import pytest

from ingrechner.calculators.lueftung._lu import d_gleichwertig, d_hydraulisch
from ingrechner.calculators.lueftung.feuchte_luft import FeuchteLuft
from ingrechner.calculators.lueftung.kanal import Luftkanal
from ingrechner.calculators.lueftung.kanalnetz import Kanalnetz
from ingrechner.calculators.lueftung.luftmenge import Luftmenge
from ingrechner.calculators.lueftung.ventilator import Ventilator, sfp_klasse
from ingrechner.calculators.lueftung.wrg import Waermerueckgewinnung
from ingrechner.calculators.fluid.druckverlust_rohr import rohrreibungszahl
from ingrechner.core import feuchte, links as lk, medien
from ingrechner.core.model import Level
from ingrechner.core.project import Project
from ingrechner.core.registry import by_id

approx = pytest.approx


def warned(r, text):
    return any(m.level is Level.WARNUNG and text in m.text for m in r.messages)


class TestFeuchte:
    @pytest.mark.parametrize("t, ps", [(-10, 259.9), (0, 611.2), (20, 2339), (30, 4246), (50, 12352)])
    def test_saettigungsdruck(self, t, ps):
        assert feuchte.p_saett(t) == approx(ps, rel=0.01)      # Tabellenwerte (über Eis unter 0 °C)

    def test_mollier_20_50(self):
        z = feuchte.Zustand(20, 0.5)
        assert z.x * 1000 == approx(7.26, abs=0.03)
        assert z.h == approx(38.5, abs=0.1)
        assert z.tau == approx(9.3, abs=0.1)
        assert z.rho == approx(1.199, abs=0.003)

    def test_umkehrungen(self):
        z = feuchte.Zustand(25, 0.6)
        assert feuchte.theta_aus_h(z.h, z.x) == approx(25)
        assert feuchte.phi_aus_x(25, z.x) == approx(0.6)
        assert feuchte.p_saett(z.tau) == approx(z.pd, rel=1e-6)
        assert feuchte.hoehe_druck(0) == approx(101325) and feuchte.hoehe_druck(1000) == approx(89875, rel=1e-3)

    def test_mischung_bilanz(self):
        r = FeuchteLuft().run({"modus": "mischung", "t1": 30, "phi1": 40, "V1": 3000, "t2": 20, "phi2": 50, "V2": 3000,
                                "hoehe": 0})
        z1, z2 = feuchte.Zustand(30, 0.4), feuchte.Zustand(20, 0.5)
        m1, m2 = 3000 * z1.rho / (1 + z1.x), 3000 * z2.rho / (1 + z2.x)
        assert r.value("xm") == approx((m1 * z1.x + m2 * z2.x) / (m1 + m2) * 1000)
        assert r.value("hm") == approx((m1 * z1.h + m2 * z2.h) / (m1 + m2))

    def test_erwaermen(self):
        r = FeuchteLuft().run({"modus": "erwaermen", "t1": 5, "phi1": 80, "V1": 3600, "th": 25, "hoehe": 0})
        z1 = feuchte.Zustand(5, 0.8)
        m = 1.0 * z1.rho / (1 + z1.x)
        assert r.value("Q") == approx(m * (feuchte.enthalpie(25, z1.x) - z1.h))
        assert r.value("x2") == approx(z1.x * 1000)

    def test_kuehlen_entfeuchten(self):
        r = FeuchteLuft().run({"modus": "kuehlen", "t1": 32, "phi1": 40, "V1": 4000, "tz": 16, "tk": 10,
                              "hoehe": 0})
        z1 = feuchte.Zustand(32, 0.4)
        xk = feuchte.x_saett(10)
        x2 = xk + (z1.x - xk) * 6 / 22
        assert r.value("x2") == approx(x2 * 1000)
        m = 4000 / 3600 * z1.rho / (1 + z1.x)
        assert r.value("kond") == approx(m * (z1.x - x2) * 3600)
        # trockenes Kühlen: Kühlfläche über dem Taupunkt
        r = FeuchteLuft().run({"modus": "kuehlen", "t1": 26, "phi1": 40, "tz": 18, "tk": 15})
        assert r.value("kond") == approx(0)


class TestLuftmenge:
    def test_personen_kategorien(self):
        r = Luftmenge().run({"modus": "personen", "n_p": 10, "A": 50, "kat": "I", "emission": "nicht"})
        assert r.value("Vls") == approx(10 * 10 + 50 * 2.0)

    def test_last_und_co2(self):
        r = Luftmenge().run({"modus": "last", "Q": 5, "dT": 8, "theta": 18, "hoehe": 0})
        z = medien.medium("luft").zustand(18, 101325)
        assert r.value("V") == approx(5000 / (z.rho * z.cp * 1000 * 8) * 3600)
        r = Luftmenge().run({"modus": "co2", "n_p": 20, "co2_p": 20, "ci": 1000, "ca": 400})
        assert r.value("V") == approx(20 * 0.020 / 600e-6)
        assert not Luftmenge().run({"modus": "co2", "ci": 300}).ok


class TestKanal:
    def test_durchmesser(self):
        assert d_hydraulisch(0.5, 0.3) == approx(0.375)
        assert d_gleichwertig(0.5, 0.3) == approx(0.420, abs=0.002)

    def test_rund_auto_und_druckverlust(self):
        r = Luftkanal().run({"V": 2000, "form": "rund", "dim": "auto", "vmax": 5, "L": 20, "zeta": 1.5,
                             "rauheit": "blech", "theta": 20, "hoehe": 0})
        assert r.value("d") == 400                     # Ø 355 hätte 5,6 m/s
        z = medien.medium("luft").zustand(20, 101325)
        v = 2000 / 3600 / (math.pi * 0.4**2 / 4)
        lam = rohrreibungszahl(v * 0.4 / z.nu, 0.15e-3 / 0.4)
        pd = z.rho * v**2 / 2
        assert r.value("dp") == approx(lam / 0.4 * pd * 20 + 1.5 * pd)

    def test_rechteck_auto(self):
        r = Luftkanal().run({"V": 3600, "form": "rechteck", "dim": "auto", "b": 250, "vmax": 4})
        assert r.value("a") == 1000 and r.value("v") <= 4


class TestKanalnetz:
    def test_summe(self):
        rows = [[3000, 400, None, 10, 1.0, 20], [1500, 500, 250, 8, None, None]]
        r = Kanalnetz().run({"strecken": rows, "dp_g": 300, "res": 0, "theta": 20, "hoehe": 0, "rauheit": "blech"})
        z = medien.medium("luft").zustand(20, 101325)

        def dp(V, A, dh, L, zeta):
            v = V / 3600 / A
            lam = rohrreibungszahl(v * dh / z.nu, 0.15e-3 / dh)
            return lam / dh * z.rho * v**2 / 2 * L + zeta * z.rho * v**2 / 2
        soll = dp(3000, math.pi * 0.16 / 4, 0.4, 10, 1.0) + 20 + dp(1500, 0.125, d_hydraulisch(0.5, 0.25), 8, 0)
        assert r.value("dpext") == approx(soll)
        assert r.value("dp") == approx(soll + 300) and r.value("V") == approx(3000)

    def test_auto_rund(self):
        r = Kanalnetz().run({"strecken": [[1000, None, None, 10, None, None]], "vmax": 4, "Rmax": 1.0})
        assert r.ok and r.value("vmax") <= 4


class TestVentilator:
    def test_leistung_sfp(self):
        r = Ventilator().run({"V": 3600, "dp_ext": 400, "dp_int": 400, "eta": 50, "t": 2000, "teil": 100,
                              "preis": 0.25})
        assert r.value("P") == approx(1.0 * 800 / 0.5 / 1000)
        assert r.value("sfp") == approx(1600)
        assert r.value("K") == approx(1.6 * 2000 * 0.25)
        assert sfp_klasse(1600) == "SFP 4" and sfp_klasse(500) == "SFP 1"

    def test_teillast(self):
        r = Ventilator().run({"teil": 50})
        assert r.value("E") == approx(r.value("P") * 0.125 * 3000)


class TestWRG:
    def test_temperaturen_und_leistung(self):
        r = Waermerueckgewinnung().run({"V": 3600, "Vab": 3600, "phi_t": 80, "tau": -10, "tab": 20, "tzu": 20})
        assert r.value("tnach") == approx(14)
        z = medien.medium("luft").zustand(-10)
        assert r.value("Qwrg") == approx(1.0 * z.rho * z.cp * 24)
        assert r.value("tfo") == approx(-4) and warned(r, "Vereisungsgefahr")

    def test_jahreseinsparung_gas(self):
        r = Waermerueckgewinnung().run({"V": 3600, "Vab": 3600, "phi_t": 70, "tau": -12, "Gh": 40000, "dp": 0,
                                        "energie": "gas", "brenngas": "erdgas_h", "eta_k": 100, "p_gas": 0.1})
        z = medien.medium("luft").zustand(-12)
        E = z.rho * z.cp * 0.7 * 40000
        assert r.value("E") == approx(E / 1000)
        assert r.value("dK") == approx(E * 0.1)

    def test_druckverlust_frisst_einsparung(self):
        r = Waermerueckgewinnung().run({"phi_t": 20, "Gh": 5000, "dp": 400, "t": 8760})
        assert warned(r, "übersteigt")


def test_kette_lueftungsanlage():
    p = Project()
    ids = lk.kette_anlegen(p, lk.KETTEN[3])
    res = lk.aufloesen(p, by_id())
    assert not res.fehler and all(res.results[i].ok for i in ids)
    assert res.inputs[ids[2]]["dp_ext"] == approx(res.results[ids[1]].value("dpext"), rel=1e-3)
