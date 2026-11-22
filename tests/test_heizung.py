"""Heizung / Wärme: Stoffwerte, Wärmeverlust, Wärmemenge, Wärmetauscher, Temperaturabfall."""

import math

import pytest

from ingrechner.calculators.heizung.rohrverlust_luft import RohrverlustLuft
from ingrechner.calculators.heizung.temperaturabfall import Temperaturabfall
from ingrechner.calculators.heizung.waermemenge import Waermemenge
from ingrechner.calculators.heizung.waermetauscher import Waermetauscher, lmtd
from ingrechner.core.materials import MaterialLibrary
from ingrechner.core.model import Level
from ingrechner.core.stoffwerte import stoffwerte
from ingrechner.core.waermeverlust import h_konvektion, h_strahlung, rohrverlust, temperaturverlauf

approx = pytest.approx


def warned(r, text):
    return any(m.level is Level.WARNUNG and text in m.text for m in r.messages)


# ------------------------------------------------------------- Stoffwerte
class TestStoffwerte:
    @pytest.mark.parametrize("t, rho, cp", [(20, 998.2, 4.182), (60, 983.2, 4.185), (100, 958.4, 4.216)])
    def test_wasser_tabelle(self, t, rho, cp):
        sw = stoffwerte("wasser", t)
        assert (sw.rho, sw.cp) == (rho, cp)

    def test_interpolation(self):
        sw = stoffwerte("wasser", 65)
        assert sw.rho == approx((983.2 + 977.8) / 2) and sw.cp == approx((4.185 + 4.190) / 2)

    def test_prandtl(self):
        assert stoffwerte("wasser", 20).pr == approx(7.0, abs=0.05)
        assert stoffwerte("luft", 20).pr == approx(0.71, abs=0.01)

    def test_ausserhalb(self):
        with pytest.raises(ValueError):
            stoffwerte("wasser", 160)


# ------------------------------------------------------------ Wärmeverlust
class TestWaermeverlust:
    def test_konvektion_iso12241(self):
        # laminar: 1,25·(ΔT/D)^0,25; turbulent: 1,21·ΔT^(1/3); Wind: 8,9·v^0,9/D^0,1
        assert h_konvektion(0.1, 20, "innen") == approx(1.25 * (20 / 0.1) ** 0.25)
        assert h_konvektion(3.0, 20, "innen") == approx(1.21 * 20 ** (1 / 3))
        assert h_konvektion(0.2, 20, "aussen", 5) == approx(8.9 * 5**0.9 / 0.2**0.1)
        assert h_konvektion(0.001, 20, "aussen", 1) == approx(8.1e-3 / 0.001 + 3.14 * math.sqrt(1 / 0.001))

    def test_strahlung(self):
        hr = h_strahlung(0.9, 50, 20)
        assert hr == approx(0.9 * 5.67e-8 * (323.15**4 - 293.15**4) / 30, rel=1e-3)

    def test_energiebilanz(self):
        r = rohrverlust(70, 20, 0.0603, 0.0036, 50, 0.05, 0.04, 0.93)
        # Wärmestrom durch die Dämmung = Wärmeabgabe an der Oberfläche
        q_daemm = (70 - r.ts - r.q * r.R_rohr) / r.R_daemm
        q_aussen = math.pi * r.D * (r.h_conv + r.h_rad) * (r.ts - 20)
        assert r.q == approx(q_daemm, rel=1e-6) and r.q == approx(q_aussen, rel=1e-6)

    def test_plausibel_dn50(self):
        """DN 50, 70/20 °C: ungedämmt ≈ 110–125 W/m (Tabellenwerte), 50 mm MW ≈ 11–13 W/m."""
        assert 110 < rohrverlust(70, 20, 0.0603, 0.0036, 50, 0, 0.04, 0.8).q < 125
        assert 11 < rohrverlust(70, 20, 0.0603, 0.0036, 50, 0.05, 0.037, 0.93).q < 13

    def test_mehr_daemmung_weniger_verlust(self):
        qs = [rohrverlust(80, 10, 0.0889, 0.004, 50, d, 0.035, 0.93).q for d in (0.02, 0.04, 0.08)]
        assert qs[0] > qs[1] > qs[2] > 0

    def test_temperaturverlauf(self):
        t = temperaturverlauf(70, 10, 0.3, 4190, 2.0, 500)
        assert t == approx(10 + 60 * math.exp(-500 / (0.3 * 4190 * 2.0)))


