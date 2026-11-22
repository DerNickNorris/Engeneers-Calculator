"""Pumpen: Tabellenfeld, Dampfdruck, Auslegung, Kennlinie/Betriebspunkt, Leistung, Energie, NPSH."""

import math

import pytest

from ingrechner.calculators.fluid.druckverlust_rohr import DruckverlustRohr
from ingrechner.calculators.pumpen._pumpe import IE3, Kennlinie, motor_groesse, nullstelle
from ingrechner.calculators.pumpen.auslegung import PumpenAuslegung
from ingrechner.calculators.pumpen.betriebspunkt import Betriebspunkt
from ingrechner.calculators.pumpen.energie import Energiekosten
from ingrechner.calculators.pumpen.leistung import PumpenLeistung
from ingrechner.calculators.pumpen.npsh import NPSH
from ingrechner.core.model import Column, Level, TableField
from ingrechner.core.stoffwerte import dampfdruck, stoffwerte

approx = pytest.approx
G = 9.80665
# Parabel H = 6 − 0,2·V̇² mit η-Werten (Bestpunkt bei 3 m³/h)
PARABEL = [[q, 6 - 0.2 * q**2, e] for q, e in ((0, 0), (1, 30), (2, 42), (3, 45), (4, 42), (5, 30))]


def warned(r, text):
    return any(m.level is Level.WARNUNG and text in m.text for m in r.messages)


# ------------------------------------------------------------- Tabellenfeld
class TestTableField:
    f = TableField("k", "Kennlinie", [Column("q", "Q", "m**3/hour", min=0), Column("h", "H", "m"),
                                      Column("e", "η", "percent", optional=True)], [[0, 1, None], [1, 2, None]])

    def test_leere_zeilen_und_optionale_spalte(self):
        rows, msg = self.f.parse([[0, "6,5", ""], [None, None, None], ["1.5", 5, 40]])
        assert msg is None and rows == [[0.0, 6.5, None], [1.5, 5.0, 40.0]]

    @pytest.mark.parametrize("value, text", [
        ([[0, 1, None], [1, "x", None]], "keine gültige Zahl"),
        ([[0, None, None], [1, 2, None]], "„H“ fehlt"),
        ([[-1, 1, None], [1, 2, None]], "muss ≥"),
        ([[0, 1, None]], "mindestens 2"),
        ("kaputt", "ungültige Tabelle"),
    ])
    def test_fehler(self, value, text):
        assert text in self.f.parse(value)[1]

    def test_run_meldet_feldfehler(self):
        r = Betriebspunkt().run({"kennlinie": [[0, 6, None], [1, 5, None]]})
        assert "kennlinie" in r.field_errors

    def test_defaults_sind_kopien(self):
        c = Betriebspunkt()
        d = c.defaults()
        d["kennlinie"][0][1] = 99
        assert c.defaults()["kennlinie"][0][1] != 99


# --------------------------------------------------------------- Dampfdruck
@pytest.mark.parametrize("t, p", [(20, 2.3393), (50, 12.352), (100, 101.42),
                                  (25, 3.1699), (65, 25.042), (95, 84.609)])   # IAPWS-IF97
def test_dampfdruck(t, p):
    assert dampfdruck(t) == approx(p, rel=1e-3)


def test_dampfdruck_bereich():
    with pytest.raises(ValueError):
        dampfdruck(160)


# --------------------------------------------------------------- Kennlinie
class TestKennlinie:
    def test_parabel_exakt(self):
        kl = Kennlinie(PARABEL)
        assert kl.ch == approx([-0.2, 0, 6], abs=1e-9)
        assert kl.abw < 1e-9 and not kl.instabil

    def test_affinitaet(self):
        kl = Kennlinie(PARABEL)
        # H(V̇, n) = n²·H(V̇/n): Nullförderhöhe ~ n², Punkt (3 | 4,2) → (1,5 | 1,05) bei n = 0,5
        assert kl.H(0, 0.5) == approx(1.5)
        assert kl.H(1.5, 0.5) == approx(0.25 * (6 - 0.2 * 9))
        assert float(kl.eta(1.5, 0.5)) == approx(float(kl.eta(3.0)))

    def test_bestpunkt(self):
        q, e = Kennlinie(PARABEL).bep()
        assert q == approx(3.0, abs=0.05) and e == approx(0.45, abs=0.005)

    def test_ohne_eta(self):
        kl = Kennlinie([[r[0], r[1], None] for r in PARABEL])
        assert not kl.hat_eta and kl.eta(2) is None and kl.bep() is None

    def test_zu_wenige_punkte(self):
        with pytest.raises(ValueError):
            Kennlinie([[1, 5], [1, 5], [2, 4]])

    def test_nullstelle(self):
        assert nullstelle(lambda x: x**2 - 2, 0, 2) == approx(math.sqrt(2))
        assert nullstelle(lambda x: x + 1, 0, 2) is None


