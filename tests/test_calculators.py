"""Rechenkern gegen unabhängig ermittelte Referenzwerte prüfen."""

import math

import pytest

from ingrechner.calculators.elektro.spannungsfall import Spannungsfall
from ingrechner.calculators.fluid.druckverlust_rohr import DruckverlustRohr, lambda_colebrook
from ingrechner.calculators.maschinenbau.biegung_einfeldtraeger import BiegungEinfeldtraeger
from ingrechner.calculators.statik.querschnittswerte import Querschnittswerte
from ingrechner.core.model import Level

approx = pytest.approx


# ------------------------------------------------------------------ Biegung
class TestBiegung:
    def test_einzellast_rechteck(self):
        # F = 10 kN, L = 2 m, b×h = 50×100 mm, E = 210 000 N/mm²
        r = BiegungEinfeldtraeger().run({})
        assert r.ok
        assert r.value("M") == approx(5.0)                    # F·L/4 = 5 kN·m
        assert r.value("Wy") == approx(83.3333, rel=1e-5)     # b·h²/6 cm³
        assert r.value("Iy") == approx(416.6667, rel=1e-5)    # b·h³/12 cm⁴
        assert r.value("sigma") == approx(60.0)               # M/W N/mm²
        w_ref = 10_000 * 2000**3 / (48 * 210_000 * 50 * 100**3 / 12)
        assert r.value("w") == approx(w_ref, rel=1e-9)        # ≈ 1,905 mm
        assert r.value("tau") == approx(1.5)                  # 1,5·5000/(50·100)
        assert r.value("eta_s") == approx(60 / (235 / 1.5) * 100)

    def test_streckenlast_profilwerte(self):
        # IPE 200 mit q = 10 kN/m, L = 5 m
        r = BiegungEinfeldtraeger().run({"lastfall": "streckenlast", "querschnitt": "werte",
                                         "q": 10, "L": 5000, "Iy": 1943, "Wy": 194})
        assert r.ok
        assert r.value("M") == approx(31.25)                  # q·L²/8
        assert r.value("A") == approx(25.0)                   # q·L/2
        assert r.value("sigma") == approx(31.25e6 / 194e3)
        assert r.value("w") == approx(5 * 10 * 5000**4 / (384 * 210_000 * 1943e4))

    def test_warnung_bei_ueberlastung(self):
        r = BiegungEinfeldtraeger().run({"F": 100})
        assert any(m.level is Level.WARNUNG and "NICHT erfüllt" in m.text for m in r.messages)

    def test_feldvalidierung(self):
        r = BiegungEinfeldtraeger().run({"L": 0, "S": 0.5})
        assert not r.ok
        assert set(r.field_errors) == {"L", "S"}

    def test_ausgeblendete_felder_werden_nicht_validiert(self):
        # q ist bei Einzellast ausgeblendet -> ungültiger Wert darf nicht stören
        assert BiegungEinfeldtraeger().run({"q": -5}).ok


# ------------------------------------------------------- Querschnittswerte
class TestQuerschnitt:
    def test_rechteck(self):
        r = Querschnittswerte().run({"form": "rechteck", "b": 100, "h": 200})
        assert r.value("A") == approx(200.0)
        assert r.value("Iy") == approx(100 * 200**3 / 12 / 1e4)
        assert r.value("Wz") == approx(200 * 100**2 / 6 / 1e3)
        assert r.value("g") == approx(0.02 * 7850)

    def test_kreisrohr(self):
        r = Querschnittswerte().run({"form": "kreisrohr", "d": 100, "t": 5})
        assert r.value("A") == approx(math.pi * (100**2 - 90**2) / 4 / 100)
        assert r.value("Iy") == approx(math.pi * (100**4 - 90**4) / 64 / 1e4)
        assert r.value("Iy") == approx(r.value("Iz"))

    def test_i_profil_ipe200_ohne_radien(self):
        r = Querschnittswerte().run({"form": "i_profil", "b": 100, "h": 200, "tw": 5.6, "tf": 8.5})
        assert r.value("A") == approx((2 * 100 * 8.5 + 183 * 5.6) / 100)
        assert r.value("Iy") == approx((100 * 200**3 - 94.4 * 183**3) / 12 / 1e4)
        # Tabellenwert IPE 200 (mit Radien): 1943 cm⁴ -> ohne Radien etwas kleiner
        assert 1800 < r.value("Iy") < 1943

    def test_rechteckrohr_symmetrie(self):
        r = Querschnittswerte().run({"form": "rechteckrohr", "b": 80, "h": 80, "t": 4})
        assert r.value("Iy") == approx(r.value("Iz"))
        assert r.value("Iy") == approx((80**4 - 72**4) / 12 / 1e4)

    def test_wanddicke_zu_gross(self):
        r = Querschnittswerte().run({"form": "kreisrohr", "d": 20, "t": 10})
        assert not r.ok
        assert any(m.level is Level.FEHLER for m in r.messages)