# --------------------------------------------------------- Wärmemenge
class TestWaermemenge:
    def test_volumenstrom(self):
        r = Waermemenge().run({"modus": "volumenstrom", "Q": 20, "dt": 20, "tvl": 70})
        sw = stoffwerte("wasser", 60)
        assert r.value("V") == approx(20 / (sw.rho * sw.cp * 20) * 3600)

    def test_modi_konsistent(self):
        v = Waermemenge().run({"modus": "volumenstrom", "Q": 15, "dt": 10, "tvl": 55}).value("V")
        assert Waermemenge().run({"modus": "leistung", "V": v, "dt": 10, "tvl": 55}).value("Q") == approx(15)
        assert Waermemenge().run({"modus": "spreizung", "Q": 15, "V": v, "tvl": 55}).value("dt") == approx(10, rel=1e-3)

    def test_waermemenge_kwh(self):
        r = Waermemenge().run({"modus": "leistung", "V": 1, "dt": 10, "t": 8})
        assert r.value("E") == approx(r.value("Q") * 8)

    def test_luft(self):
        r = Waermemenge().run({"medium": "luft", "modus": "leistung", "V": 1000, "dt": 10, "tvl": 30})
        sw = stoffwerte("luft", 25)
        assert r.value("Q") == approx(1000 / 3600 * sw.rho * sw.cp * 10)


# ------------------------------------------------------- Wärmetauscher
class TestWaermetauscher:
    def test_lmtd(self):
        assert lmtd(20, 10) == approx(10 / math.log(2))
        assert lmtd(15, 15) == 15

    def test_gegenstrom(self):
        r = Waermetauscher().run({"Q": 50, "t1e": 80, "t1a": 55, "t2e": 45, "t2a": 70, "k": 4000, "z": 10})
        dtm = lmtd(10, 10)
        assert r.value("dtm") == approx(dtm)
        assert r.value("A") == approx(50000 / (4000 * dtm))
        assert r.value("Az") == approx(r.value("A") * 1.1)

    def test_standardwerte_beide_stromfuehrungen(self):
        assert Waermetauscher().run({"strom": "gegen"}).ok and Waermetauscher().run({"strom": "gleich"}).ok

    def test_gleichstrom_kreuzung(self):
        r = Waermetauscher().run({"strom": "gleich", "t1e": 80, "t1a": 55, "t2e": 45, "t2a": 70})
        assert not r.ok and any("Temperaturkreuzung" in m.text for m in r.messages)

    def test_gleichstrom_braucht_mehr_flaeche(self):
        base = {"t1e": 90, "t1a": 60, "t2e": 20, "t2a": 50}
        g = Waermetauscher().run({**base, "strom": "gegen"}).value("A")
        p = Waermetauscher().run({**base, "strom": "gleich"}).value("A")
        assert p > g

    def test_sekundaer_volumenstrom(self):
        r = Waermetauscher().run({"sek": "strom", "V2": 2.5})
        sw = stoffwerte("wasser", (40 + r.value("t2a")) / 2)
        assert r.value("t2a") == approx(40 + 50 / (2.5 / 3600 * sw.rho * sw.cp), rel=1e-4)

    def test_kleine_graedigkeit(self):
        assert warned(Waermetauscher().run({"t1e": 80, "t1a": 47, "t2e": 45, "t2a": 70}), "Grädigkeit")


