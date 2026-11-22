"""Getriebe: Verzahnungsgeometrie, Tragfähigkeit, Antrieb, Übersetzung, Lager, Passfeder, Riemen, Kette."""

import math

import pytest

from ingrechner.calculators.maschinenbau._getriebe import Radpaar, betriebsfaktor, inv, inv_umkehr, passfeder, y_fs
from ingrechner.calculators.maschinenbau.antrieb import Antriebsauslegung
from ingrechner.calculators.maschinenbau.passfeder import Passfeder
from ingrechner.calculators.maschinenbau.riemen_kette import Keilriementrieb, Kettentrieb, winkelfaktor
from ingrechner.calculators.maschinenbau.stirnrad import Stirnrad
from ingrechner.calculators.maschinenbau.uebersetzung import Uebersetzung, zaehne_vorschlag
from ingrechner.calculators.maschinenbau.waelzlager import Waelzlager, rillenkugel_ey
from ingrechner.calculators.maschinenbau.zahnrad_tragfaehigkeit import ZahnradTragfaehigkeit
from ingrechner.core import links as lk
from ingrechner.core.model import Level
from ingrechner.core.project import Project
from ingrechner.core.registry import by_id

approx = pytest.approx
A20 = math.radians(20)


def warned(r, text):
    return any(m.level is Level.WARNUNG and text in m.text for m in r.messages)


class TestGeometrie:
    def test_evolventenfunktion(self):
        assert inv(A20) == approx(0.014904, abs=1e-6)
        assert inv_umkehr(inv(math.radians(23.5))) == approx(math.radians(23.5))

    def test_geradverzahnung_ohne_x(self):
        r = Radpaar(2, 20, 40, 0, A20, 0, 0, 20)
        assert (r.a, r.d1, r.da1, r.df1, r.db1) == approx((60, 40, 44, 35, 40 * math.cos(A20)))
        assert r.eps_a == approx(1.635, abs=0.002)                   # Tabellenwert ≈ 1,64
        k, w = r.zahnweite(20, 0)
        assert k == 3 and w == approx(15.3209, abs=1e-3)            # DIN 3960 Tabelle W₃ = 15,321 (m = 2)

    def test_profilverschiebung_achsabstand(self):
        r = Radpaar(3, 19, 71, math.radians(15), A20, 0.3, -0.1, 40)
        # inv α_wt = 2·Σx·tan α_n/(z₁+z₂) + inv α_t
        assert inv(r.alpha_wt) == approx(2 * 0.2 * math.tan(A20) / 90 + inv(r.alpha_t))
        assert r.a == approx(r.ad * math.cos(r.alpha_t) / math.cos(r.alpha_wt))
        assert r.eps_b == approx(40 * math.sin(math.radians(15)) / (math.pi * 3))

    def test_achsabstand_vorgabe(self):
        r = Stirnrad().run({"x_art": "achsabstand", "a_soll": 140})
        assert r.value("a") == approx(140, abs=1e-6)
        assert r.value("x1") - r.value("x2") == approx(0.4)

    def test_unterschnitt_und_ueberdeckung(self):
        r = Stirnrad().run({"z1": 12, "x1": 0, "x2": 0, "beta": 0})
        assert warned(r, "Unterschnitt")
        assert Radpaar(2, 12, 40, 0, A20, 0, 0, 20).x_min(12) == approx(1 - 12 * math.sin(A20) ** 2 / 2)


class TestTragfaehigkeit:
    def test_kraefte_und_spannungen(self):
        inp = {"mn": 3, "z1": 20, "z2": 60, "beta": 0, "alpha": 20, "x1": 0, "x2": 0, "b": 30, "M1": 150,
               "n1": 1000, "w1": "16mncr5", "w2": "16mncr5", "KA": 1, "Kv": 1, "KHb": 1, "KHa": 1}
        r = ZahnradTragfaehigkeit().run(inp)
        Ft = 2000 * 150 / 60
        assert r.value("Ft") == approx(Ft) and r.value("Fr") == approx(Ft * math.tan(A20))
        rp = Radpaar(3, 20, 60, 0, A20, 0, 0, 30)
        ZH = math.sqrt(2 / (math.cos(A20) * math.sin(A20)))           # 2,495 für Geradverzahnung ohne x
        assert ZH == approx(2.495, abs=0.001)
        ZE = 189.8                                                   # Stahl/Stahl
        Zeps = math.sqrt((4 - rp.eps_a) / 3)
        sH = ZH * ZE * Zeps * math.sqrt(Ft / (60 * 30) * 4 / 3)
        assert r.value("sH") == approx(sH, rel=2e-3)
        sF1 = Ft / (30 * 3) * y_fs(20, 0) * (0.25 + 0.75 / rp.eps_a)
        assert r.value("sF1") == approx(sF1)
        assert r.value("SH1") == approx(1470 / sH, rel=2e-3)

    def test_kopffaktor(self):
        assert y_fs(20, 0) == approx(2.80 * 1.55)
        assert y_fs(25, 0.5) < y_fs(25, 0)

    def test_ueberlast_warnt(self):
        assert warned(ZahnradTragfaehigkeit().run({"M1": 600}), "Sicherheit")