# --------------------------------------------------------- Betriebspunkt
class TestBetriebspunkt:
    base = {"kennlinie": PARABEL, "Va": 3.0, "Ha": 3.6, "Hs": 0.0}   # Anlage H = 0,4·V̇²

    def run(self, **kw):
        r = Betriebspunkt().run(self.base | kw)
        assert r.ok, r.messages
        return r

    def test_einzelpumpe(self):
        r = self.run()
        # 6 − 0,2·Q² = 0,4·Q²  →  Q = √10
        assert r.value("Qb") == approx(math.sqrt(10), rel=1e-6)
        assert r.value("Hb") == approx(4.0, rel=1e-6)

    def test_parallel(self):
        r = self.run(schaltung="parallel", z=2)
        q = math.sqrt(6 / 0.45)            # 6 − 0,05·Q² = 0,4·Q²
        assert r.value("Qb") == approx(q, rel=1e-6)
        assert r.value("Qp") == approx(q / 2, rel=1e-6)

    def test_reihe(self):
        r = self.run(schaltung="reihe", z=2)
        assert r.value("Qb") == approx(math.sqrt(15), rel=1e-6)   # 12 − 0,4·Q² = 0,4·Q²

    def test_drehzahl_anpassen(self):
        r = self.run(drehzahl="anpassen")
        # 6·n² − 0,2·3² = 3,6  →  n = √0,9
        assert r.value("n") == approx(math.sqrt(0.9) * 100, rel=1e-6)
        assert r.value("Qb") == approx(3.0, rel=1e-6) and r.value("Hb") == approx(3.6, rel=1e-6)
        assert r.value("nabs") == approx(2900 * math.sqrt(0.9), rel=1e-6)

    def test_feste_drehzahl_und_leistung(self):
        r = self.run(drehzahl="fest", n=80, rho=1000)
        # 6·0,64 − 0,2·Q² = 0,4·Q²
        q = math.sqrt(3.84 / 0.6)
        assert r.value("Qb") == approx(q, rel=1e-6)
        eta = float(Kennlinie(PARABEL).eta(q / 0.8))
        assert r.value("eta") == approx(eta * 100, rel=1e-6)
        assert r.value("P2") == approx(1000 * G * q / 3600 * 0.4 * q**2 / eta / 1000, rel=1e-6)

    def test_bestpunktlage(self):
        r = self.run(Va=5.0, Ha=1.25)          # sehr flache Anlage → weit rechts
        assert warned(r, "außerhalb des zulässigen Bereichs")

    def test_extrapolation_warnt(self):
        r = self.run(Va=6.0, Ha=0.5)
        assert warned(r, "extrapoliert")

    def test_kein_foerderstrom(self):
        r = Betriebspunkt().run(self.base | {"Hs": 7.0, "Ha": 8.0})
        assert not r.ok

    def test_zu_kleine_pumpe(self):
        r = Betriebspunkt().run(self.base | {"drehzahl": "anpassen", "Ha": 20.0})
        assert not r.ok and "nicht erreichbar" in r.messages[0].text


# --------------------------------------------------------------- Auslegung
class TestAuslegung:
    def test_gegen_druckverlustrechner(self):
        common = {"rho": 998.2, "nu": 1.004}
        a = PumpenAuslegung().run({"quelle": "volumen", "V": 10, "medium": "benutzer", **common, "rohr": "frei",
                                   "di": 50, "L": 100, "rauheit": "frei", "k": 0.05, "zeta": 4, "dp_k": 0,
                                   "kvs": 0, "res": 0})
        d = DruckverlustRohr().run({"Q": 10, "d": 50, "L": 100, "k": 0.05, "zeta": 4, "medium": "benutzer",
                                    **common})
        assert a.ok and d.ok
        assert a.value("H") == approx(d.value("hv"), rel=1e-6)
        assert a.value("v") == approx(d.value("v"), rel=1e-9)

    def test_volumenstrom_aus_leistung(self):
        r = PumpenAuslegung().run({"quelle": "waerme", "P": 100, "dT": 20, "theta": 60})
        sw = stoffwerte("wasser", 60)
        assert r.value("V") == approx(100 / (sw.rho * sw.cp * 20) * 3600, rel=1e-6)

    def test_statik_ventil_zuschlag(self):
        base = {"quelle": "volumen", "V": 4, "theta": 20, "hgeo": 10, "dp_b": 50, "kvs": 4, "dp_k": 20,
                "L": 0, "zeta": 0, "res": 10}
        r = PumpenAuslegung().run(base)
        rho = stoffwerte("wasser", 20).rho
        assert r.value("Hstat") == approx(10 + 50e3 / (rho * G))
        # Δp_V = (4/4)² bar = 100 kPa; + 20 kPa Komponenten; Zuschlag 10 %
        assert r.value("Hdyn") == approx(120e3 * 1.1 / (rho * G))
        assert r.value("Phyd") == approx(rho * G * 4 / 3600 * r.value("H"), rel=1e-6)

    def test_warnungen(self):
        r = PumpenAuslegung().run({"quelle": "volumen", "V": 30, "rohr": "st:DN 40"})
        assert warned(r, "Fließgeschwindigkeit") and warned(r, "Druckgefälle")
        r = PumpenAuslegung().run({"medium": "benutzer", "nu": 50, "rho": 900})
        assert warned(r, "ISO/TR 17766")


