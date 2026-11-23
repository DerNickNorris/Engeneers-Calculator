"""Elektromotoren (Asynchron): Auswahl, Kenndaten, Anlauf, FU, Zuleitung, Effizienz."""

import math

import numpy as np
import pytest

from ingrechner.calculators.elektro._motor import Kennlinie, leistungsklasse, mindestklasse, polzahl, teillast, typwerte
from ingrechner.calculators.elektro.motoranlauf import Motoranlauf
from ingrechner.calculators.elektro.motorauswahl import Motorauswahl
from ingrechner.calculators.elektro.motordaten import Motordaten
from ingrechner.calculators.elektro.motoreffizienz import Motoreffizienz
from ingrechner.calculators.elektro.motorfu import MotorUmrichter
from ingrechner.calculators.elektro.motorzuleitung import Motorzuleitung, spannungsfall
from ingrechner.core import links as lk
from ingrechner.core.model import Level
from ingrechner.core.project import Project
from ingrechner.core.registry import by_id

approx = pytest.approx
G = 9.80665


def warned(r, text):
    return any(m.level is Level.WARNUNG and text in m.text for m in r.messages)


class TestGrundlagen:
    def test_polzahl_und_klasse(self):
        assert polzahl(50, 1445) == 4 and polzahl(50, 2900) == 2 and polzahl(60, 1750) == 4
        assert mindestklasse(0.37, 4) == "IE2" and mindestklasse(11, 4) == "IE3"
        assert mindestklasse(90, 4) == "IE4" and mindestklasse(90, 8) == "IE3"
        assert leistungsklasse(11, "IE3") == 91.4 and leistungsklasse(11, "IE4") == 93.3

    def test_kloss(self):
        k = Kennlinie(26.4, 0.0367, 2.9, 2.3)
        assert float(k.M(0.0367)) == approx(26.4, rel=0.01)       # Bemessungspunkt
        assert float(k.M(k.sK)) == approx(2.9 * 26.4, rel=0.01)    # Kippmoment
        assert float(k.M(1.0)) == approx(2.3 * 26.4)               # Anlaufmoment angepasst

    def test_teillast(self):
        assert teillast(0.9, 1.0) == approx(0.9)
        assert teillast(0.9, 0.5) < 0.9 < teillast(0.9, 0.8) and teillast(0.9, 0.0) == 0
        assert typwerte(4).cosphi == approx(0.82) and typwerte(4).eta == 88.6


class TestAuswahl:
    def test_hubwerk(self):
        r = Motorauswahl().run({"anwendung": "hub", "m": 1000, "v": 0.2, "eta": 90, "reserve": 0, "tk": 40, "h": 0})
        assert r.value("PL") == approx(1000 * G * 0.2 / 1000)
        assert r.value("PW") == approx(1000 * G * 0.2 / 0.9 / 1000)
        assert r.value("PN") == 2.2

    def test_band_und_abminderung(self):
        r = Motorauswahl().run({"anwendung": "band", "m": 2000, "v": 0.5, "mu": 0.03, "steig": 5, "eta": 90,
                                "reserve": 0, "tk": 50, "h": 2000})
        F = 2000 * G * (0.03 * math.cos(math.radians(5)) + math.sin(math.radians(5)))
        assert r.value("PL") == approx(F * 0.5 / 1000)
        assert r.value("Perf") == approx(F * 0.5 / 0.9 / (0.92 * 0.94) / 1000)

    def test_betriebsart(self):
        s1 = Motorauswahl().run({"anwendung": "quadratisch", "PW": 10, "reserve": 0, "eta": 100})
        s3 = Motorauswahl().run({"anwendung": "quadratisch", "PW": 10, "reserve": 0, "eta": 100,
                                 "betriebsart": "S3", "ed": "25"})
        assert s3.value("Perf") == approx(s1.value("Perf") / 1.3)


class TestKenndaten:
    def test_typenschild(self):
        r = Motordaten().run({"PN": 4, "UN": 400, "f": 50, "nN": 1445, "eta": 88.6, "cosphi": 0.82, "last": "keine"})
        IN = 4000 / (math.sqrt(3) * 400 * 0.886 * 0.82)
        assert r.value("IN") == approx(IN) and r.value("MN") == approx(4000 / (2 * math.pi * 1445 / 60))
        assert r.value("sN") == approx((1500 - 1445) / 1500 * 100) and r.value("pole") == 4

    def test_betriebspunkt(self):
        r = Motordaten().run({"last": "konstant", "ML": 20})
        assert 1445 < r.value("nB") < 1500 and r.value("MB") == approx(20, rel=1e-4)
        assert not Motordaten().run({"last": "konstant", "ML": 100}).ok