# ---------------------------------------------------- Rohrverlust / Abfall
class TestRohrRechner:
    def test_rohrverlust_standard(self):
        r = RohrverlustLuft().run({})
        assert r.ok and 10 < r.value("q") < 13
        assert r.value("Qges") == approx(r.value("q") * 10)
        assert r.value("red") > 85

    def test_werkstoffauswahl(self):
        stahl = RohrverlustLuft().run({"daemm": 0}).value("q")
        pex = RohrverlustLuft().run({"daemm": 0, "werkstoff": "b:pe-xa"}).value("q")
        assert pex < stahl                                    # Kunststoffwand dämmt etwas
        frei = RohrverlustLuft().run({"werkstoff": "frei", "lam_rohr": 50})
        auto = RohrverlustLuft().run({})
        assert frei.value("q") == approx(auto.value("q"))     # P235GH hat λ = 50

    def test_daemmstoffauswahl(self):
        pur = RohrverlustLuft().run({"daemmstoff": "b:pur-en253"}).value("q")
        mw = RohrverlustLuft().run({"daemmstoff": "b:mw-rohrschale"}).value("q")
        assert pur < mw

    def test_beruehrschutz(self):
        assert warned(RohrverlustLuft().run({"daemm": 0}), "60 °C")

    def test_temperaturabfall_bilanz(self):
        r = Temperaturabfall().run({})
        sw = stoffwerte("wasser", 70)
        m = 1.0 / 3600 * sw.rho
        assert r.value("Q") == approx(m * sw.cp * 1000 * r.value("dT"))
        assert 0 < r.value("dT") < 5

    def test_laengere_leitung_kuehlt_mehr(self):
        a = Temperaturabfall().run({"L": 100}).value("taus")
        b = Temperaturabfall().run({"L": 400}).value("taus")
        assert b < a


def test_fernwaerme_werkstoffe_in_datenbank():
    lib = MaterialLibrary(None)
    rohr = {m.name for m in lib.search("", "Rohrwerkstoff")}
    assert {"P235GH", "P235TR1", "PE-Xa", "PE-HD Mantelrohr", "Cu-DHP R250"} <= rohr
    pur = next(m for m in lib.builtin if m.id == "b:pur-en253")
    assert pur.lam <= 0.029 and pur.gruppe == "Dämmstoff"


# ================================================================ Teil 2
from ingrechner.calculators.heizung.heizkoerper import DT_NORM, Heizkoerper, dt_log  # noqa: E402
from ingrechner.calculators.heizung.mischtemperatur import Mischtemperatur  # noqa: E402
from ingrechner.calculators.heizung.pufferspeicher import Pufferspeicher  # noqa: E402
from ingrechner.calculators.heizung.rohrverlust_erde import (RohrverlustErde, r_erdreich,  # noqa: E402
                                                             r_gegenseitig, verlust_paar)


class TestErdreich:
    def test_erdreichwiderstand(self):
        lam, H, D = 1.0, 0.8, 0.14
        h = H + 0.0685 * lam
        assert r_erdreich(H, D, lam) == approx(math.acosh(2 * h / D) / (2 * math.pi * lam))
        assert r_gegenseitig(H, 0.3, lam) == approx(math.log(1 + (2 * h / 0.3) ** 2) / (4 * math.pi * lam))

    def test_symmetrie_gleiche_temperaturen(self):
        """Bei gleicher Vor- und Rücklauftemperatur: q = Δθ / (R + R_h) für beide Rohre."""
        q1, q2 = verlust_paar(70, 70, 10, 5.0, 0.3)
        assert q1 == approx(q2) and q1 == approx(60 / 5.3)

    def test_kopplung_verschwindet_bei_grossem_abstand(self):
        einzel = RohrverlustErde().run({"anordnung": "einzel"}).value("qges")
        weit = RohrverlustErde().run({"abstand": 50}).value("q1")
        assert weit == approx(einzel, rel=0.02)

    def test_dicke_serie_weniger_verlust(self):
        q = [RohrverlustErde().run({"serie": s}).value("qges") for s in ("1", "2", "3")]
        assert q[0] > q[1] > q[2] > 0

    def test_plausibel_kmr(self):
        """DN 50 Serie 2, 80/50 °C, θ_E = 10 °C, H = 0,8 m: Trassenverlust im Bereich 15–25 W/m."""
        assert 15 < RohrverlustErde().run({}).value("qges") < 25

    def test_jahresverlust(self):
        r = RohrverlustErde().run({"L": 250, "stunden": 8760})
        assert r.value("Qa") == approx(r.value("qges") * 250 * 8760 / 1000)

    def test_ungueltige_geometrie(self):
        assert not RohrverlustErde().run({"H": 0.05}).ok
        # Achsabstand ergibt sich aus Manteldurchmesser + lichtem Abstand – auch für DN 200
        assert RohrverlustErde().run({"kmr_dn": "DN 200", "H": 1.2}).ok

    def test_enger_abstand_mehr_kopplung(self):
        eng = RohrverlustErde().run({"abstand": 0.05}).value("q2")
        weit = RohrverlustErde().run({"abstand": 1.0}).value("q2")
        assert eng < weit          # Rücklauf wird vom nahen Vorlauf stärker „mitgeheizt"

    def test_eigene_daemmung(self):
        a = RohrverlustErde().run({"bauart": "frei", "daemm": 30}).value("qges")
        b = RohrverlustErde().run({"bauart": "frei", "daemm": 80}).value("qges")
        assert a > b