# --------------------------------------------------------------- Spannungsfall
class TestSpannungsfall:
    def test_wechselstrom_20grad(self):
        # Klassische Handformel ΔU = 2·L·I/(κ·A), κ = 1/0,017241 ≈ 58 m/(Ω·mm²)
        r = Spannungsfall().run({"netz": "1ac", "Un": 230, "I": 16, "L": 20, "S": 1.5,
                                 "theta": 20, "cosphi": 1.0})
        dU = 2 * 0.017241 * 20 / 1.5 * 16
        assert r.value("dU") == approx(dU, rel=1e-6)
        assert r.value("du") == approx(dU / 230 * 100, rel=1e-6)

    def test_temperaturkorrektur(self):
        r20 = Spannungsfall().run({"theta": 20}).value("dU")
        r70 = Spannungsfall().run({"theta": 70}).value("dU")
        assert r70 / r20 == approx(1 + 0.00393 * 50)

    def test_drehstrom_mit_reaktanz(self):
        r = Spannungsfall().run({"netz": "3ac", "Un": 400, "I": 63, "L": 80, "S": 10,
                                 "theta": 20, "cosphi": 0.9, "lam": 0.08})
        sin = math.sqrt(1 - 0.81)
        dU = (0.017241 * 80 / 10 * 0.9 + 0.08e-3 * 80 * sin) * 63
        assert r.value("dU") == approx(dU, rel=1e-6)
        assert r.value("du") == approx(dU / (400 / math.sqrt(3)) * 100, rel=1e-6)
        # Entspricht der Außenleiter-Formel √3·ΔU_Strang / 400 V
        assert r.value("du") == approx(math.sqrt(3) * dU / 400 * 100, rel=1e-6)

    def test_querschnittsvorschlag(self):
        r = Spannungsfall().run({"netz": "3ac", "Un": 400, "I": 63, "L": 80, "S": 10, "cosphi": 0.9})
        assert any("Vorschlag Kupfer 16,0 mm²" in m.text for m in r.messages)
        # Gegenprobe: mit 16 mm² ist der Grenzwert eingehalten
        r16 = Spannungsfall().run({"netz": "3ac", "Un": 400, "I": 63, "L": 80, "S": 16, "cosphi": 0.9})
        assert r16.value("du") <= 3.0

    def test_gleichstrom_ignoriert_cosphi(self):
        a = Spannungsfall().run({"netz": "dc", "Un": 24, "cosphi": 0.5}).value("dU")
        b = Spannungsfall().run({"netz": "dc", "Un": 24, "cosphi": 1.0}).value("dU")
        assert a == approx(b)

    def test_plausibilitaetswarnung_drehstrom_230v(self):
        r = Spannungsfall().run({"netz": "3ac", "Un": 230})
        assert any("Außenleiterspannung" in m.text for m in r.messages)


# ----------------------------------------------------------- Druckverlust
class TestDruckverlust:
    @pytest.mark.parametrize("re, k_rel, ref", [
        (1e5, 1e-4, 0.0185),   # Moody-Diagramm
        (1e6, 0.0, 0.0116),    # hydraulisch glatt (Prandtl-Kármán)
        (1e7, 1e-3, 0.0196),   # vollrau (Kármán-Nikuradse ≈ 0,0196)
    ])
    def test_colebrook(self, re, k_rel, ref):
        assert lambda_colebrook(re, k_rel) == approx(ref, abs=2e-4)

    def test_colebrook_erfuellt_gleichung(self):
        lam = lambda_colebrook(5e4, 2e-3)
        rhs = -2 * math.log10(2e-3 / 3.71 + 2.51 / (5e4 * math.sqrt(lam)))
        assert 1 / math.sqrt(lam) == approx(rhs, rel=1e-10)

    def test_turbulent_wasser(self):
        r = DruckverlustRohr().run({})
        v = 10 / 3600 / (math.pi * 0.05**2 / 4)
        re = v * 0.05 / 1.004e-6
        lam = lambda_colebrook(re, 0.05 / 50)
        assert r.value("v") == approx(v)
        assert r.value("Re") == approx(re)
        assert r.value("dp") == approx(lam * 100 / 0.05 * 998.2 * v**2 / 2 / 1e5)

    def test_laminar(self):
        r = DruckverlustRohr().run({"Q": 0.01, "d": 20, "medium": "benutzer", "rho": 900, "nu": 100})
        assert r.value("Re") < 2320
        assert r.value("lam") == approx(64 / r.value("Re"))

    def test_zeta_und_geodaetisch(self):
        base = DruckverlustRohr().run({})
        r = DruckverlustRohr().run({"zeta": 2, "dz": 10})
        pdyn = 998.2 * base.value("v") ** 2 / 2
        assert r.value("dp_e") == approx(2 * pdyn / 1e5)
        assert r.value("dp_g") == approx(998.2 * 9.80665 * 10 / 1e5)
        assert r.value("dp") == approx(base.value("dp") + r.value("dp_e") + r.value("dp_g"))

    def test_warnung_hohe_geschwindigkeit(self):
        r = DruckverlustRohr().run({"Q": 40})
        assert any(m.level is Level.WARNUNG and "3 m/s" in m.text for m in r.messages)