class TestAnlauf:
    def test_direkt_hochlaufzeit(self):
        inp = {"art": "direkt", "last": "konstant", "ML": 0, "JL": 0.1, "JM": 1e-6, "leitung": "nein"}
        r = Motoranlauf().run(inp)
        # Kontrolle: t = J·Δω / mittleres Beschleunigungsmoment liegt zwischen den Grenzen M_N … M_K
        J, w = 0.1, 2 * math.pi * 0.98 * 1445 / 60
        MN = 4000 / (2 * math.pi * 1445 / 60)
        assert J * w / (2.9 * MN) < r.value("tA") < J * w / (2.3 * MN)
        assert r.value("IA") == approx(7 * r.value("IN"))

    def test_stern_dreieck_und_sanft(self):
        r = Motoranlauf().run({"art": "stern_dreieck", "last": "quadratisch", "leitung": "nein"})
        assert r.value("IA") == approx(7 * r.value("IN") / 3)
        r = Motoranlauf().run({"art": "sanft", "ki": 3.5, "last": "quadratisch", "leitung": "nein"})
        assert r.value("IA") == approx(3.5 * r.value("IN"), rel=1e-3)
        bad = Motoranlauf().run({"art": "stern_dreieck", "last": "konstant", "ML": 30, "leitung": "nein"})
        assert not bad.ok

    def test_spannungsfall(self):
        r = Motoranlauf().run({"art": "direkt", "L": 60, "S": 2.5, "leitung": "ja", "last": "quadratisch"})
        assert r.value("duA") == approx(spannungsfall(r.value("IA"), 60, 2.5, 400, 0.35))


class TestFU:
    def test_feldschwaechung(self):
        r = MotorUmrichter().run({"fmin": 20, "fmax": 100, "last": "konstant", "ML": 20, "kuehlung": "fremd",
                                  "bremsen": "keins"})
        MN = 4000 / (2 * math.pi * 1445 / 60)
        assert r.value("ausl") == approx(20 / (MN * 50 / 100) * 100, rel=1e-3)   # bei 100 Hz: M_zul = M_N/2
        assert warned(r, "übersteigt")

    def test_bremswiderstand(self):
        r = MotorUmrichter().run({"bremsen": "massen", "J": 0.2, "tb": 2, "fmax": 50, "Udc": 780, "ED": 10})
        w = 2 * math.pi * 1445 / 60
        E = 0.2 * w**2 / 2 * 0.886
        assert r.value("Pbr") == approx(2 * E / 2 / 1000)
        assert r.value("Rmax") == approx(780**2 / (2 * E / 2))
        r = MotorUmrichter().run({"bremsen": "hub", "m": 500, "v": 0.5, "eta_mech": 85})
        assert r.value("Pbr") == approx(500 * G * 0.5 * 0.85 * 0.886 / 1000)

    def test_87hz(self):
        r = MotorUmrichter().run({"schaltung": "87", "fmax": 87, "bremsen": "keins", "fmin": 20})
        assert r.value("feck") == approx(50 * math.sqrt(3))


class TestZuleitung:
    def test_querschnitt_und_sicherung(self):
        r = Motorzuleitung().run({"vorgabe": "strom", "IN": 21, "cosphi": 0.84, "UN": 400, "L": 10,
                                  "verlegeart": "C", "tu": 30, "n": 1, "anlauf": "direkt", "ia": 7.3, "tA": 3})
        assert r.value("S") == 2.5 and r.value("Iz") == approx(24)
        assert r.value("In") == 35                       # 153 A / 35 A = 4,4 ≤ 4,67 (t_A = 3 s)
        r2 = Motorzuleitung().run({"vorgabe": "strom", "IN": 21, "L": 10, "verlegeart": "C", "tu": 40, "n": 3,
                                   "anlauf": "direkt"})
        assert r2.value("S") == 6 and r2.value("Iz") == approx(41 * 0.87 * 0.70)

    def test_stern_dreieck(self):
        r = Motorzuleitung().run({"vorgabe": "strom", "IN": 21, "anlauf": "stern_dreieck"})
        assert r.value("Ir") == approx(21 / math.sqrt(3))


class TestEffizienz:
    def test_vergleich(self):
        r = Motoreffizienz().run({"PN": 11, "last": 100, "t": 4000, "a": "IE2", "b": "IE4", "preis": 0.25,
                                  "invest": 500})
        Ea, Eb = 11 / 0.898 * 4000, 11 / 0.933 * 4000
        assert r.value("dE") == approx(Ea - Eb, rel=1e-6)
        assert r.value("ta") == approx(500 / ((Ea - Eb) * 0.25), rel=1e-6)


def test_kette_motor():
    p = Project()
    ids = lk.kette_anlegen(p, lk.KETTEN[5])
    res = lk.aufloesen(p, by_id())
    assert not res.fehler and all(res.results[i].ok for i in ids)
    assert res.inputs[ids[3]]["IN"] == approx(res.results[ids[1]].value("IN"), rel=1e-3)