class TestAntrieb:
    def test_betriebsfaktor(self):
        assert betriebsfaktor("I", 8, 5) == (1.0, 1.0, 0.0)
        assert betriebsfaktor("II", 16, 50)[0] == approx(1.5)
        assert betriebsfaktor("III", 24, 300)[0] == approx(2.1)

    def test_auslegung(self):
        r = Antriebsauslegung().run({"vorgabe": "moment", "M2": 1000, "n2": 30, "n1": 1450, "eta": 95,
                                     "fb_art": "frei", "fb": 1.4, "M2N": 1500, "element": "kette", "d0": 200,
                                     "FRzul": 20000})
        P2 = 1000 * 2 * math.pi * 30 / 60
        assert r.value("M2erf") == approx(1400) and r.value("P1") == approx(P2 / 0.95 / 1000)
        assert r.value("PN") == 4.0 and r.value("fBvorh") == approx(1.5)
        assert r.value("FQ") == approx(2000 * 1000 / 200 * 1.4)

    def test_hochlauf(self):
        r = Antriebsauslegung().run({"J": 20, "JM": 0.01})
        assert 0 < r.value("tA") < 2


class TestUebersetzung:
    def test_zaehne(self):
        z1, z2, i = zaehne_vorschlag(3.5, 17, 150)
        assert abs(i / 3.5 - 1) <= 0.005 and math.gcd(z1, z2) == 1

    def test_stufen(self):
        r = Uebersetzung().run({"n1": 1450, "n2": 40, "P": 5.5, "eta": 98})
        assert r.value("abw") == approx(0, abs=2)
        assert r.value("M_ab") == approx(5500 / (2 * math.pi * 1450 / 60) * r.value("i_ist") * 0.98**2, rel=1e-6)
        assert r.value("n_ab") == approx(1450 / r.value("i_ist"))


class TestLager:
    def test_l10(self):
        r = Waelzlager().run({"kraefte": "direkt", "Fr": 4000, "Fa": 0, "C": 30, "C0": 20, "n": 1000, "xy": "radial"})
        assert r.value("Lh") == approx((30000 / 4000) ** 3 * 1e6 / 60000)

    def test_rillenkugel_xy(self):
        e, Y = rillenkugel_ey(14 * 1000 / 19000)
        r = Waelzlager().run({"kraefte": "direkt", "Fr": 1000, "Fa": 1000, "C": 35.1, "C0": 19, "f0": 14})
        assert r.value("P") == approx(0.56 * 1000 + Y * 1000)

    def test_zahnkraefte_und_zuverlaessigkeit(self):
        inp = {"kraefte": "zahnrad", "Ft": 4000, "Fr_z": 0, "Fa_z": 0, "dw": 60, "la": 50, "lb": 150, "lager": "A",
               "xy": "radial", "zuv": "99"}
        r = Waelzlager().run(inp)
        assert r.value("Fr") == approx(3000)
        assert r.value("Lnmh") == approx(0.25 * r.value("Lh"))


class TestPassfeder:
    def test_tabelle(self):
        assert passfeder(45) == (14, 9, 5.5, 3.8) and passfeder(30) == (8, 7, 4.0, 3.3) and passfeder(300) is None

    def test_pressung(self):
        r = Passfeder().run({"d": 45, "T": 400, "KA": 1.0, "L": 56, "form": "A", "anzahl": "1", "nabe": "stahl"})
        F = 2 * 400000 / 45
        assert r.value("pN") == approx(F / (3.5 * 42))
        assert r.value("pW") == approx(F / (5.5 * 42))
        r2 = Passfeder().run({"d": 45, "T": 400, "KA": 1.0, "L": 56, "form": "B", "anzahl": "2"})
        assert r2.value("pN") == approx(F / (3.5 * 56 * 2 * 0.75))


class TestRiemenKette:
    def test_keilriemen(self):
        r = Keilriementrieb().run({"d1": 125, "d2": 315, "a0": 500})
        assert r.value("L") == 1800
        L = 1800
        a = r.value("a")
        assert 2 * a + math.pi / 2 * 440 + 190**2 / (4 * a) == approx(L, rel=1e-6)
        assert winkelfaktor(180) == approx(1.0) and winkelfaktor(120) == approx(0.82, abs=0.01)

    def test_kette(self):
        r = Kettentrieb().run({"P": 4, "n1": 200, "z1": 19, "z2": 57, "kette": "16B", "a0": 800, "fB": 1.0})
        v = 19 * 25.4 * 200 / 60000
        assert r.value("v") == approx(v)
        assert r.value("S") == approx(60000 / (4000 / v + 2.7 * v**2))
        assert r.value("X") % 2 == 0
        p, X, z1, z2, a = 25.4, r.value("X"), 19, 57, r.value("a")
        assert 2 * a / p + (z1 + z2) / 2 + ((z2 - z1) / (2 * math.pi)) ** 2 * p / a == approx(X, abs=0.05)


def test_kette_getriebeauslegung():
    p = Project()
    ids = lk.kette_anlegen(p, lk.KETTEN[4])
    res = lk.aufloesen(p, by_id())
    assert not res.fehler and all(res.results[i].ok for i in ids)
    assert res.inputs[ids[3]]["KA"] == approx(res.results[ids[0]].value("fB"))