# ------------------------------------------------------------------ Leistung
class TestLeistung:
    def test_kette_und_motor(self):
        r = PumpenLeistung().run({"V": 25, "H": 18, "rho": 998, "etaP": 72})
        phyd = 998 * G * 25 / 3600 * 18
        assert r.value("Phyd") == approx(phyd / 1000)
        assert r.value("P2") == approx(phyd / 0.72 / 1000)
        assert r.value("PN") == 2.2                         # 1,70 kW · 1,2 = 2,04 kW → 2,2 kW
        assert r.value("P1") == approx(phyd / 0.72 / 0.867 / 1000)   # IE3 2,2 kW 4-polig: 86,7 %
        assert r.value("eta") == approx(72 * 0.867)

    def test_fu_und_energie(self):
        r = PumpenLeistung().run({"motor": "frei", "etaM": 90, "fu": "ja", "etaFU": 97, "energie": "ja",
                                  "t": 4000, "preis": 0.25})
        p1 = r.value("P1")
        assert r.value("vF") == approx(p1 * 0.03)
        assert r.value("E") == approx(p1 * 4000) and r.value("K") == approx(p1 * 4000 * 0.25)

    def test_motorreihe(self):
        assert motor_groesse(0.1) == (0, 0.12)
        assert motor_groesse(7.5) == (12, 7.5)
        assert motor_groesse(400) is None
        assert len(IE3) == 29


# ------------------------------------------------------------------- Energie
class TestEnergie:
    def test_dauerbetrieb_alle_gleich(self):
        r = Energiekosten().run({"profil": "voll", "t": 1000, "VN": 3.6, "HN": 5, "eta": 50, "rho": 1000})
        e = 1000 * G * 0.001 * 5 / 0.5 / 1000 * 1000     # kWh
        for k in ("E0", "E_dpc", "E_dpv", "E_ideal"):
            assert r.value(k) == approx(e, rel=1e-9)
        assert r.value("dK") == approx(0, abs=1e-9)

    def test_rangfolge_eu_profil(self):
        r = Energiekosten().run({})
        assert r.value("E0") > r.value("E_dpc") > r.value("E_dpv") > r.value("E_ideal") > 0
        assert r.value("dK") == approx((r.value("E0") - r.value("E_dpv")) * 0.30)

    def test_amortisation_und_co2(self):
        r = Energiekosten().run({"invest": 300, "plan": "dpc", "co2": 400})
        dE = r.value("E0") - r.value("E_dpc")
        assert r.value("ta") == approx(300 / (dE * 0.30))
        assert r.value("CO2") == approx(dE * 0.4)

    def test_zeitanteile_pruefen(self):
        assert not Energiekosten().run({"profil": "eigen", "a25": 40}).ok
        assert Energiekosten().run({"profil": "eigen", "a100": 10, "a75": 20, "a50": 30, "a25": 40}).ok

    def test_plausibilitaet(self):
        assert not Energiekosten().run({"H0": 3}).ok        # H₀ < H_N


# ---------------------------------------------------------------------- NPSH
class TestNPSH:
    def test_handrechnung(self):
        r = NPSH().run({"p": 101.325, "hz": -2, "theta": 20, "verlust": "direkt", "Hv": 0.5, "npshr": 3, "S": 0.5})
        rho = stoffwerte("wasser", 20).rho
        npsha = (101325 - dampfdruck(20) * 1000) / (rho * G) - 2 - 0.5
        assert r.value("npsha") == approx(npsha)
        assert r.value("res") == approx(npsha - 3)
        assert r.value("hzmin") == approx(3.5 - (npsha + 2.5) + 0.5)

    def test_temperaturgrenze(self):
        inp = {"hz": 1.0, "verlust": "direkt", "Hv": 0.3, "npshr": 2.5, "S": 0.5}
        t = NPSH().run(inp).value("tmax")
        r = NPSH().run(inp | {"theta": t})
        assert r.value("npsha") == approx(3.0, abs=1e-4)

    def test_kavitation_warnt(self):
        r = NPSH().run({"theta": 80, "hz": -3})
        assert warned(r, "KAVITATION")

    def test_saugleitung(self):
        r = NPSH().run({"V": 20, "rohr": "frei", "di": 80, "L": 10, "rauheit": "frei", "k": 0.05, "zeta": 2,
                        "theta": 20})
        d = DruckverlustRohr().run({"Q": 20, "d": 80, "L": 10, "k": 0.05, "zeta": 2, "medium": "benutzer",
                                    "rho": stoffwerte("wasser", 20).rho, "nu": stoffwerte("wasser", 20).nu})
        assert r.value("Hv") == approx(d.value("hv"), rel=1e-6)

    def test_benutzermedium(self):
        r = NPSH().run({"medium": "benutzer", "rho": 1050, "pv": 5, "verlust": "direkt", "Hv": 0, "hz": 0,
                        "p": 100})
        assert r.value("npsha") == approx(95e3 / (1050 * G))