class TestHeizkoerper:
    def test_norm(self):
        assert DT_NORM == approx(10 / math.log(55 / 45))
        assert Heizkoerper().run({"tv": 75, "tr": 65, "ti": 20}).value("phi") == approx(1500)

    @pytest.mark.parametrize("tv, tr, faktor", [(55, 45, 0.511), (70, 55, 0.80), (45, 35, 0.297)])
    def test_umrechnung(self, tv, tr, faktor):
        """Faktoren für n = 1,3 (Umrechnungstabellen der Hersteller)."""
        f = Heizkoerper().run({"tv": tv, "tr": tr, "ti": 20, "n": 1.3}).value("f") / 100
        assert f == approx(faktor, abs=0.01)
        assert f == approx((dt_log(tv, tr, 20) / DT_NORM) ** 1.3)

    def test_erforderliche_normleistung(self):
        r = Heizkoerper().run({"Qb": 1000})
        assert r.value("phiN_erf") == approx(1000 / (r.value("f") / 100))
        assert warned(r, "deckt nur")

    def test_ungueltig(self):
        assert not Heizkoerper().run({"tr": 18, "ti": 20}).ok
        assert not Heizkoerper().run({"tv": 40, "tr": 45}).ok


class TestPuffer:
    def test_inhalt(self):
        r = Pufferspeicher().run({"V": 1000, "to": 70, "tu": 30, "P": 10, "Pl": 20})
        sw = stoffwerte("wasser", 50)
        E = sw.rho * sw.cp * 40 / 3600
        assert r.value("E") == approx(E)
        assert r.value("tE") == approx(E / 10 * 60) and r.value("tL") == approx(E / 20 * 60)

    def test_volumen_rueckrechnung(self):
        v = Pufferspeicher().run({"modus": "volumen", "Pl": 12, "t": 30, "to": 70, "tu": 35}).value("V")
        e = Pufferspeicher().run({"V": v, "to": 70, "tu": 35}).value("E")
        assert e == approx(12 * 0.5)

    def test_abnahme_beim_laden(self):
        a = Pufferspeicher().run({"modus": "volumen", "Pl": 12, "Pv": 0}).value("V")
        b = Pufferspeicher().run({"modus": "volumen", "Pl": 12, "Pv": 6}).value("V")
        assert b == approx(a / 2)


class TestMischung:
    def test_gleiche_temperatur(self):
        assert Mischtemperatur().run({"t1": 50, "t2": 50}).value("tm") == approx(50)

    def test_energiebilanz(self):
        r = Mischtemperatur().run({"V1": 1.0, "t1": 70, "V2": 0.5, "t2": 30})
        s1, s2 = stoffwerte("wasser", 70), stoffwerte("wasser", 30)
        m1, m2 = s1.rho, 0.5 * s2.rho
        assert r.value("tm") == approx((m1 * s1.cp * 70 + m2 * s2.cp * 30) / (m1 * s1.cp + m2 * s2.cp))
        assert r.value("m") == approx(m1 + m2)

    def test_drei_stroeme(self):
        r = Mischtemperatur().run({"V3": 1.0, "t3": 50})
        assert 30 < r.value("tm") < 70

    def test_beimischung(self):
        r = Mischtemperatur().run({"modus": "beimischung", "tvl": 75, "trl": 35, "tz": 45, "Vh": 1.2})
        assert r.value("x") == approx(25, abs=0.3)
        assert r.value("Ve") + r.value("Vb") == approx(1.2, rel=0.01)
        assert not Mischtemperatur().run({"modus": "beimischung", "tz": 80}).ok
